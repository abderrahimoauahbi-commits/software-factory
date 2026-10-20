"""Chargement du registre et validation de chaque fiche par le moteur de validation (Executable Schemas §30).

Deux passes : toutes les fiches sont lues, puis chacune est validée — les références se vérifient alors contre
l'ensemble du registre. Une fiche non VALID est consignée (VALIDATION_FAILED) et bloque la Factory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .validation import VALID, Validateur, Verdict

# Répertoire du registre → schéma d'objet.
TYPES = {"capabilities": "capability", "tools": "tool", "mcp": "mcp", "models": "model", "agents": "agent",
         "skills": "skill", "workflows": "workflow", "prompts": "prompt_profile"}      # ADR-0022 v2, F-4


@dataclass
class Erreur:
    fichier: str
    message: str


@dataclass
class Registre:
    racine: Path
    enums: dict
    cycles: dict
    schemas: dict
    validateur: Validateur | None = None
    objets: dict[str, dict[str, dict]] = field(default_factory=dict)   # type → id → objet
    verdicts: list[Verdict] = field(default_factory=list)
    erreurs: list[Erreur] = field(default_factory=list)
    attentes: list[str] = field(default_factory=list)                 # champs WAITING_HUMAN rencontrés

    def get(self, type_: str, ident: str) -> dict | None:
        return self.objets.get(type_, {}).get(ident)


def _yaml(chemin: Path):
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


def charger_schemas(racine_factory: Path) -> tuple[dict, dict, dict]:
    d = racine_factory / "core" / "schemas"
    return (_yaml(d / "enums.yaml"), _yaml(d / "lifecycles.yaml"),
            {p.name.split(".")[0]: _yaml(p) for p in (d / "objects").glob("*.schema.yaml")})


def charger(racine_factory: Path) -> Registre:
    enums, cycles, schemas = charger_schemas(racine_factory)
    factory = _yaml(racine_factory / "factory.yaml") or {}
    reg = Registre(racine=racine_factory, enums=enums, cycles=cycles, schemas=schemas)
    base = racine_factory / "registry"

    # Passe 1 : lecture.
    bruts: list[tuple[str, str, Path, dict]] = []
    for dossier, nom_schema in TYPES.items():
        reg.objets[dossier] = {}
        for f in sorted((base / dossier).glob("*.yaml")):
            obj = _yaml(f) or {}
            rel = f.relative_to(racine_factory).as_posix()
            ident = obj.get("id")
            if ident != f.stem:
                reg.erreurs.append(Erreur(rel, f"id {ident!r} ≠ nom de fichier {f.stem!r}"))
            if ident in reg.objets[dossier]:
                reg.erreurs.append(Erreur(rel, f"id en double : {ident}"))
            reg.objets[dossier][ident] = obj
            bruts.append((dossier, nom_schema, f, obj))
    cartes = []
    reg.objets["projects"] = {}
    for carte in sorted((base / "projects").glob("*/project.yaml")):
        c = _yaml(carte) or {}
        reg.objets["projects"][c.get("id")] = c
        cartes.append((carte, c))
    # Tickets de chaque projet (T-FACTORY-020) : validés comme le reste du registre, références comprises.
    reg.objets["tickets"] = {}
    for f in sorted((base / "projects").glob("*/tickets/*.yaml")):
        obj = _yaml(f) or {}
        rel = f.relative_to(racine_factory).as_posix()
        ident = obj.get("id")
        if ident != f.stem:
            reg.erreurs.append(Erreur(rel, f"id {ident!r} ≠ nom de fichier {f.stem!r}"))
        if ident in reg.objets["tickets"]:
            reg.erreurs.append(Erreur(rel, f"id en double : {ident}"))
        if obj.get("project_id") != f.parent.parent.name:
            reg.erreurs.append(Erreur(rel, f"project_id {obj.get('project_id')!r} ≠ dossier {f.parent.parent.name!r}"))
        reg.objets["tickets"][ident] = obj
        bruts.append(("tickets", "ticket", f, obj))

    # Passe 2 : validation, références comprises.
    reg.validateur = Validateur(enums=enums, cycles=cycles, schemas=schemas,
                                index={t: set(o) for t, o in reg.objets.items()},
                                version_factory=str((factory.get("factory") or {}).get("standard_version", "")) or None)
    for dossier, nom_schema, f, obj in bruts:
        _consigner(reg, reg.validateur.valider(nom_schema, obj, f.relative_to(racine_factory).as_posix()))
    for carte, c in cartes:
        _carte_projet(reg, racine_factory, carte, c)
    _reciprocite(reg)
    _cycles_coherents(reg)
    return reg


def _consigner(reg: Registre, v: Verdict):
    reg.verdicts.append(v)
    reg.attentes.extend(f"{v.source} : {a}" for a in v.attentes)
    if v.statut != VALID:
        for d in v.defauts:
            reg.erreurs.append(Erreur(v.source, f"{v.statut} {d.code} {d.chemin} : {d.message}"))


def _carte_projet(reg: Registre, racine_factory: Path, carte: Path, c: dict):
    rel = carte.relative_to(racine_factory).as_posix()
    for champ in ("schema_version", "id", "name", "lifecycle", "root", "manifest"):
        if champ not in c:
            reg.erreurs.append(Erreur(rel, f"champ requis absent : {champ}"))
    if c.get("id") != carte.parent.name:
        reg.erreurs.append(Erreur(rel, "id ≠ nom du répertoire"))
    etat = (c.get("lifecycle") or {}).get("state")
    if etat not in reg.cycles["project"]["states"]:
        reg.erreurs.append(Erreur(rel, f"lifecycle.state {etat!r} hors du cycle « project »"))
    brouillon = (c.get("manifest") or {}).get("draft")
    if brouillon:
        _consigner(reg, valider_manifest(reg, _yaml(racine_factory / brouillon) or {}, brouillon))


def valider_manifest(reg: Registre, document: dict, source: str) -> Verdict:
    """Un manifest porte `schema_version` au niveau du document et son contenu dans `project` (§3, §29)."""
    contenu = dict(document.get("project") or {}, schema_version=document.get("schema_version"))
    return reg.validateur.valider("project", contenu, source)


def _reciprocite(reg: Registre):
    """Une capacité ne désigne que des outils qui la déclarent (sinon le registre se contredit)."""
    for ident, c in reg.objets["capabilities"].items():
        for t in c.get("implementations", []):
            outil = reg.objets["tools"].get(t)
            if outil is not None and ident not in outil.get("capabilities", []):
                reg.erreurs.append(Erreur(f"registry/capabilities/{ident}.yaml",
                                          f"l'outil {t} ne déclare pas la capacité {ident}"))


def _cycles_coherents(reg: Registre):
    for nom, cyc in reg.cycles.items():
        if not isinstance(cyc, dict) or "states" not in cyc:
            continue
        etats = set(cyc["states"])
        if cyc["initial"] not in etats:
            reg.erreurs.append(Erreur("core/schemas/lifecycles.yaml", f"{nom} : état initial inconnu"))
        for t in cyc.get("transitions", []):
            if t["from"] not in etats or t["to"] not in etats:
                reg.erreurs.append(Erreur("core/schemas/lifecycles.yaml", f"{nom} : transition {t} hors des états"))
        for e in cyc.get("terminal", []) + cyc.get("any_to", []):
            if e not in etats:
                reg.erreurs.append(Erreur("core/schemas/lifecycles.yaml", f"{nom} : état {e} inconnu"))


def transition_valide(reg: Registre, cycle: str, depart: str, arrivee: str) -> bool:
    cyc = reg.cycles[cycle]
    if arrivee in cyc.get("any_to", []):
        return True
    return any(t["from"] == depart and t["to"] == arrivee for t in cyc.get("transitions", []))
