"""Journal d'audit en ajout seul, chaîné par empreintes (Executable Schemas §31, menace T13).

Chaque événement porte l'empreinte du précédent (`prev_hash`) et la sienne (`event_hash`). Une modification,
une suppression, une insertion ou une permutation casse la chaîne et est localisée par `verifier`.
Le journal ne s'écrit qu'en ajout ; aucune fonction ne réécrit une ligne.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path

from .approbation import canonique, empreinte
from .masquage import contient_secret

ORIGINE = "0" * 64
CHAMPS = ("id", "timestamp", "actor", "action", "result", "factory_version", "schema_version")


class AuditRefuse(Exception):
    """L'événement n'a pas été écrit."""


@dataclass
class Verification:
    valide: bool
    evenements: int
    rupture: int | None = None        # index (0-based) de la première ligne fautive
    motif: str = ""
    tete: str = ORIGINE


def _hash(evt: dict) -> str:
    return empreinte({k: v for k, v in evt.items() if k != "event_hash"})


class Journal:
    def __init__(self, chemin: Path, factory_version: str = "3.2", schema_version: str = "1.0"):
        self.chemin = Path(chemin)
        self.factory_version, self.schema_version = factory_version, schema_version

    def verifier(self) -> Verification:
        if not self.chemin.exists():
            return Verification(True, 0)
        prec = ORIGINE
        lignes = self.chemin.read_text(encoding="utf-8").splitlines()
        for i, ligne in enumerate(lignes):
            try:
                evt = json.loads(ligne)
            except ValueError:
                return Verification(False, i, i, "ligne illisible", prec)
            if evt.get("prev_hash") != prec:
                return Verification(False, i, i, "chaînage rompu (suppression, insertion ou permutation)", prec)
            if evt.get("event_hash") != _hash(evt):
                return Verification(False, i, i, "événement modifié après écriture", prec)
            prec = evt["event_hash"]
        return Verification(True, len(lignes), None, "", prec)

    def ajouter(self, **evt) -> dict:
        etat = self.verifier()
        if not etat.valide:
            raise AuditRefuse(f"journal compromis à la ligne {etat.rupture + 1} : {etat.motif}")
        evt.setdefault("timestamp", _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"))
        evt.setdefault("id", f"AE-{etat.evenements + 1:06d}")
        evt.setdefault("factory_version", self.factory_version)
        evt.setdefault("schema_version", self.schema_version)
        manquants = [c for c in CHAMPS if evt.get(c) in (None, "")]
        if manquants:
            raise AuditRefuse("champs requis absents : " + ", ".join(manquants))
        if contient_secret(canonique(evt)):
            raise AuditRefuse("secret ou identifiant en clair dans l'événement")
        evt["prev_hash"] = etat.tete
        evt["event_hash"] = _hash(evt)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chemin, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(evt, ensure_ascii=False, sort_keys=True) + "\n")
        return evt
