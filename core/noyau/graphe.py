"""Graphe de tâches dynamique (Master Evolution Prompt v4 §21, §22, §48).

Opérations : CREATE, SPLIT, MERGE, REORDER, PAUSE, RESUME, RETRY, CANCEL, REASSIGN. Une tâche peut en créer
d'autres. Les tâches prêtes et sans conflit (fichiers écrits, ressources) forment des lots exécutables en parallèle.

Chaque changement d'état suit la table du cycle « task » (core/schemas/lifecycles.yaml) ; une transition absente
est refusée. Chaque opération s'inscrit dans un journal chaîné (noyau.audit.Journal) quand il est fourni.
WAITING_HUMAN n'est admis que pour une frontière humaine déclarée : un échec de build, de test, de migration ou
d'outil n'y mène jamais (§48) — il mène à la reprise.
"""
from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field

PENDING, READY, RUNNING, BLOCKED, FAILED = "PENDING", "READY", "RUNNING", "BLOCKED", "FAILED"
RETRYING, WAITING_DEPENDENCY, WAITING_HUMAN = "RETRYING", "WAITING_DEPENDENCY", "WAITING_HUMAN"
SUCCEEDED, CANCELLED = "SUCCEEDED", "CANCELLED"
PAUSE = "PAUSE"


class RefusGraphe(Exception):
    """Opération refusée : le graphe est inchangé."""


@dataclass
class Tache:
    id: str
    titre: str
    role: str                                        # rôle d'agent attendu (registre des agents)
    dependances: list[str] = field(default_factory=list)
    ecrit: list[str] = field(default_factory=list)   # chemins écrits : deux tâches qui se recouvrent ne vont pas ensemble
    ressources: list[str] = field(default_factory=list)   # ressources exclusives (base, port, environnement…)
    capacites: list[str] = field(default_factory=list)
    priorite: int = 0
    phase: str | None = None
    optionnelle: bool = False
    entree: dict = field(default_factory=dict)       # données de la tâche (jamais des instructions de pouvoir, §43)
    etat: str = PENDING
    assigne: str | None = None
    modele: str | None = None
    tentatives: int = 0
    parent: str | None = None
    motif: str | None = None
    frontiere: str | None = None
    resultat: dict | None = None


def _recouvre(a: str, b: str) -> bool:
    a, b = a.replace("\\", "/").rstrip("/"), b.replace("\\", "/").rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/") or a in ("", ".") or b in ("", ".")


