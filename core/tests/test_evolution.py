"""Évolution E : runtime d'agent (adaptateur), modèle, connaissance, Project Factory (Master Evolution Prompt v4)."""
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from fournisseurs.runtime_claude_code import RuntimeClaudeCode
from noyau import connaissance as K
from noyau import modeles, projet_factory as PF
from noyau.graphe import Tache
from noyau.organisation import Membre
from noyau.runtime import Contexte


def ctx(tache, espace=None, **plus):
    return Contexte("M-1", "projet-a", tache, Membre("specialist-database-1", "database", "SPECIALIST"),
                    espace=espace, consignes=["Rôle : database."], **plus)


class RuntimeAgentDeCode(unittest.TestCase):
    def test_droits_projetes_depuis_les_capacites(self):
        rt = RuntimeClaudeCode(commandes_permises=["npm test"], a_blanc=True)
        lecture = Tache("r", "revue", "security", capacites=["FILESYSTEM_READ"])
        ecriture = Tache("w", "impl", "database", capacites=["FILESYSTEM_WRITE", "TEST", "DATABASE_MIGRATION"])
        p1, refus = rt.outils(lecture)
        self.assertNotIn("Edit", p1)
        p2, _ = rt.outils(ecriture)
        self.assertIn("Edit", p2)
        self.assertIn("Bash(npm test:*)", p2)
        self.assertIn("PowerShell(npm test:*)", p2)                           # même commande sous l'autre shell
        self.assertTrue(any(" env:*" in p for p in p2))                      # base : point d'entrée Factory seul
        self.assertIn("WebFetch", refus)
        self.assertIn("Bash(psql:*)", refus)

    def test_jamais_sans_espace_ni_contournement(self):
        rt = RuntimeClaudeCode(a_blanc=True)
        t = Tache("w", "impl", "database", capacites=["FILESYSTEM_WRITE"], ecrit=["db/"])
        self.assertEqual(rt.executer(ctx(t)).classe_echec, "TOOL_FAILED")    # pas d'espace isolé
        with tempfile.TemporaryDirectory() as d:
            esp = Path(d) / "espace"
            esp.mkdir()
            r = rt.executer(ctx(t, str(esp), modele="modele-x"))
            argv = json.loads(r.sortie)
            self.assertNotIn("--dangerously-skip-permissions", argv)
            self.assertIn("--strict-mcp-config", argv)                       # MCP refusé par défaut (§34)
            self.assertEqual(argv[argv.index("--model") + 1], "modele-x")
            reglages = json.loads(Path(argv[argv.index("--settings") + 1]).read_text(encoding="utf-8"))
            self.assertEqual(reglages["permissions"]["disableBypassPermissionsMode"], "disable")
            self.assertTrue(any("approvals/human" in r for r in reglages["permissions"]["deny"]))
            self.assertIn("Read(**/agents/evaluations/**)", reglages["permissions"]["deny"])   # solutions cachées (G4)
            consigne = argv[argv.index("-p") + 1]
            self.assertIn("arrête-toi AVANT d'écrire quoi que ce soit", consigne)         # condition d'arrêt (§12.6)

    def test_compte_rendu_oriente_la_reprise_sans_etre_une_preuve(self):
        ok = {"type": "result", "is_error": False, "num_turns": 7, "usage": {"input_tokens": 100, "output_tokens": 50},
              "result": 'fait\n```json\n{"status": "success", "summary": "migration écrite", "new_tasks": []}\n```'}
        r = RuntimeClaudeCode.interpreter(0, json.dumps(ok))
        self.assertTrue(r.succes)
        self.assertEqual((r.jetons, r.appels), (150, 7))
        ko = dict(ok, result='```json\n{"status": "failure", "failure": "migration", "summary": "colonne"}\n```')
        self.assertEqual(RuntimeClaudeCode.interpreter(0, json.dumps(ko)).classe_echec, "MIGRATION_FAILED")
        muet = dict(ok, result="j'ai fini, tout marche")                    # déclaration sans compte rendu
        self.assertFalse(RuntimeClaudeCode.interpreter(0, json.dumps(muet)).succes)
        self.assertEqual(RuntimeClaudeCode.interpreter(1, "pas du json").classe_echec, "TOOL_FAILED")


