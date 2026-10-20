"""CLI `factory` (J6) : chaque commande s'exécute, rend le code de sortie documenté et ne modifie rien."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import CORE, FACTORY

CLI = FACTORY / "factory.py"


def lancer(*args, timeout=240):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-P", str(CLI), *args], capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout, env=env)


def instantane():
    etat = {}
    for dossier, sous, fichiers in os.walk(FACTORY):
        sous[:] = [s for s in sous if s not in (".git", "__pycache__", "reports")]
        for f in fichiers:
            p = Path(dossier) / f
            etat[str(p)] = p.stat().st_mtime_ns
    return etat


class Cli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dossier = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fichier(self, nom, contenu):
        p = self.dossier / nom
        p.write_text(json.dumps(contenu) if nom.endswith(".json") else yaml.safe_dump(contenu, allow_unicode=True),
                     encoding="utf-8")
        return str(p)

    def manifest(self, **modifs):
        doc = yaml.safe_load((CORE / "tests" / "fixtures" / "project-a.factory.yaml").read_text(encoding="utf-8"))
        for chemin, val in modifs.items():
            cible = doc["project"]
            *tete, fin = chemin.split(".")
            for k in tete:
                cible = cible[k]
            if val is None:
                cible.pop(fin)
            else:
                cible[fin] = val
        return doc

    def test_validate_registre(self):
        r = lancer("validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VALID", r.stdout)

    def test_validate_fichier_valid_invalid_rejected(self):
        self.assertEqual(lancer("validate", self.fichier("ok.yaml", self.manifest())).returncode, 0)
        self.assertEqual(lancer("validate", self.fichier("sans-id.yaml", self.manifest(id=None))).returncode, 1)
        r = lancer("validate", self.fichier("c5.yaml", self.manifest(**{"lifecycle.criticality_default": "C5"})))
        self.assertEqual(r.returncode, 2)
        self.assertIn("ENUM_VALUE", r.stdout)

    def test_validate_sans_type(self):
        self.assertEqual(lancer("validate", self.fichier("objet.yaml", {"id": "x"})).returncode, 3)

    def test_registry_list(self):
        r = lancer("--json", "registry", "list", "agents")
        self.assertEqual(r.returncode, 0)
        agents = json.loads(r.stdout)
        self.assertEqual(len(agents), 15)
        self.assertTrue(all(a["etat"] == "DISCOVERED" for a in agents))
        self.assertEqual(lancer("registry", "list", "inexistant").returncode, 3)

    def test_policy_check_refus_reel_agent_non_habilite(self):
        d = {"actor": {"type": "agent", "id": "backend"}, "project_id": "gestionfil", "action": "read",
             "ticket": {"id": "T-X", "project_id": "gestionfil", "criticality": "C1"},
             "resource": {"kind": "path", "path": "backend/src/main.rs", "environment": "LOCAL"}}
        r = lancer("--json", "policy", "check", self.fichier("d1.json", d))
        self.assertEqual(r.returncode, 2, r.stdout)
        sortie = json.loads(r.stdout)
        # Avant l'habilitation provisoire : R04 (non habilité). Après : R24 (chemins PROPOSED non normatifs).
        self.assertEqual(sortie["decision"], "DENY")
        self.assertIn(sortie["regle"], ("R04", "R24"))

    def test_chemins_proposes_non_normatifs(self):
        # Règle M2, prouvée sur un brouillon temporaire (indépendante de l'état d'un projet réel).
        from noyau.contexte import manifest_du_projet
        brouillon = self.manifest()
        brouillon["project"]["paths"]["status"] = "PROPOSED"
        chemin = self.fichier("brouillon.yaml", brouillon)
        carte = {"root": {"path": str(self.dossier / "inexistant")}, "manifest": {"path": "factory.yaml", "draft": chemin}}
        bloc, source, notes = manifest_du_projet(Path("/"), carte)
        self.assertEqual(source, "DRAFT")
        self.assertNotIn("paths", bloc)
        self.assertIn("paths PROPOSED écartés : non normatifs (M2)", notes)

    def test_policy_check_manifest_du_projet_fait_foi(self):
        d = {"actor": {"type": "system", "id": "bootstrap"}, "project_id": "gestionfil", "action": "read",
             "resource": {"kind": "path", "path": "backend/src/main.rs", "environment": "LOCAL"}}
        r = lancer("--json", "policy", "check", self.fichier("d2.json", d))
        sortie = json.loads(r.stdout)
        self.assertIn("manifest : PROJECT", sortie["remarques_projets"]["gestionfil"])
        self.assertEqual(sortie["decision"], "ALLOW", sortie["motifs"])            # dans paths.read validés
        d["resource"]["path"] = "backend/.env"
        sortie = json.loads(lancer("--json", "policy", "check", self.fichier("d2b.json", d)).stdout)
        self.assertEqual((sortie["decision"], sortie["regle"]), ("DENY", "R23"))

    def test_policy_check_allow_et_projet_inconnu(self):
        # La CLI n'authentifie personne : une identité humaine déclarée dans la requête est refusée (ADR-0017 D24).
        humain = {"actor": {"type": "human", "id": "o", "role": "factory_owner"}, "action": "change_policy"}
        self.assertEqual(lancer("policy", "check", self.fichier("d3.json", humain)).returncode, 2)
        lecture = {"actor": {"type": "system", "id": "bootstrap"}, "action": "read", "project_id": "gestionfil",
                   "resource": {"path": "db/pg/seed_001_referentiels.sql"}}
        self.assertEqual(lancer("policy", "check", self.fichier("d3b.json", lecture)).returncode, 0)
        self.assertEqual(lancer("policy", "check", self.fichier("d4.json", {"actor": {"type": "agent", "id": "x"},
                                                                          "action": "read", "project_id": "z"})).returncode, 2)

    def test_state_check(self):
        r = lancer("state", "check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("chaîne intacte", r.stdout)

    def test_bootstrap_et_check(self):
        r = lancer("bootstrap", "check", "--sans-rapport")
        self.assertIn(r.returncode, (0, 1, 2))
        self.assertIn("Factory : READY", r.stdout)
        r = lancer("check")
        derniere = r.stdout.splitlines()[-1]
        # L'état de la Factory et l'aptitude à exécuter des agents sont deux verdicts distincts (K5).
        self.assertTrue(derniere.startswith("FACTORY READY"), derniere)
        self.assertIn("exécution d'agents :", derniere)
        self.assertEqual(r.returncode, 0)

    def test_plan_execute_refuse_a_un_agent(self):
        # Garde procédurale (G2) : un marqueur de runtime d'agent suffit à refuser, avant toute lecture du plan.
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDECODE="1")
        r = subprocess.run([sys.executable, "-P", str(CLI), "plan", "execute", "inexistant.json"], capture_output=True,
                           text=True, encoding="utf-8", timeout=120, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("réservée à l'humain", r.stdout)

    def test_commande_inconnue(self):
        self.assertEqual(lancer("approve").returncode, 3)       # aucune approbation par la CLI
        self.assertEqual(lancer("tout").returncode, 3)

    def test_la_cli_ne_modifie_rien(self):
        avant = instantane()
        for args in (("validate",), ("registry", "list"), ("state", "check"), ("bootstrap", "check", "--sans-rapport")):
            lancer(*args)
        self.assertEqual(instantane(), avant)


if __name__ == "__main__":
    unittest.main()
