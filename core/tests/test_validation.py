"""Moteur de validation (jalon J2) : cas du guide §14 et contrôles du §30 des Executable Schemas."""
import copy
import unittest

import yaml

from tests.aide import CORE, FACTORY
from noyau.registre import charger, valider_manifest
from noyau.validation import INVALID, REJECTED, VALID, version_compatible


class Manifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = charger(FACTORY)
        with open(CORE / "tests" / "fixtures" / "project-a.factory.yaml", encoding="utf-8") as f:
            cls.base = yaml.safe_load(f)

    def verdict(self, modifier=None):
        doc = copy.deepcopy(self.base)
        if modifier:
            modifier(doc)
        return valider_manifest(self.reg, doc, "test")

    def codes(self, v):
        return {(d.code, d.chemin) for d in v.defauts}

    # --- Guide §14 -------------------------------------------------------------------------------
    def test_projet_valide(self):
        v = self.verdict()
        self.assertEqual(v.statut, VALID, v.defauts)
        self.assertTrue(v.executable)

    def test_projet_sans_id_invalide(self):
        v = self.verdict(lambda d: d["project"].pop("id"))
        self.assertEqual(v.statut, INVALID)
        self.assertIn(("IDENTITY_MISSING", "id"), self.codes(v))
        self.assertFalse(v.executable)

    def test_id_vide_invalide(self):
        v = self.verdict(lambda d: d["project"].__setitem__("id", "  "))
        self.assertEqual(v.statut, INVALID)

    def test_version_de_schema_incompatible_rejetee(self):
        for ver in ("2.0", "1.1", "0.9", "un", None):
            with self.subTest(version=ver):
                v = self.verdict(lambda d: d.__setitem__("schema_version", ver))
                self.assertEqual(v.statut, REJECTED)
                self.assertIn(("VERSION_INCOMPATIBLE", "schema_version"), self.codes(v))

    def test_criticite_c5_rejetee(self):
        v = self.verdict(lambda d: d["project"]["lifecycle"].__setitem__("criticality_default", "C5"))
        self.assertEqual(v.statut, REJECTED)
        self.assertIn(("ENUM_VALUE", "lifecycle.criticality_default"), self.codes(v))

    # --- Autres contrôles du §30 -------------------------------------------------------------------
    def test_champ_requis_absent(self):
        v = self.verdict(lambda d: d["project"].pop("governance"))
        self.assertEqual(v.statut, INVALID)
        self.assertIn(("REQUIRED_MISSING", "governance"), self.codes(v))

    def test_environnement_et_classification_hors_enumeration(self):
        def m(d):
            d["project"]["environments"][0]["type"] = "SANDBOX"
            d["project"]["data"]["classification"] = "SECRETISSIME"
        v = self.verdict(m)
        self.assertEqual(v.statut, REJECTED)
        self.assertTrue({("ENUM_VALUE", "environments[].type"), ("ENUM_VALUE", "data.classification")}
                        <= self.codes(v))

    def test_reference_inconnue(self):
        v = self.verdict(lambda d: d["project"]["tools"]["required"].append("outil-inexistant"))
        self.assertEqual(v.statut, INVALID)
        self.assertIn(("REFERENCE_UNKNOWN", "tools.required[]"), self.codes(v))

    def test_affaiblissement_de_la_securite_rejete(self):
        for chemin in ("production_write", "production_delete", "secrets_allowed", "outbound_network_default",
                       "sensitive_data_to_ai"):
            with self.subTest(champ=chemin):
                v = self.verdict(lambda d: d["project"]["security"].__setitem__(chemin, True))
                self.assertEqual(v.statut, REJECTED)
                self.assertIn(("POLICY_WEAKENING", f"security.{chemin}"), self.codes(v))

    def test_secret_en_clair_rejete(self):
        v = self.verdict(lambda d: d["project"]["repositories"][0].__setitem__(
            "remote", "https://utilisateur:motdepasse@depot.example/projet.git"))
        self.assertEqual(v.statut, REJECTED)
        self.assertIn(("SECRET_IN_CLEAR", "repositories[0].remote"), self.codes(v))

    def test_budget_au_dela_de_trois_tentatives(self):
        v = self.verdict(lambda d: d["project"]["budgets"].__setitem__("max_attempts", 5))
        self.assertEqual(v.statut, REJECTED)
        self.assertIn(("LIMIT_EXCEEDED", "budgets.max_attempts"), self.codes(v))

    def test_version_de_factory_incompatible(self):
        v = self.verdict(lambda d: d["project"]["factory"].__setitem__("minimum_version", "4.0"))
        self.assertEqual(v.statut, REJECTED)
        self.assertIn(("FACTORY_VERSION_INCOMPATIBLE", "factory.minimum_version"), self.codes(v))

    def test_attente_humaine_relevee_sans_invalider(self):
        v = self.verdict(lambda d: d["project"]["data"].__setitem__("classification", "WAITING_HUMAN"))
        self.assertEqual(v.statut, VALID)
        self.assertIn("data.classification", v.attentes)

    def test_chemins_qui_sortent_de_la_racine_rejetes(self):
        for mauvais in ("../voisin/", "/etc/", "C:/Windows/", "C:\\Users\\", "~/.ssh/", "%APPDATA%/x", "$HOME/x",
                        "src/../../x", ""):
            with self.subTest(chemin=mauvais):
                v = self.verdict(lambda d: d["project"]["paths"]["read"].append(mauvais))
                self.assertEqual(v.statut, REJECTED)
                self.assertIn(("PATH_ESCAPE", "paths.read[]"), self.codes(v))

    def test_chemins_relatifs_acceptes(self):
        v = self.verdict(lambda d: d["project"]["paths"]["write"].append("src/module/sous-dossier/"))
        self.assertEqual(v.statut, VALID)

    def test_rejet_prioritaire_sur_invalide(self):
        def m(d):
            d["project"].pop("id")
            d["project"]["lifecycle"]["criticality_default"] = "C5"
        self.assertEqual(self.verdict(m).statut, REJECTED)


