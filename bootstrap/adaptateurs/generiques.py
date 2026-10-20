"""Adaptateurs génériques : version par commande, présence d'un exécutable ou d'un fichier, Python."""
from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import re
import shutil
import sys


def _obs(**k):
    from . import observation
    return observation(**k)


def command_version(ctx, spec: dict) -> dict:
    r = ctx.executeur.lancer(list(spec["command"]))
    if not r.autorisee:
        return _obs(present=None, nature="UNVERIFIABLE", detail=f"commande refusée ({r.motif_refus})")
    if not r.executee:
        return _obs(present=False, detail="exécutable introuvable dans le PATH")
    if r.code != 0:
        return _obs(present=True, nature="VERIFIED", detail=f"code de sortie {r.code}")
    m = re.search(spec.get("pattern", r"(\S+)"), r.sortie, re.M)
    return _obs(present=True, version=m.group(1) if m else None,
                detail="" if m else "version non reconnue dans la sortie", chemin=shutil.which(spec["command"][0]))


def executable_present(ctx, spec: dict) -> dict:
    chemin = shutil.which(spec["executable"])
    if chemin is None:
        return _obs(present=False, detail="absent du PATH")
    return _obs(present=True, detail="présent (version non lue : commande hors liste blanche)", chemin=chemin)


def file_present(ctx, spec: dict) -> dict:
    for p in spec.get("paths", []):
        if os.path.isfile(p):                    # métadonnée seule : le fichier n'est pas ouvert
            return _obs(present=True, detail="présent (version non lue)", chemin=p)
    return _obs(present=False, detail="aucun des emplacements déclarés")


def python_runtime(ctx, spec: dict) -> dict:
    version = platform.python_version()
    minimum = tuple(int(x) for x in str(spec.get("minimum", "0")).split("."))
    ok = sys.version_info[:len(minimum)] >= minimum
    return _obs(present=True, version=version, detail="" if ok else f"version < {spec.get('minimum')}",
                chemin=sys.executable, conforme=ok)


def python_module(ctx, spec: dict) -> dict:
    trouve = importlib.util.find_spec(spec["module"])
    if trouve is None:
        return _obs(present=False, detail="module introuvable")
    mod = importlib.import_module(spec["module"])
    return _obs(present=True, version=getattr(mod, "__version__", None), chemin=trouve.origin)
