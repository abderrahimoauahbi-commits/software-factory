"""Demandes de décision humaine (ADR-0017 I8 ; étape G1) : créées par le Core, dédoublonnées, sous quota.

- Dédoublonnage : une demande dont l'empreinte de contexte existe déjà (quel que soit son nom) n'est pas recréée ;
  la demande existante est rendue.
- Quota : au-delà de `max_open_requests` demandes OUVERTES (sans enregistrement humain de même empreinte, qu'il
  approuve ou refuse), toute nouvelle demande est refusée : un agent ne noie pas l'humain sous les demandes.
Une demande n'accorde rien ; seule la commande humaine décide (W1).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .approbation import canonique, empreinte

_NOM = re.compile(r"^AR-[A-Za-z0-9._-]{1,120}\.json$")


class RefusDemande(Exception):
    """Demande non déposée (nom invalide, contexte incohérent, quota atteint)."""


def _lire(p: Path) -> dict | None:
    try:
        e = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return e if isinstance(e, dict) else None


def decidees(approbations: Path) -> set[str]:
    """Empreintes de contexte qui ont reçu une décision humaine (approbation ou refus)."""
    approbations = Path(approbations)
    return {e.get("context_sha256") for p in (sorted(approbations.glob("HA-*.json")) if approbations.is_dir() else [])
            if (e := _lire(p)) and e.get("context_sha256")}


def ouvertes(dossier: Path, approbations: Path) -> list[str]:
    """Noms des demandes sans décision humaine."""
    dossier, faites = Path(dossier), decidees(approbations)
    return [p.name for p in (sorted(dossier.glob("AR-*.json")) if dossier.is_dir() else [])
            if (e := _lire(p)) and e.get("context_sha256") not in faites]


def deposer(dossier: Path, nom: str, demande: dict, approbations: Path, quota: int | None) -> tuple[Path, bool]:
    """→ (chemin, créée). Dédoublonne par empreinte de contexte, puis applique le quota des demandes ouvertes."""
    if not _NOM.match(nom or ""):
        raise RefusDemande(f"nom de demande invalide : {nom!r}")
    ctx = demande.get("context")
    if not isinstance(ctx, dict) or demande.get("context_sha256") != empreinte(ctx):
        raise RefusDemande("demande incohérente : l'empreinte ne correspond pas au contexte")
    dossier = Path(dossier)
    for p in sorted(dossier.glob("AR-*.json")) if dossier.is_dir() else []:
        if (e := _lire(p)) and e.get("context_sha256") == demande["context_sha256"]:
            return p, False
    if quota is not None and len(ouvertes(dossier, approbations)) >= int(quota):
        raise RefusDemande(f"quota atteint : {quota} demandes ouvertes au plus (I8) — l'humain doit d'abord décider")
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    with open(chemin, "x", encoding="utf-8") as f:
        f.write(canonique(demande))
    return chemin, True
