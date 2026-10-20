"""Garde W1 (J7) : la projection dans le runtime d'agent refuse l'écriture des approbations et la commande humaine."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.aide import FACTORY

GARDE = FACTORY / "scripts" / "hooks" / "garde_approbations.py"
HUMAIN = FACTORY / "audit" / "approvals" / "human"


def evaluer(evt):
    r = subprocess.run([sys.executable, "-P", str(GARDE)], input=json.dumps(evt) if not isinstance(evt, str) else evt,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r.returncode, r.stdout


class Garde(unittest.TestCase):
    def test_ecriture_d_approbation_refusee(self):
        for outil in ("Write", "Edit", "MultiEdit"):
            with self.subTest(outil=outil):
                code, sortie = evaluer({"tool_name": outil, "tool_input": {"file_path": str(HUMAIN / "HA-faux.json")}})
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(sortie)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_contournement_par_chemin_relatif_refuse(self):
        chemin = str(FACTORY / "audit" / "approvals" / "requests" / ".." / "human" / "x.json")
        self.assertEqual(evaluer({"tool_name": "Write", "tool_input": {"file_path": chemin}})[0], 2)

    def test_commande_d_approbation_refusee(self):
        for cmd in ("python -P scripts/factory_approve.py audit/approvals/requests/AR-x.json",
                    "py scripts\\\\factory_approve.py x", "echo {} > audit/approvals/human/HA-x.json",
                    "Set-Content audit\\approvals\\human\\HA-x.json '{}'"):
            with self.subTest(commande=cmd):
                self.assertEqual(evaluer({"tool_name": "Bash", "tool_input": {"command": cmd}})[0], 2)
                self.assertEqual(evaluer({"tool_name": "PowerShell", "tool_input": {"command": cmd}})[0], 2)

    def test_travail_ordinaire_permis(self):
        for evt in ({"tool_name": "Write", "tool_input": {"file_path": str(FACTORY / "docs" / "x.md")}},
                    {"tool_name": "Write", "tool_input": {"file_path": str(FACTORY / "audit" / "approvals" / "requests" / "AR-x.json")}},
                    {"tool_name": "Bash", "tool_input": {"command": "python -P factory.py check"}},
                    {"tool_name": "Read", "tool_input": {"file_path": str(HUMAIN / "HA-x.json")}}):
            with self.subTest(evt=evt["tool_name"]):
                self.assertEqual(evaluer(evt)[0], 0)

    def test_evenement_illisible_refuse(self):
        self.assertEqual(evaluer("{pas du json")[0], 2)

    def test_configuration_de_projet_cohérente(self):
        reglages = json.loads((FACTORY / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertTrue(any("approvals/human" in r for r in reglages["permissions"]["deny"]))
        self.assertTrue(any("factory_approve" in r for r in reglages["permissions"]["deny"]))
        self.assertEqual(reglages["permissions"]["disableBypassPermissionsMode"], "disable")
        cmds = [h["command"] for g in reglages["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertTrue(any("garde_approbations.py" in c for c in cmds))


class DiffDeRevue(unittest.TestCase):
    """T-FACTORY-018 : la commande humaine n'affiche que le diff exact couvert par l'empreinte de la demande."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("factory_approve", FACTORY / "scripts" / "factory_approve.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)                      # n'exécute pas main()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.tmp.name)
        (self.dossier / "EX-1-review.diff").write_bytes(b"+ligne\n")      # octets exacts (pas de CRLF)
        self.ctx = {"kind": "CODE_REVIEW", "diff_file": "EX-1-review.diff",
                    "diff_sha256": hashlib.sha256(b"+ligne\n").hexdigest()}

    def tearDown(self):
        self.tmp.cleanup()

    def test_diff_intact(self):
        chemin, motif = self.module.diff_de_revue(self.ctx, self.dossier)
        self.assertIsNone(motif)
        self.assertEqual(chemin.name, "EX-1-review.diff")

    def test_diff_modifie_depuis_la_demande(self):
        (self.dossier / "EX-1-review.diff").write_bytes(b"+autre\n")
        self.assertIn("modifié", self.module.diff_de_revue(self.ctx, self.dossier)[1])

    def test_chemin_hors_des_preuves(self):
        for nom in ("../x.diff", "a/b.diff", "a\\b.diff", ""):
            self.assertIsNotNone(self.module.diff_de_revue({**self.ctx, "diff_file": nom}, self.dossier)[1])


if __name__ == "__main__":
    unittest.main()
