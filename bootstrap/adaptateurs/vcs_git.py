"""Adaptateurs du contrôle de version Git (capacités SOURCE_CONTROL et ISOLATED_WORKSPACE).

Commandes de lecture seulement (liste blanche) ; GIT_OPTIONAL_LOCKS=0 empêche toute écriture d'index.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def _obs(**k):
    from . import observation
    return observation(**k)


def _git(ctx, *args):
    return ctx.executeur.lancer(["git", "-C", str(ctx.racine_projet), *args])


def git_repository(ctx, spec: dict) -> dict:
    if ctx.racine_projet is None:
        return _obs(present=None, nature="UNVERIFIABLE", detail="aucun projet ciblé")
    top = _git(ctx, "rev-parse", "--show-toplevel")
    if not top.executee or top.code != 0:
        return _obs(present=False, detail="pas un dépôt Git")
    racine_git = os.path.normcase(os.path.realpath(top.sortie.strip()))
    if racine_git != os.path.normcase(str(ctx.racine_projet)):
        return _obs(present=False, detail="la racine Git ne coïncide pas avec la racine du projet")
    statut = _git(ctx, "status", "--short", "--branch")
    lignes = statut.sortie.splitlines() if statut.executee else []
    entete = lignes[0] if lignes else ""
    m = re.match(r"## (?:No commits yet on )?([^.\s]+)(?:\.\.\.(\S+))?(?: \[(.*)\])?", entete)
    avance = re.search(r"ahead (\d+)", entete)
    retard = re.search(r"behind (\d+)", entete)
    distants = _git(ctx, "remote", "-v")
    arbres = _git(ctx, "worktree", "list")
    crochets = _git(ctx, "config", "--get", "core.hookspath")   # Git ignore la casse des clés
    hooks_dir = ctx.racine_projet / ".git" / "hooks"
    actifs = []
    if hooks_dir.is_dir():
        actifs = [n for n in ctx.perimetre.lister(hooks_dir) if not n.endswith(".sample")]
    return _obs(
        present=True, detail="dépôt Git valide",
        branche=m.group(1) if m else None, amont=m.group(2) if m and m.group(2) else None,
        en_avance=int(avance.group(1)) if avance else 0, en_retard=int(retard.group(1)) if retard else 0,
        sans_commit="No commits yet" in entete,
        modifies=len([l for l in lignes[1:] if l.strip()]),
        distants=sorted({l.split()[1] for l in distants.sortie.splitlines() if len(l.split()) >= 2}),
        espaces_isoles=len([l for l in arbres.sortie.splitlines() if l.strip()]),
        hooks_path=crochets.sortie.strip() or None, hooks_actifs=actifs)


def git_worktree(ctx, spec: dict) -> dict:
    if ctx.racine_projet is None:
        return _obs(present=None, nature="UNVERIFIABLE", detail="aucun projet ciblé")
    r = _git(ctx, "worktree", "list")
    if not r.executee or r.code != 0:
        return _obs(present=False, detail="« git worktree list » indisponible")
    n = len([l for l in r.sortie.splitlines() if l.strip()])
    return _obs(present=True, detail=f"disponible ; {n} espace(s) de travail", espaces=n)


def git_files(ctx, spec: dict) -> dict:
    """Noms des fichiers suivis et des fichiers ignorés présents (jamais leur contenu)."""
    if ctx.racine_projet is None:
        return _obs(present=None, nature="UNVERIFIABLE", detail="aucun projet ciblé", tracked=[], ignored=[])
    suivis = _git(ctx, "ls-files")
    ignores = _git(ctx, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory")
    return _obs(present=True, detail="inventaire des noms de fichiers",
                tracked=suivis.sortie.splitlines() if suivis.executee else [],
                ignored=ignores.sortie.splitlines() if ignores.executee else [])
