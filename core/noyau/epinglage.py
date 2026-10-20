"""Épinglage des artefacts de gouvernance (ADR-0017, étape G1 ; annexe E « Épinglage », niveau L1 détectif).

La référence épinglée est une DÉCISION HUMAINE (W1) : l'agent prépare une demande qui porte l'empreinte de chaque
fichier couvert ; l'humain l'approuve avec la commande d'approbation ; aucune fonction ici n'écrit d'approbation.
Au lancement, l'état courant est comparé à la dernière référence approuvée :

- PINNED   : chaque fichier couvert a l'empreinte approuvée ;
- BLOCKED  : un fichier couvert est modifié, ajouté ou supprimé (le lancement est refusé) ;
- UNPINNED : aucune référence approuvée (attente humaine).

Les motifs vérifiés sont ceux de la référence approuvée, jamais ceux du fichier de politique courant : réduire la
couverture exige une nouvelle approbation. Limite L1 (ADR-0017 R2) : un acteur qui peut forger une approbation
peut forger une référence ; la modification d'un fichier couvert sans nouvelle approbation est détectée.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .approbation import CANAL, TYPE, empreinte, empreinte_enregistrement

KIND = "PIN_REFERENCE"
PINNED, BLOCKED, UNPINNED = "PINNED", "BLOCKED", "UNPINNED"


@dataclass
class Etat:
    statut: str
    reference: str | None = None                  # identifiant de l'approbation humaine qui fait référence
    ecarts: list[str] = field(default_factory=list)
    motif: str = ""


def releve(racine: Path, motifs: list[str]) -> dict[str, str]:
    """Empreinte SHA-256 de chaque fichier couvert par les motifs (chemins relatifs, séparateur « / »)."""
    racine = Path(racine)
    fichiers = {}
    for motif in motifs:
        for p in racine.glob(motif):
            if p.is_file():
                fichiers[p.relative_to(racine).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(sorted(fichiers.items()))


def contexte(racine: Path, motifs: list[str]) -> dict:
    fichiers = releve(racine, motifs)
    return {"kind": KIND, "patterns": sorted(motifs), "files": fichiers, "manifest_sha256": empreinte(fichiers)}


def demande(racine: Path, motifs: list[str], roles: list[str], maintenant: _dt.datetime | None = None) -> dict:
    """Demande d'approbation de la référence (l'agent DEMANDE ; l'humain approuve ou refuse)."""
    ctx = contexte(racine, motifs)
    ctx["requested_at"] = (maintenant or _dt.datetime.now(_dt.timezone.utc)).isoformat(timespec="seconds")
    return {"context": ctx, "context_sha256": empreinte(ctx), "roles": sorted(roles),
            "purpose": f"Référence d'épinglage : {len(ctx['files'])} fichiers de gouvernance à ces empreintes "
                       f"exactes (manifeste {ctx['manifest_sha256'][:12]}). Toute modification ultérieure d'un de "
                       f"ces fichiers bloquera le lancement jusqu'à une nouvelle approbation."}


def _reference_valide(e: dict, roles: list[str]) -> bool:
    ctx = e.get("context")
    return (e.get("kind") == TYPE and e.get("channel") == CANAL and e.get("decision") == "APPROVED"
            and e.get("record_sha256") == empreinte_enregistrement(e) and isinstance(ctx, dict)
            and ctx.get("kind") == KIND and e.get("context_sha256") == empreinte(ctx)
            and e.get("approver_role") in roles and isinstance(ctx.get("files"), dict)
            and ctx.get("manifest_sha256") == empreinte(ctx["files"]))


def derniere_reference(approbations: Path, roles: list[str]) -> dict | None:
    """Dernière approbation humaine valide d'une référence d'épinglage (par date de création)."""
    approbations = Path(approbations)
    retenues = []
    for p in sorted(approbations.glob("HA-*.json")) if approbations.is_dir() else []:
        try:
            e = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(e, dict) and _reference_valide(e, roles):
            retenues.append((str(e.get("created_at", "")), p.stem, e))
    return max(retenues)[2] if retenues else None


def verifier(racine: Path, approbations: Path, roles: list[str]) -> Etat:
    ref = derniere_reference(approbations, roles)
    if ref is None:
        return Etat(UNPINNED, motif="aucune référence d'épinglage approuvée (acte humain W1)")
    attendu = ref["context"]["files"]
    actuel = releve(racine, ref["context"].get("patterns") or [])
    ecarts = ([f"modifié : {f}" for f in sorted(attendu) if f in actuel and actuel[f] != attendu[f]]
              + [f"supprimé : {f}" for f in sorted(attendu) if f not in actuel]
              + [f"ajouté : {f}" for f in sorted(actuel) if f not in attendu])
    if ecarts:
        return Etat(BLOCKED, ref.get("id"), ecarts, f"{len(ecarts)} écart(s) avec la référence {ref.get('id')}")
    return Etat(PINNED, ref.get("id"), [], f"{len(attendu)} fichiers conformes à la référence {ref.get('id')}")
