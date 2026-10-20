"""Exceptions de politique (ADR-0017 D12, I5, flux F8 ; étape G1) : « l'Exception Manager gère, le Policy Engine décide ».

Une exception de politique (identifiant PEX-…, distinct des exceptions de construction EXC-… de policies/exceptions/)
lève UNE règle DENY_BY_POLICY pour UNE portée exacte (acteur, projet, action, ressource, ticket, commande, outil,
MCP), pour une durée et un nombre d'usages bornés. Elle n'existe que comme DÉCISION HUMAINE (W1) : l'agent prépare
la demande, l'humain l'approuve avec la commande d'approbation ; aucune fonction ici n'écrit d'approbation.

I5 est contrôlé deux fois : à la demande (une demande plus large que la capacité d'exception de sa règle est
rejetée avant le moteur) et à chaque usage (règle exceptable et DENY_BY_POLICY au catalogue courant, rôle de
l'approbateur parmi les rôles admis, durée et usages dans la capacité). Un DENY_ABSOLUTE ne s'excepte jamais.

Usages et révocations sont des événements du journal chaîné (ajout seul). Une révocation ne fait que restreindre :
tout acteur peut la demander. La qualification seule ne consomme rien ; l'appelant qui exécute consomme.
Limite L1 (ADR-0017 R2) : qui forge une approbation forge une exception (NE2).
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path

from .approbation import CANAL, TYPE, empreinte, empreinte_enregistrement

KIND = "POLICY_EXCEPTION"
USAGE, REVOCATION = "usage d'exception de politique", "révocation d'exception de politique"
DENY_BY_POLICY = "DENY_BY_POLICY"


class RefusException(Exception):
    """Demande ou usage d'exception refusé (I5, portée, expiration, usages, révocation)."""


def portee(d: dict) -> dict:
    """Portée exacte couverte par une exception : tout changement de l'un de ces champs la rend inapplicable."""
    acteur, ressource, ticket = d.get("actor") or {}, d.get("resource") or {}, d.get("ticket") or {}
    return {"project_id": d.get("project_id"), "actor": {"type": acteur.get("type"), "id": acteur.get("id")},
            "action": d.get("action"), "resource": {k: ressource.get(k) for k in ("kind", "path", "id", "environment")},
            "ticket_id": ticket.get("id"), "command": d.get("command"), "tool": d.get("tool"), "mcp": d.get("mcp")}


def controle_i5(ctx: dict, catalogue: dict, role: str | None = None) -> list[str]:
    """Écarts entre une exception et la capacité d'exception de sa règle (vide = conforme)."""
    regle = ((catalogue or {}).get("rules") or {}).get(ctx.get("rule"))
    if regle is None:
        return [f"règle {ctx.get('rule')!r} absente du catalogue"]
    capacite = regle.get("exception") or {}
    ecarts = []
    if regle.get("nature") != DENY_BY_POLICY:
        ecarts.append(f"{ctx['rule']} est {regle.get('nature')} : seul un DENY_BY_POLICY s'excepte")
    if not capacite.get("exceptable"):
        ecarts.append(f"{ctx['rule']} n'est pas exceptable")
    try:
        heures, usages = float(ctx.get("duration_hours")), int(ctx.get("max_uses"))
    except (TypeError, ValueError):
        return ecarts + ["durée ou nombre d'usages illisible"]
    if not 0 < heures <= float(capacite.get("max_duration_hours") or 0):
        ecarts.append(f"durée {heures} h hors de la capacité ({capacite.get('max_duration_hours')} h au plus)")
    if not 0 < usages <= int(capacite.get("max_uses") or 0):
        ecarts.append(f"{usages} usage(s) hors de la capacité ({capacite.get('max_uses')} au plus)")
    if role is not None and role not in (capacite.get("allowed_roles") or []):
        ecarts.append(f"rôle {role!r} non admis pour excepter {ctx['rule']}")
    return ecarts


@dataclass
class ExceptionActive:
    id: str
    rule: str
    scope_sha256: str
    expires_at: _dt.datetime
    max_uses: int
    uses: int
    approval: str


