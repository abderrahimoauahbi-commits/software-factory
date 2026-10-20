"""Connaissance et apprentissage entre projets (Master Evolution Prompt v4 §50, §55).

Classes de connaissance séparées ; hiérarchie NORM > POLICY > IMPLEMENTATION > TEST > PROOF pour trancher un
conflit (l'ordre des catégories d'architecture et de documentation suit celui du dépôt : knowledge/).

Transfert entre projets : seuls les motifs, anti-motifs, leçons, principes génériques d'architecture et règles
génériques de sécurité passent, et seulement s'ils ne contiennent ni secret, ni identifiant du projet d'origine
(nom, racine, hôtes, chemins), ni donnée métier marquée. Jamais : secrets, identifiants, source privée, données
métier, documents privés. Le transfert n'est pas automatique pour le reste : il est refusé.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .masquage import contient_secret

CLASSES = ("NORM", "POLICY", "ARCHITECTURE", "ADR", "BUSINESS_RULE", "TECHNICAL_DOC", "PATTERN", "ANTI_PATTERN",
           "LESSON", "PROJECT_KNOWLEDGE", "EXECUTION_MEMORY")
HIERARCHIE = ("NORM", "POLICY", "IMPLEMENTATION", "TEST", "PROOF")
TRANSFERABLES = {"PATTERN", "ANTI_PATTERN", "LESSON", "GENERIC_ARCHITECTURE_PRINCIPLE", "GENERIC_SECURITY_RULE"}
JAMAIS = {"SECRET", "CREDENTIAL", "PRIVATE_SOURCE", "BUSINESS_DATA", "PRIVATE_DOCUMENT"}


@dataclass
class Element:
    id: str
    classe: str
    projet: str | None
    texte: str
    marques: list[str] = field(default_factory=list)       # SECRET, BUSINESS_DATA… posées à l'enregistrement


@dataclass
class Verdict:
    transferable: bool
    motif: str


def autorite(source_a: str, source_b: str) -> str:
    """Laquelle l'emporte en cas de conflit (norme > politique > implémentation > test > preuve)."""
    for s in (source_a, source_b):
        if s not in HIERARCHIE:
            raise ValueError(f"source hors hiérarchie : {s!r}")
    return min(source_a, source_b, key=HIERARCHIE.index)


def transferable(e: Element, projet_origine: dict, projet_cible: str) -> Verdict:
    if e.projet == projet_cible:
        return Verdict(True, "même projet")
    if e.classe not in TRANSFERABLES:
        return Verdict(False, f"classe {e.classe} : jamais transférée automatiquement")
    if set(e.marques) & JAMAIS:
        return Verdict(False, "marquée " + ", ".join(sorted(set(e.marques) & JAMAIS)))
    if contient_secret(e.texte):
        return Verdict(False, "secret ou identifiant détecté")
    texte = e.texte.lower()
    for marque in _identifiants(projet_origine):
        if marque and marque.lower() in texte:
            return Verdict(False, f"identifiant du projet d'origine présent : {marque!r}")
    return Verdict(True, "connaissance générique")


def _identifiants(p: dict) -> list[str]:
    out = [p.get("id"), p.get("name")]
    out += [str((p.get("root") or {}).get("path") or "")]
    for env in p.get("environments") or []:
        out += [str(h) for h in env.get("hosts") or []]
    out += [str(x) for x in p.get("private_terms") or []]
    return [x for x in out if x and len(x) >= 3 and not re.fullmatch(r"\W*", x)]
