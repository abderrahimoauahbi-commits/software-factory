"""Runtime des gates du manifest : la gate s'exécute dans son répertoire (cwd), relatif à l'espace, jamais au-dehors."""
import sys
import tempfile
import unittest
from pathlib import Path

from tests.aide import FACTORY  # noqa: F401  (chemins d'import)

from noyau.graphe import Tache
from noyau.organisation import Membre
from noyau.perimetre import Perimetre, Racine, canonique
from noyau.runtime import Contexte, RuntimeGates


class GatesEtRepertoire(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.espace = Path(self.tmp.name) / "espace"
        (self.espace / "backend").mkdir(parents=True)
        (self.espace / "backend" / "verifier.py").write_text("print('dans backend')\n", encoding="utf-8")
        self.preuves = Path(self.tmp.name) / "preuves"

    def tearDown(self):
        self.tmp.cleanup()

    def lancer(self, gate, espace=True):
        gates = {"g": gate}
        perim = Perimetre({"WORKSPACE": Racine("WORKSPACE", canonique(self.espace))}, [], [], [], [])
        rt = RuntimeGates(gates, perim, self.preuves)
        t = Tache("gate-g", "gate g", "qa", entree={"gate": "g"})
        ctx = Contexte("M-1", "projet-a", t, Membre("qa-1", "qa", "SPECIALIST"),
                       espace=str(self.espace) if espace else None)
        return rt.executer(ctx)

    def test_cwd_du_manifest_respecte(self):
        r = self.lancer({"command": f"{sys.executable} verifier.py", "cwd": "backend"})
        self.assertTrue(r.succes, r.motif + r.sortie)
        self.assertIn("dans backend", r.sortie)

    def test_sans_cwd_la_racine_de_l_espace(self):
        r = self.lancer({"command": f"{sys.executable} verifier.py"})      # absent à la racine : échec attendu
        self.assertFalse(r.succes)
        self.assertEqual(r.classe_echec, "QUALITY_GATE_FAILED")

    def test_cwd_hors_de_l_espace_refuse(self):
        for cwd in ("../dehors", "C:/Windows"):
            with self.subTest(cwd=cwd):
                r = self.lancer({"command": f"{sys.executable} verifier.py", "cwd": cwd})
                self.assertEqual((r.succes, r.classe_echec), (False, "TOOL_FAILED"))
        r = self.lancer({"command": f"{sys.executable} verifier.py", "cwd": "backend"}, espace=False)
        self.assertEqual(r.classe_echec, "TOOL_FAILED")


if __name__ == "__main__":
    unittest.main()
