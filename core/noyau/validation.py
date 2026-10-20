"""Moteur de validation des objets de la Factory (Executable Schemas §30).

Ordre des contrôles : version → identité → champs requis → énumérations (dont la criticité) → références →
politiques obligatoires → secrets → limites → versions de Factory. Les règles viennent des schémas
(`core/schemas/objects/*.schema.yaml`) : ce module ne connaît aucun type d'objet ni aucun outil.

Verdicts :
  VALID     l'objet respecte le contrat ;
  INVALID   l'objet est incomplet ou mal référencé (champ absent, identité vide, référence inconnue) ;
  REJECTED  l'objet contredit le contrat : version incompatible, valeur hors énumération, affaiblissement d'une
            politique obligatoire, secret en clair, limite dépassée.
INVALID et REJECTED valent VALIDATION_FAILED : aucun objet non VALID n'entre dans un état exécutable.
Une valeur `WAITING_HUMAN` n'invalide pas l'objet : elle est relevée comme décision humaine attendue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .masquage import contient_secret

VALID, INVALID, REJECTED = "VALID", "INVALID", "REJECTED"
EN_ATTENTE = "WAITING_HUMAN"

# Gravité de chaque code : il fixe le verdict.
_REJET = {"VERSION_INCOMPATIBLE", "ENUM_VALUE", "POLICY_WEAKENING", "SECRET_IN_CLEAR", "LIMIT_EXCEEDED",
          "FACTORY_VERSION_INCOMPATIBLE", "SCHEMA_UNKNOWN", "PATH_ESCAPE", "ACTIVE_WITHOUT_APPROVAL"}


@dataclass
class Defaut:
    code: str
    chemin: str
    message: str

    @property
    def verdict(self) -> str:
        return REJECTED if self.code in _REJET else INVALID


@dataclass
class Verdict:
    objet: str
    source: str
    statut: str = VALID
    defauts: list[Defaut] = field(default_factory=list)
    attentes: list[str] = field(default_factory=list)
    remarques: list[str] = field(default_factory=list)      # sans effet sur le verdict (ex. synonyme accepté)

    @property
    def executable(self) -> bool:
        return self.statut == VALID

    def ajouter(self, code: str, chemin: str, message: str):
        d = Defaut(code, chemin, message)
        self.defauts.append(d)
        if d.verdict == REJECTED:
            self.statut = REJECTED
        elif self.statut == VALID:
            self.statut = INVALID


def version(texte) -> tuple[int, ...] | None:
    try:
        return tuple(int(x) for x in str(texte).split("."))
    except (TypeError, ValueError):
        return None


def version_compatible(demandee, supportee) -> bool:
    """Même majeure, et pas plus récente que la version supportée (Executable Schemas §29)."""
    d, s = version(demandee), version(supportee)
    return bool(d and s and d[0] == s[0] and d <= s)


def chemin_relatif_sur(val) -> bool:
    """Chemin relatif qui ne peut pas sortir de sa racine (ni absolu, ni lecteur, ni UNC, ni « .. »)."""
    if not isinstance(val, str) or not val.strip():
        return False
    p = val.replace("\\", "/")
    if p.startswith("/") or p.startswith("~") or re.match(r"^[A-Za-z]:", p) or "%" in p or "$" in p:
        return False
    return ".." not in p.split("/")


def valeurs(obj, chemin: str) -> list:
    """Valeurs d'un chemin pointé ; « [] » parcourt une liste (ex. environments[].type)."""
    courants = [obj]
    for morceau in chemin.split("."):
        liste = morceau.endswith("[]")
        cle = morceau[:-2] if liste else morceau
        suivants = []
        for c in courants:
            if isinstance(c, dict) and cle in c:
                v = c[cle]
                if liste and isinstance(v, list):
                    suivants.extend(v)
                elif not liste:
                    suivants.append(v)
        courants = suivants
    return courants


