"""Rattachement d'un projet à la Factory (ADR-0001 : le manifest vit dans le dépôt du projet ; la Factory reste
installée une seule fois). Commande `factory project init` — acte de l'humain, refusé dans une session d'agent.

Pose dans le dossier du projet, sans jamais écraser un fichier existant :
- `factory.yaml` : manifest minimal (pile, chemins et gates à compléter après l'architecture), validé par le
  registre AVANT d'être écrit ;
- `CLAUDE.md` : règles de travail de la session ouverte dans le projet (ordre des rôles, validations humaines,
  décisions réservées, commandes de la Factory) ;
- `.claude/settings.json` : gardes de la Factory (approbations humaines protégées) pour cette session.
Inscrit la carte du projet au registre de la Factory.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import yaml

ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")


def manifest(ident: str, nom: str) -> dict:
    return {"schema_version": "1.0", "project": {
        "id": ident, "name": nom,
        "description": "Projet rattaché à la Factory ; pile, chemins et gates définis après l'architecture technique",
        "factory": {"version": "3.2", "minimum_version": "3.2"},
        "lifecycle": {"state": "REGISTERED", "criticality_default": "C2"},
        "stack": {k: [] for k in ("languages", "frameworks", "databases", "frontend", "backend", "mobile",
                                  "infrastructure", "build_systems", "test_systems")},
        "capabilities": {"required": [], "optional": []},
        "repositories": [{"id": "main", "type": "git", "path": ".", "remote": None, "branch": "main"}],
        "paths": {"status": "PROPOSED", "read": ["docs/"], "write": ["docs/"], "forbidden": [".env", ".env.*"]},
        "environments": [
            {"id": "local", "type": "LOCAL", "allowed": True, "write_allowed": True, "data_classification": "INTERNAL"},
            {"id": "production", "type": "PRODUCTION", "allowed": False, "write_allowed": False,
             "data_classification": "CONFIDENTIAL"}],
        "agents": {"required": [], "allowed": []},
        "tools": {"required": [], "allowed": []},
        "skills": {"required": [], "allowed": []},
        "models": {"allowed": [], "preferred": None, "fallback": None},
        "mcp": {"allowed": [], "production_write": False, "production_delete": False},
        "security": {"production_write": False, "production_delete": False, "secrets_allowed": False,
                     "outbound_network_default": False, "sensitive_data_to_ai": False},
        "data": {"classification": "INTERNAL", "owners": [], "retention_policy": None},
        "compliance": {"frameworks": []},
        "quality": {"required": [], "optional": [], "gates": {}},
        "budgets": {"token_limit": None, "cost_limit": None, "time_limit_minutes": None, "max_attempts": 3},
        "governance": {"project_owner": "Factory Owner", "release_approver": None, "security_owner": None,
                       "data_owner": None, "architect": None}}}


def contexte(ident: str, nom: str, factory: Path) -> str:
    f = factory.as_posix()
    return f"""# CLAUDE.md — projet {nom} (`{ident}`), rattaché à l'AI Software Factory

> Fichier de contexte, sans autorité propre : les règles qui font foi sont celles de la Factory
> (`{f}`), ses politiques, ses ADR et les décisions du Factory Owner.

## 1. Comment on travaille ici

Le projet suit les rôles de la Factory, dans cet ordre, avec une **validation du Factory Owner entre chaque étape** :

| Étape | Rôle | Livrable |
|---|---|---|
| 1. Cahier des charges | planner | `docs/01-…` |
| 2. Spécification, règles métier | planner, business-rules | `docs/02-…` |
| 3. Architecture technique : options comparées, **choix des outils par le Factory Owner** | architect | `docs/03-…` |
| 4. Découpage en tickets | planner | tickets au registre de la Factory |
| 5. Réalisation, ticket par ticket | orchestrateur et rôles d'ingénierie | code, preuves, revue humaine |

L'état du projet est tenu dans `README.md`. **Ne jamais commencer une étape dont la précédente n'est pas validée.**

## 2. Décisions réservées au Factory Owner

Quoi construire, la pile et les outils, le périmètre, l'organisation du travail, l'acceptation d'un ADR, toute
approbation. Pour chacune : présenter 2 ou 3 options expliquées en clair (avantages, risques, recommandation) et
**attendre son choix**. Une délégation générale (« fais ce que tu veux ») ne couvre jamais ces décisions.

## 3. Règles permanentes

- Aucun code, aucune migration, aucune installation d'outil avant la validation de l'architecture technique.
- Après elle, tout changement passe par un ticket de la Factory, dans un espace isolé, avec revue humaine.
- Aucun commit ni push sans accord explicite du Factory Owner.
- Tout point ambigu est marqué « À ARBITRER », jamais inventé.
- Les approbations sont des actes humains : `python -P {f}/scripts/factory_approve.py --ouvertes`, lancé par le
  Factory Owner dans son terminal ; jamais par un agent.

## 4. Commandes de la Factory

