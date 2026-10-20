"""Capability Manager et baux de capacités (Master Evolution Prompt v4 §5, §6, §14 ; ADR-0016 proposé).

Une capacité n'existe que dans un bail : acteur × projet × exécution × ticket × environnement × ressources ×
capacités × durée. Le gestionnaire n'accorde rien de lui-même : chaque couple (capacité, ressource) demandé est
soumis au Policy Engine (action « use_capability ») ; un seul DENY = aucun bail ; un APPROVAL_REQUIRED = aucun
bail et la frontière humaine est signalée. Tant que le Policy Engine ne connaît pas cette action, tout est refusé.

À chaque opération, le bail est vérifié (actif, non expiré, même acteur, même exécution, capacité et ressource
couvertes) PUIS la politique est réinterrogée (l'identité de la ressource se revérifie à l'appel). La fin de
l'exécution libère ses baux. Chaque émission, refus, usage refusé, libération et révocation est audité.

Authenticité (ADR-0017 D7, trou S3 ; étape G1) : chaque bail porte un code d'authentification (HMAC-SHA256) calculé
avec la clé de service sur l'ensemble de sa fiche. Un bail modifié ou forgé est refusé. Sans clé de service, aucun
bail n'est émis (refus par défaut). Le bail porte l'empreinte de la politique qui l'a qualifié ; si la politique
change, le bail passe à INVALIDATED (P18). En L1, la clé est lisible par le compte : l'altération est détectée, la
falsification par un processus qui lit la clé n'est pas empêchée (ADR-0017 R2).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .approbation import canonique

ALLOW, DENY, APPROVAL_REQUIRED = "ALLOW", "DENY", "APPROVAL_REQUIRED"
LEASE_SCHEMA_VERSION = 1


class RefusBail(Exception):
    """Bail introuvable ou mal formé."""


@dataclass
class Bail:
    id: str
    actor: dict
    project_id: str
    execution_id: str
    ticket_id: str
    environment_id: str | None
    capabilities: list[str]
    resources: list[str]
    limits: dict
    granted_at: str
    expires_at: str
    expires_event: str = "EXECUTION_END"
    state: str = "REQUESTED"
    decisions: list[dict] = field(default_factory=list)
    reason: str | None = None
    operations: int = 0
    lease_schema_version: int = LEASE_SCHEMA_VERSION
    authority: dict = field(default_factory=dict)       # d'où vient l'autorité (règles de la politique, décision)
    policy_fingerprint: str | None = None               # empreinte de la politique qui a qualifié le bail
    mac: str = ""                                       # HMAC-SHA256 de la fiche (sans ce champ)


def _iso(t: _dt.datetime) -> str:
    return t.isoformat(timespec="seconds")


class GestionnaireCapacites:
    def __init__(self, racine: Path, moteur, cycle: dict, plafond: dict, journal=None, horloge=None,
                 cle: bytes | None = None, empreinte_politique: str | None = None):
        self.racine = Path(racine)
        self.moteur = moteur                       # noyau.politique.Moteur (ou tout objet doté de decider)
        self.cycle = cycle                         # lifecycles.yaml : capability_lease
        self.plafond = plafond                     # autonomy : budgets.lease
        self.journal = journal
        self.horloge = horloge or (lambda: _dt.datetime.now(_dt.timezone.utc))
        self.cle = cle                             # clé de service (D36) ; absente = aucun bail émis
        self.empreinte_politique = empreinte_politique

    # ------------------------------------------------------------------ authenticité
    def _mac(self, b: Bail) -> str:
        contenu = {k: v for k, v in asdict(b).items() if k != "mac"}
        return hmac.new(self.cle, canonique(contenu).encode("utf-8"), hashlib.sha256).hexdigest()

    def authentique(self, b: Bail) -> bool:
        return bool(self.cle) and bool(b.mac) and hmac.compare_digest(b.mac, self._mac(b))

    # ------------------------------------------------------------------ persistance et transitions
    def _fiche(self, ident: str) -> Path:
        if not ident.startswith("lease-") or any(c in ident for c in "/\\:."):
            raise RefusBail(f"identifiant de bail invalide : {ident!r}")
        return self.racine / f"{ident}.json"

    def obtenir(self, ident: str) -> Bail | None:
        try:
            p = self._fiche(ident)
        except RefusBail:
            return None
        if not p.is_file():
            return None
        try:
            return Bail(**json.loads(p.read_text(encoding="utf-8")))
        except (TypeError, ValueError):                 # fiche illisible ou champs inconnus : pas un bail
            return None

    def _sauver(self, b: Bail):
        if not self.cle:
            raise RefusBail("clé de service absente : aucun bail ne peut être émis ni modifié (cérémonie ADR-0017 D36)")
        b.mac = self._mac(b)
        self.racine.mkdir(parents=True, exist_ok=True)
        self._fiche(b.id).write_text(json.dumps(asdict(b), ensure_ascii=False, indent=1), encoding="utf-8")

    def _passer(self, b: Bail, vers: str, motif: str):
        ok = vers in self.cycle.get("any_to", []) or any(t["from"] == b.state and t["to"] == vers
                                                          for t in self.cycle["transitions"])
        if not ok or b.state in self.cycle.get("terminal", []):
            raise RefusBail(f"{b.id} : transition {b.state} → {vers} absente du cycle capability_lease")
        depart, b.state, b.reason = b.state, vers, motif
        self._sauver(b)
        self._auditer(b, f"transition capability_lease", depart, vers, motif)

    def _auditer(self, b: Bail, action: str, depart, vers, motif: str, **plus):
        if self.journal is not None:
            self.journal.ajouter(actor={"type": "system", "id": "capability-manager"}, project_id=b.project_id,
                                 ticket_id=b.ticket_id, execution_id=b.execution_id, lease_id=b.id,
                                 environment_id=b.environment_id, action=action, from_state=depart, to_state=vers,
                                 result=vers or "REFUSED", reasons=[motif] if motif else [], **plus)

    # ------------------------------------------------------------------ demande
    def _requete(self, acteur, projet, ticket, execution, capacite, ressource) -> dict:
        return {"actor": acteur, "project_id": projet, "ticket": ticket, "execution": execution,
                "action": "use_capability", "capability": capacite, "resource": {"id": ressource}}

    def demander(self, acteur: dict, projet: str, ticket: dict, execution: dict, environnement: str | None,
                 capacites: list[str], ressources: list[str], duree_s: int | None = None) -> tuple[Bail, dict]:
        """→ (bail, synthèse). Le bail est ACTIVE seulement si TOUTES les décisions sont ALLOW."""
        if not capacites or not ressources:
            raise RefusBail("un bail couvre au moins une capacité et une ressource")
        if not self.cle:
            raise RefusBail("clé de service absente : aucun bail ne peut être émis (cérémonie ADR-0017 D36)")
        maintenant = self.horloge()
        maxi = int(self.plafond.get("max_duration_s", 3600))
        duree = min(int(duree_s or maxi), maxi)                   # un bail ne dépasse jamais le plafond (§52)
        b = Bail(f"lease-{secrets.token_hex(8)}", {"type": acteur.get("type"), "id": acteur.get("id")}, projet,
                 execution.get("id", ""), ticket.get("id", ""), environnement, sorted(set(capacites)),
                 sorted(set(ressources)), {"max_duration_s": duree,
                                            "max_parallel_operations": int(self.plafond.get("max_parallel_operations", 4))},
                 _iso(maintenant), _iso(maintenant + _dt.timedelta(seconds=duree)))
        for c in b.capabilities:
            for r in b.resources:
                d = self.moteur.decider(self._requete(acteur, projet, ticket, execution, c, r))
                dd = d.en_dict() if hasattr(d, "en_dict") else dict(d)
                b.decisions.append({"capability": c, "resource": r, "decision": dd.get("decision"),
                                    "rule": dd.get("regle"), "reasons": dd.get("motifs"),
                                    "context_sha256": dd.get("empreinte_contexte")})
        b.authority = {"kind": "POLICY", "rules": sorted({x["rule"] for x in b.decisions if x.get("rule")})}
        b.policy_fingerprint = self.empreinte_politique
        self._sauver(b)
        refus = [x for x in b.decisions if x["decision"] == DENY]
        attente = [x for x in b.decisions if x["decision"] == APPROVAL_REQUIRED]
        if refus or attente or any(x["decision"] != ALLOW for x in b.decisions):
            premier = (refus or attente or b.decisions)[0]
            self._passer(b, "DENIED", f"{premier['capability']} sur {premier['resource']} : {premier['decision']} "
                                      f"({premier['rule']})")
            return b, {"decision": DENY if refus else APPROVAL_REQUIRED, "lease": None,
                       "reasons": [f"{x['capability']}/{x['resource']} → {x['decision']} {x['rule']} "
                                   f"{'; '.join(x['reasons'] or [])}" for x in (refus or attente)]}
        self._passer(b, "ACTIVE", f"{len(b.decisions)} décision(s) ALLOW")
        return b, {"decision": ALLOW, "lease": b.id, "reasons": []}

    # ------------------------------------------------------------------ usage
    def verifier(self, ident: str, acteur_id: str, execution_id: str, capacite: str, ressource: str) -> tuple[bool, str]:
        ok, motif, b = self._controler(ident, acteur_id, execution_id)
        if not ok:
            return False, motif
        if capacite not in b.capabilities:
            return False, f"capacité {capacite} hors du bail"
        if ressource not in b.resources:
            return False, f"ressource {ressource} hors du bail"
        return True, "bail valide"

    def verifier_session(self, ident: str, acteur_id: str, execution_id: str,
                         capacite: str | None = None) -> tuple[bool, str]:
        """Contrôle de la projection dans le runtime (hook) : bail authentique, actif, non expiré, de cet acteur et de
        cette exécution ; la capacité n'est vérifiée que si l'outil en désigne une. La ressource reste vérifiée par
        `autoriser_operation` au point d'entrée qui la manipule."""
        ok, motif, b = self._controler(ident, acteur_id, execution_id)
        if ok and capacite is not None and capacite not in b.capabilities:
            return False, f"capacité {capacite} hors du bail"
        return ok, motif

    def _controler(self, ident: str, acteur_id: str, execution_id: str) -> tuple[bool, str, Bail | None]:
        b = self.obtenir(ident)
        if b is None:
            return False, "bail inconnu", None
        if not self.authentique(b):
            return False, "bail non authentifié (altéré, forgé ou clé de service absente)", b
        if b.state == "ACTIVE" and self.empreinte_politique and b.policy_fingerprint != self.empreinte_politique:
            self._passer(b, "INVALIDATED", "politique modifiée depuis l'émission du bail (P18)")
        if b.state == "ACTIVE" and self.horloge() > _dt.datetime.fromisoformat(b.expires_at):
            self._passer(b, "EXPIRED", "durée du bail écoulée")
        if b.state != "ACTIVE":
            return False, f"bail {b.state}", b
        if b.actor.get("id") != acteur_id:
            return False, "bail d'un autre acteur", b
        if b.execution_id != execution_id:
            return False, "bail d'une autre exécution", b
        return True, "bail valide", b

    def autoriser_operation(self, ident: str, acteur: dict, projet: str, ticket: dict, execution: dict,
                            capacite: str, ressource: str) -> dict:
        """Point de contrôle de CHAQUE opération : bail valide ET politique réinterrogée (identité revérifiée)."""
        ok, motif = self.verifier(ident, acteur.get("id"), execution.get("id"), capacite, ressource)
        b = self.obtenir(ident)
        if not ok:
            if b is not None and self.cle:
                self._auditer(b, "use capability", b.state, None, f"refus : {motif}", capability=capacite,
                              resource=ressource)
            return {"decision": DENY, "reasons": [motif]}
        d = self.moteur.decider(self._requete(acteur, projet, ticket, execution, capacite, ressource))
        dd = d.en_dict() if hasattr(d, "en_dict") else dict(d)
        if dd.get("decision") != ALLOW:
            self._auditer(b, "use capability", b.state, None, f"refus de la politique : {dd.get('regle')}",
                          capability=capacite, resource=ressource)
            return {"decision": dd.get("decision"), "reasons": dd.get("motifs") or []}
        b.operations += 1
        self._sauver(b)
        return {"decision": ALLOW, "reasons": [motif]}

    # ------------------------------------------------------------------ fin
    def liberer(self, execution_id: str, motif: str = "fin de l'exécution") -> list[str]:
        liberes = []
        for p in sorted(self.racine.glob("lease-*.json")) if self.racine.is_dir() else []:
            b = self.obtenir(p.stem)
            if b is None or not self.authentique(b):
                continue                                # un bail forgé n'est ni libéré ni pris en compte
            if b.execution_id == execution_id and b.state == "ACTIVE":
                self._passer(b, "RELEASED", motif)
                liberes.append(b.id)
        return liberes

    def revoquer(self, ident: str, motif: str):
        b = self.obtenir(ident)
        if b is None:
            raise RefusBail(f"bail inconnu : {ident}")
        if b.state not in self.cycle.get("terminal", []):
            self._passer(b, "REVOKED", motif)
