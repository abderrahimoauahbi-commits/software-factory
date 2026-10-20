"""Construction du Policy Engine et du moteur d'états à partir d'une Factory (registre, politiques, manifests).

Point unique d'assemblage pour la CLI et, plus tard, pour la garde de l'agent : aucune règle ici, seulement le
chargement. Un manifest dont les `paths` sont `PROPOSED` n'a pas de chemins normatifs (décision M2) : ils sont
écartés, et tout accès qui en dépend retombe sur le refus par défaut.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import yaml

from .approbation import Magasin
from .audit import Journal
from .derogations import GestionnaireExceptions
from .etats import Machine
from .politique import Moteur, ProjetPolitique
from .portes import Portes
from .registre import Registre, charger


def _yaml(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def manifest_du_projet(racine_factory: Path, carte: dict) -> tuple[dict | None, str | None, list[str]]:
    """(bloc « project », source PROJECT|DRAFT, remarques). Le manifest du projet prime sur le brouillon."""
    remarques = []
    racine = Path(carte["root"]["path"])
    chemin = racine / (carte.get("manifest") or {}).get("path", "factory.yaml")
    doc, source = None, None
    if chemin.is_file():
        doc, source = _yaml(chemin), "PROJECT"
    elif (carte.get("manifest") or {}).get("draft"):
        doc, source = _yaml(racine_factory / carte["manifest"]["draft"]), "DRAFT"
    bloc = (doc or {}).get("project") if isinstance(doc, dict) else None
    if bloc is None:
        return None, source, remarques
    bloc = copy.deepcopy(bloc)
    if isinstance(bloc.get("paths"), dict) and bloc["paths"].get("status") == "PROPOSED":
        bloc.pop("paths")
        remarques.append("paths PROPOSED écartés : non normatifs (M2)")
    return bloc, source, remarques


def projets(racine_factory: Path, reg: Registre) -> tuple[dict[str, ProjetPolitique], dict[str, list[str]]]:
    resultat, remarques = {}, {}
    for ident, carte in reg.objets["projects"].items():
        bloc, source, notes = manifest_du_projet(racine_factory, carte)
        if bloc is None:
            continue                                     # la Factory elle-même n'a pas de manifest de projet
        resultat[ident] = ProjetPolitique(
            id=ident, racine=Path(carte["root"]["path"]), manifest=bloc,
            sensibles=list(carte.get("sensitive_paths", [])),
            marqueurs=list(((carte.get("root") or {}).get("resolution") or {}).get("identity_markers", [])),
            espace=dict(carte.get("workspace") or {}))
        remarques[ident] = [f"manifest : {source}"] + notes
    return resultat, remarques


def moteur(racine_factory: Path, reg: Registre | None = None, ressources=None) -> tuple[Moteur, dict]:
    """`ressources` : registre des ressources (noyau.ressources.Registre) ; sans lui, toute capacité est DENY (R32)."""
    reg = reg or charger(racine_factory)
    p = racine_factory / "policies"
    projs, remarques = projets(racine_factory, reg)
    m = Moteur(regles=_yaml(p / "policy-engine.yaml"), classes=_yaml(p / "command-classes.yaml"),
               liste_blanche=_yaml(p / "command-whitelist.yaml")["allowed"],
               confiance=_yaml(racine_factory / "core" / "schemas" / "trust.yaml"),
               racine_scope=_yaml(p / "root-scope.yaml"), registre=reg, projets=projs,
               approbations=Magasin(racine_factory / "audit" / "approvals" / "human"),
               autonomie=_yaml(p / "autonomy.yaml") if (p / "autonomy.yaml").is_file() else {},
               ressources=ressources,
               catalogue=_yaml(p / "rule-catalog.yaml") if (p / "rule-catalog.yaml").is_file() else {},
               exceptions=GestionnaireExceptions(racine_factory / "audit" / "approvals" / "human",
                                                 Journal(racine_factory / "audit" / "journal.jsonl")))
    return m, remarques


FICHIERS_DE_POLITIQUE = ("policies/policy-engine.yaml", "policies/command-classes.yaml",
                         "policies/command-whitelist.yaml", "policies/root-scope.yaml", "policies/autonomy.yaml",
                         "policies/rule-catalog.yaml", "core/schemas/trust.yaml")


def empreinte_politique(racine_factory: Path) -> str:
    """Empreinte des fichiers qui qualifient une décision ; un bail émis sous une autre empreinte est invalidé (P18)."""
    h = hashlib.sha256()
    for rel in FICHIERS_DE_POLITIQUE:
        p = racine_factory / rel
        h.update(rel.encode("utf-8") + b"\0" + (p.read_bytes() if p.is_file() else b"ABSENT") + b"\0")
    return h.hexdigest()


def machine(racine_factory: Path, journal: Path | None = None) -> Machine:
    schemas = racine_factory / "core" / "schemas"
    a = racine_factory / "audit"
    return Machine(cycles=_yaml(schemas / "lifecycles.yaml"),
                   exigences=_yaml(racine_factory / "policies" / "transitions.yaml"),
                   types_preuve=_yaml(schemas / "enums.yaml")["EVIDENCE_TYPE"],
                   racine_preuves=racine_factory / "compliance" / "evidence" / "artifacts",
                   journal=Journal(journal or a / "journal.jsonl"),
                   portes=Portes(a / "gates", a / "approvals" / "requests"),
                   approbations=Magasin(a / "approvals" / "human"),
                   roles_par_niveau=_yaml(racine_factory / "policies" / "policy-engine.yaml")["approval_roles"],
                   roles_revue=_yaml(racine_factory / "policies" / "human-approval.yaml").get("review_roles", []))