```bash
python -P {f}/factory.py check                 # état de la Factory
python -P {f}/factory.py decide list           # demandes de décision et leur état
python -P {f}/factory.py registry list projects
```
"""


def reglages(factory: Path) -> dict:
    garde = (factory / "scripts" / "hooks" / "garde_approbations.py").as_posix()
    humain = (factory / "audit" / "approvals" / "human").as_posix()
    return {"env": {"PYTHONIOENCODING": "utf-8"},
            "permissions": {"deny": [f"Edit({humain}/**)", f"Write({humain}/**)",
                                     "Bash(python -P scripts/factory_approve.py *)",
                                     f"Bash(python -P {factory.as_posix()}/scripts/factory_approve.py *)",
                                     f"PowerShell(python -P {factory.as_posix()}/scripts/factory_approve.py *)"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash|PowerShell|Edit|Write|NotebookEdit|MultiEdit",
                                      "hooks": [{"type": "command", "command": f'python -P "{garde}"',
                                                 "timeout": 30}]}]}}


def carte(ident: str, nom: str, dossier: Path, jour: str) -> dict:
    return {"schema_version": "1.0", "id": ident, "name": nom,
            "lifecycle": {"state": "REGISTERED", "role_in_factory": "project"},
            "root": {"path": dossier.as_posix(),
                     "resolution": {"method": "commande « factory project init », lancée par le Factory Owner",
                                    "identity_markers": [{"file": "factory.yaml", "pattern": f"^  id: {ident}$"}],
                                    "validated_by": "Factory Owner", "validated_on": jour}},
            "manifest": {"path": "factory.yaml"},
            "sensitive_paths": [".env", ".env.*", ".claude/settings.local.json"]}


def initialiser(factory: Path, registre, dossier: Path, ident: str, nom: str,
                jour: str | None = None) -> list[Path]:
    """Écrit les fichiers de rattachement ; refuse tout écrasement. `registre` : noyau.registre.Registre."""
    from noyau.registre import valider_manifest
    dossier, factory = Path(dossier).resolve(), Path(factory).resolve()
    jour = jour or _dt.date.today().isoformat()
    if not ID.match(ident or ""):
        raise ValueError(f"identifiant de projet invalide : {ident!r} (minuscules, chiffres, tirets)")
    if not dossier.is_dir():
        raise ValueError(f"dossier du projet introuvable : {dossier}")
    if dossier == factory or factory in dossier.parents or dossier in factory.parents:
        raise ValueError("le dossier du projet ne peut ni contenir la Factory ni être dans la Factory")
    fiche = factory / "registry" / "projects" / ident / "project.yaml"
    cibles = {dossier / "factory.yaml": None, dossier / "CLAUDE.md": None,
              dossier / ".claude" / "settings.json": None, fiche: None}
    deja = [str(p) for p in cibles if p.exists()]
    if deja:
        raise ValueError("refus : fichiers déjà présents (jamais écrasés) : " + ", ".join(deja))
    if ident in (registre.objets.get("projects") or {}):
        raise ValueError(f"refus : le projet {ident!r} est déjà inscrit au registre")
    doc = manifest(ident, nom)
    verdict = valider_manifest(registre, doc, "factory.yaml")
    if verdict.statut != "VALID":
        raise ValueError(f"manifest refusé par le registre : {verdict.statut} — "
                         + "; ".join(str(e) for e in verdict.defauts[:5]))
    ecrits = []
    for chemin, contenu in ((dossier / "factory.yaml", yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)),
                            (dossier / "CLAUDE.md", contexte(ident, nom, factory)),
                            (dossier / ".claude" / "settings.json",
                             json.dumps(reglages(factory), ensure_ascii=False, indent=2) + "\n"),
                            (fiche, yaml.safe_dump(carte(ident, nom, dossier, jour), allow_unicode=True,
                                                   sort_keys=False))):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(chemin, "x", encoding="utf-8") as f:          # écriture exclusive : jamais d'écrasement
            f.write(contenu)
        ecrits.append(chemin)
    return ecrits


def cmd_project(a, sortir) -> int:
    from fournisseurs import cablage
    from noyau.audit import Journal
    from noyau.registre import charger
    if cablage.dans_une_session_d_agent():
        sortir({"refus": "session d'agent"}, "refus : rattacher un projet à la Factory est un acte du Factory Owner, "
                                              "à lancer dans votre terminal")
        return 2
    if not a.id or not a.nom:
        sortir({"refus": "usage"}, "usage : factory project init DOSSIER --id ID --nom NOM")
        return 3
    try:
        ecrits = initialiser(cablage.FACTORY, charger(cablage.FACTORY), Path(a.dossier), a.id, a.nom)
    except ValueError as e:
        sortir({"refus": str(e)}, f"refus : {e}")
        return 2
    Journal(cablage.FACTORY / "audit" / "journal.jsonl").ajouter(
        actor={"type": "human", "id": "console"}, project_id=a.id, action="rattachement du projet à la Factory",
        result="REGISTERED", from_state=None, to_state="REGISTERED",
        evidence_refs=[p.as_posix() for p in ecrits],
        reasons=["commande « factory project init », refusée en session d'agent"])
    sortir({"ecrits": [str(p) for p in ecrits]},
           "projet rattaché :\n" + "\n".join(f"  {p}" for p in ecrits)
           + f"\nensuite : ouvrir {Path(a.dossier).resolve()} dans VS Code, puis lancer Claude Code dans ce dossier")
    return 0