class AutresObjets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = charger(FACTORY)

    def test_agent_avec_acces_production_rejete(self):
        agent = copy.deepcopy(next(iter(self.reg.objets["agents"].values())))
        agent["security"]["production_access"] = True
        v = self.reg.validateur.valider("agent", agent, "test")
        self.assertEqual(v.statut, REJECTED)

    def test_mcp_ecriture_production_rejetee(self):
        mcp = copy.deepcopy(next(iter(self.reg.objets["mcp"].values())))
        mcp["production"]["write"] = True
        self.assertEqual(self.reg.validateur.valider("mcp", mcp, "test").statut, REJECTED)

    def test_synonymes_du_master_acceptes(self):
        # M1 (ADR-0005) : REEVALUATED et RETIRED du Master Package valent REEVALUATION et REMOVED.
        outil = copy.deepcopy(self.reg.objets["tools"]["git"])
        for synonyme in ("REEVALUATED", "RETIRED"):
            with self.subTest(etat=synonyme):
                outil["lifecycle"] = synonyme
                v = self.reg.validateur.valider("tool", outil, "test")
                self.assertEqual(v.statut, VALID, v.defauts)
                self.assertTrue(v.remarques)
        outil["lifecycle"] = "RETIRE"            # faute de frappe : jamais un synonyme
        self.assertEqual(self.reg.validateur.valider("tool", outil, "test").statut, REJECTED)

    def test_schema_inconnu(self):
        self.assertEqual(self.reg.validateur.valider("inexistant", {}, "test").statut, REJECTED)

    def test_compatibilite_de_version(self):
        self.assertTrue(version_compatible("1.0", "1.0"))
        self.assertTrue(version_compatible("1.0", "1.2"))      # ancien mais compatible (§29)
        self.assertFalse(version_compatible("1.3", "1.2"))     # plus récent que supporté
        self.assertFalse(version_compatible("2.0", "1.0"))


if __name__ == "__main__":
    unittest.main()