class SelectionModele(unittest.TestCase):
    MODELES = {
        "fort": {"lifecycle": "APPROVED", "evaluation": {"reasoning": 9, "coding": 8}, "cost": {"output": 10}},
        "econome": {"lifecycle": "APPROVED", "evaluation": {"reasoning": 4, "coding": 6}, "cost": {"output": 0.5}},
        "non-evalue": {"lifecycle": "DISCOVERED", "evaluation": {"reasoning": 10, "coding": 10}},
        "interdit-secu": {"lifecycle": "APPROVED", "evaluation": {"reasoning": 10}, "security": {"prohibited_for": ["security"]}},
    }

    def test_profil_et_approbation(self):
        self.assertEqual(modeles.choisir(self.MODELES, Tache("a", "a", "architect")), "interdit-secu")
        self.assertEqual(modeles.choisir(self.MODELES, Tache("s", "s", "security")), "fort")
        self.assertEqual(modeles.choisir(self.MODELES, Tache("d", "d", "documentation")), "econome")
        self.assertEqual(modeles.choisir(self.MODELES, Tache("s", "s", "security"), {"fort"}), "econome")

    def test_registre_reel_sans_modele_approuve(self):
        reg = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (FACTORY / "registry" / "models").glob("*.yaml")}
        self.assertIsNone(modeles.choisir(reg, Tache("x", "x", "backend")))   # aucun n'est APPROVED : pas d'invention


class Connaissance(unittest.TestCase):
    ORIGINE = {"id": "projet-a", "name": "Projet A", "root": {"path": "C:/depots/projet-a"},
               "environments": [{"hosts": ["10.0.0.7"]}], "private_terms": ["Tissage Nord"]}

    def test_seul_le_generique_passe(self):
        lecon = K.Element("L1", "LESSON", "projet-a", "Une migration se rejoue sur une base vierge avant fusion.")
        self.assertTrue(K.transferable(lecon, self.ORIGINE, "projet-b").transferable)
        for e in (K.Element("x", "BUSINESS_RULE", "projet-a", "remise de 3 %"),
                  K.Element("x", "LESSON", "projet-a", "le serveur 10.0.0.7 tombe le lundi"),
                  K.Element("x", "PATTERN", "projet-a", "chez Tissage Nord on arrondit"),
                  K.Element("x", "PATTERN", "projet-a", "générique", ["BUSINESS_DATA"]),
                  K.Element("x", "LESSON", "projet-a", "password=hunter2-hunter2")):
            with self.subTest(e=e.texte):
                self.assertFalse(K.transferable(e, self.ORIGINE, "projet-b").transferable)

    def test_hierarchie(self):
        self.assertEqual(K.autorite("TEST", "POLICY"), "POLICY")
        self.assertEqual(K.autorite("PROOF", "IMPLEMENTATION"), "IMPLEMENTATION")


class ProjectFactory(unittest.TestCase):
    def test_squelette_sans_ecrasement_et_portee(self):
        with tempfile.TemporaryDirectory() as d:
            crees = PF.squelette(Path(d), "projet-a", "Projet A")
            self.assertTrue((Path(d) / ".factory" / "environments").is_dir())
            self.assertEqual(PF.squelette(Path(d), "projet-a", "Projet A"), [])          # rien d'écrasé
            pj = Path(d) / ".factory" / "project.yaml"
            doc = yaml.safe_load(pj.read_text(encoding="utf-8"))
            doc["capabilities"] = ["BROWSER_TEST"]
            pj.write_text(yaml.safe_dump(doc), encoding="utf-8")
            c = PF.charger(Path(d), "projet-a")
            self.assertEqual(c["capabilities"][0]["scope"], {"project": "projet-a"})
            vues = PF.fusionner_capacites(["BUILD"], {"projet-a": c["capabilities"]}, "projet-b")
            self.assertEqual(vues, ["BUILD"])                                         # jamais globale
            with self.assertRaises(PF.RefusProjet):
                PF.charger(Path(d), "projet-b")
            (Path(d) / ".factory" / "policies" / "x.yaml").write_text("allow: ['*']", encoding="utf-8")
            with self.assertRaises(PF.RefusProjet):
                PF.charger(Path(d), "projet-a")
            self.assertGreater(len(crees), 5)


if __name__ == "__main__":
    unittest.main()
