"""Registre des ressources (Master Evolution Prompt v4 §11, §37, §38).

Une ressource (base, répertoire, processus…) est connue par sa fiche : projet, environnement, profil,
propriétaire, caractère jetable, classification, criticité, opérations admises, connexion (sans secret) et
**empreinte d'identité relevée à sa création**. L'identité se vérifie à chaque usage en interrogeant la ressource
réelle par son fournisseur ; elle ne se déduit jamais d'un nom (« une base appelée test peut être réelle »).

Deux origines :
- `factory` : créée par l'Environment Manager, jetable, détruite avec son environnement ;
- `external` : déclarée par le manifest d'un projet (base locale réelle, production…), jamais jetable ici.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .masquage import contient_secret

FACTORY, EXTERNAL = "factory", "external"


class RefusRessource(Exception):
    """Fiche refusée ou ressource introuvable."""


@dataclass
class Ressource:
    id: str
    kind: str                                   # database | filesystem | process | network | container
    project_id: str
    environment_id: str
    profile: str                                # profil d'environnement (autonomy : profiles)
    owner: str                                  # factory | external
    disposable: bool
    classification: str = "INTERNAL"
    criticality: str = "C1"
    allowed_operations: list[str] = field(default_factory=list)
    provider: str | None = None                 # fournisseur qui sait l'interroger (adaptateur)
    connection: dict = field(default_factory=dict)
    identity: dict = field(default_factory=dict)
    state: str = "ACTIVE"
    created_at: str = ""


def _maintenant() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class Registre:
    def __init__(self, racine: Path, fournisseurs: dict | None = None, racine_environnements: Path | None = None):
        self.racine = Path(racine)
        self.fournisseurs = fournisseurs or {}
        self.racine_environnements = Path(racine_environnements) if racine_environnements else None

    def _fiche(self, ident: str) -> Path:
        if not ident or any(c in ident for c in "/\\:") or ident.startswith("."):
            raise RefusRessource(f"identifiant de ressource invalide : {ident!r}")
        return self.racine / f"{ident}.json"

    def enregistrer(self, r: Ressource) -> Ressource:
        if r.owner not in (FACTORY, EXTERNAL):
            raise RefusRessource(f"propriétaire inconnu : {r.owner!r}")
        if r.owner == EXTERNAL and r.disposable:
            raise RefusRessource("une ressource externe n'est jamais jetable pour la Factory")
        if r.disposable and not r.identity:
            raise RefusRessource("ressource jetable sans empreinte d'identité")
        if contient_secret(json.dumps(r.connection, ensure_ascii=False)):
            raise RefusRessource("secret dans la connexion d'une ressource")
        chemin = self._fiche(r.id)
        if chemin.exists():
            ancienne = json.loads(chemin.read_text(encoding="utf-8"))
            if ancienne.get("owner") != r.owner or ancienne.get("project_id") != r.project_id:
                raise RefusRessource(f"{r.id} existe déjà avec un autre propriétaire ou projet")
        r.created_at = r.created_at or _maintenant()
        self.racine.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(asdict(r), ensure_ascii=False, indent=1), encoding="utf-8")
        return r

    def obtenir(self, ident: str) -> Ressource | None:
        try:
            chemin = self._fiche(ident)
        except RefusRessource:
            return None
        if not chemin.is_file():
            return None
        return Ressource(**json.loads(chemin.read_text(encoding="utf-8")))

    def lister(self, projet: str | None = None, environnement: str | None = None) -> list[Ressource]:
        if not self.racine.is_dir():
            return []
        res = [Ressource(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(self.racine.glob("*.json"))]
        return [r for r in res if (projet is None or r.project_id == projet)
                and (environnement is None or r.environment_id == environnement)]

    def marquer(self, ident: str, etat: str):
        r = self.obtenir(ident)
        if r is None:
            raise RefusRessource(f"ressource inconnue : {ident}")
        r.state = etat
        self._fiche(ident).write_text(json.dumps(asdict(r), ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ identité (§38)
    def verifier_identite(self, ident: str) -> tuple[bool, str]:
        """La ressource interrogée maintenant est-elle celle que la Factory a créée ? Jamais par son nom."""
        r = self.obtenir(ident)
        if r is None:
            return False, f"ressource {ident!r} non enregistrée"
        if r.state != "ACTIVE":
            return False, f"ressource {ident!r} dans l'état {r.state}"
        if not r.identity:
            return False, "aucune empreinte d'identité relevée"
        if r.owner == FACTORY:
            dossier = r.identity.get("data_directory") or r.connection.get("data_dir")
            if self.racine_environnements is None or not dossier:
                return False, "ressource de la Factory sans répertoire vérifiable"
            try:
                Path(os.path.realpath(dossier)).relative_to(Path(os.path.realpath(self.racine_environnements)))
            except ValueError:
                return False, "répertoire de la ressource hors de la racine des environnements"
        f = self.fournisseurs.get(r.provider)
        if f is None:
            return False, f"fournisseur {r.provider!r} indisponible : identité invérifiable"
        try:
            observee = f.identite(r)
        except Exception as e:                          # injoignable = non vérifiée, jamais « supposée bonne »
            return False, f"ressource injoignable : {type(e).__name__}"
        ecarts = [k for k, v in r.identity.items() if str(observee.get(k)) != str(v)]
        if ecarts:
            return False, "identité différente de celle relevée à la création : " + ", ".join(sorted(ecarts))
        return True, "identité vérifiée"
