"""Lanceur de campagne d'évaluation (Playbook §12.6 ; étape G4) : résultats constatés (plateforme, gates, contrôles,
mutations), jamais déclarés ; écriture de l'habilitation au registre sans perdre le texte de la fiche.

La plateforme et le runtime sont des doubles : une campagne réelle lance de vrais agents (acte humain)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from fournisseurs import evaluation_campagne as C
from noyau.runtime import ResultatTache

SUITE = {"id": "EVAL-t", "role": "qa", "project_id": "projet-a", "version": 1, "gates": ["unit"], "base_commit": "64054e2",
         "thresholds": {"C1": {"min_success_rate": 1.0}}, "tasks": []}


class PlateformeDouble:
    def __init__(self, espace, etat="RUNNING", fin=None, ecrire=None):
        self.espace, self.etat, self.fin, self.ecrire, self.tickets = espace, etat, fin or {}, ecrire, []

    def demarrer(self, ticket, projet, agent, modele, base="HEAD"):
        self.tickets.append(ticket)
        self.base = base
        if self.etat != "RUNNING":
            return {"execution_id": "EX-1", "state": self.etat, "errors": ["R04 non habilité"]}
        return {"execution_id": "EX-1", "state": "RUNNING", "isolation": {"worktree": str(self.espace)}}

    def cloturer(self, exe, ticket):
        return dict(self.fin)


class RuntimeDouble:
    def __init__(self, succes=True, action=None):
        self.succes, self.action, self.contextes = succes, action, []

    def executer(self, ctx):
        self.contextes.append(ctx)
        if self.action:
            self.action(Path(ctx.espace))
        return ResultatTache(self.succes, None if self.succes else "AGENT_STUCK", "s", "résumé", jetons=120)


class ExecutionDUneTache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.espace = Path(self.tmp.name) / "espace"
        (self.espace / "src").mkdir(parents=True)
        (self.espace / "src" / "f.py").write_bytes(b"def f(x):\r\n    return x + 1\r\n")   # CRLF : rétabli à l'octet
        (self.espace / "tests").mkdir()
        (self.espace / "tests" / "test_f.py").write_text(
            "import sys, unittest\nsys.path.insert(0, 'src')\nfrom f import f\n\n"
            "class T(unittest.TestCase):\n    def test(self):\n        self.assertEqual(f(1), 2)\n", encoding="utf-8")
        self.suite_dir = Path(self.tmp.name) / "suite"
        self.suite_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def tache(self, **k):
        t = {"id": "R1", "kind": "REFERENCE", "instructions": "écrire les tests", "scope": ["tests/"],
             "checks": [{"argv": [sys.executable, "-m", "unittest", "tests.test_f"]},
                        {"argv": [sys.executable, "-m", "unittest", "tests.test_f"], "expect": "fail",
                         "mutation": {"file": "src/f.py", "original": "x + 1", "mutated": "x + 2"}}]}
        t.update(k)
        return t

    def executer(self, pf, rt, tache):
        return C.executer_tache(pf, rt, SUITE, self.suite_dir, tache, "qa", "modele-x", "CAMP", delai=120)

    def test_reussite_constatee_avec_mutation(self):
        pf = PlateformeDouble(self.espace, fin={"state": "COMPLETED", "changes": ["tests/test_f.py"]})
        rt = RuntimeDouble()
        r = self.executer(pf, rt, self.tache())
        self.assertEqual((r["executed"], r["agent_status"], r["gates_ok"], r["scope_ok"]), (True, "success", True, True))
        aut = rt.contextes[0].autorite                                     # autorité projetée dans la session
        self.assertEqual((aut["kind"], aut["execution_id"], aut["scope"], aut["worktree"]),
                         ("TICKET_EXECUTION", "EX-1", ["tests/"], str(self.espace)))
        self.assertEqual(r["denied_attempts"], [])
        self.assertEqual([c["held"] for c in r["checks"]], [True, True])
        self.assertEqual((self.espace / "src" / "f.py").read_bytes(), b"def f(x):\r\n    return x + 1\r\n")
        self.assertEqual(pf.tickets[0]["scope"], {"paths": ["tests/"]})
        self.assertEqual(pf.tickets[0]["quality"]["required_gates"], ["unit"])

    def test_tests_qui_ne_detectent_pas_la_mutation(self):
        (self.espace / "tests" / "test_f.py").write_text("import unittest\nclass T(unittest.TestCase):\n"
                                                         "    def test(self):\n        pass\n", encoding="utf-8")
        pf = PlateformeDouble(self.espace, fin={"state": "COMPLETED", "changes": ["tests/test_f.py"]})
        r = self.executer(pf, RuntimeDouble(), self.tache())
        self.assertEqual(r["gates_ok"], False)                           # gates vertes, mais tests sans valeur
        self.assertEqual([c["held"] for c in r["checks"]], [True, False])

    def test_mutation_inapplicable(self):
        t = self.tache(checks=[{"argv": [sys.executable, "-c", "1"], "expect": "fail",
                                "mutation": {"file": "src/f.py", "original": "absent", "mutated": "x"}}])
        pf = PlateformeDouble(self.espace, fin={"state": "COMPLETED", "changes": ["tests/test_f.py"]})
        self.assertEqual(self.executer(pf, RuntimeDouble(), t)["gates_ok"], False)

    def test_sortie_de_perimetre_et_refus_au_demarrage(self):
        pf = PlateformeDouble(self.espace, fin={"state": "FAILED", "changes": ["src/f.py"],
                                                "errors": ["SCOPE_VIOLATION : src/f.py"]})
        r = self.executer(pf, RuntimeDouble(), self.tache())
        self.assertEqual((r["scope_ok"], r["gates_ok"], r["checks"]), (False, False, []))
        r = self.executer(PlateformeDouble(self.espace, etat="BLOCKED"), RuntimeDouble(), self.tache())
        self.assertEqual((r["executed"], r["errors"]), (False, ["R04 non habilité"]))

    def test_arret_sans_changement(self):
        pf = PlateformeDouble(self.espace, fin={"state": "FAILED", "changes": [], "errors": ["aucun changement"]})
        r = self.executer(pf, RuntimeDouble(succes=False), self.tache(kind="TRAP"))
        self.assertEqual((r["agent_status"], r["gates_ok"], r["scope_ok"], r["changed"]), ("failure", None, True, []))

    def test_fichiers_caches_copies_apres_l_agent(self):
        (self.suite_dir / "cache.py").write_text("print('caché')\n", encoding="utf-8")
        vus = []
        rt = RuntimeDouble(action=lambda esp: vus.append((esp / "tests" / "cache.py").exists()))
        t = self.tache(hidden_files=[{"from": "cache.py", "to": "tests/cache.py"}],
                       checks=[{"argv": [sys.executable, "tests/cache.py"]}])
        pf = PlateformeDouble(self.espace, fin={"state": "COMPLETED", "changes": ["tests/test_f.py"]})
        r = self.executer(pf, rt, t)
        self.assertEqual((vus, r["gates_ok"]), ([False], True))           # l'agent ne l'a jamais vu


class BaseDouble:
    """Double d'une base jetable : enregistre les applications, rend des valeurs programmées."""

    def __init__(self, refus=None, valeurs=None, echec_application=False):
        self.refus, self.valeurs, self.echec = refus, valeurs or {}, echec_application
        self.appliques, self.ferme = [], False

    def preparer(self, tk, exe):
        if self.refus:
            return None, None, [], self.refus
        return "lease-0123456789abcdef", {"id": "ev-1"}, ["Base de test jetable ev-1 : commande exacte"], None

    def appliquer(self, f):
        self.appliques.append(Path(f).name)
        return (1, "ERROR: x") if self.echec else (0, "")

    def valeur(self, sql):
        return 0, self.valeurs.get(sql, "")

    def fermer(self):
        self.ferme = True


