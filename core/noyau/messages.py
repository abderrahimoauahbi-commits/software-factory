"""Communication entre agents et artefacts (Master Evolution Prompt v4 §23–§25, §43).

Les agents collaborent par messages typés et artefacts versionnés, jamais par des instructions de pouvoir :
le contenu d'un message est une DONNÉE (§43). Un message d'agent qui porte une clé de pouvoir (politique,
capacités, approbation, permissions) est refusé ; une décision qui franchit une frontière humaine exige la
référence d'une décision humaine.

Artefact : propriétaire, version, statut, dépendances, revues, preuves. Il n'est approuvé qu'après une revue
favorable d'un relecteur différent de son auteur (invariant I3) ; une nouvelle version remplace la précédente.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import itertools
from dataclasses import dataclass, field

TYPES = ("TASK_REQUEST", "TASK_RESULT", "ARTIFACT_PUBLISHED", "REVIEW_REQUEST", "REVIEW_RESULT", "BLOCKER",
         "DEPENDENCY_REQUEST", "RISK", "DECISION_PROPOSAL", "DECISION_RESULT", "FAILURE", "ESCALATION")
CLES_DE_POUVOIR = {"policy", "policies", "capabilities", "capability", "approval", "approvals", "permissions",
                   "permission", "grant", "lease_override"}
TYPES_ARTEFACT = ("requirements", "business-rules", "architecture", "ADR", "api-contract", "database-design",
                  "migration", "seeder", "implementation-plan", "implementation", "test-plan", "test-report",
                  "security-review", "release-plan", "documentation")
DRAFT, IN_REVIEW, APPROVED, REJECTED, SUPERSEDED = "DRAFT", "IN_REVIEW", "APPROVED", "REJECTED", "SUPERSEDED"


class RefusMessage(Exception):
    """Message ou artefact refusé : rien n'est publié."""


def _maintenant() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _cles(objet) -> set[str]:
    if isinstance(objet, dict):
        return {str(k).lower() for k in objet} | {c for v in objet.values() for c in _cles(v)}
    if isinstance(objet, list):
        return {c for v in objet for c in _cles(v)}
    return set()


@dataclass
class Message:
    type: str
    de: str
    a: str                                   # destinataire (membre, rôle) ou « * »
    contenu: dict = field(default_factory=dict)
    tache_id: str | None = None
    refs: list[str] = field(default_factory=list)
    frontiere: str | None = None             # DECISION_RESULT qui tranche une frontière humaine
    acteur_humain: bool = False
    id: str = ""
    horodatage: str = ""


class Bus:
    def __init__(self, mission_id: str, journal=None, frontieres: list[str] | None = None):
        self.mission_id = mission_id
        self.journal = journal
        self.frontieres = set(frontieres or [])
        self.messages: list[Message] = []
        self.acquittes: set[tuple[str, str]] = set()
        self._n = itertools.count(1)

    def publier(self, m: Message) -> Message:
        if m.type not in TYPES:
            raise RefusMessage(f"type de message inconnu : {m.type!r}")
        if not m.de or not m.a:
            raise RefusMessage("émetteur et destinataire obligatoires")
        if not m.acteur_humain and (_cles(m.contenu) & CLES_DE_POUVOIR):
            raise RefusMessage("un message d'agent ne porte aucune instruction de pouvoir (§43) : "
                               + ", ".join(sorted(_cles(m.contenu) & CLES_DE_POUVOIR)))
        if m.type == "DECISION_RESULT" and m.frontiere:
            if m.frontiere in self.frontieres and not (m.acteur_humain and m.refs):
                raise RefusMessage(f"la frontière {m.frontiere} ne se tranche que par une décision humaine référencée")
        m.id = f"MSG-{self.mission_id}-{next(self._n):05d}"
        m.horodatage = _maintenant()
        self.messages.append(m)
        if self.journal is not None:
            self.journal.ajouter(actor={"type": "human" if m.acteur_humain else "agent", "id": m.de},
                                 mission_id=self.mission_id, action=f"message {m.type}", result="PUBLISHED",
                                 message_id=m.id, to=m.a, task_id=m.tache_id, refs=m.refs)
        return m

    def boite(self, destinataire: str, roles: tuple[str, ...] = ()) -> list[Message]:
        cibles = {destinataire, "*", *roles}
        return [m for m in self.messages if m.a in cibles and (destinataire, m.id) not in self.acquittes]

    def acquitter(self, destinataire: str, ident: str):
        self.acquittes.add((destinataire, ident))

    def fil(self, tache_id: str) -> list[Message]:
        return [m for m in self.messages if m.tache_id == tache_id]


