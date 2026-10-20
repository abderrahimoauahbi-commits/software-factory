"""Preuves (Executable Schemas §15) : une déclaration n'est jamais une preuve.

Une preuve d'exécution (COMMAND, TEST, BUILD, SECURITY_SCAN, MIGRATION, BACKUP, RESTORE, PERFORMANCE) exige une
commande, un code de sortie entier, un horodatage et un artefact dont l'empreinte SHA-256 se vérifie. Une revue
(REVIEW) exige un relecteur identifié et un artefact. « tests passed » sans tout cela est rejeté.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass
from pathlib import Path

EXECUTION = {"COMMAND", "TEST", "BUILD", "SECURITY_SCAN", "MIGRATION", "BACKUP", "RESTORE", "PERFORMANCE"}


@dataclass
class Verdict:
    valide: bool
    motif: str


def verifier(preuve: dict, types_admis: list[str], racine_artefacts: Path) -> Verdict:
    if not isinstance(preuve, dict):
        return Verdict(False, "preuve non structurée")
    t = preuve.get("type")
    if t not in types_admis:
        return Verdict(False, f"type de preuve inconnu : {t!r} (une déclaration n'est pas une preuve)")
    for champ in ("id", "source", "timestamp", "result", "generated_by", "artifact_ref", "hash"):
        if not preuve.get(champ):
            return Verdict(False, f"preuve sans {champ}")
    if preuve.get("immutable") is not True:
        return Verdict(False, "preuve non marquée immuable")
    try:
        _dt.datetime.fromisoformat(preuve["timestamp"])
    except (TypeError, ValueError):
        return Verdict(False, "horodatage illisible")
    if t in EXECUTION:
        if not preuve.get("command"):
            return Verdict(False, "preuve d'exécution sans commande")
        if not isinstance(preuve.get("exit_code"), int) or isinstance(preuve.get("exit_code"), bool):
            return Verdict(False, "preuve d'exécution sans code de sortie entier")
        attendu = "SUCCESS" if preuve["exit_code"] == 0 else "FAILURE"
        if preuve["result"] != attendu:
            return Verdict(False, f"résultat {preuve['result']} incohérent avec le code de sortie {preuve['exit_code']}")
    if t == "REVIEW" and not preuve.get("verified_by"):
        return Verdict(False, "revue sans relecteur identifié")
    artefact = (Path(racine_artefacts) / preuve["artifact_ref"]).resolve()
    try:
        artefact.relative_to(Path(racine_artefacts).resolve())
    except ValueError:
        return Verdict(False, "artefact hors du répertoire des preuves")
    if not artefact.is_file():
        return Verdict(False, "artefact introuvable")
    if hashlib.sha256(artefact.read_bytes()).hexdigest() != preuve["hash"]:
        return Verdict(False, "artefact modifié : empreinte différente")
    return Verdict(True, f"preuve {preuve['id']} vérifiée ({t}, {preuve['result']})")


def enregistrer_commande(resultat, type_: str, ident: str, racine_artefacts: Path, generated_by: str) -> dict:
    """Fabrique une preuve à partir d'une commande RÉELLEMENT exécutée (noyau.commandes.Resultat)."""
    if not getattr(resultat, "executee", False):
        raise ValueError("aucune preuve sans exécution réelle")
    racine = Path(racine_artefacts)
    racine.mkdir(parents=True, exist_ok=True)
    nom = f"{ident}.log"
    with open(racine / nom, "x", encoding="utf-8") as f:            # jamais d'écrasement d'un artefact
        f.write(resultat.sortie)
    return {"id": ident, "type": type_, "source": resultat.preuve.source, "timestamp": resultat.preuve.timestamp,
            "command": resultat.preuve.source, "exit_code": resultat.code,
            "result": "SUCCESS" if resultat.code == 0 else "FAILURE", "artifact_ref": nom,
            "hash": hashlib.sha256((racine / nom).read_bytes()).hexdigest(), "generated_by": generated_by,
            "verified_by": None, "immutable": True}