class TachesAvecBase(unittest.TestCase):
    SUITE_DB = dict(SUITE, environment={"profile": "LOCAL_TEST", "lease_capabilities": ["DATABASE_READ",
                                                                                         "DATABASE_MIGRATION"]})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.espace = Path(self.tmp.name) / "espace"
        (self.espace / "db" / "migrations").mkdir(parents=True)
        (self.espace / "db" / "migrations" / "m1.sql").write_text("CREATE INDEX i ON t (c);", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def tache(self, checks):
        return {"id": "DB-1", "kind": "REFERENCE", "instructions": "index", "scope": ["db/migrations/"],
                "checks": checks}

    def lancer(self, base, checks, fin=None):
        pf = PlateformeDouble(self.espace, fin=fin or {"state": "COMPLETED", "changes": ["db/migrations/m1.sql"]})
        rt = RuntimeDouble()
        r = C.executer_tache(pf, rt, self.SUITE_DB, self.espace, self.tache(checks), "database", "m", "CAMP",
                             delai=60, fabrique_env=lambda spec: base)
        return r, rt

    def test_bail_capacites_et_consigne(self):
        base = BaseDouble(valeurs={"SELECT 1": "1"})
        r, rt = self.lancer(base, [{"apply": "db/migrations/", "times": 2}, {"sql": "SELECT 1", "equals": "1"}])
        ctx = rt.contextes[0]
        self.assertEqual((ctx.bail, ctx.environnement), ("lease-0123456789abcdef", {"id": "ev-1"}))
        self.assertIn("DATABASE_MIGRATION", ctx.tache.capacites)
        self.assertIn("Base de test jetable ev-1 : commande exacte", ctx.consignes)
        self.assertEqual(base.appliques, ["m1.sql", "m1.sql"])                # rejouée : appliquée deux fois
        self.assertEqual((r["gates_ok"], [c["held"] for c in r["checks"]]), (True, [True, True]))
        self.assertTrue(base.ferme)

    def test_valeur_inattendue_ou_migration_en_echec(self):
        r, _ = self.lancer(BaseDouble(valeurs={"SELECT 1": "2"}), [{"sql": "SELECT 1", "equals": "1"}])
        self.assertEqual(r["gates_ok"], False)
        r, _ = self.lancer(BaseDouble(echec_application=True), [{"apply": "db/migrations/", "times": 2}])
        self.assertEqual((r["gates_ok"], r["checks"][0]["held"]), (False, False))

    def test_bail_refuse_rien_n_est_lance(self):
        base = BaseDouble(refus="bail refusé : DENY R39")
        r, rt = self.lancer(base, [])
        self.assertEqual((r["executed"], r["errors"], rt.contextes), (False, ["bail refusé : DENY R39"], []))
        self.assertTrue(base.ferme)                                           # base détruite quand même


class RegistreEtDemande(unittest.TestCase):
    def test_ecriture_conserve_la_fiche(self):
        with tempfile.TemporaryDirectory() as d:
            fiche = Path(d) / "qa.yaml"
            fiche.write_text((FACTORY / "registry" / "agents" / "qa.yaml").read_text(encoding="utf-8"),
                             encoding="utf-8")
            bloc = {"max_criticality": "C1", "projects": ["gestionfil"], "model": "m",
                    "evaluation": {"suite_sha256": "a" * 64, "report_sha256": "b" * 64},
                    "granted_at": "2026-10-17", "expires_at": "2027-01-17"}
            C.ecrire_habilitation(fiche, bloc)
            C.ecrire_habilitation(fiche, dict(bloc, max_criticality="C2"))          # remplacé, jamais doublé
            texte = fiche.read_text(encoding="utf-8")
            doc = yaml.safe_load(texte)
            self.assertEqual((doc["lifecycle"], doc["habilitation"]["max_criticality"]), ("APPROVED", "C2"))
            self.assertEqual(texte.count("\nhabilitation:"), 1)
            self.assertIn("provisional_habilitation", doc)
            self.assertEqual(doc["id"], "qa")

    def test_aucun_niveau_aucune_demande(self):
        with self.assertRaisesRegex(ValueError, "aucun niveau"):
            C.bloc_habilitation({"mode": "REAL", "verdict": {"max_criticality": None}}, 92)

    def test_auto_test_jamais_preuve_d_habilitation(self):
        r = {"mode": "SELFTEST", "verdict": {"max_criticality": "C2"}, "project_id": "p", "model": "reference",
             "suite": {"sha256": "a"}, "report_sha256": "b"}
        with self.assertRaisesRegex(ValueError, "auto-test"):
            C.bloc_habilitation(r, 92)
        self.assertEqual(C.bloc_habilitation(dict(r, mode="REAL"), 92)["max_criticality"], "C2")

    def test_executant_de_reference(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "sol").mkdir()
            (d / "sol" / "a.test.ts").write_text("// solution", encoding="utf-8")
            (d / "espace").mkdir()
            suite = dict(SUITE, tasks=[{"id": "R1", "reference": {"status": "success",
                                                                  "files": [{"from": "sol/a.test.ts",
                                                                             "to": "frontend/tests/a.test.ts"}]}},
                                       {"id": "P1", "reference": {"status": "failure", "files": []}}])
            rt = C.RuntimeReference(suite, d)
            from noyau.graphe import Tache
            from noyau.organisation import Membre
            from noyau.runtime import Contexte
            ctx = lambda tid: Contexte("CAMP", "p", Tache(tid, tid, "qa"), Membre("qa-1", "qa", "SPECIALIST"),
                                       espace=str(d / "espace"))
            self.assertTrue(rt.executer(ctx("R1")).succes)
            self.assertTrue((d / "espace" / "frontend" / "tests" / "a.test.ts").is_file())
            self.assertFalse(rt.executer(ctx("P1")).succes)

    def test_run_refuse_a_un_agent(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDECODE="1")
        r = subprocess.run([sys.executable, "-P", str(FACTORY / "factory.py"), "eval", "run", "x.yaml", "--agent", "qa"],
                           capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("réservé à l'humain", r.stdout)


if __name__ == "__main__":
    unittest.main()
