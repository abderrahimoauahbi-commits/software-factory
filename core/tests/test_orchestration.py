"""Évolution E (Master Evolution Prompt v4) : graphe dynamique, superviseur, organisation, communication, mission,
méta-orchestrateur et boucle d'auto-réparation — sans humain entre le début et la fin, sauf vraie frontière."""
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from noyau import graphe as G
from noyau.audit import Journal
from noyau.messages import Artefacts, Bus, Message, RefusMessage
from noyau.mission import analyser, detecter
from noyau.orchestrateur import ALLOW, MetaOrchestrateur
from noyau.organisation import Organisation, RefusOrganisation
from noyau.runtime import ResultatTache as R, RuntimeScripte, Runtimes
from noyau.superviseur import Budget, Superviseur


def _y(p):
    return yaml.safe_load((FACTORY / p).read_text(encoding="utf-8"))


CYCLES = _y("core/schemas/lifecycles.yaml")
ORGA = _y("orchestrator/organisation.yaml")
DOMAINES = _y("orchestrator/domaines.yaml")
AGENTS = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (FACTORY / "registry" / "agents").glob("*.yaml")}
FRONTIERES = ["PRODUCTION_WRITE", "RELEASE", "SENSITIVE_DATA_ACCESS", "PERMISSION_MODEL_CHANGE"]
RECUPERABLES = ["BUILD_FAILED", "TEST_FAILED", "MIGRATION_FAILED", "SEED_FAILED", "TOOL_FAILED", "AGENT_STUCK",
                "PLAN_INVALID", "TASK_TOO_LARGE", "ENVIRONMENT_FAILED", "QUALITY_GATE_FAILED"]
STRATEGIES = {"default": ["RETRY", "CHANGE_STRATEGY", "SPAWN_SPECIALIST", "SPLIT_TASK", "ESCALATE"],
              "MIGRATION_FAILED": ["RESET_ENVIRONMENT", "RETRY", "SPAWN_SPECIALIST", "ESCALATE"],
              "TASK_TOO_LARGE": ["SPLIT_TASK", "RETRY", "ESCALATE"],
              "specialists": {"MIGRATION_FAILED": "database", "TEST_FAILED": "qa"}}
TOUS = set(AGENTS)


def graphe(journal=None):
    return G.Graphe(CYCLES["task"], FRONTIERES, journal, "M-1")


def superviseur(**budget):
    return Superviseur(Budget(**budget), STRATEGIES, RECUPERABLES)


def tout_permis(tache, membre):
    """Double de test : le gestionnaire de capacités (et donc le Policy Engine) accorde tout."""
    return {"decision": ALLOW, "motif": "double de test"}


