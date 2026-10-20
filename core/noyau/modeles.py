"""Sélection dynamique du modèle (Master Evolution Prompt v4 §53), sans lien avec un fournisseur.

Le profil d'une tâche (raisonnement, volume de code, revue de sécurité, simple refactorisation) se traduit en
traits recherchés ; seuls les modèles du registre APPROUVÉS (cycle « model ») sont candidats, et un modèle n'est
jamais retenu pour un rôle que sa fiche interdit. Sans candidat : None — le runtime garde son modèle par défaut,
la Factory n'en invente pas. Un changement de modèle (stratégie CHANGE_MODEL) exclut ceux déjà essayés.
"""
from __future__ import annotations

APPROUVES = {"APPROVED", "DEPLOYED", "MONITORED"}
PROFILS = {
    "architecture": {"reasoning": 3, "cost": 1},
    "security": {"reasoning": 3, "cost": 1},
    "coding": {"coding": 3, "reasoning": 2, "cost": 2},
    "simple": {"cost": 3, "coding": 1},
    "review": {"reasoning": 2, "cost": 2},
}
ROLE_PROFIL = {"architect": "architecture", "planner": "architecture", "security": "security",
               "refactoring": "simple", "documentation": "simple", "qa": "review"}


def profil(tache) -> str:
    voulu = (tache.entree or {}).get("profile")
    if voulu in PROFILS:
        return voulu
    if (tache.entree or {}).get("critic"):
        return "security" if tache.role == "security" else "review"
    return ROLE_PROFIL.get(tache.role, "coding")


def _note(fiche: dict, trait: str) -> float:
    ev = fiche.get("evaluation") or {}
    if trait == "cost":
        cout = (fiche.get("cost") or {}).get("output")
        return 3.0 / (1.0 + float(cout)) if isinstance(cout, (int, float)) else 0.0
    v = ev.get(trait) if trait in ev else (fiche.get("context") or {}).get(trait)
    return float(v) if isinstance(v, (int, float)) else 0.0


def choisir(modeles: dict, tache, exclus: set | None = None) -> str | None:
    p = PROFILS[profil(tache)]
    cands = []
    for ident, f in modeles.items():
        if exclus and ident in exclus:
            continue
        if f.get("lifecycle") not in APPROUVES:
            continue
        sec = f.get("security") or {}
        if tache.role in (sec.get("prohibited_for") or []):
            continue
        permis = (f.get("roles") or {}).get("allowed") or []
        if permis and tache.role not in permis:
            continue
        cands.append((sum(poids * _note(f, trait) for trait, poids in p.items()), ident))
    return max(cands)[1] if cands else None
