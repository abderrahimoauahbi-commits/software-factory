"""Environment Manager (Master Evolution Prompt v4 §11, §12, §40).

    Exécution → environnement jetable → ressources (base, processus…) → [migrations, seeds, tests] → destruction

Le gestionnaire ne crée que des environnements de profil **jetable** (autonomy : profiles.*.disposable) ; un
environnement durable (DEV partagé, STAGING, PRODUCTION) se déclare, il ne se fabrique pas ici. Chaque
environnement vit dans son répertoire sous la racine des environnements, marqué d'un fichier d'identité ; la
destruction n'efface que ce que la Factory a créé et dont l'identité se vérifie. Le fournisseur d'une ressource
(adaptateur hors du cœur) fait le travail propre à l'outil.

Chaque changement d'état suit le cycle « environment » et s'inscrit au journal quand il est fourni.

Quotas (Resource Broker, étape G1) : la création est refusée au-delà du nombre d'environnements vivants ou de
l'espace disque occupé sous la racine ; l'occupation de chaque environnement se mesure à la demande et un
dépassement est constaté, pas empêché (aucun quota du système de fichiers). Sans quotas fournis : aucun plafond.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .ressources import FACTORY, Registre, Ressource

MARQUEUR = ".factory-environment"
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")


class RefusEnvironnement(Exception):
    """Opération refusée : rien n'a été créé ni détruit."""


@dataclass
class Environnement:
    id: str
    project_id: str
    execution_id: str
    profile: str
    state: str = "REQUESTED"
    root: str = ""
    resources: list[str] = field(default_factory=list)
    created_at: str = ""
    expires_at: str | None = None
    history: list[dict] = field(default_factory=list)


def _maintenant() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


