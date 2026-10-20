"""Constats, preuves et agrégation des états de santé (Playbook §7.3, Executable Schemas §2 et §15)."""
from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field

SANTE = ("READY", "WARNING", "DEGRADED", "BLOCKED", "FAILED", "UNKNOWN")
NATURE_PREUVE = ("VERIFIED", "DECLARED", "UNVERIFIABLE", "HUMAN_REQUIRED")
GRAVITE = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


def maintenant() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class Preuve:
    """Une preuve observable (Executable Schemas §15). Une déclaration d'agent n'en est jamais une."""
    type: str                      # COMMAND, DOCUMENT, ARTIFACT…
    source: str                    # commande masquée ou chemin lu
    result: str                    # SUCCESS, FAILURE, WARNING
    exit_code: int | None = None
    extrait: str | None = None     # premières lignes, MASQUÉES
    timestamp: str = field(default_factory=maintenant)


@dataclass
class Constat:
    id: str
    domaine: str
    element: str
    statut: str                    # SANTE
    nature: str                    # NATURE_PREUVE
    gravite: str = "INFO"          # GRAVITE
    critique: bool = False
    detail: str = ""
    bloque: list[str] = field(default_factory=list)       # phases bloquées (décision K5)
    preuves: list[Preuve] = field(default_factory=list)
    action_humaine: str | None = None

    def __post_init__(self):
        if self.statut not in SANTE:
            raise ValueError(f"état de santé inconnu : {self.statut}")
        if self.nature not in NATURE_PREUVE:
            raise ValueError(f"nature de preuve inconnue : {self.nature}")
        if self.gravite not in GRAVITE:
            raise ValueError(f"gravité inconnue : {self.gravite}")

    def en_dict(self) -> dict:
        return asdict(self)


_MAUVAIS = {"BLOCKED", "FAILED"}


def etat_phase(constats: list[Constat], phase: str) -> str:
    """READY, DEGRADED ou BLOCKED pour une phase donnée.

    Jamais READY si un constat critique n'est pas prouvé bon : un critique UNKNOWN bloque (Playbook §7.3).
    """
    concernes = [c for c in constats if phase in c.bloque]
    if any(c.critique and c.statut in _MAUVAIS | {"UNKNOWN"} for c in concernes):
        return "BLOCKED"
    if any(c.statut in _MAUVAIS for c in concernes):
        return "BLOCKED"
    if any(c.statut in {"DEGRADED", "UNKNOWN"} for c in concernes):
        return "DEGRADED"
    return "READY"


def etat_factory(constats: list[Constat]) -> str:
    """État global de la Factory (machine « factory ») : seuls les constats du domaine factory comptent."""
    propres = [c for c in constats if c.domaine == "factory"]
    if any(c.critique and c.statut != "READY" and c.statut != "WARNING" for c in propres):
        return "BLOCKED"
    if any(c.statut in _MAUVAIS | {"DEGRADED", "UNKNOWN"} for c in propres):
        return "DEGRADED"
    return "READY"
