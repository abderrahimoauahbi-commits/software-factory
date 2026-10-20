"""Centre de décision, niveau L1 en ligne de commande (ADR-0017 D31, I8 ; Playbook v3.3 §17, étape G2).

Rassemble les demandes de décision humaine et leur état ; ne décide jamais. La décision reste un enregistrement
créé par la commande humaine (W1) : ce module LIT les enregistrements, il n'en écrit aucun.

États d'une demande :
- OPEN      : aucune décision humaine pour son empreinte de contexte ;
- APPROVED  : la dernière décision humaine l'approuve ;
- REJECTED  : la dernière décision humaine la refuse ;
- OBSOLETE  : ouverte, mais ce qu'elle couvre a changé depuis (constat fourni par l'appelant, par type) ;
- EXECUTED  : approuvée et déjà exécutée (plans d'exécution humaine, usage unique).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .approbation import CANAL, TYPE, empreinte, empreinte_enregistrement

OPEN, APPROVED, REJECTED, OBSOLETE, EXECUTED = "OPEN", "APPROVED", "REJECTED", "OBSOLETE", "EXECUTED"


@dataclass
class EtatDemande:
    nom: str
    type: str
    statut: str
    empreinte: str
    roles: list[str] = field(default_factory=list)
    objet: str = ""
    decision: str | None = None                 # identifiant de l'enregistrement humain
    motif: str = ""


def _lire(p: Path) -> dict | None:
    try:
        e = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return e if isinstance(e, dict) else None


def decisions_humaines(approbations: Path) -> dict[str, dict]:
    """Dernière décision humaine VALIDE (forme de la commande, empreintes intactes) par empreinte de contexte."""
    approbations, out = Path(approbations), {}
    for p in sorted(approbations.glob("HA-*.json")) if approbations.is_dir() else []:
        e = _lire(p)
        if not e or e.get("kind") != TYPE or e.get("channel") != CANAL:
            continue
        if e.get("record_sha256") != empreinte_enregistrement(e) or e.get("context_sha256") != empreinte(e.get("context")):
            continue
        h = e["context_sha256"]
        if h not in out or str(e.get("created_at", "")) >= str(out[h].get("created_at", "")):
            out[h] = e
    return out


def etats(demandes: Path, approbations: Path, obsolete: Callable[[dict], str | None] | None = None,
          executees: set[str] | None = None) -> list[EtatDemande]:
    """État de chaque demande. `obsolete(contexte)` → motif si la demande ne correspond plus à l'état courant.
    `executees` : empreintes de contexte déjà exécutées (journal)."""
    demandes, decisions, executees = Path(demandes), decisions_humaines(approbations), executees or set()
    out = []
    for p in sorted(demandes.glob("AR-*.json")) if demandes.is_dir() else []:
        d = _lire(p)
        if not d or not isinstance(d.get("context"), dict):
            continue
        ctx, h = d["context"], d.get("context_sha256")
        if h != empreinte(ctx):
            out.append(EtatDemande(p.name, str(ctx.get("kind") or "?"), OBSOLETE, str(h), motif="demande incohérente"))
            continue
        e = EtatDemande(p.name, str(ctx.get("kind") or ("HUMAN_GATE" if d.get("human_gate") else "?")), OPEN, h,
                        list(d.get("roles") or []), str(d.get("purpose") or "")[:200])
        dec = decisions.get(h)
        if dec is not None:
            e.decision = dec.get("id")
            e.statut = APPROVED if dec.get("decision") == "APPROVED" else REJECTED
            if e.statut == APPROVED and h in executees:
                e.statut = EXECUTED
        elif obsolete is not None:
            motif = obsolete(ctx)
            if motif:
                e.statut, e.motif = OBSOLETE, motif
        out.append(e)
    return out
