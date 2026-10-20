"""Abstraction des runtimes d'agents (Master Evolution Prompt v4 §31–§32, §53).

La Factory décide QUOI, POURQUOI, QUI, OÙ, AVEC QUELS DROITS ; le runtime réalise le COMMENT dans le périmètre
accordé. Le cœur ne connaît que l'interface `Runtime` ; un runtime réel (agent de code, runtime distant) est un
adaptateur hors du cœur (core/fournisseurs/). Deux runtimes génériques vivent ici :

- `RuntimeScripte` : comportements déterminés à l'avance (essais, démonstrations, rejeu) ;
- `RuntimeGates` : exécute les commandes déclarées par le manifest du projet (quality gates) sous liste blanche
  et en fait des preuves — le résultat d'une gate n'est jamais la déclaration d'un agent.

Un runtime qui lève une exception produit un échec TOOL_FAILED : il ne casse jamais la mission.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

from . import preuves as _preuves
from .commandes import Executeur
from .validation import chemin_relatif_sur


@dataclass
class ResultatTache:
    succes: bool
    classe_echec: str | None = None              # autonomy.recoverable_failures ou classe non récupérable
    signature: str = ""                          # empreinte courte de l'erreur (détection de boucle)
    motif: str = ""
    sortie: str = ""
    artefacts: list[dict] = field(default_factory=list)      # {id, type, contenu, dependances?}
    preuves: list[dict] = field(default_factory=list)
    jetons: int = 0
    appels: int = 0
    nouvelles_taches: list[dict] = field(default_factory=list)   # TASK_CREATE proposés par l'agent
    sous_taches: list[dict] = field(default_factory=list)        # SPLIT proposé
    frontiere: str | None = None                 # frontière humaine atteinte (§49)


@dataclass
class Contexte:
    mission_id: str
    projet_id: str
    tache: object                                # noyau.graphe.Tache
    membre: object                               # noyau.organisation.Membre
    modele: str | None = None
    espace: str | None = None                    # espace isolé de l'exécution
    environnement: dict | None = None            # environnement jetable (identifiants, jamais de secret)
    bail: str | None = None
    consignes: list[str] = field(default_factory=list)
    messages: list = field(default_factory=list)
    # Autorité d'une exécution de ticket accordée par le Policy Engine (run_ticket), à défaut de bail :
    # {"kind": "TICKET_EXECUTION", "execution_id", "worktree", "scope": [chemins], "executions_dir"}.
    autorite: dict | None = None
    # Prompt effectif d'un ticket v2 (ADR-0022 D8) : placé AVANT la consigne du runtime, qui vient en dernier et prévaut.
    prompt_contrat: str | None = None


class Runtime:
    """Interface : un runtime déclare ce qu'il sait faire et exécute une tâche dans son contexte."""
    id = "abstract"
    roles: tuple[str, ...] = ()                  # vide = tout rôle

    def disponible(self) -> tuple[bool, str]:
        return True, "disponible"

    def accepte(self, tache) -> bool:
        return not self.roles or tache.role in self.roles

    def executer(self, ctx: Contexte) -> ResultatTache:   # pragma: no cover - interface
        raise NotImplementedError


class RuntimeScripte(Runtime):
    """Pour chaque tâche (par identifiant, préfixe « role: » ou « * »), une suite de résultats ou de fonctions."""

    def __init__(self, scripts: dict, ident: str = "scripted", roles: tuple[str, ...] = ()):
        self.id, self.roles = ident, roles
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.appels: list[tuple[str, str | None]] = []
        self._rangs: dict[str, itertools.count] = {}

    def executer(self, ctx: Contexte) -> ResultatTache:
        t = ctx.tache
        cle = next((k for k in (t.id, t.parent and f"{t.parent}/*", f"role:{t.role}", "*")
                    if k and k in self.scripts), None)
        self.appels.append((t.id, ctx.modele))
        if cle is None:
            return ResultatTache(True, motif="aucun script : succès neutre")
        suite = self.scripts[cle]
        i = next(self._rangs.setdefault(f"{cle}|{t.id}", itertools.count()))
        etape = suite[min(i, len(suite) - 1)]
        return etape(ctx) if callable(etape) else etape


class RuntimeGates(Runtime):
    """Exécute la commande d'une gate déclarée par le manifest (argv, sans shell), dans l'espace de la tâche."""
    id = "quality-gates"

    def __init__(self, gates: dict, perimetre, racine_preuves: Path, delai: int = 600, roles: tuple[str, ...] = ()):
        self.gates = gates                       # manifest : quality.gates → {nom: {command: "…"}}
        self.racine_preuves = Path(racine_preuves)
        self.roles = roles
        commandes = [str(g["command"]).split() for g in gates.values() if (g or {}).get("command")]
        self.executeur = Executeur(autorisees=commandes, jokers={}, perimetre=perimetre, delai=delai)
        self._n = itertools.count(1)

    def accepte(self, tache) -> bool:
        return bool((tache.entree or {}).get("gate"))

    def executer(self, ctx: Contexte) -> ResultatTache:
        nom = ctx.tache.entree.get("gate")
        g = self.gates.get(nom) or {}
        if not g.get("command"):
            return ResultatTache(False, "QUALITY_GATE_FAILED", f"gate:{nom}:absente",
                                 f"gate {nom!r} non déclarée par le manifest")
        argv = str(g["command"]).split()
        env = (ctx.environnement or {}).get("variables") or {}
        self.executeur.environnement = dict(env)
        # Répertoire de la gate (manifest : cwd), relatif à l'espace de la tâche et jamais au-dehors, comme pour
        # la plateforme d'exécution des tickets.
        sous_dossier = str(g.get("cwd") or ".")
        if sous_dossier != "." and (not ctx.espace or not chemin_relatif_sur(sous_dossier)):
            return ResultatTache(False, "TOOL_FAILED", f"gate:{nom}:cwd",
                                 f"gate {nom} : répertoire {sous_dossier!r} hors de l'espace isolé ou sans espace")
        r = self.executeur.lancer(argv, cwd=ctx.espace if sous_dossier == "." else str(Path(ctx.espace) / sous_dossier))
        if not r.executee:
            return ResultatTache(False, "TOOL_FAILED", f"gate:{nom}:{r.motif_refus}", r.motif_refus or "non exécutée")
        ident = f"{ctx.mission_id}-{ctx.tache.id}-{next(self._n)}"
        preuve = _preuves.enregistrer_commande(r, g.get("evidence_type", "TEST"), ident, self.racine_preuves,
                                               f"runtime:{self.id}")
        if r.code == 0:
            return ResultatTache(True, motif=f"gate {nom} réussie", sortie=r.sortie, preuves=[preuve])
        derniere = (r.sortie.strip().splitlines() or [""])[-1][:200]
        return ResultatTache(False, "QUALITY_GATE_FAILED", f"gate:{nom}:{derniere}", f"gate {nom} en échec",
                             sortie=r.sortie, preuves=[preuve])


class Runtimes:
    """Registre des runtimes : le premier disponible qui accepte la tâche, dans l'ordre déclaré."""

    def __init__(self, runtimes: list[Runtime]):
        self.runtimes = list(runtimes)

    def choisir(self, tache, exclus: set[str] | None = None) -> Runtime | None:
        voulu = (tache.entree or {}).get("runtime")
        for r in self.runtimes:
            if exclus and r.id in exclus:
                continue
            if voulu and r.id != voulu:
                continue
            if r.accepte(tache) and r.disponible()[0]:
                return r
        return None
