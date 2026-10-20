"""Organisation dynamique (Master Evolution Prompt v4 §18–§20, §26–§27).

Construit, pour une mission, l'arbre MISSION_MANAGER → DEPARTMENT_LEAD → TEAM_LEAD → SPECIALIST → WORKER à partir
des domaines touchés : un département sans domaine n'est pas créé. Recrute un spécialiste en cours de route
(spawning) dans le budget d'agents, et seulement un rôle du registre que le projet autorise. Les critiques
(adversariaux) et les agents métier sont des rôles du registre dotés d'une posture ou d'un domaine.

Ce module n'accorde aucun droit : un membre de l'organisation n'agit que par les tâches du graphe et les décisions
du Policy Engine.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

MISSION_MANAGER, DEPARTMENT_LEAD, TEAM_LEAD, SPECIALIST, WORKER = (
    "MISSION_MANAGER", "DEPARTMENT_LEAD", "TEAM_LEAD", "SPECIALIST", "WORKER")


class RefusOrganisation(Exception):
    """Recrutement ou modification refusé."""


@dataclass
class Membre:
    id: str
    role: str                          # rôle du registre des agents
    niveau: str
    parent: str | None = None
    departement: str | None = None
    posture: str | None = None         # critique adversarial
    domaine_metier: str | None = None  # agent métier
    motif: str | None = None
    actif: bool = True


@dataclass
class Organisation:
    structure: dict                    # orchestrator/organisation.yaml
    agents: dict                       # registre : id → fiche
    autorises: set                     # rôles autorisés par le projet (manifest agents.required ∪ allowed)
    max_agents: int = 12
    membres: dict = field(default_factory=dict)
    _n: object = field(default_factory=lambda: itertools.count(1))

    # ------------------------------------------------------------------ outillage
    def _verifier_role(self, role: str):
        if role not in self.agents:
            raise RefusOrganisation(f"rôle {role!r} absent du registre des agents")
        if role not in self.autorises:
            raise RefusOrganisation(f"rôle {role!r} non autorisé par le projet")

    def effectif(self) -> int:
        return sum(1 for m in self.membres.values() if m.actif)

    def _ajouter(self, role, niveau, parent=None, **plus) -> Membre:
        self._verifier_role(role)
        if self.effectif() >= self.max_agents:
            raise RefusOrganisation(f"budget d'agents atteint ({self.max_agents})")
        m = Membre(f"{niveau.lower()}-{role}-{next(self._n)}", role, niveau, parent, **plus)
        self.membres[m.id] = m
        return m

    def racine(self) -> Membre | None:
        return next((m for m in self.membres.values() if m.niveau == MISSION_MANAGER), None)

    def departement(self, domaine: str) -> Membre | None:
        return next((m for m in self.membres.values()
                     if m.niveau == DEPARTMENT_LEAD and m.departement == domaine and m.actif), None)

    def par_role(self, role: str) -> list[Membre]:
        return [m for m in self.membres.values() if m.role == role and m.actif]

    # ------------------------------------------------------------------ construction
    def construire(self, domaines: list[str], domaines_metier: list[str] | None = None,
                   critiques: list[str] | None = None, roles_requis: list[str] | None = None) -> "Organisation":
        """Racine, un responsable par domaine touché, les rôles que le plan exige, puis métier et critiques
        dans la limite du budget d'agents (un chef d'équipe n'est créé qu'au premier recrutement sous lui)."""
        s = self.structure
        racine = self._ajouter(s["mission_manager_role"], MISSION_MANAGER, motif="mission")
        inconnus = [d for d in domaines if d not in s["departments"]]
        if inconnus:
            raise RefusOrganisation(f"domaines sans département : {inconnus}")
        for dom in dict.fromkeys(domaines):
            dep = s["departments"][dom]
            if dep["lead"] not in self.autorises:
                continue                                  # domaine touché mais rôle non autorisé : pas d'équipe
            self._ajouter(dep["lead"], DEPARTMENT_LEAD, racine.id, departement=dom, motif=f"domaine {dom}")
        for role in dict.fromkeys(roles_requis or []):
            if role in self.autorises and self.membre_pour(role) is None:
                self.recruter(role, racine.id, "rôle exigé par le plan")
        for dm in domaines_metier or []:
            if s["business_role"] in self.autorises and self.effectif() < self.max_agents:
                self.recruter_metier(dm)
        voulus = list(s.get("always_critics", []))
        for dom in domaines:
            voulus += (s.get("critics_by_domain") or {}).get(dom, [])
        for c in dict.fromkeys(voulus + list(critiques or [])):
            if s["critics"][c]["role"] in self.autorises and self.effectif() < self.max_agents:
                self.recruter_critique(c)
        return self

    # ------------------------------------------------------------------ recrutement (spawning, §20)
    def recruter(self, role: str, demandeur: str | None = None, motif: str = "", niveau: str = SPECIALIST) -> Membre:
        """Un spécialiste rejoint l'équipe du domaine dont son rôle relève (ou la racine)."""
        dom = next((d for d, v in self.structure["departments"].items() if role in v["specialists"]), None)
        dep = self.departement(dom) if dom else None
        parent = dep or self.membres.get(demandeur) or self.racine()
        return self._ajouter(role, niveau, parent.id if parent else None, departement=dom,
                             motif=motif or f"recruté par {demandeur}")

    def recruter_critique(self, nom: str) -> Membre:
        c = self.structure["critics"].get(nom)
        if c is None:
            raise RefusOrganisation(f"critique inconnu : {nom}")
        r = self.racine()
        return self._ajouter(c["role"], SPECIALIST, r.id if r else None, posture=f"{nom} : {c['stance']}",
                             motif="revue adversariale")

    def recruter_metier(self, domaine: str) -> Membre:
        if domaine not in self.structure["business_domains"]:
            raise RefusOrganisation(f"domaine métier inconnu : {domaine}")
        r = self.racine()
        return self._ajouter(self.structure["business_role"], SPECIALIST, r.id if r else None,
                             domaine_metier=domaine, motif=f"expertise métier {domaine}")

    def liberer(self, ident: str):
        if ident in self.membres:
            self.membres[ident].actif = False

    def membre_pour(self, role: str, critique: str | None = None) -> Membre | None:
        """Le membre actif le moins haut placé qui tient ce rôle (le travail descend la hiérarchie). Un critique
        ne reçoit que sa revue ; une tâche ordinaire ne va jamais à un critique ni à un agent métier."""
        ordre = self.structure["levels"]
        if critique:
            cands = [m for m in self.par_role(role) if (m.posture or "").startswith(f"{critique} :")]
        else:
            cands = [m for m in self.par_role(role) if not m.posture and not m.domaine_metier]
        return max(cands, key=lambda m: ordre.index(m.niveau)) if cands else None

    def arbre(self) -> list[dict]:
        return [m.__dict__ for m in self.membres.values()]