class GrapheDynamique(unittest.TestCase):
    def test_dependances_et_lots_paralleles(self):
        g = graphe()
        g.creer(G.Tache("a", "A", "architect"))
        for x in ("db", "api", "ui"):
            g.creer(G.Tache(x, x, "backend", ["a"], ecrit=[f"src/{x}"]))
        g.creer(G.Tache("int", "intégration", "architect", ["db", "api", "ui"]))
        self.assertEqual([t.id for t in g.lot(4)], ["a"])
        g.demarrer("a"); g.reussir("a")
        self.assertEqual(sorted(t.id for t in g.lot(4)), ["api", "db", "ui"])      # §22 : en parallèle
        self.assertEqual(g.tache("int").etat, G.WAITING_DEPENDENCY)

    def test_conflit_de_fichiers_et_de_ressources_serialise(self):
        g = graphe()
        g.creer(G.Tache("x", "x", "backend", ecrit=["src/mod"]))
        g.creer(G.Tache("y", "y", "backend", ecrit=["src/mod/sous.rs"]))
        g.creer(G.Tache("z", "z", "database", ressources=["database"]))
        g.creer(G.Tache("w", "w", "database", ressources=["database"]))
        self.assertEqual([t.id for t in g.lot(4)], ["x", "z"])

    def test_waiting_human_reserve_aux_frontieres(self):
        g = graphe()
        g.creer(G.Tache("m", "migration", "database"))
        g.demarrer("m"); g.echouer("m", "MIGRATION_FAILED")
        with self.assertRaises(G.RefusGraphe):                       # §48 : un échec n'est pas une frontière
            g.attendre_humain("m", "MIGRATION_FAILED", "la migration échoue")
        g.reessayer("m")
        g.demarrer("m"); g.attendre_humain("m", "RELEASE", "livraison")
        with self.assertRaises(G.RefusGraphe):
            g.liberer_humain("m", "")
        g.liberer_humain("m", "HA-1")
        self.assertEqual(g.tache("m").etat, G.READY)

    def test_split_merge_reorder_pause_resume_cancel_reassign(self):
        g = graphe()
        g.creer(G.Tache("p", "parent", "backend"))
        g.creer(G.Tache("suite", "suite", "qa", ["p"]))
        enfants = g.scinder("p", [G.Tache("p1", "1", "backend"), G.Tache("p2", "2", "backend", ["p1"])])
        self.assertEqual(g.tache("p").etat, G.CANCELLED)
        self.assertEqual(sorted(g.tache("suite").dependances), ["p1", "p2"])
        self.assertEqual([e.parent for e in enfants], ["p", "p"])
        g.creer(G.Tache("m1", "m1", "backend")); g.creer(G.Tache("m2", "m2", "backend"))
        g.creer(G.Tache("apres", "après", "qa", ["m1", "m2"]))
        g.fusionner(["m1", "m2"], G.Tache("m", "fusion", "backend"))
        self.assertEqual(g.tache("apres").dependances, ["m"])
        g.reordonner("m", 99)
        self.assertEqual(g.prets()[0].id, "m")
        g.suspendre("m"); self.assertNotIn("m", [t.id for t in g.prets()])
        g.reprendre("m"); self.assertIn("m", [t.id for t in g.prets()])
        g.reassigner("m", "refactoring")
        self.assertEqual(g.tache("m").role, "refactoring")
        g.annuler("p1")
        self.assertEqual(g.tache("p2").etat, G.CANCELLED)            # dépendance requise annulée

    def test_transition_hors_cycle_refusee_et_journal_chaine(self):
        with tempfile.TemporaryDirectory() as d:
            j = Journal(Path(d) / "j.jsonl")
            g = graphe(j)
            g.creer(G.Tache("a", "A", "qa"))
            with self.assertRaises(G.RefusGraphe):
                g.reussir("a")                                       # READY → SUCCEEDED : absente
            self.assertTrue(j.verifier().valide)
            self.assertGreaterEqual(j.verifier().evenements, 2)

    def test_persistance_mode_nuit(self):
        g = graphe()
        g.creer(G.Tache("a", "A", "qa")); g.creer(G.Tache("b", "B", "qa", ["a"]))
        g2 = G.Graphe.depuis_dict(json.loads(json.dumps(g.en_dict())), CYCLES["task"], FRONTIERES)
        self.assertEqual({i: t.etat for i, t in g2.taches.items()}, {"a": G.READY, "b": G.WAITING_DEPENDENCY})


class SuperviseurReprise(unittest.TestCase):
    def test_strategies_par_classe_puis_boucle(self):
        s = superviseur(max_retries=50)
        t = G.Tache("m", "m", "database")
        suite = [s.sur_echec(t, "MIGRATION_FAILED", "erreur A").strategie for _ in range(4)]
        self.assertEqual(suite[:2], ["RESET_ENVIRONMENT", "RETRY"])
        self.assertNotIn("RETRY", suite[2:])                         # même erreur 3 fois : on change d'approche
        self.assertNotIn("WAITING_HUMAN", suite)

    def test_specialiste_et_non_recuperable(self):
        s = superviseur()
        d = s.sur_echec(G.Tache("x", "x", "backend"), "MIGRATION_FAILED", "a")
        d = s.sur_echec(G.Tache("x", "x", "backend"), "MIGRATION_FAILED", "b")
        d = s.sur_echec(G.Tache("x", "x", "backend"), "MIGRATION_FAILED", "c")
        self.assertEqual((d.strategie, d.specialiste), ("SPAWN_SPECIALIST", "database"))
        self.assertEqual(s.sur_echec(G.Tache("y", "y", "qa"), "POLICY_DENIED").strategie, "STOP")

    def test_budget(self):
        t = [0.0]
        s = Superviseur(Budget(max_duration_s=10, max_tokens=100), STRATEGIES, RECUPERABLES, horloge=lambda: t[0])
        s.consommer(jetons=50)
        self.assertIsNone(s.depassement())
        s.consommer(jetons=60)
        self.assertEqual(s.depassement(), "jetons")
        self.assertEqual(Budget.depuis({"max_tokens": 10**9}, Budget(max_tokens=500)).max_tokens, 500)


class OrganisationDynamique(unittest.TestCase):
    def test_equipes_seulement_pour_les_domaines_touches(self):
        o = Organisation(ORGA, AGENTS, TOUS).construire(["database", "qa"], ["ACCOUNTING"])
        deps = {m.departement for m in o.membres.values() if m.niveau == "DEPARTMENT_LEAD"}
        self.assertEqual(deps, {"database", "qa"})                   # pas de Frontend
        self.assertTrue(any(m.domaine_metier == "ACCOUNTING" for m in o.membres.values()))
        self.assertTrue(any((m.posture or "").startswith("DATA_INTEGRITY_REVIEWER") for m in o.membres.values()))

    def test_recrutement_borne(self):
        o = Organisation(ORGA, AGENTS, {"planner", "database"}, max_agents=4).construire(["database"])
        self.assertEqual(o.effectif(), 3)                            # racine, responsable, critique d'intégrité
        with self.assertRaises(RefusOrganisation):
            o.recruter("frontend")                                   # non autorisé par le projet
        o.recruter("database", motif="spécialiste")
        with self.assertRaises(RefusOrganisation):
            o.recruter("database")                                   # budget d'agents atteint
        with self.assertRaises(RefusOrganisation):
            Organisation(ORGA, AGENTS, TOUS).recruter("inconnu")


