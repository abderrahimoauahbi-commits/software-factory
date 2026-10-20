"""Adaptateurs de dépendances déclarées par un projet (paquets Node, dépendances Cargo).

Ils lisent les fichiers de dépendances et de verrouillage du projet, jamais ses sources. La recherche se
limite à la racine du projet et à ses sous-répertoires de premier niveau (Progressive Disclosure).
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

from noyau.perimetre import AccesRefuse


def _obs(**k):
    from . import observation
    return observation(**k)


def _emplacements(ctx, nom_fichier: str) -> list[Path]:
    if ctx.racine_projet is None:
        return []
    racine = ctx.racine_projet
    trouves = [racine / nom_fichier] if (racine / nom_fichier).is_file() else []
    for nom in ctx.perimetre.lister(racine):
        sous = racine / nom
        if sous.is_dir() and not nom.startswith(".") and nom not in ctx.perimetre.jamais_parcourus \
                and (sous / nom_fichier).is_file():
            trouves.append(sous / nom_fichier)
    return trouves


def node_package(ctx, spec: dict) -> dict:
    paquet = spec["package"]
    for manifeste in _emplacements(ctx, "package.json"):
        try:
            declare = json.loads(ctx.perimetre.lire_texte(manifeste))
        except (AccesRefuse, ValueError):
            continue
        plage = {**declare.get("dependencies", {}), **declare.get("devDependencies", {})}.get(paquet)
        if plage is None:
            continue
        installe = manifeste.parent / "node_modules" / paquet / "package.json"
        if installe.is_file():
            # Métadonnée d'installation de l'outil (TOOL_INSTALL_ROOTS) : seul ce package.json est lu.
            version = json.loads(ctx.perimetre.lire_texte(installe)).get("version")
            return _obs(present=True, version=version, detail=f"déclaré {plage} ; installé",
                        manifeste=str(manifeste.relative_to(ctx.racine_projet).as_posix()))
        return _obs(present=False, nature="DECLARED", detail=f"déclaré {plage} mais non installé",
                    manifeste=str(manifeste.relative_to(ctx.racine_projet).as_posix()))
    return _obs(present=False, nature="DECLARED", detail="non déclaré par le projet")


def cargo_dependency(ctx, spec: dict) -> dict:
    caisse = spec["crate"]
    for manifeste in _emplacements(ctx, "Cargo.toml"):
        try:
            cargo = tomllib.loads(ctx.perimetre.lire_texte(manifeste))
        except (AccesRefuse, tomllib.TOMLDecodeError):
            continue
        dep = cargo.get("dependencies", {}).get(caisse)
        if dep is None:
            continue
        exigence = dep if isinstance(dep, str) else dep.get("version")
        verrou = manifeste.parent / "Cargo.lock"
        if verrou.is_file():
            for p in tomllib.loads(ctx.perimetre.lire_texte(verrou)).get("package", []):
                if p.get("name") == caisse:
                    return _obs(present=True, version=p.get("version"),
                                detail=f"exige {exigence} ; résolu par le fichier de verrouillage",
                                manifeste=str(manifeste.relative_to(ctx.racine_projet).as_posix()))
        return _obs(present=True, nature="DECLARED", detail=f"exige {exigence} ; non résolu")
    return _obs(present=False, nature="DECLARED", detail="non déclaré par le projet")
