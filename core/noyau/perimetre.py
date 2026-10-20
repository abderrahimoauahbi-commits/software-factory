"""ROOT_SCOPE : résolution, validation et garde de toute lecture (politique root-scope).

Toute lecture du Bootstrap passe par `Perimetre.lire_texte` ou `Perimetre.lister` : un chemin hors des racines
validées, un fichier sensible ou un répertoire de données est refusé AVANT ouverture, et chaque lecture est
consignée (preuve d'exécution).
"""
from __future__ import annotations

import fnmatch
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


class AccesRefuse(Exception):
    """Lecture hors périmètre ou d'un fichier sensible : elle n'a pas eu lieu."""


def canonique(chemin: str | Path) -> Path:
    return Path(os.path.realpath(os.path.expandvars(os.path.expanduser(str(chemin)))))


def est_lien(chemin: Path) -> bool:
    """Lien symbolique ou jonction (point de réanalyse sous Windows)."""
    try:
        st = os.lstat(chemin)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


@dataclass
class Racine:
    nom: str
    chemin: Path
    sensibles: list[str] = field(default_factory=list)   # motifs relatifs propres à la racine (carte du projet)


@dataclass
class Perimetre:
    racines: dict[str, Racine]
    motifs_fichiers_sensibles: list[str]
    noms_repertoires_sensibles: list[str]
    jamais_parcourus: list[str]
    fichiers_hors_racines: list[Path]                    # approuvés un par un (APR-0001)
    lectures: list[str] = field(default_factory=list)
    refus: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ appartenance
    def racine_de(self, chemin: Path) -> Racine | None:
        c = canonique(chemin)
        for r in self.racines.values():
            try:
                c.relative_to(r.chemin)
                return r
            except ValueError:
                continue
        return None

    def dans_perimetre(self, chemin: Path) -> bool:
        return self.racine_de(chemin) is not None

    def est_sensible(self, chemin: Path) -> bool:
        c = canonique(chemin)
        nom = c.name.lower()
        if any(fnmatch.fnmatch(nom, m.lower()) for m in self.motifs_fichiers_sensibles):
            return True
        r = self.racine_de(c)
        if r is not None:
            relatif = PurePosixPath(c.relative_to(r.chemin).as_posix())
            parties = [p.lower() for p in relatif.parts]
            if any(p in (n.lower() for n in self.noms_repertoires_sensibles) for p in parties[:-1] + [nom]):
                return True
            for motif in r.sensibles:
                motif = motif.rstrip("/")
                if fnmatch.fnmatch(str(relatif), motif) or any(
                        fnmatch.fnmatch(str(PurePosixPath(*relatif.parts[:i])), motif)
                        for i in range(1, len(relatif.parts))):
                    return True
        return False

    # ------------------------------------------------------------------ lectures gardées
    def _verifier(self, chemin: Path, *, hors_racine_ok: bool = False) -> Path:
        c = canonique(chemin)
        if est_lien(Path(os.path.expandvars(os.path.expanduser(str(chemin))))):
            self.refus.append(f"{chemin} : lien ou jonction (EXTERNAL_TARGET_DETECTED)")
            raise AccesRefuse(f"lien ou jonction : {chemin}")
        if not self.dans_perimetre(c):
            if not (hors_racine_ok and c in self.fichiers_hors_racines):
                self.refus.append(f"{c} : hors ROOT_SCOPE (PATH_ACCESS_REQUIRED)")
                raise AccesRefuse(f"hors périmètre : {c}")
        elif self.est_sensible(c):
            self.refus.append(f"{c} : fichier ou répertoire sensible (DENY)")
            raise AccesRefuse(f"sensible : {c}")
        return c

    def lire_texte(self, chemin: str | Path, *, hors_racine_ok: bool = False, max_octets: int = 2_000_000) -> str:
        c = self._verifier(Path(chemin), hors_racine_ok=hors_racine_ok)
        with open(c, "rb") as f:
            donnees = f.read(max_octets)
        self.lectures.append(str(c))
        return donnees.decode("utf-8", errors="replace")

    def existe(self, chemin: str | Path, *, hors_racine_ok: bool = False) -> bool:
        """Existence seule (métadonnée) : permise aussi pour un fichier sensible, jamais son contenu."""
        c = canonique(chemin)
        if not self.dans_perimetre(c) and not (hors_racine_ok and c in self.fichiers_hors_racines):
            self.refus.append(f"{c} : existence hors ROOT_SCOPE non vérifiée")
            raise AccesRefuse(f"hors périmètre : {c}")
        return c.exists()

    def lister(self, repertoire: str | Path) -> list[str]:
        """Noms de premier niveau d'un répertoire du périmètre (pas de récursion, Progressive Disclosure)."""
        c = self._verifier(Path(repertoire))
        if c.name in self.jamais_parcourus:
            raise AccesRefuse(f"jamais parcouru : {c}")
        noms = sorted(os.listdir(c))
        self.lectures.append(f"{c}/ (liste)")
        return noms


def resoudre_racine(nom: str, chemin: str, marqueurs: list[dict], perimetre_lecture=None) -> tuple[Racine | None, list[str]]:
    """Valide une racine candidate : existence, type, lien, identité. Rend (racine, motifs de rejet)."""
    rejets: list[str] = []
    brut = Path(os.path.expandvars(os.path.expanduser(chemin)))
    if not brut.exists():
        return None, ["inexistant"]
    if not brut.is_dir():
        return None, ["pas un répertoire"]
    if est_lien(brut):
        return None, ["lien symbolique ou jonction (ROOT_EXTERNAL_TARGET)"]
    c = canonique(brut)
    for m in marqueurs:
        f = c / m["file"]
        if not f.is_file():
            rejets.append(f"marqueur absent : {m['file']}")
            continue
        motif = re.compile(m["pattern"], re.M)
        # Lecture minimale d'identité : seul le fichier marqueur, jamais un fichier sensible.
        with open(f, "rb") as h:
            if not motif.search(h.read(200_000).decode("utf-8", errors="replace")):
                rejets.append(f"identité non confirmée : {m['file']}")
        if perimetre_lecture is not None:
            perimetre_lecture.append(str(f))
    if rejets:
        return None, rejets
    return Racine(nom=nom, chemin=c), []
