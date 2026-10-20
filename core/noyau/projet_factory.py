"""Project Factory (Master Evolution Prompt v4 §35, §36, §54).

Chaque projet peut porter un dossier `.factory/` (project.yaml, agents, tools, workflows, policies, knowledge,
quality, security, prompts, environments, evidence). Ce module crée le squelette (sans rien écraser) et lit ce
qui s'y trouve comme des DONNÉES du projet.

Règles : une capacité, un outil ou une politique déclarée par un projet reste attachée à CE projet — elle ne
devient jamais globale ; une politique de projet ne peut que restreindre la politique de la Factory (jamais
l'élargir) ; un projet ne lit pas le `.factory/` d'un autre.
"""
from __future__ import annotations

from pathlib import Path

import yaml

DOSSIERS = ("agents", "tools", "workflows", "policies", "knowledge", "quality", "security", "prompts",
            "environments", "evidence")
ELARGISSEMENTS = ("allow", "grant", "approval_bypass", "disable_policy")


class RefusProjet(Exception):
    """Configuration de projet refusée."""


def squelette(racine_projet: Path, ident: str, nom: str) -> list[str]:
    """Crée `.factory/` et ses sous-dossiers ; n'écrase aucun fichier existant. → chemins créés."""
    base = Path(racine_projet) / ".factory"
    crees = []
    for d in ("",) + DOSSIERS:
        p = base / d
        if not p.exists():
            p.mkdir(parents=True)
            crees.append(str(p))
    pj = base / "project.yaml"
    if not pj.exists():
        pj.write_text(yaml.safe_dump({"schema_version": "1.0", "project": {"id": ident, "name": nom},
                                      "autonomy": {"level": "A2"}, "environments": [], "capabilities": []},
                                     allow_unicode=True, sort_keys=False), encoding="utf-8")
        crees.append(str(pj))
    return crees


def charger(racine_projet: Path, ident: str) -> dict:
    """Lit `.factory/` d'UN projet : capacités et politiques portées par ce projet, marquées de sa portée."""
    base = Path(racine_projet) / ".factory"
    if not (base / "project.yaml").is_file():
        return {"project": ident, "present": False}
    pj = yaml.safe_load((base / "project.yaml").read_text(encoding="utf-8")) or {}
    if (pj.get("project") or {}).get("id") != ident:
        raise RefusProjet(f".factory/ d'un autre projet ({(pj.get('project') or {}).get('id')!r})")
    politiques = []
    for f in sorted((base / "policies").glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        elargit = [k for k in ELARGISSEMENTS if k in doc]
        if elargit:
            raise RefusProjet(f"{f.name} : une politique de projet ne fait que restreindre ({', '.join(elargit)})")
        politiques.append({"file": f.name, "scope": {"project": ident}, "rules": doc})
    caps = [{"capability": c, "scope": {"project": ident}} for c in pj.get("capabilities") or []]
    return {"project": ident, "present": True, "manifest": pj, "capabilities": caps, "policies": politiques,
            "folders": [d for d in DOSSIERS if (base / d).is_dir()]}


def fusionner_capacites(globales: list[str], par_projet: dict[str, list[dict]], projet: str) -> list[str]:
    """Capacités visibles pour `projet` : les globales + les siennes. Celles d'un autre projet n'y entrent jamais."""
    propres = [c["capability"] for c in par_projet.get(projet, []) if (c.get("scope") or {}).get("project") == projet]
    return sorted(set(globales) | set(propres))
