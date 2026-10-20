"""Superviseur (Master Evolution Prompt v4 §28–§30, §48, §52).

Surveille budgets (durée, jetons, appels d'outils, agents, parallélisme, reprises), boucles, santé des agents,
outils et environnements ; choisit la stratégie de reprise d'un échec à partir des données (autonomy.recovery).
Il ne décide jamais d'une permission : il ne contourne pas le Policy Engine, il ne crée pas d'approbation.

Un échec récupérable ne mène jamais à l'humain (§48) : RETRY, RESET, SPAWN_SPECIALIST, SPLIT… puis ESCALATE vers
la hiérarchie d'agents ; l'arrêt (STOP) vient du budget ou d'un échec non récupérable (sécurité, politique).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

RETRY, STOP, ESCALATE = "RETRY", "STOP", "ESCALATE"
NON_RECUPERABLES = {"POLICY_DENIED", "SECURITY_STOP", "SCOPE_VIOLATION", "SECRET_EXPOSED"}


@dataclass
class Budget:
    max_duration_s: float = 7200
    max_tokens: int = 400_000
    max_tool_calls: int = 800
    max_agents: int = 12
    max_parallel: int = 4
    max_retries: int = 5

    @classmethod
    def depuis(cls, donnees: dict | None, plafond: "Budget | None" = None) -> "Budget":
        """Un budget de mission ou de projet peut abaisser le plafond, jamais le dépasser (§52)."""
        b = cls(**{k: v for k, v in (donnees or {}).items() if k in cls.__dataclass_fields__})
        if plafond:
            for k in cls.__dataclass_fields__:
                setattr(b, k, min(getattr(b, k), getattr(plafond, k)))
        return b


@dataclass
class DecisionReprise:
    strategie: str
    motif: str
    specialiste: str | None = None


@dataclass
class Superviseur:
    budget: Budget
    strategies: dict                                   # autonomy.recovery : classe d'échec → [stratégies]
    recuperables: list[str]                            # autonomy.recoverable_failures
    horloge: object = time.monotonic
    seuil_boucle: int = 3                              # même signature d'échec N fois = boucle
    debut: float = field(default=0.0)
    jetons: int = 0
    appels: int = 0
    reprises: int = 0
    agents: set = field(default_factory=set)
    echecs: dict = field(default_factory=dict)         # tâche → nombre d'échecs
    signatures: dict = field(default_factory=dict)     # (tâche racine, signature) → occurrences
    sante: dict = field(default_factory=dict)          # (genre, id) → {"ok": n, "ko": n}
    journal: list = field(default_factory=list)

    def __post_init__(self):
        self.debut = self.horloge()

    # ------------------------------------------------------------------ consommation et budgets
    def consommer(self, jetons: int = 0, appels: int = 0, agent: str | None = None):
        self.jetons += int(jetons or 0)
        self.appels += int(appels or 0)
        if agent:
            self.agents.add(agent)

    def depassement(self) -> str | None:
        b = self.budget
        if self.horloge() - self.debut > b.max_duration_s:
            return "durée"
        if self.jetons > b.max_tokens:
            return "jetons"
        if self.appels > b.max_tool_calls:
            return "appels d'outils"
        if self.reprises > b.max_retries:
            return "reprises"
        return None

    def places(self, en_cours: int) -> int:
        return max(0, self.budget.max_parallel - en_cours)

    def peut_recruter(self, effectif: int) -> bool:
        return effectif < self.budget.max_agents

    # ------------------------------------------------------------------ santé
    def noter_sante(self, genre: str, ident: str, ok: bool):
        s = self.sante.setdefault((genre, ident), {"ok": 0, "ko": 0})
        s["ok" if ok else "ko"] += 1

    def en_mauvaise_sante(self, genre: str, ident: str, seuil: int = 3) -> bool:
        s = self.sante.get((genre, ident)) or {"ok": 0, "ko": 0}
        return s["ko"] >= seuil and s["ko"] > s["ok"]

    # ------------------------------------------------------------------ échecs
    def sur_echec(self, tache, classe: str, signature: str = "") -> DecisionReprise:
        racine = tache.parent or tache.id
        n = self.echecs[tache.id] = self.echecs.get(tache.id, 0) + 1
        self.noter_sante("agent", tache.assigne or tache.role, False)
        if classe in NON_RECUPERABLES:
            return self._decider(DecisionReprise(STOP, f"{classe} : échec non récupérable, arrêt de la branche"), tache)
        if self.depassement():
            return self._decider(DecisionReprise(STOP, f"budget épuisé ({self.depassement()})"), tache)
        if classe not in self.recuperables:
            return self._decider(DecisionReprise(ESCALATE, f"classe d'échec inconnue {classe!r} : escalade"), tache)
        cle = (racine, signature or classe)
        self.signatures[cle] = self.signatures.get(cle, 0) + 1
        suite = list(self.strategies.get(classe) or self.strategies.get("default") or [RETRY, ESCALATE])
        rang = n - 1
        if self.signatures[cle] >= self.seuil_boucle:
            # Boucle : la même erreur revient ; on abandonne les stratégies « refaire pareil ».
            suite = [s for s in suite if s not in (RETRY, "RESET_ENVIRONMENT")] or [ESCALATE]
            rang = min(self.signatures[cle] - self.seuil_boucle, len(suite) - 1)
        strategie = suite[min(rang, len(suite) - 1)]
        specialiste = (self.strategies.get("specialists") or {}).get(classe) if strategie == "SPAWN_SPECIALIST" else None
        if strategie == "SPAWN_SPECIALIST" and not specialiste:
            strategie = suite[min(rang + 1, len(suite) - 1)] if rang + 1 < len(suite) else ESCALATE
        if strategie not in (STOP, ESCALATE):
            self.reprises += 1
        return self._decider(DecisionReprise(strategie, f"{classe} (échec n°{n}) → {strategie}", specialiste), tache)

    def _decider(self, d: DecisionReprise, tache) -> DecisionReprise:
        self.journal.append({"task_id": tache.id, "strategy": d.strategie, "reason": d.motif,
                             "specialist": d.specialiste})
        return d
