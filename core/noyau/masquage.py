"""Masquage des secrets dans toute sortie (Executable Schemas §7 règle 3, §34).

Le masquage est une défense en profondeur : le Bootstrap n'ouvre pas les fichiers sensibles et ne recopie
jamais une valeur de configuration secrète. Tout texte sortant passe malgré tout par ici.
"""
from __future__ import annotations

import re

_MOTIFS = [
    # schéma://utilisateur:motdepasse@hôte
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@/]+@"), r"\1***@"),
    # clé=valeur ou clé: valeur pour les noms évocateurs
    (re.compile(r"(?i)\b((?:pg)?pass(?:word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key"
                r"|jwt[_-]?secret|client[_-]?secret)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"), r"\1\2***"),
    # en-tête d'autorisation
    (re.compile(r"(?i)\b(authorization\s*:\s*(?:bearer|basic)\s+)\S+"), r"\1***"),
    # clés privées
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "***CLÉ PRIVÉE***"),
]

_NOMS_SECRETS = re.compile(r"(?i)(pass|pwd|secret|token|api[_-]?key|credential|private[_-]?key|auth)")


def masquer(texte: str | None) -> str | None:
    if texte is None:
        return None
    for motif, remplacement in _MOTIFS:
        texte = motif.sub(remplacement, texte)
    return texte


def nom_evoque_secret(nom: str) -> bool:
    """Vrai si un nom de clé ou de variable évoque un secret : sa valeur ne doit jamais être lue."""
    return bool(_NOMS_SECRETS.search(nom))


def contient_secret(texte: str) -> bool:
    """Vrai si le masquage changerait le texte : une valeur secrète y figure en clair."""
    return masquer(texte) != texte