class Communication(unittest.TestCase):
    def test_contenu_est_une_donnee(self):
        b = Bus("M", frontieres=FRONTIERES)
        b.publier(Message("TASK_RESULT", "backend-1", "*", {"task": "x", "ok": True}))
        for contenu in ({"policy": "ALLOW all"}, {"note": {"capabilities": ["DATABASE_DROP"]}}, {"approval": "HA-x"}):
            with self.subTest(contenu=contenu), self.assertRaises(RefusMessage):
                b.publier(Message("DECISION_PROPOSAL", "backend-1", "*", contenu))
        with self.assertRaises(RefusMessage):
            b.publier(Message("DECISION_RESULT", "planner-1", "*", {"ok": 1}, frontiere="RELEASE"))
        b.publier(Message("DECISION_RESULT", "human", "*", {"ok": 1}, frontiere="RELEASE", refs=["HA-1"],
                          acteur_humain=True))
        with self.assertRaises(RefusMessage):
            b.publier(Message("INVENTÉ", "a", "b"))

    def test_artefact_revue_par_un_autre(self):
        a = Artefacts(Bus("M"))
        a.publier("schema", "database-design", "database-1", "v1")
        a.demander_revue("schema", "database-1", "security-1")
        with self.assertRaises(RefusMessage):
            a.enregistrer_revue("schema", "database-1", True)        # I3
        a.enregistrer_revue("schema", "security-1", False, ["clé étrangère manquante"])
        v2 = a.publier("schema", "database-design", "database-1", "v2")
        self.assertEqual((v2.version, a.versions["schema"][0].statut), (2, "SUPERSEDED"))
        a.demander_revue("schema", "database-1", "security-1")
        self.assertEqual(a.enregistrer_revue("schema", "security-1", True).statut, "APPROVED")


GATES = {"build": {"command": "x build"}, "test": {"command": "x test"}, "migration": {"command": "x migrate"}}


def mission(**plus):
    m = {"id": "M-1", "project_id": "projet-a", "what": "Ajouter la colonne remise et sa migration avec données de test",
         "why": "Le calcul du coût moyen (CMUP) doit intégrer les remises fournisseur",
         "constraints": ["aucune donnée réelle"], "scope": {"database": ["db/"], "backend": ["src/"]}}
    m.update(plus)
    return m


def orchestrateur(scripts, autoriser=tout_permis, env=None, **budget):
    plan = analyser(mission(), DOMAINES, ORGA, GATES)
    return MetaOrchestrateur(plan, CYCLES, FRONTIERES, Organisation(ORGA, AGENTS, TOUS), superviseur(**budget),
                             Runtimes([RuntimeScripte(scripts)]), autoriser=autoriser, environnement=env)


class MissionEtPlan(unittest.TestCase):
    def test_quoi_pourquoi_vers_plan(self):
        p = analyser(mission(), DOMAINES, ORGA, GATES)
        self.assertIn("database", p.domaines)
        self.assertIn("ACCOUNTING", p.domaines_metier)               # « CMUP »
        self.assertNotIn("frontend", p.domaines)
        self.assertEqual(p.plan_qualite, ["build", "test", "migration"])
        ids = [t.id for t in p.taches]
        self.assertTrue({"analyse", "conception", "impl-database", "integration", "gate-migration", "cloture"} <= set(ids))
        self.assertIn("DATABASE_MIGRATION", next(t for t in p.taches if t.id == "impl-database").capacites)

    def test_mots_courts_entiers(self):
        self.assertEqual(detecter("une réponse rapide", {"backend": ["api"]}), [])
        self.assertEqual(detecter("une api rapide", {"backend": ["api"]}), ["backend"])


