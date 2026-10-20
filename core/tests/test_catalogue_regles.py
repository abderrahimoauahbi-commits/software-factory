"""Catalogue des règles (ADR-0017 D30, D11 ; étape G1) : correspondance code ↔ catalogue, nature des refus,
explication, refus par défaut d'une règle non cataloguée."""
import copy
import re
import unittest

import yaml

from tests.aide import CORE, FACTORY, habiliter

from noyau import contexte
from noyau.politique import DENY_ABSOLUTE, DENY_BY_POLICY

CATALOGUE = yaml.safe_load((FACTORY / "policies" / "rule-catalog.yaml").read_text(encoding="utf-8"))
SOURCE = (CORE / "noyau" / "politique.py").read_text(encoding="utf-8")


def regles_du_code() -> set[str]:
    return set(re.findall(r'Decision\([A-Z_]+, "(R[0-9A-Z-]+)"', SOURCE)) | set(re.findall(r'\("(R[0-9]+)",', SOURCE))


class CorrespondanceCodeCatalogue(unittest.TestCase):
    def test_toute_regle_du_code_est_cataloguee(self):
        manquantes = regles_du_code() - set(CATALOGUE["rules"])
        self.assertEqual(manquantes, set(), "règles appliquées par le moteur mais absentes du catalogue")

    def test_toute_regle_cataloguee_est_appliquee_ou_declarative(self):
        orphelines = {r for r, v in CATALOGUE["rules"].items() if r not in regles_du_code() and not v.get("declarative")}
        self.assertEqual(orphelines, set(), "règles du catalogue qu'aucun code n'applique")

    def test_structure_de_chaque_regle(self):
        for rid, r in CATALOGUE["rules"].items():
            with self.subTest(regle=rid):
                self.assertTrue(r.get("name") and r.get("why") and r.get("decisions"))
                if "DENY" in r["decisions"]:
                    self.assertIn(r.get("nature"), (DENY_ABSOLUTE, DENY_BY_POLICY))
                    self.assertIn("exception", r)
                if r.get("nature") == DENY_ABSOLUTE:
                    self.assertFalse(r["exception"].get("exceptable"), "un refus absolu ne s'excepte jamais")


class NatureEtExplication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, _ = contexte.moteur(FACTORY)

    def decider(self, **d):
        base = {"actor": {"type": "agent", "id": "backend"}, "project_id": "gestionfil", "action": "read",
                "ticket": {"id": "T-X", "project_id": "gestionfil", "criticality": "C1"},
                "resource": {"path": "backend/src/main.rs"}}
        base.update(d)
        return self.m.decider(base)

    def test_action_inconnue_refus_absolu(self):
        d = self.decider(action="inventee")
        self.assertEqual((d.decision, d.regle, d.nature), ("DENY", "R00", DENY_ABSOLUTE))

    def test_auto_approbation_refus_absolu(self):
        d = self.decider(action="approve")
        self.assertEqual((d.decision, d.regle, d.nature), ("DENY", "R01", DENY_ABSOLUTE))
        self.assertEqual(d.explication["frontiere_humaine"], "PERMISSION_MODEL_CHANGE")

    def test_abaissement_de_criticite_refus_absolu(self):
        m = copy.copy(self.m)
        m.registre = copy.copy(self.m.registre)
        m.registre.objets = dict(self.m.registre.objets, agents=dict(self.m.registre.objets["agents"]))
        habiliter(m, "backend")
        d = m.decider({"actor": {"type": "agent", "id": "backend"}, "project_id": "gestionfil", "action": "read",
                       "ticket": {"id": "T-X", "project_id": "gestionfil", "criticality": "C2"}, "criticality": "C0",
                       "resource": {"path": "backend/src/main.rs"}})
        self.assertEqual((d.decision, d.regle, d.nature), ("DENY", "R07", DENY_ABSOLUTE))

    def test_refus_par_politique_porte_sa_capacite_d_exception(self):
        d = self.decider(action="network", resource={"kind": "network"})
        self.assertEqual((d.decision, d.regle, d.nature), ("DENY", "R03", DENY_BY_POLICY))
        self.assertTrue(d.explication["exception"]["exceptable"])
        self.assertTrue(d.explication["nom"] and d.explication["pourquoi"])

    def test_allow_porte_une_explication_sans_nature(self):
        m = copy.copy(self.m)
        d = m.decider({"actor": {"type": "system", "id": "x"}, "project_id": "gestionfil", "action": "read",
                       "resource": {"path": "db/pg/seed_001_referentiels.sql"}})
        self.assertEqual(d.decision, "ALLOW")
        self.assertIsNone(d.nature)
        self.assertEqual(d.explication["regle"], d.regle)

    def test_regle_non_cataloguee_refus_absolu(self):
        m = copy.copy(self.m)
        m.catalogue = {"rules": {k: v for k, v in CATALOGUE["rules"].items() if k != "R03"}}
        d = m.decider({"actor": {"type": "agent", "id": "backend"}, "project_id": "gestionfil", "action": "network",
                       "ticket": {"id": "T-X", "project_id": "gestionfil", "criticality": "C1"},
                       "resource": {"kind": "network"}})
        self.assertEqual((d.regle, d.nature), ("R03", DENY_ABSOLUTE))
        self.assertIsNone(d.explication)

    def test_sans_catalogue_tout_refus_est_absolu(self):
        m = copy.copy(self.m)
        m.catalogue = {}
        self.assertEqual(m.decider({"action": "x"}).nature, DENY_ABSOLUTE)


if __name__ == "__main__":
    unittest.main()
