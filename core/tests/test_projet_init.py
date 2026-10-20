"""Rattachement d'un projet à la Factory (`factory project init`, ADR-0001) : fichiers posés, manifest valide, jamais
d'écrasement, refus en session d'agent. Tout est écrit dans des dossiers temporaires (Factory et projet de test)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from fournisseurs import projet_init as P
from noyau.registre import charger, valider_manifest


class Rattachement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = charger(FACTORY)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.factory, self.projet = t / "factory", t / "projet"
        (self.factory / "registry" / "projects").mkdir(parents=True)
        (self.projet / "docs").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def init(self, **k):
        return P.initialiser(self.factory, self.reg, self.projet, k.get("ident", "projet-essai"), "Projet essai", "2026-10-19")

    def test_fichiers_poses_et_manifest_valide(self):
        ecrits = self.init()
        self.assertEqual({p.name for p in ecrits}, {"factory.yaml", "CLAUDE.md", "settings.json", "project.yaml"})
        doc = yaml.safe_load((self.projet / "factory.yaml").read_text(encoding="utf-8"))
        self.assertEqual(valider_manifest(self.reg, doc, "factory.yaml").statut, "VALID")
        self.assertEqual(doc["project"]["paths"]["status"], "PROPOSED")             # chemins non normatifs (M2)
        carte = yaml.safe_load((self.factory / "registry/projects/projet-essai/project.yaml").read_text(encoding="utf-8"))
        self.assertEqual((carte["id"], carte["lifecycle"]["state"], carte["manifest"]["path"]),
                         ("projet-essai", "REGISTERED", "factory.yaml"))
        self.assertEqual(carte["root"]["path"], self.projet.resolve().as_posix())

    def test_contexte_et_gardes(self):
        self.init()
        ctx = (self.projet / "CLAUDE.md").read_text(encoding="utf-8")
        for attendu in ("validation du Factory Owner entre chaque étape", "Décisions réservées au Factory Owner",
                        "Aucun code, aucune migration", "factory_approve.py --ouvertes"):
            self.assertIn(attendu, ctx)
        reglages = json.loads((self.projet / ".claude" / "settings.json").read_text(encoding="utf-8"))
        commande = reglages["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("garde_approbations.py", commande)
        self.assertIn(self.factory.resolve().as_posix(), commande)                    # chemin absolu de la Factory
        self.assertTrue(any("approvals/human" in r for r in reglages["permissions"]["deny"]))

    def test_jamais_d_ecrasement(self):
        (self.projet / "CLAUDE.md").write_text("mon contexte", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "jamais écrasés"):
            self.init()
        self.assertEqual((self.projet / "CLAUDE.md").read_text(encoding="utf-8"), "mon contexte")
        self.assertFalse((self.projet / "factory.yaml").exists())                    # rien d'écrit à moitié

    def test_refus(self):
        with self.assertRaisesRegex(ValueError, "identifiant"):
            self.init(ident="GMAO !")
        with self.assertRaisesRegex(ValueError, "déjà inscrit"):
            self.init(ident="gestionfil")                                           # carte existante au registre
        with self.assertRaisesRegex(ValueError, "dans la Factory"):
            P.initialiser(self.factory, self.reg, self.factory / "registry", "x-1", "X", "2026-10-19")
        with self.assertRaisesRegex(ValueError, "introuvable"):
            P.initialiser(self.factory, self.reg, self.projet / "absent", "x-2", "X", "2026-10-19")

    def test_refus_en_session_d_agent(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDECODE="1")
        r = subprocess.run([sys.executable, "-P", str(FACTORY / "factory.py"), "project", "init", str(self.projet),
                            "--id", "gmao", "--nom", "GMAO"], capture_output=True, text=True, encoding="utf-8",
                           timeout=120, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("acte du Factory Owner", r.stdout)
        self.assertFalse((self.projet / "factory.yaml").exists())


if __name__ == "__main__":
    unittest.main()