class Gestionnaire:
    def __init__(self, racine: Path, profils: dict, cycle: dict, ressources: Registre, fournisseurs: dict,
                 journal=None, quotas: dict | None = None):
        self.racine = Path(racine)
        self.quotas = quotas or {}                  # orchestrator/environnements.yaml : quotas
        self.profils = profils                      # autonomy : profiles
        self.cycle = cycle                          # lifecycles.yaml : environment
        self.ressources = ressources
        self.fournisseurs = fournisseurs            # genre de ressource → fournisseur
        self.journal = journal

    # ------------------------------------------------------------------ état
    def _fiche(self, ident: str) -> Path:
        return self.racine / ident / "environment.json"

    def obtenir(self, ident: str) -> Environnement | None:
        p = self._fiche(ident) if _ID.match(ident or "") else None
        return Environnement(**json.loads(p.read_text(encoding="utf-8"))) if p and p.is_file() else None

    def _sauver(self, e: Environnement):
        self._fiche(e.id).write_text(json.dumps(asdict(e), ensure_ascii=False, indent=1), encoding="utf-8")

    def _passer(self, e: Environnement, vers: str, motif: str = ""):
        ok = vers in self.cycle.get("any_to", []) or any(t["from"] == e.state and t["to"] == vers
                                                          for t in self.cycle["transitions"])
        if not ok or e.state in self.cycle.get("terminal", []):
            raise RefusEnvironnement(f"{e.id} : transition {e.state} → {vers} absente du cycle environment")
        depart, e.state = e.state, vers
        e.history.append({"from": depart, "to": vers, "at": _maintenant().isoformat(timespec="seconds"),
                          "reason": motif})
        if self.journal is not None:
            self.journal.ajouter(actor={"type": "system", "id": "environment-manager"}, project_id=e.project_id,
                                 execution_id=e.execution_id, environment_id=e.id, action="transition environment",
                                 from_state=depart, to_state=vers, result=vers, reasons=[motif] if motif else [])
        if Path(e.root).is_dir():
            self._sauver(e)

    # ------------------------------------------------------------------ création
    def creer(self, ident: str, projet: str, execution: str, profil: str, specs: list[dict]) -> Environnement:
        if not _ID.match(ident or ""):
            raise RefusEnvironnement(f"identifiant d'environnement invalide : {ident!r}")
        p = self.profils.get(profil)
        if p is None:
            raise RefusEnvironnement(f"profil inconnu : {profil!r}")
        if not p.get("disposable"):
            raise RefusEnvironnement(f"le profil {profil} n'est pas jetable : il se déclare, il ne se crée pas")
        dossier = self.racine / ident
        if dossier.exists():
            raise RefusEnvironnement(f"l'environnement {ident} existe déjà")
        self._quotas_de_creation()
        heures = p.get("retention_hours")
        e = Environnement(ident, projet, execution, profil, root=str(dossier),
                          created_at=_maintenant().isoformat(timespec="seconds"),
                          expires_at=(_maintenant() + _dt.timedelta(hours=heures)).isoformat(timespec="seconds")
                          if heures else None)
        dossier.mkdir(parents=True)
        (dossier / MARQUEUR).write_text(json.dumps({"environment_id": ident, "project_id": projet,
                                                    "execution_id": execution}), encoding="utf-8")
        self._sauver(e)
        self._passer(e, "PROVISIONING")
        try:
            for i, spec in enumerate(specs):
                f = self.fournisseurs.get(spec.get("kind"))
                if f is None:
                    raise RefusEnvironnement(f"aucun fournisseur pour {spec.get('kind')!r}")
                brut = f.creer(dossier, spec, e)
                r = Ressource(id=f"{ident}-{spec.get('name') or spec['kind']}-{i + 1}", kind=spec["kind"],
                              project_id=projet, environment_id=ident, profile=profil, owner=FACTORY,
                              disposable=True, classification=spec.get("classification", "INTERNAL"),
                              criticality=p.get("criticality", "C1"),
                              allowed_operations=list(spec.get("allowed_operations") or []),
                              provider=getattr(f, "id", spec["kind"]), connection=brut["connection"],
                              identity=brut["identity"])
                self.ressources.enregistrer(r)
                e.resources.append(r.id)
                self._sauver(e)
        except Exception as ex:
            self._passer(e, "FAILED", f"création : {ex}")
            raise
        self._passer(e, "READY", f"{len(e.resources)} ressource(s)")
        return e

    # ------------------------------------------------------------------ quotas
    def vivants(self) -> list[Environnement]:
        out = []
        for p in sorted(self.racine.glob("*/environment.json")) if self.racine.is_dir() else []:
            e = self.obtenir(p.parent.name)
            if e is not None and e.state not in self.cycle.get("terminal", []):
                out.append(e)
        return out

    def occupation_mo(self, env_id: str | None = None) -> float:
        """Espace occupé (Mo) par un environnement, ou par toute la racine (archives comprises)."""
        base = (self.racine / env_id) if env_id else self.racine
        total = 0
        for dossier, _, fichiers in os.walk(base):
            for f in fichiers:
                try:
                    total += os.lstat(os.path.join(dossier, f)).st_size
                except OSError:
                    continue
        return total / (1024 * 1024)

    def _quotas_de_creation(self):
        maxi = self.quotas.get("max_active_environments")
        if maxi is not None and len(self.vivants()) >= int(maxi):
            raise RefusEnvironnement(f"quota atteint : {maxi} environnement(s) vivant(s) au plus")
        total = self.quotas.get("max_disk_mb_total")
        if total is not None and self.occupation_mo() >= float(total):
            raise RefusEnvironnement(f"quota disque atteint : {self.occupation_mo():.0f} Mo occupés, {total} Mo au plus")

    def depassements(self) -> list[str]:
        """Constat (détectif) des dépassements de quota disque des environnements vivants et de la racine."""
        out = []
        par_env = self.quotas.get("max_disk_mb_per_environment")
        if par_env is not None:
            for e in self.vivants():
                mo = self.occupation_mo(e.id)
                if mo > float(par_env):
                    out.append(f"{e.id} : {mo:.0f} Mo > {par_env} Mo")
        total = self.quotas.get("max_disk_mb_total")
        if total is not None and self.occupation_mo() > float(total):
            out.append(f"racine des environnements : {self.occupation_mo():.0f} Mo > {total} Mo")
        return out

    # ------------------------------------------------------------------ usage
    def ressource(self, env_id: str, genre: str) -> Ressource:
        e = self._exiger(env_id)
        for rid in e.resources:
            r = self.ressources.obtenir(rid)
            if r and r.kind == genre and r.state == "ACTIVE":
                return r
        raise RefusEnvironnement(f"{env_id} : aucune ressource {genre}")

    def variables(self, env_id: str) -> dict:
        """Variables de connexion à transmettre aux commandes de l'environnement (jamais de secret)."""
        out = {}
        for rid in self._exiger(env_id).resources:
            r = self.ressources.obtenir(rid)
            f = self.fournisseurs.get(r.kind) if r else None
            if f is not None and hasattr(f, "variables"):
                out.update(f.variables(r))
        return out

    def _exiger(self, env_id: str) -> Environnement:
        e = self.obtenir(env_id)
        if e is None:
            raise RefusEnvironnement(f"environnement inconnu : {env_id!r}")
        return e

    def _verifiee(self, rid: str) -> Ressource:
        ok, motif = self.ressources.verifier_identite(rid)
        if not ok:
            raise RefusEnvironnement(f"{rid} : {motif}")
        return self.ressources.obtenir(rid)

    def reinitialiser(self, env_id: str, genre: str | None = None) -> Environnement:
        """Reset d'une ressource jetable (base vidée et recréée) : identité vérifiée d'abord."""
        e = self._exiger(env_id)
        if e.state != "READY":
            raise RefusEnvironnement(f"{env_id} n'est pas prêt ({e.state})")
        self._passer(e, "RESETTING", f"reset {genre or 'toutes ressources'}")
        try:
            for rid in e.resources:
                r = self._verifiee(rid)
                if genre is None or r.kind == genre:
                    self.fournisseurs[r.kind].reinitialiser(r)
        except Exception as ex:
            self._passer(e, "FAILED", f"reset : {ex}")
            raise
        self._passer(e, "READY", "reset terminé")
        return e

    # ------------------------------------------------------------------ destruction
    def detruire(self, env_id: str, motif: str = "fin d'exécution", garder: tuple[str, ...] = ("*.log",)) -> dict:
        """Détruit ressources et répertoire ; conserve les journaux demandés (preuves) dans `<racine>/_archives`."""
        e = self._exiger(env_id)
        dossier = Path(e.root)
        try:
            dossier.resolve().relative_to(self.racine.resolve())
        except ValueError:
            raise RefusEnvironnement("répertoire hors de la racine des environnements : refus")
        marque = json.loads((dossier / MARQUEUR).read_text(encoding="utf-8")) if (dossier / MARQUEUR).is_file() else {}
        if marque.get("environment_id") != e.id:
            raise RefusEnvironnement("marqueur d'identité absent ou différent : la Factory ne détruit que ce qu'elle a créé")
        self._passer(e, "DESTROYING", motif)
        refus = []
        for rid in e.resources:
            ok, raison = self.ressources.verifier_identite(rid)
            r = self.ressources.obtenir(rid)
            if r is None:
                continue
            if not ok and "injoignable" not in raison:
                refus.append(f"{rid} : {raison}")          # une autre ressource répond à cette adresse : on n'y touche pas
                continue
            try:
                self.fournisseurs[r.kind].detruire(r)
            except Exception as ex:
                refus.append(f"{rid} : arrêt impossible ({ex})")
                continue
            self.ressources.marquer(rid, "DESTROYED")
        if refus:
            self._passer(e, "FAILED", "destruction partielle : " + " ; ".join(refus))
            return {"environment": e.id, "destroyed": False, "refused": refus}
        archives = self.racine / "_archives" / e.id
        archives.mkdir(parents=True, exist_ok=True)
        for motif_fichier in garder:
            for f in dossier.rglob(motif_fichier):
                if f.is_file():
                    shutil.copy2(f, archives / f.name)
        self._passer(e, "DESTROYED", motif)
        (archives / "environment.json").write_text(json.dumps(asdict(e), ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.rmtree(dossier, onexc=_forcer)
        return {"environment": e.id, "destroyed": True, "archive": str(archives)}

    def expires(self) -> list[str]:
        maintenant = _maintenant()
        out = []
        for p in sorted(self.racine.glob("*/environment.json")):
            e = Environnement(**json.loads(p.read_text(encoding="utf-8")))
            if e.expires_at and e.state not in ("DESTROYED",) and _dt.datetime.fromisoformat(e.expires_at) < maintenant:
                out.append(e.id)
        return out


def _forcer(fonction, chemin, _info):
    """Fichiers en lecture seule (répertoires de données) : on lève la protection, dans l'environnement seulement."""
    os.chmod(chemin, 0o700)
    fonction(chemin)
