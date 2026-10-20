"""Jalon J3 : le modèle de menaces, le modèle de données et le modèle de confiance sont cohérents et prouvés.

Un contrôle déclaré VERIFIED doit citer un test qui existe vraiment : le modèle ne peut pas affirmer une
protection imaginaire (preuve > déclaration).
"""
import ast
import unittest

import yaml

from tests.aide import CORE, FACTORY

SCHEMAS = CORE / "schemas"


def charger(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def tests_existants() -> set[str]:
    """« chemin::nom » de chaque méthode de test réellement définie dans les dépôts de tests."""
    trouves = set()
    for dossier in (FACTORY / "core" / "tests", FACTORY / "bootstrap" / "tests"):
        for f in dossier.glob("test_*.py"):
            rel = f.relative_to(FACTORY).as_posix()
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"):
                    trouves.add(f"{rel}::{n.name}")
    return trouves


class ModeleDeMenaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = charger(FACTORY / "security" / "threats.yaml")

    def test_chaque_menace_est_complete(self):
        for t in self.m["threats"]:
            with self.subTest(menace=t["id"]):
                for champ in ("step", "threat", "impact", "probability", "controls", "detection", "reaction"):
                    self.assertIn(champ, t)
                self.assertIn(t["step"], self.m["chain"])
                self.assertTrue(t["controls"])

    def test_chaque_etape_de_la_chaine_est_couverte(self):
        couvertes = {t["step"] for t in self.m["threats"]}
        self.assertEqual(set(self.m["chain"]) - couvertes, set())

    def test_un_controle_verifie_cite_un_test_existant(self):
        existants = tests_existants()
        for t in self.m["threats"]:
            for c in t["controls"]:
                with self.subTest(controle=c["id"]):
                    self.assertIn(c["status"], ("VERIFIED", "DECLARED", "PLANNED", "ABSENT"))
                    if c["status"] == "VERIFIED":
                        self.assertIn(c.get("evidence"), existants, "preuve citée introuvable")
                    if c["status"] == "PLANNED":
                        self.assertTrue(c.get("milestone"))

    def test_identifiants_uniques(self):
        ids = [c["id"] for t in self.m["threats"] for c in t["controls"]] + [t["id"] for t in self.m["threats"]]
        self.assertEqual(len(ids), len(set(ids)))


class ModeleDeDonnees(unittest.TestCase):
    def test_relations_entre_objets_definis(self):
        objets = {p.name.split(".")[0] for p in (SCHEMAS / "objects").glob("*.schema.yaml")}
        for r in charger(SCHEMAS / "relations.yaml")["relations"]:
            with self.subTest(relation=f"{r['from']} {r['name']} {r['to']}"):
                self.assertIn(r["from"], objets)
                self.assertIn(r["to"], objets)
                self.assertIn(r["cardinality"], ("1-1", "1-N", "N-1", "N-N"))

    def test_execution_reliee_a_toute_sa_provenance(self):
        # Guide §22 : une exécution se relie au projet (via le ticket), à l'agent, au modèle, aux outils, aux MCP,
        # aux preuves et à sa provenance.
        rel = {(r["from"], r["to"]) for r in charger(SCHEMAS / "relations.yaml")["relations"]}
        for cible in ("ticket", "agent", "model", "tool", "mcp", "provenance"):
            self.assertIn(("execution", cible), rel)
        self.assertIn(("evidence", "execution"), rel)
        self.assertIn(("ticket", "project"), rel)


class ModeleDeConfiance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = charger(SCHEMAS / "trust.yaml")

    def test_verbes_de_pouvoir_reserves(self):
        # I1, I2, I4 : approuver, accorder, changer = humain ; décider = Policy Engine.
        for a in self.t["edges"]:
            with self.subTest(arete=f"{a['from']} {a['verb']} {a['to']}"):
                autorises = self.t["power_verbs"].get(a["verb"])
                if autorises is not None:
                    self.assertIn(a["from"], autorises)

    def test_aucun_pouvoir_pour_les_non_humains(self):
        for source in ("agent", "model", "tool", "mcp", "external_content"):
            verbes = {a["verb"] for a in self.t["edges"] if a["from"] == source}
            self.assertFalse(verbes & set(self.t["power_verbs"]), source)

    def test_donnee_externe_jamais_instruction(self):
        # I5 : la seule arête qui part d'une donnée externe est « informs ».
        self.assertEqual({a["verb"] for a in self.t["edges"] if a["from"] == "external_content"}, {"informs"})

    def test_aretes_entre_acteurs_connus(self):
        acteurs = set(self.t["actors"])
        for a in self.t["edges"]:
            self.assertIn(a["from"], acteurs)

    def test_faiblesse_w1_tracee(self):
        w1 = next(w for w in self.t["weaknesses"] if w["id"] == "W1")
        self.assertEqual(w1["status"], "OPEN")
        self.assertEqual(w1["decision"], "WAITING_HUMAN")


if __name__ == "__main__":
    unittest.main()
