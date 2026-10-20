"""Sauvegarde, vérification et restauration d'essai d'une arborescence (décision D2).

Générique : ne connaît ni la Factory ni un projet ; la politique (portées exigées, exclusions, destination) et la
revalidation après restauration sont fournies par l'appelant. Aucune opération destructive : une archive n'est
jamais écrasée, une restauration se fait toujours dans un répertoire neuf.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

MANIFESTE = "BACKUP-MANIFEST.json"


class SauvegardeRefusee(Exception):
    """La sauvegarde n'a pas été faite : rien n'a été écrit."""


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def repertoire_exclu(rel_dir: str, motifs: list[str]) -> bool:
    """Motifs de répertoire : « x/ » (depuis la racine) ou « **/x/ » (à toute profondeur)."""
    parties = rel_dir.split("/")
    for m in motifs:
        if not m.endswith("/"):
            continue
        base = m[:-1]
        if base.startswith("**/"):
            if base[3:] in parties:
                return True
        elif rel_dir == base or rel_dir.startswith(base + "/"):
            return True
    return False


def fichier_exclu(rel: str, motifs: list[str]) -> bool:
    if "/" in rel and repertoire_exclu(rel.rsplit("/", 1)[0], motifs):
        return True
    nom = PurePosixPath(rel).name
    return any(fnmatch.fnmatch(nom, m) or fnmatch.fnmatch(rel, m) for m in motifs if not m.endswith("/"))


def inventaire(racine: Path, exclusions: list[str]) -> list[dict]:
    fichiers = []
    for dossier, sous, noms in os.walk(racine):
        rel_dossier = Path(dossier).relative_to(racine).as_posix()
        prefixe = "" if rel_dossier == "." else rel_dossier + "/"
        sous[:] = sorted(s for s in sous if not repertoire_exclu(prefixe + s, exclusions))
        for n in sorted(noms):
            rel = prefixe + n
            if fichier_exclu(rel, exclusions):
                continue
            p = Path(dossier) / n
            if p.is_symlink():
                continue                                  # un lien n'est jamais suivi hors de la racine
            fichiers.append({"path": rel, "size": p.stat().st_size, "sha256": sha256_fichier(p)})
    return fichiers


@dataclass
class Rapport:
    operation: str
    statut: str = "OK"                                    # OK | FAIL
    archive: str | None = None
    details: list[str] = field(default_factory=list)
    mesures: dict = field(default_factory=dict)

    def echec(self, message: str):
        self.statut = "FAIL"
        self.details.append(message)

    def en_dict(self) -> dict:
        return self.__dict__


def _dedans(enfant: Path, parent: Path) -> bool:
    try:
        enfant.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def sauvegarder(racine: Path, destination: Path, portees: list[str], exclusions: list[str], meta: dict) -> Rapport:
    r = Rapport("backup")
    racine, destination = racine.resolve(), Path(destination)
    if _dedans(destination, racine) or _dedans(racine, destination):
        raise SauvegardeRefusee("la destination ne doit être ni dans la source ni la contenir")
    manquantes = [p for p in portees if not (racine / p).exists()]
    if manquantes:
        raise SauvegardeRefusee("portées exigées absentes : " + ", ".join(manquantes))
    debut = time.monotonic()
    fichiers = inventaire(racine, exclusions)
    couvertes = {p: sum(1 for f in fichiers if f["path"] == p or f["path"].startswith(p.rstrip("/") + "/"))
                 for p in portees}
    vides = [p for p, n in couvertes.items() if n == 0]
    if vides:
        raise SauvegardeRefusee("portées exigées sans aucun fichier sauvegardé : " + ", ".join(vides))
    horodatage = time.strftime("%Y%m%dT%H%M%S")
    empreinte = hashlib.sha256(json.dumps(fichiers, sort_keys=True).encode()).hexdigest()
    manifeste = {"format": 1, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "source": str(racine),
                 "meta": meta, "required_scopes": portees, "scope_file_counts": couvertes,
                 "excluded": exclusions, "files": fichiers, "content_sha256": empreinte}
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"factory-backup-{horodatage}-{empreinte[:12]}.zip"
    # « x » : création exclusive — une archive existante n'est jamais écrasée.
    with open(archive, "xb") as brut, zipfile.ZipFile(brut, "w", zipfile.ZIP_DEFLATED) as z:
        for f in fichiers:
            z.write(racine / f["path"], f["path"])
        z.writestr(MANIFESTE, json.dumps(manifeste, ensure_ascii=False, indent=1))
    compagnon = archive.with_name(archive.name + ".sha256")
    with open(compagnon, "x", encoding="ascii") as h:
        h.write(f"{sha256_fichier(archive)}  {archive.name}\n")
    r.archive = str(archive)
    r.mesures = {"files": len(fichiers), "bytes": archive.stat().st_size, "seconds": round(time.monotonic() - debut, 2),
                 "content_sha256": empreinte, "scope_file_counts": couvertes}
    return r


def verifier(archive: Path) -> Rapport:
    r = Rapport("verify", archive=str(archive))
    compagnon = Path(str(archive) + ".sha256")
    if not compagnon.is_file():
        r.echec("fichier d'empreinte compagnon absent")
    else:
        attendu = compagnon.read_text(encoding="ascii").split()[0]
        if attendu != sha256_fichier(archive):
            r.echec("empreinte de l'archive différente du fichier compagnon")
    try:
        with zipfile.ZipFile(archive) as z:
            manifeste = json.loads(z.read(MANIFESTE))
            noms = set(z.namelist()) - {MANIFESTE}
            declares = {f["path"]: f for f in manifeste["files"]}
            for nom in sorted(noms - set(declares)):
                r.echec(f"fichier non déclaré dans le manifeste : {nom}")
            for chemin, f in declares.items():
                if chemin not in noms:
                    r.echec(f"fichier manquant : {chemin}")
                    continue
                donnees = z.read(chemin)
                if len(donnees) != f["size"] or hashlib.sha256(donnees).hexdigest() != f["sha256"]:
                    r.echec(f"contenu altéré : {chemin}")
            r.mesures = {"files": len(declares), "required_scopes": manifeste.get("required_scopes")}
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        r.echec(f"archive illisible : {type(e).__name__}")
    return r


def exercice_reprise(archive: Path, commandes: list[list[str]], revalider=None, delai: int = 900) -> Rapport:
    """Exercice de reprise : restaurer dans un répertoire neuf, puis y FAIRE TOURNER la Factory.

    `commandes` : argv exécutés sans shell dans la copie restaurée ({racine} = son chemin). Toutes doivent
    réussir. La durée totale mesure le RTO réel.
    """
    import subprocess

    r = verifier(archive)
    r.operation = "drill"
    if r.statut != "OK":
        return r
    debut = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="factory-drill-") as tmp:
        cible = Path(tmp).resolve()
        with zipfile.ZipFile(archive) as z:
            for nom in z.namelist():
                if not _dedans((cible / nom).resolve(), cible) or ".." in PurePosixPath(nom).parts:
                    r.echec(f"chemin d'archive refusé : {nom}")
                    return r
            z.extractall(cible)
        if revalider is not None:
            for message in revalider(cible) or []:
                r.echec(message)
        etapes = []
        for argv in commandes:
            argv = [a.replace("{racine}", str(cible)) for a in argv]
            t0 = time.monotonic()
            res = subprocess.run(argv, cwd=cible, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=delai, stdin=subprocess.DEVNULL)
            etapes.append({"commande": " ".join(argv[1:] if len(argv) > 1 else argv), "code": res.returncode,
                           "secondes": round(time.monotonic() - t0, 1),
                           "fin": "\n".join((res.stdout or "").strip().splitlines()[-2:])})
            if res.returncode != 0:
                r.echec(f"commande en échec dans la copie restaurée : {etapes[-1]['commande']} (code {res.returncode})")
        r.mesures["etapes"] = etapes
        r.mesures["rto_seconds"] = round(time.monotonic() - debut, 1)
    return r


def tester_restauration(archive: Path, revalider=None) -> Rapport:
    """Restaure dans un répertoire temporaire neuf, vérifie chaque fichier, puis appelle `revalider(racine)`."""
    r = verifier(archive)
    r.operation = "restore-test"
    if r.statut != "OK":
        return r
    debut = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="factory-restore-") as tmp:
        cible = Path(tmp).resolve()
        with zipfile.ZipFile(archive) as z:
            for nom in z.namelist():
                destination = (cible / nom).resolve()
                if not _dedans(destination, cible) or PurePosixPath(nom).is_absolute() or ".." in PurePosixPath(nom).parts:
                    r.echec(f"chemin d'archive refusé (sortie du répertoire de restauration) : {nom}")
                    return r
            z.extractall(cible)
            manifeste = json.loads(z.read(MANIFESTE))
        for f in manifeste["files"]:
            if sha256_fichier(cible / f["path"]) != f["sha256"]:
                r.echec(f"fichier restauré différent : {f['path']}")
        if revalider is not None and r.statut == "OK":
            for message in revalider(cible) or []:
                r.echec(message)
        r.mesures["restore_seconds"] = round(time.monotonic() - debut, 2)
    return r