class GestionnaireExceptions:
    def __init__(self, approbations: Path, journal=None, horloge=None):
        self.approbations = Path(approbations)          # enregistrements de la commande humaine (lecture seule)
        self.journal = journal                          # noyau.audit.Journal : usages et révocations
        self.horloge = horloge or (lambda: _dt.datetime.now(_dt.timezone.utc))

    # ------------------------------------------------------------------ demande (l'agent DEMANDE)
    def demande(self, regle: str, d: dict, heures: float, usages: int, motif: str, catalogue: dict) -> dict:
        p = portee(d)
        ctx = {"kind": KIND, "rule": regle, "scope": p, "scope_sha256": empreinte(p), "duration_hours": heures,
               "max_uses": usages, "reason": motif,
               "requested_at": self.horloge().isoformat(timespec="seconds")}
        ecarts = controle_i5(ctx, catalogue)
        if ecarts:
            raise RefusException("demande rejetée avant le moteur (I5) : " + " ; ".join(ecarts))
        ctx["exception_id"] = f"PEX-{regle}-{empreinte(ctx)[:8]}"
        roles = ((catalogue["rules"][regle].get("exception") or {}).get("allowed_roles") or [])
        return {"context": ctx, "context_sha256": empreinte(ctx), "roles": sorted(roles),
                "purpose": f"Exception de politique {ctx['exception_id']} : lever {regle} pour cette portée exacte "
                           f"seulement, {heures} h, {usages} usage(s). Motif : {motif}. Toutes les autres règles "
                           f"restent appliquées."}

    # ------------------------------------------------------------------ état
    def _evenements(self) -> list[dict]:
        if self.journal is None or not Path(self.journal.chemin).is_file():
            return []
        if not self.journal.verifier().valide:
            raise RefusException("journal compromis : usages et révocations illisibles, aucune exception appliquée")
        return [json.loads(x) for x in Path(self.journal.chemin).read_text(encoding="utf-8").splitlines() if x]

    def actives(self, catalogue: dict) -> list[ExceptionActive]:
        evts = self._evenements()
        revoquees = {e.get("exception_id") for e in evts if e.get("action") == REVOCATION}
        usages: dict[str, int] = {}
        for e in evts:
            if e.get("action") == USAGE:
                usages[e.get("exception_id")] = usages.get(e.get("exception_id"), 0) + 1
        maintenant, out = self.horloge(), []
        for p in sorted(self.approbations.glob("HA-*.json")) if self.approbations.is_dir() else []:
            try:
                e = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            ctx = e.get("context") if isinstance(e, dict) else None
            if not (isinstance(ctx, dict) and ctx.get("kind") == KIND and e.get("kind") == TYPE
                    and e.get("channel") == CANAL and e.get("decision") == "APPROVED"
                    and e.get("record_sha256") == empreinte_enregistrement(e)
                    and e.get("context_sha256") == empreinte(ctx)
                    and ctx.get("scope_sha256") == empreinte(ctx.get("scope"))
                    and not controle_i5(ctx, catalogue, e.get("approver_role"))):
                continue
            ident = ctx.get("exception_id")
            try:
                cree = _dt.datetime.fromisoformat(e["created_at"])
            except (KeyError, ValueError):
                continue
            fin = cree + _dt.timedelta(hours=float(ctx["duration_hours"]))
            if ident in revoquees or not cree <= maintenant + _dt.timedelta(minutes=5) or maintenant >= fin:
                continue
            if usages.get(ident, 0) >= int(ctx["max_uses"]):
                continue
            out.append(ExceptionActive(ident, ctx["rule"], ctx["scope_sha256"], fin, int(ctx["max_uses"]),
                                       usages.get(ident, 0), e.get("id")))
        return out

    def applicable(self, regle: str, d: dict, catalogue: dict) -> str | None:
        """Identifiant d'une exception active pour CETTE règle et CETTE portée exacte, sinon None."""
        h = empreinte(portee(d))
        for x in self.actives(catalogue):
            if x.rule == regle and x.scope_sha256 == h:
                return x.id
        return None

    # ------------------------------------------------------------------ usage et révocation (journal)
    def consommer(self, ident: str, d: dict, catalogue: dict):
        x = next((a for a in self.actives(catalogue) if a.id == ident), None)
        if x is None or x.scope_sha256 != empreinte(portee(d)):
            raise RefusException(f"exception {ident} inactive ou hors de sa portée")
        if self.journal is None:
            raise RefusException("aucun journal : un usage d'exception doit être tracé")
        self.journal.ajouter(actor={"type": "system", "id": "exception-manager"}, action=USAGE, exception_id=ident,
                             project_id=d.get("project_id"), result="CONSUMED", rule=x.rule,
                             reasons=[f"usage {x.uses + 1}/{x.max_uses} (approbation {x.approval})"])

    def revoquer(self, ident: str, motif: str, acteur: dict):
        if self.journal is None:
            raise RefusException("aucun journal : une révocation doit être tracée")
        self.journal.ajouter(actor=acteur, action=REVOCATION, exception_id=ident, result="REVOKED", reasons=[motif])