@dataclass
class Artefact:
    id: str
    type: str
    proprietaire: str
    version: int
    contenu_sha256: str
    statut: str = DRAFT
    dependances: list[str] = field(default_factory=list)
    revues: list[dict] = field(default_factory=list)
    preuves: list[str] = field(default_factory=list)
    chemin: str | None = None


class Artefacts:
    def __init__(self, bus: Bus | None = None):
        self.bus = bus
        self.versions: dict[str, list[Artefact]] = {}

    def courant(self, ident: str) -> Artefact | None:
        v = self.versions.get(ident)
        return v[-1] if v else None

    def publier(self, ident: str, type_: str, proprietaire: str, contenu: bytes | str,
                dependances: list[str] | None = None, chemin: str | None = None) -> Artefact:
        if type_ not in TYPES_ARTEFACT:
            raise RefusMessage(f"type d'artefact inconnu : {type_!r}")
        manquantes = [d for d in dependances or [] if self.courant(d) is None]
        if manquantes:
            raise RefusMessage(f"dépendances d'artefact inconnues : {manquantes}")
        octets = contenu.encode("utf-8") if isinstance(contenu, str) else contenu
        prec = self.courant(ident)
        if prec is not None:
            if prec.type != type_:
                raise RefusMessage("un artefact ne change pas de type entre deux versions")
            prec.statut = SUPERSEDED
        a = Artefact(ident, type_, proprietaire, (prec.version + 1) if prec else 1,
                     hashlib.sha256(octets).hexdigest(), dependances=list(dependances or []), chemin=chemin)
        self.versions.setdefault(ident, []).append(a)
        if self.bus:
            self.bus.publier(Message("ARTIFACT_PUBLISHED", proprietaire, "*",
                                     {"artifact": ident, "version": a.version, "sha256": a.contenu_sha256}))
        return a

    def demander_revue(self, ident: str, demandeur: str, relecteur: str) -> Artefact:
        a = self.courant(ident)
        if a is None or a.statut not in (DRAFT, REJECTED):
            raise RefusMessage(f"revue impossible pour {ident}")
        a.statut = IN_REVIEW
        if self.bus:
            self.bus.publier(Message("REVIEW_REQUEST", demandeur, relecteur, {"artifact": ident, "version": a.version}))
        return a

    def enregistrer_revue(self, ident: str, relecteur: str, favorable: bool, remarques: list[str] | None = None,
                          preuve: str | None = None) -> Artefact:
        a = self.courant(ident)
        if a is None or a.statut != IN_REVIEW:
            raise RefusMessage(f"{ident} n'est pas en revue")
        if relecteur == a.proprietaire:
            raise RefusMessage("le relecteur ne peut pas être l'auteur (I3)")
        a.revues.append({"reviewer": relecteur, "favorable": favorable, "remarks": remarques or [],
                         "version": a.version, "sha256": a.contenu_sha256, "at": _maintenant()})
        if preuve:
            a.preuves.append(preuve)
        a.statut = APPROVED if favorable else REJECTED
        if self.bus:
            self.bus.publier(Message("REVIEW_RESULT", relecteur, a.proprietaire,
                                     {"artifact": ident, "version": a.version, "favorable": favorable,
                                      "remarks": remarques or []}))
        return a