def _chaines(obj, prefixe=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _chaines(v, f"{prefixe}.{k}" if prefixe else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _chaines(v, f"{prefixe}[{i}]")
    elif isinstance(obj, str):
        yield prefixe, obj


@dataclass
class Validateur:
    enums: dict
    cycles: dict
    schemas: dict
    index: dict[str, set] = field(default_factory=dict)   # type de registre → identifiants connus
    version_factory: str | None = None                     # version du standard (pour les manifests)

    def valider(self, nom_schema: str, obj, source: str = "") -> Verdict:
        v = Verdict(objet=nom_schema, source=source)
        schema = self.schemas.get(nom_schema)
        if schema is None:
            v.ajouter("SCHEMA_UNKNOWN", "", f"schéma inconnu : {nom_schema}")
            return v
        if not isinstance(obj, dict):
            v.ajouter("REQUIRED_MISSING", "", "objet absent ou non structuré")
            return v
        # 1. VERSION_COMPATIBILITY — un objet d'une version inconnue n'est pas lu plus avant.
        if not version_compatible(obj.get("schema_version"), schema["schema_version"]):
            v.ajouter("VERSION_INCOMPATIBLE", "schema_version",
                      f"{obj.get('schema_version')!r} incompatible avec {schema['schema_version']}")
            return v
        # 2. IDENTITY
        ident_champ = "id" if "id" in schema.get("required", []) else None
        if ident_champ and (not isinstance(obj.get("id"), str) or not obj.get("id").strip()):
            v.ajouter("IDENTITY_MISSING", "id", "identifiant absent ou vide")
        # 3. Champs requis
        for champ in schema.get("required", []):
            if champ != ident_champ and champ not in obj:
                v.ajouter("REQUIRED_MISSING", champ, "champ requis absent")
        # 4. ENUMS (dont CRITICALITY, DATA_CLASSIFICATION, ENVIRONMENT)
        for chemin, ref in (schema.get("enums") or {}).items():
            cycle = self.cycles.get(ref.split(":", 1)[1], {}) if ref.startswith("lifecycle:") else {}
            admis = cycle.get("states", []) if cycle else self.enums.get(ref, [])
            synonymes = cycle.get("aliases", {}) if cycle else {}
            for val in valeurs(obj, chemin):
                if val == EN_ATTENTE:
                    v.attentes.append(chemin)
                elif val in synonymes:
                    v.remarques.append(f"{chemin} : synonyme {val} lu comme {synonymes[val]}")
                elif val not in admis:
                    v.ajouter("ENUM_VALUE", chemin, f"{val!r} hors de {ref}")
        # 5. REFERENCES
        for chemin, type_ in (schema.get("references") or {}).items():
            connus = self.index.get(type_)
            if connus is None:
                continue                                   # pas d'index : contrôle impossible, pas d'invention
            for val in valeurs(obj, chemin):
                if val != EN_ATTENTE and val not in connus:
                    v.ajouter("REFERENCE_UNKNOWN", chemin, f"{val!r} absent du registre « {type_} »")
        # 6. PERMISSIONS / SECURITY — une valeur obligatoire ne s'affaiblit pas sans exception approuvée.
        for chemin, attendu in (schema.get("mandatory") or {}).items():
            for val in valeurs(obj, chemin):
                if val != attendu:
                    v.ajouter("POLICY_WEAKENING", chemin,
                              f"{val!r} au lieu de {attendu!r} : exige une exception approuvée (Executable Schemas §25)")
        # 7. SECRETS — aucun secret ni identifiant en clair, où que ce soit.
        for chemin, texte in _chaines(obj):
            if contient_secret(texte):
                v.ajouter("SECRET_IN_CLEAR", chemin, "secret ou identifiant en clair")
            elif texte == EN_ATTENTE and chemin not in v.attentes:
                v.attentes.append(chemin)
        # 7 bis. SCOPE — un chemin déclaré reste relatif à la racine : ni absolu, ni remontée par « .. ».
        for chemin in schema.get("relative_paths") or []:
            for val in valeurs(obj, chemin):
                if not chemin_relatif_sur(val):
                    v.ajouter("PATH_ESCAPE", chemin, f"{val!r} sort de la racine du projet")
        # 7 ter. APPROVALS — un état « approuvé / actif » sans approbation enregistrée est rejeté (Master §56).
        regle = schema.get("active_requires_approval")
        if regle and obj.get("lifecycle") in regle["states"]:
            vals = valeurs(obj, regle["field"])
            ok = (any(v == regle["equals"] for v in vals) if "equals" in regle
                  else any(v not in (None, "", [], {}) for v in vals))
            if not ok:
                v.ajouter("ACTIVE_WITHOUT_APPROVAL", regle["field"],
                          f"état {obj.get('lifecycle')} sans approbation ({regle['field']})")
        # 8. BUDGET et limites
        for chemin, borne in (schema.get("limits") or {}).items():
            for val in valeurs(obj, chemin):
                if isinstance(val, (int, float)) and "max" in borne and val > borne["max"]:
                    v.ajouter("LIMIT_EXCEEDED", chemin, f"{val} > {borne['max']}")
        # 9. Version de la Factory exigée par l'objet.
        if self.version_factory:
            for chemin, regle in (schema.get("version_fields") or {}).items():
                for val in valeurs(obj, chemin):
                    d, f = version(val), version(self.version_factory)
                    ok = bool(d and f) and (d[0] == f[0] if regle == "same_major" else d <= f)
                    if not ok:
                        v.ajouter("FACTORY_VERSION_INCOMPATIBLE", chemin,
                                  f"{val!r} incompatible avec la Factory {self.version_factory}")
        return v
