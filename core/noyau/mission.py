"""Mission Manager (Master Evolution Prompt v4 §1, §17).

L'humain donne QUOI, POURQUOI, l'objectif métier et les contraintes ; le Mission Manager en tire objectifs,
exigences, contraintes, domaines techniques et métier, plans qualité, sécurité et livraison, puis le graphe de
tâches initial. Il n'invente aucune règle : la détection des domaines et les plans viennent des données
(orchestrator/domaines.yaml, orchestrator/organisation.yaml, manifest du projet).

Le graphe initial : analyse → conception → implémentation par domaine (en parallèle) → intégration → gates du
plan qualité et revues adversariales (en parallèle) → clôture [→ livraison, frontière humaine RELEASE].
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .graphe import Tache


class RefusMission(Exception):
    """Mission mal formée : rien n'est planifié."""


@dataclass
class Plan:
    mission_id: str
    projet_id: str
    objectifs: dict
    exigences: list[str]
    contraintes: list[str]
    domaines: list[str]
    domaines_metier: list[str]
    plan_qualite: list[str]
    plan_securite: list[str]
    plan_livraison: dict
    taches: list[Tache] = field(default_factory=list)


def _texte(mission: dict) -> str:
    morceaux = [mission.get("what", ""), mission.get("why", ""), mission.get("business_objective", "")]
    morceaux += [str(c) for c in mission.get("constraints") or []]
    return " ".join(morceaux).lower()


def _trouve(mot: str, texte: str) -> bool:
    """Début de mot ; un mot court (≤ 4 lettres) doit être entier (« api » ne se trouve pas dans « rapide »)."""
    fin = r"(?!\w)" if len(mot) <= 4 else ""
    return re.search(r"(?<!\w)" + re.escape(mot.lower()) + fin, texte) is not None


def detecter(texte: str, regles: dict) -> list[str]:
    return [dom for dom, mots in regles.items() if any(_trouve(m, texte) for m in mots)]


def analyser(mission: dict, donnees: dict, organisation: dict, gates_du_projet: dict) -> Plan:
    for champ in ("id", "project_id", "what", "why"):
        if not mission.get(champ):
            raise RefusMission(f"mission sans {champ} (QUOI et POURQUOI sont fournis par l'humain)")
    texte = _texte(mission)
    domaines = list(mission.get("domains") or detecter(texte, donnees["technical"]))
    if len([d for d in domaines if d not in ("qa", "architecture")]) >= donnees.get("architecture_when_domains_at_least", 99):
        domaines.append("architecture")
    domaines = list(dict.fromkeys(domaines + list(donnees.get("always") or [])))
    inconnus = [d for d in domaines if d not in organisation["departments"]]
    if inconnus:
        raise RefusMission(f"domaines sans département : {inconnus}")
    metier = list(mission.get("business_domains") or detecter(texte, donnees["business"]))

    qg = donnees.get("quality_gates") or {}
    voulues = list(qg.get("always") or []) + [g for d in domaines for g in qg.get(d, [])]
    declarees = {str(n).upper(): n for n in gates_du_projet}
    plan_qualite = [declarees[g] for g in dict.fromkeys(voulues) if g in declarees]

    critiques = list(organisation.get("always_critics") or [])
    for d in domaines:
        critiques += (organisation.get("critics_by_domain") or {}).get(d, [])
    plan_securite = list(dict.fromkeys(critiques))
    livraison = {"requested": bool(mission.get("release")), "boundary": "RELEASE", "human": True}

    plan = Plan(mission["id"], mission["project_id"],
                {"business": mission.get("business_objective") or mission["why"], "technical": mission["what"]},
                list(mission.get("acceptance") or []) or [mission["what"]], list(mission.get("constraints") or []),
                domaines, metier, plan_qualite, plan_securite, livraison)
    plan.taches = graphe_initial(plan, mission, donnees, organisation)
    return plan


def graphe_initial(plan: Plan, mission: dict, donnees: dict, organisation: dict) -> list[Tache]:
    s = organisation
    perimetres = mission.get("scope") or {}
    caps = donnees.get("capabilities") or {}
    entree = {"mission": mission["what"], "why": mission["why"], "constraints": plan.contraintes,
              "acceptance": plan.exigences}
    taches = [Tache("analyse", "Analyse métier et exigences", s["mission_manager_role"], phase="BUSINESS_ANALYSIS",
                    priorite=100, entree=dict(entree, business_domains=plan.domaines_metier),
                    capacites=["FILESYSTEM_READ"]),
              Tache("conception", "Conception technique et découpage", s["architecture_role"], ["analyse"],
                    phase="TECHNICAL_DESIGN", priorite=90, entree=dict(entree), capacites=["FILESYSTEM_READ"])]
    impl = []
    for d in plan.domaines:
        if d in ("qa", "architecture", "security"):
            continue
        dep = s["departments"][d]
        t = Tache(f"impl-{d}", f"Implémentation {dep['department']}", dep["lead"], ["conception"],
                  ecrit=list(perimetres.get(d) or []), phase="EXECUTION", priorite=50,
                  entree=dict(entree, domain=d), capacites=list(caps.get(d) or caps.get("default") or []))
        if d == "database":
            t.ressources = ["database"]
        impl.append(t)
    taches += impl
    apres_impl = [t.id for t in impl] or ["conception"]
    taches.append(Tache("integration", "Intégration des contributions", s["architecture_role"], apres_impl,
                        phase="EXECUTION", priorite=40, entree=dict(entree), capacites=["FILESYSTEM_READ", "TEST"]))
    controles = []
    for g in plan.plan_qualite:
        controles.append(Tache(f"gate-{str(g).lower()}", f"Quality gate {g}", "qa", ["integration"], phase="QUALITY",
                               priorite=30, entree={"gate": g}, capacites=["TEST"],
                               ressources=["database"] if str(g).upper() == "MIGRATION" else []))
    for c in plan.plan_securite:
        crit = s["critics"][c]
        controles.append(Tache(f"revue-{c.lower()}", f"Revue adversariale {c}", crit["role"], ["integration"],
                               phase="REVIEW", priorite=30, entree={"critic": c, "stance": crit["stance"]},
                               capacites=["FILESYSTEM_READ"]))
    taches += controles
    taches.append(Tache("cloture", "Clôture : preuves, synthèse, prochaine étape", s["mission_manager_role"],
                        [t.id for t in controles] or ["integration"], phase="REVIEW", priorite=10,
                        entree=dict(entree), capacites=["FILESYSTEM_READ"]))
    if plan.plan_livraison["requested"]:
        taches.append(Tache("livraison", "Livraison (frontière humaine RELEASE)", s["mission_manager_role"],
                            ["cloture"], phase="MERGE", entree={"boundary": "RELEASE"}, capacites=["RELEASE"]))
    return taches
