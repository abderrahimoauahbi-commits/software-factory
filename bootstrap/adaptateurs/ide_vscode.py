"""Inventaire d'un IDE de type « VS Code » (lecture seule, fichiers approuvés un par un : APR-0001)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from noyau.masquage import masquer
from noyau.perimetre import AccesRefuse

_UTILISATEUR = Path(os.path.expandvars("%APPDATA%/Code/User"))


def _obs(**k):
    from . import observation
    return observation(**k)


def _json_souple(texte: str):
    """JSON avec commentaires et virgules finales, comme l'accepte l'éditeur."""
    texte = re.sub(r"^\s*//.*$", "", texte, flags=re.M)
    texte = re.sub(r",(\s*[}\]])", r"\1", texte)
    return json.loads(texte)


def _lire(ctx, chemin: Path, refus: list[str]):
    try:
        return _json_souple(ctx.perimetre.lire_texte(chemin, hors_racine_ok=True))
    except FileNotFoundError:
        return None
    except (AccesRefuse, ValueError) as e:
        refus.append(f"{chemin} : {type(e).__name__}")
        return None


def inventaire(ctx, spec: dict) -> dict:
    refus: list[str] = []
    reglages = _lire(ctx, _UTILISATEUR / "settings.json", refus) or {}
    mcp = _lire(ctx, _UTILISATEUR / "mcp.json", refus) or {}
    stockage = _lire(ctx, _UTILISATEUR / "globalStorage" / "storage.json", refus) or {}
    extensions = ctx.executeur.lancer(["code", "--list-extensions"])
    liste = [l.strip() for l in extensions.sortie.splitlines() if l.strip()] if extensions.code == 0 else []
    serveurs = [{"nom": n, "portee": "IDE (mcp.json)", "actif": True,
                 "descripteur": masquer(" ".join([str(s.get("command", "")), *map(str, s.get("args", []) or []),
                                                  str(s.get("url", ""))]).strip())}
                for n, s in (mcp.get("servers") or {}).items() if isinstance(s, dict)]
    return _obs(present=True, detail="configuration inventoriée (clés seulement)",
                cles_reglages=len(reglages), profils=[p.get("name") for p in stockage.get("userDataProfiles", [])],
                extensions=liste, nombre_extensions=len(liste),
                mcp_declares=serveurs, refus=refus)