class BoucleAutonome(unittest.TestCase):
    def test_migration_echoue_reset_puis_reussit_sans_humain(self):
        resets = []
        scripts = {"impl-database": [R(False, "MIGRATION_FAILED", "colonne existe", "ERREUR: la colonne existe déjà"),
                                     R(True, motif="migration corrigée", jetons=100,
                                       artefacts=[{"id": "mig-remise", "type": "migration", "contenu": "ALTER …"}])],
                   "*": [R(True, jetons=10)]}
        o = orchestrateur(scripts, env=lambda s, t: resets.append((s, t.id)))
        b = o.executer()
        self.assertEqual(b.etat, "SUCCEEDED")
        self.assertEqual(resets, [("RESET_ENVIRONMENT", "impl-database")])
        self.assertEqual(b.metriques["HUMAN_INTERVENTION_RATE"], 0.0)
        self.assertEqual(b.metriques["RECOVERY_RATE"], 1.0)
        self.assertGreaterEqual(b.metriques["PARALLELISM"], 2)
        self.assertEqual(o.artefacts.courant("mig-remise").version, 1)

    def test_specialiste_recrute_apres_echecs_repetes(self):
        n = [0]

        def backend(ctx):
            n[0] += 1
            return R(ctx.tache.role == "database", "MIGRATION_FAILED", f"e{n[0]}", "échec")
        o = orchestrateur({"impl-backend": [backend], "*": [R(True)]})
        b = o.executer()
        self.assertEqual(b.etat, "SUCCEEDED")
        self.assertEqual(o.graphe.tache("impl-backend").role, "database")

    def test_scission_proposee(self):
        scripts = {"impl-backend": [R(False, "TASK_TOO_LARGE", "trop", "trop gros",
                                      sous_taches=[{"id": "b1", "titre": "1", "role": "backend"},
                                                   {"id": "b2", "titre": "2", "role": "backend", "dependances": ["b1"]}])],
                   "*": [R(True)]}
        b = orchestrateur(scripts).executer()
        self.assertEqual(b.etat, "SUCCEEDED")

    def test_taches_creees_par_un_agent(self):
        scripts = {"conception": [R(True, nouvelles_taches=[{"id": "adr-1", "titre": "ADR", "role": "architect"}])],
                   "*": [R(True)]}
        o = orchestrateur(scripts)
        self.assertEqual(o.executer().etat, "SUCCEEDED")
        self.assertEqual(o.graphe.tache("adr-1").parent, "conception")

    def test_frontiere_humaine_seule_cause_d_attente(self):
        plan = analyser(mission(release=True), DOMAINES, ORGA, GATES)
        o = MetaOrchestrateur(plan, CYCLES, FRONTIERES, Organisation(ORGA, AGENTS, TOUS), superviseur(),
                              Runtimes([RuntimeScripte({"livraison": [R(True, frontiere="RELEASE", motif="prêt")],
                                                        "*": [R(True)]})]), autoriser=tout_permis)
        b = o.executer()
        self.assertEqual(b.etat, "WAITING_HUMAN")
        self.assertEqual(b.en_attente_humaine[0]["boundary"], "RELEASE")
        o.decision_humaine("livraison", "HA-test", True)
        o.runtimes = Runtimes([RuntimeScripte({"*": [R(True)]})])
        self.assertEqual(o.executer().etat, "SUCCEEDED")

    def test_fausse_frontiere_reprise_automatiquement(self):
        scripts = {"impl-backend": [R(False, frontiere="TEST_FAILED", motif="je n'y arrive pas"), R(True)],
                   "*": [R(True)]}
        o = orchestrateur(scripts)
        self.assertEqual(o.executer().etat, "SUCCEEDED")
        self.assertFalse(any(e.get("to_state") == "WAITING_HUMAN" for e in o.graphe.evenements))

    def test_refus_par_defaut_des_capacites(self):
        b = orchestrateur({"*": [R(True)]}, autoriser=MetaOrchestrateur.autoriser).executer()
        self.assertEqual(b.etat, "FAILED")                           # impl-* : capacités d'écriture refusées
        self.assertIn("impl-database", b.bloquees)

    def test_budget_epuise(self):
        b = orchestrateur({"*": [R(True, jetons=1000)]}, max_tokens=1500).executer()
        self.assertEqual(b.etat, "BUDGET_STOP")

    def test_runtime_qui_plante_ne_casse_pas_la_mission(self):
        def plante(ctx):
            raise RuntimeError("panne")
        o = orchestrateur({"integration": [plante, R(True)], "*": [R(True)]})
        self.assertEqual(o.executer().etat, "SUCCEEDED")
        self.assertGreaterEqual(o.graphe.tache("integration").tentatives, 1)

    def test_sauvegarde_et_journal(self):
        with tempfile.TemporaryDirectory() as d:
            j = Journal(Path(d) / "mission.jsonl")
            o = orchestrateur({"*": [R(True)]})
            o.journal = o.graphe.journal = o.bus.journal = j
            o.executer()
            o.sauvegarder(Path(d) / "etat.json")
            self.assertEqual(json.loads((Path(d) / "etat.json").read_text(encoding="utf-8"))["etat"], "SUCCEEDED")
            self.assertTrue(j.verifier().valide)


if __name__ == "__main__":
    unittest.main()