class Graphe:
    def __init__(self, cycle: dict, frontieres: list[str], journal=None, mission_id: str | None = None):
        self.cycle = cycle                           # lifecycles.yaml : task
        self.frontieres = set(frontieres)            # autonomy : human_boundaries
        self.journal = journal
        self.mission_id = mission_id
        self.taches: dict[str, Tache] = {}
        self._ordre = itertools.count()
        self._rang: dict[str, int] = {}
        self.evenements: list[dict] = []

    # ------------------------------------------------------------------ transitions et journal
    def _permise(self, depart: str, vers: str) -> bool:
        if depart in self.cycle.get("terminal", []):
            return False
        if vers in self.cycle.get("any_to", []):
            return True
        return any(t["from"] == depart and t["to"] == vers for t in self.cycle["transitions"])

    def _passer(self, t: Tache, vers: str, motif: str | None = None):
        if not self._permise(t.etat, vers):
            raise RefusGraphe(f"{t.id} : transition {t.etat} → {vers} absente du cycle task")
        depart, t.etat = t.etat, vers
        if motif is not None:
            t.motif = motif
        self._noter("transition task", t.id, depart, vers, motif)

    def _noter(self, action: str, ident: str, depart=None, vers=None, motif=None, **plus):
        evt = {"action": action, "task_id": ident, "from_state": depart, "to_state": vers, "reason": motif, **plus}
        self.evenements.append(evt)
        if self.journal is not None:
            self.journal.ajouter(actor={"type": "system", "id": "task-graph"}, mission_id=self.mission_id,
                                 action=action, result=vers or "APPLIED", task_id=ident, from_state=depart,
                                 to_state=vers, reasons=[motif] if motif else [], **plus)

    # ------------------------------------------------------------------ lecture
    def tache(self, ident: str) -> Tache:
        if ident not in self.taches:
            raise RefusGraphe(f"tâche inconnue : {ident}")
        return self.taches[ident]

    def _faites(self, t: Tache) -> bool:
        return all(self.taches[d].etat == SUCCEEDED for d in t.dependances)

    def _impossible(self, t: Tache) -> bool:
        return any(self.taches[d].etat == CANCELLED and not self.taches[d].optionnelle for d in t.dependances)

    def dependants(self, ident: str) -> list[Tache]:
        return [t for t in self.taches.values() if ident in t.dependances]

    def prets(self) -> list[Tache]:
        return sorted((t for t in self.taches.values() if t.etat == READY),
                      key=lambda t: (-t.priorite, self._rang[t.id]))

    def en_cours(self) -> list[Tache]:
        return [t for t in self.taches.values() if t.etat == RUNNING]

    def conflit(self, a: Tache, b: Tache) -> bool:
        if set(a.ressources) & set(b.ressources):
            return True
        return any(_recouvre(x, y) for x in a.ecrit for y in b.ecrit)

    def lot(self, places: int) -> list[Tache]:
        """Tâches prêtes à lancer ensemble : sans conflit entre elles ni avec celles qui tournent."""
        choisis: list[Tache] = []
        occupees = self.en_cours()
        for t in self.prets():
            if len(choisis) >= places:
                break
            if any(self.conflit(t, o) for o in occupees + choisis):
                continue
            choisis.append(t)
        return choisis

    def termine(self) -> bool:
        return all(t.etat in (SUCCEEDED, CANCELLED) for t in self.taches.values())

    def en_attente_humaine(self) -> list[Tache]:
        return [t for t in self.taches.values() if t.etat == WAITING_HUMAN]

    def resume(self) -> dict[str, int]:
        r: dict[str, int] = {}
        for t in self.taches.values():
            r[t.etat] = r.get(t.etat, 0) + 1
        return r

    # ------------------------------------------------------------------ CREATE
    def creer(self, t: Tache) -> Tache:
        if not t.id or t.id in self.taches:
            raise RefusGraphe(f"identifiant de tâche absent ou déjà pris : {t.id!r}")
        inconnues = [d for d in t.dependances if d not in self.taches]
        if inconnues:
            raise RefusGraphe(f"{t.id} : dépendances inconnues {inconnues}")
        t.etat = PENDING
        self.taches[t.id] = t
        self._rang[t.id] = next(self._ordre)
        self._noter("create task", t.id, None, PENDING, None, role=t.role, parent=t.parent)
        self._evaluer(t)
        return t

    def _evaluer(self, t: Tache):
        """PENDING / WAITING_DEPENDENCY → READY quand les dépendances sont faites ; tâche impossible → CANCELLED."""
        if t.etat not in (PENDING, WAITING_DEPENDENCY, READY):
            return
        if self._impossible(t):
            self._passer(t, CANCELLED, "dépendance annulée")
            for d in self.dependants(t.id):
                self._evaluer(d)
        elif self._faites(t):
            if t.etat != READY:
                self._passer(t, READY)
        elif t.etat != WAITING_DEPENDENCY:
            self._passer(t, WAITING_DEPENDENCY)

    def _reevaluer_dependants(self, ident: str):
        for d in self.dependants(ident):
            self._evaluer(d)

    # ------------------------------------------------------------------ exécution
    def demarrer(self, ident: str, agent: str | None = None) -> Tache:
        t = self.tache(ident)
        if t.etat != READY:
            raise RefusGraphe(f"{ident} n'est pas prête ({t.etat})")
        t.assigne = agent or t.assigne
        self._passer(t, RUNNING)
        return t

    def reussir(self, ident: str, resultat: dict | None = None) -> Tache:
        t = self.tache(ident)
        t.resultat = resultat or {}
        self._passer(t, SUCCEEDED)
        self._reevaluer_dependants(ident)
        return t

    def echouer(self, ident: str, motif: str) -> Tache:
        t = self.tache(ident)
        self._passer(t, FAILED, motif)
        return t

    # ------------------------------------------------------------------ RETRY, REASSIGN, REORDER
    def reessayer(self, ident: str, motif: str = "nouvelle tentative") -> Tache:
        t = self.tache(ident)
        self._passer(t, RETRYING, motif)
        t.tentatives += 1
        self._passer(t, READY)
        return t

    def reassigner(self, ident: str, role: str, agent: str | None = None) -> Tache:
        t = self.tache(ident)
        if t.etat in (SUCCEEDED, CANCELLED):
            raise RefusGraphe(f"{ident} est terminée")
        ancien, t.role, t.assigne = t.role, role, agent
        if t.etat == RUNNING:
            self._passer(t, READY, f"réassignée {ancien} → {role}")
        self._noter("reassign task", ident, t.etat, t.etat, f"{ancien} → {role}")
        return t

    def reordonner(self, ident: str, priorite: int) -> Tache:
        t = self.tache(ident)
        t.priorite = priorite
        self._noter("reorder task", ident, t.etat, t.etat, f"priorité {priorite}")
        return t

    # ------------------------------------------------------------------ PAUSE, RESUME, CANCEL
    def suspendre(self, ident: str) -> Tache:
        t = self.tache(ident)
        if t.etat not in (PENDING, READY, WAITING_DEPENDENCY):
            raise RefusGraphe(f"{ident} ne se suspend pas dans l'état {t.etat}")
        self._passer(t, BLOCKED, PAUSE)
        return t

    def reprendre(self, ident: str) -> Tache:
        t = self.tache(ident)
        if t.etat != BLOCKED:
            raise RefusGraphe(f"{ident} n'est pas suspendue")
        self._passer(t, READY, "reprise")
        if not self._faites(t):
            self._passer(t, WAITING_DEPENDENCY)
        return t

    def bloquer(self, ident: str, motif: str) -> Tache:
        t = self.tache(ident)
        self._passer(t, BLOCKED, motif)
        return t

    def annuler(self, ident: str, motif: str = "annulée") -> Tache:
        t = self.tache(ident)
        self._passer(t, CANCELLED, motif)
        self._reevaluer_dependants(ident)
        return t

    # ------------------------------------------------------------------ SPLIT, MERGE
    def scinder(self, ident: str, sous_taches: list[Tache]) -> list[Tache]:
        """La tâche est remplacée par ses sous-tâches ; ses dépendants attendent toutes les sous-tâches."""
        t = self.tache(ident)
        if t.etat in (SUCCEEDED, CANCELLED, RUNNING) or not sous_taches:
            raise RefusGraphe(f"{ident} ne se scinde pas ({t.etat})")
        ids = {s.id for s in sous_taches}
        for s in sous_taches:
            s.parent = ident
            s.dependances = list(dict.fromkeys(list(t.dependances) + [d for d in s.dependances if d in ids or d in self.taches]))
        crees = self._creer_ensemble(sous_taches)
        dependants = self.dependants(ident)
        for d in dependants:
            d.dependances = [x for x in d.dependances if x != ident] + [s.id for s in crees]
        self._passer(t, CANCELLED, "SPLIT → " + ", ".join(s.id for s in crees))
        for d in dependants:
            self._evaluer(d)
        return crees

    def _creer_ensemble(self, taches: list[Tache]) -> list[Tache]:
        restantes, crees = list(taches), []
        while restantes:
            pret = [s for s in restantes if all(d in self.taches for d in s.dependances)]
            if not pret:
                raise RefusGraphe("dépendances circulaires ou inconnues entre sous-tâches")
            for s in pret:
                crees.append(self.creer(s))
                restantes.remove(s)
        return crees

    def fusionner(self, ids: list[str], nouvelle: Tache) -> Tache:
        """Les tâches fusionnées sont annulées ; la nouvelle hérite de leurs dépendances et de leurs dépendants."""
        anciennes = [self.tache(i) for i in ids]
        if len(anciennes) < 2 or any(a.etat in (SUCCEEDED, CANCELLED, RUNNING) for a in anciennes):
            raise RefusGraphe("fusion : au moins deux tâches non commencées")
        nouvelle.dependances = list(dict.fromkeys(
            [d for a in anciennes for d in a.dependances if d not in ids] + nouvelle.dependances))
        nouvelle.ecrit = list(dict.fromkeys([p for a in anciennes for p in a.ecrit] + nouvelle.ecrit))
        nouvelle.ressources = list(dict.fromkeys([r for a in anciennes for r in a.ressources] + nouvelle.ressources))
        self.creer(nouvelle)
        dependants = {d.id: d for i in ids for d in self.dependants(i) if d.id != nouvelle.id}
        for d in dependants.values():
            d.dependances = list(dict.fromkeys([nouvelle.id if x in ids else x for x in d.dependances]))
        for a in anciennes:
            self._passer(a, CANCELLED, f"MERGE → {nouvelle.id}")
        for d in dependants.values():
            self._evaluer(d)
        return nouvelle

    # ------------------------------------------------------------------ frontière humaine
    def attendre_humain(self, ident: str, frontiere: str, motif: str) -> Tache:
        if frontiere not in self.frontieres:
            raise RefusGraphe(f"WAITING_HUMAN refusé : {frontiere!r} n'est pas une frontière humaine (§48 : "
                              "un échec se reprend, il ne s'escalade pas vers l'humain)")
        t = self.tache(ident)
        t.frontiere = frontiere
        self._passer(t, WAITING_HUMAN, motif)
        return t

    def liberer_humain(self, ident: str, reference: str) -> Tache:
        t = self.tache(ident)
        if t.etat != WAITING_HUMAN or not reference:
            raise RefusGraphe(f"{ident} : libération sans décision humaine référencée")
        self._passer(t, READY, f"décision humaine {reference}")
        return t

    # ------------------------------------------------------------------ persistance (mode nuit, reprise)
    def en_dict(self) -> dict:
        return {"mission_id": self.mission_id, "taches": [asdict(self.taches[i]) for i in
                                                           sorted(self.taches, key=self._rang.get)]}

    @classmethod
    def depuis_dict(cls, donnees: dict, cycle: dict, frontieres: list[str], journal=None) -> "Graphe":
        g = cls(cycle, frontieres, journal, donnees.get("mission_id"))
        for brut in donnees["taches"]:
            t = Tache(**brut)
            g.taches[t.id] = t
            g._rang[t.id] = next(g._ordre)
        return g
