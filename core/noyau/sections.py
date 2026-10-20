"""Résolution du contexte par sections (ADR-0022 v2, F-7 ; modèle canonique GMAO v1.0 § 2.6).

Une référence est :
- « chemin#ancre » : la section du document Markdown dont le titre a cet identifiant (titre normalisé : minuscules,
  sans accents ni ponctuation, espaces → tirets), jusqu'au titre suivant de même niveau ou plus haut ;
- « chemin#identifiant » (ex. « #rg-12 ») ou « RG-12 » seul : les lignes qui citent cet identifiant (ligne de tableau ou
  paragraphe), dans le document indiqué, ou dans la spécification déclarée par le manifest ;
- « chemin » seul : le document entier.

Lecture GOUVERNÉE (correction 2 du § 9) : seul un document dans les chemins lisibles du manifest, et non sensible, est
lu ; sa présence dans le dépôt ne vaut jamais autorisation. Rien n'est écrit.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .validation import chemin_relatif_sur

_TITRE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_IDENT = re.compile(r"^[A-Za-z]{1,6}-\d+[a-z]?$")


def ancre(titre: str) -> str:
    t = unicodedata.normalize("NFKD", titre)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9 -]", "", t)
    return re.sub(r"-{2,}", "-", re.sub(r"\s+", "-", t.strip())).strip("-")


def _section(lignes: list[str], cible: str) -> str | None:
    for i, l in enumerate(lignes):
        m = _TITRE.match(l)
        if m and ancre(m.group(2)) == cible:
            niveau, fin = len(m.group(1)), len(lignes)
            for j in range(i + 1, len(lignes)):
                n = _TITRE.match(lignes[j])
                if n and len(n.group(1)) <= niveau:
                    fin = j
                    break
            return "\n".join(lignes[i:fin]).strip()
    return None


def _citations(lignes: list[str], ident: str) -> str | None:
    motif = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(ident)}(?![0-9a-z])", re.IGNORECASE)
    blocs, i = [], 0
    while i < len(lignes):
        if motif.search(lignes[i]):
            if lignes[i].lstrip().startswith("|"):
                blocs.append(lignes[i].strip())
                i += 1
                continue
            debut, fin = i, i
            while debut > 0 and lignes[debut - 1].strip() and not _TITRE.match(lignes[debut - 1]):
                debut -= 1
            while fin + 1 < len(lignes) and lignes[fin + 1].strip() and not _TITRE.match(lignes[fin + 1]):
                fin += 1
            blocs.append("\n".join(lignes[debut:fin + 1]).strip())
            i = fin + 1
            continue
        i += 1
    return "\n\n".join(dict.fromkeys(blocs)) or None


@dataclass
class Section:
    reference: str
    chemin: str
    ancre: str | None
    texte: str
    sha256: str

    def en_dict(self) -> dict:
        return {"ref": self.reference, "path": self.chemin, "anchor": self.ancre, "sha256": self.sha256,
                "chars": len(self.texte)}


def resoudre(racine_projet: Path, ref: str, lisible, specification: str | None) -> tuple[Section | None, str | None]:
    """(section, None) ou (None, motif). `lisible(chemin)` : vrai si le chemin est dans les chemins lisibles du manifest
    et non sensible."""
    if not isinstance(ref, str) or not ref.strip():
        return None, f"référence de contexte vide ou illisible ({ref!r})"
    ref = ref.strip()
    chemin, _, cible = ref.partition("#")
    if not cible and _IDENT.match(chemin):
        if not specification:
            return None, f"{ref} : spécification non déclarée par le manifest (context.specification)"
        chemin, cible = specification, chemin
    if not chemin_relatif_sur(chemin):
        return None, f"{ref} : chemin hors de la racine du projet"
    if not lisible(chemin):
        return None, f"{ref} : document hors des chemins lisibles du manifest, ou sensible"
    fichier = Path(racine_projet) / chemin
    if not fichier.is_file():
        return None, f"{ref} : document introuvable"
    lignes = fichier.read_text(encoding="utf-8", errors="replace").splitlines()
    if not cible:
        texte = "\n".join(lignes).strip()
    else:
        texte = _section(lignes, ancre(cible)) if not _IDENT.match(cible) else None
        texte = texte or _citations(lignes, cible)
        if texte is None:
            return None, f"{ref} : section ou identifiant introuvable dans {chemin}"
    return Section(ref, chemin, cible or None, texte, hashlib.sha256(texte.encode("utf-8")).hexdigest()), None
