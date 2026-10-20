"""Aide commune aux tests du cœur : chemins d'import (lancé avec « python -P ») et habilitation de test."""
import datetime as _dt
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
FACTORY = CORE.parent
BOOTSTRAP = FACTORY / "bootstrap"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))


def habilitation_de_test(plafond: str = "C2", projets=("gestionfil", "projet-a", "projet-b")) -> dict:
    """Bloc `habilitation` complet et valide aujourd'hui (Playbook §12.6, G4)."""
    jour = _dt.date.today()
    return {"max_criticality": plafond, "projects": list(projets), "model": "modele-de-test",
            "evaluation": {"suite_sha256": "a" * 64, "report_sha256": "b" * 64},
            "granted_at": jour.isoformat(), "expires_at": (jour + _dt.timedelta(days=30)).isoformat()}


class MagasinHabilitant:
    """Double du magasin d'approbations : tient pour approuvée par l'humain toute habilitation définitive
    (AGENT_HABILITATION) et délègue le reste au magasin réel. La vérification réelle d'une habilitation par
    enregistrement est prouvée à part (test_habilitation)."""

    def __init__(self, base):
        self.base = base

    def trouver(self, ctx, roles_admis, age_max_h):
        from noyau.approbation import Verification
        if isinstance(ctx, dict) and ctx.get("kind") == "AGENT_HABILITATION":
            return Verification(True, "habilitation de test")
        return self.base.trouver(ctx, roles_admis, age_max_h)

    def __getattr__(self, nom):
        return getattr(self.base, nom)


def habiliter(moteur, *agents: str, plafond: str = "C2", projets=("gestionfil", "projet-a", "projet-b")):
    """Agents APPROVED avec une habilitation définitive tenue pour approuvée (tests hors habilitation)."""
    objets = moteur.registre.objets
    objets["agents"] = dict(objets["agents"])
    for a in agents:
        objets["agents"][a] = dict(objets["agents"][a], lifecycle="APPROVED",
                                   habilitation=habilitation_de_test(plafond, projets))
    if not isinstance(moteur.approbations, MagasinHabilitant):
        moteur.approbations = MagasinHabilitant(moteur.approbations)
    return moteur
