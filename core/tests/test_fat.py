"""Factory Acceptance Tests (jalon J9) : on essaie de casser la Factory, avec ses politiques et son registre RÉELS.

Les dix essais du Factory Owner (15/10/2026) + ceux du guide d'utilisation (§16, §19–§21). Chaque test porte le
numéro de l'essai. Un échec ici interdit de déclarer la Factory opérationnelle.
"""
import copy
import json
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY
from tests.test_etats import Base as BaseEtats
from tests.test_politique import Base as BasePolitique
from noyau import sauvegarde
from noyau.etats import APPLIED, REFUSED, WAITING_HUMAN
from noyau.politique import ALLOW, APPROVAL_REQUIRED, DENY
from noyau.registre import charger


class EssaisPolitique(BasePolitique):
    def test_fat01_agent_lit_env(self):
        self.decider(self.demande(action="read", resource={"kind": "path", "path": ".env"}), DENY, "R23")

    def test_fat02_agent_c2_tente_c4(self):
        self.decider(self.demande(action="delete"), DENY)                          # suppression = humain
        d = self.demande()
        d["ticket"]["criticality"] = "C4"
        self.decider(d, DENY, "R08")                                                # au-delà du maximum C2

    def test_fat03_sortie_de_project_root(self):
        self.decider(self.demande(resource={"kind": "path", "path": "../projet-b/src/x.py"}), DENY, "R22")

    def test_fat04_modification_hors_ticket(self):
        self.decider(self.demande(resource={"kind": "path", "path": "tests/x.py"}), DENY, "R25")

    def test_fat05a_c3_sans_porte_humaine(self):
        d = self.demande(actor={"type": "agent", "id": "agent-test"})
        d["ticket"]["criticality"] = "C3"
        self.decider(d, APPROVAL_REQUIRED)

    def test_fat09b_mcp_non_declare(self):
        self.decider(self.demande(action="use_mcp", mcp="mcp-pirate", resource={"kind": "mcp"}), DENY, "R15")

    def test_guide16_jamais_c4_vers_c2(self):
        d = self.demande(actor={"type": "agent", "id": "agent-test"}, criticality="C2")
        d["ticket"]["criticality"] = "C4"
        self.decider(d, DENY, "R07")

    def test_guide19_isolation_entre_projets(self):
        d = self.demande(action="read", resource={"kind": "path", "path": str(self.racine_b / "src" / "x.py")})
        self.decider(d, DENY, "R22")
        d = self.demande(project_id="project-b", action="read",
                         resource={"kind": "path", "path": str(self.racine_a / "src" / "x.py")})
        d["ticket"]["project_id"] = "project-b"
        self.moteur.projets["project-b"].manifest["agents"]["allowed"].append("backend")
        self.decider(d, DENY)

    def test_guide20_c4_sans_reponse_jamais_approuve(self):
        d = self.demande(actor={"type": "agent", "id": "agent-test"})
        d["ticket"]["criticality"] = "C4"
        for _ in range(3):                                                          # le temps ne vaut pas accord
            self.assertEqual(self.moteur.decider(d).decision, APPROVAL_REQUIRED)


class EssaisEtats(BaseEtats):
    def test_fat05b_c3_sans_porte_pas_de_fusion(self):
        r = self.m.transitionner("ticket", self.ticket("READY_TO_MERGE", "C3"), "MERGED", {"type": "agent", "id": "a"},
                                 preuves=[self.preuve()])
        self.assertEqual(r.statut, REFUSED)
        r = self.m.transitionner("ticket", self.ticket("HUMAN_APPROVAL", "C3"), "MERGED", {"type": "agent", "id": "a"},
                                 preuves=[self.preuve()])
        self.assertEqual(r.statut, WAITING_HUMAN)

    def test_fat07_ci_en_echec_pas_de_fusion(self):
        p = self.preuve()
        p.update(exit_code=1, result="FAILURE")
        r = self.m.transitionner("ticket", self.ticket("READY_TO_MERGE"), "MERGED", {"type": "agent", "id": "a"}, preuves=[p])
        self.assertEqual(r.statut, REFUSED)

    def test_fat08_relecteur_auteur(self):
        r = self.m.transitionner("ticket", self.ticket("CODE_REVIEW"), "QA", {"type": "agent", "id": "backend"},
                                 preuves=[self.preuve("REVIEW", relecteur="backend")])
        self.assertEqual(r.statut, REFUSED)

    def test_guide21_declaration_n_est_pas_une_preuve(self):
        r = self.m.transitionner("ticket", self.ticket("QA"), "ACCEPTED", {"type": "agent", "id": "a"},
                                 preuves=[{"type": "TEST", "result": "SUCCESS", "source": "tests passed"}])
        self.assertEqual(r.statut, REFUSED)


class EssaisRegistre(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = charger(FACTORY)

    def test_fat06_outil_declare_non_verifie_jamais_actif(self):
        outil = copy.deepcopy(self.reg.objets["tools"]["gitleaks"])            # CANDIDATE, absent du poste
        outil["lifecycle"] = "ACTIVE"
        v = self.reg.validateur.valider("tool", outil, "fat06")
        self.assertEqual(v.statut, "REJECTED")
        self.assertIn("ACTIVE_WITHOUT_APPROVAL", {d.code for d in v.defauts})
        for type_ in ("tools", "mcp", "agents", "models"):
            for o in self.reg.objets[type_].values():
                if o.get("lifecycle") in ("ACTIVE", "DEPLOYED", "AUTHORIZED_FOR_PROJECT"):
                    self.fail(f"{o['id']} actif sans parcours d'approbation")

    def test_fat09a_mcp_avec_permission_non_declaree(self):
        mcp = copy.deepcopy(self.reg.objets["mcp"]["dbhub"])
        mcp["production"]["write"] = True
        self.assertEqual(self.reg.validateur.valider("mcp", mcp, "fat09").statut, "REJECTED")
        mcp = copy.deepcopy(self.reg.objets["mcp"]["dbhub"])
        mcp["lifecycle"] = "APPROVED"                                            # approuvé sans approbation
        self.assertEqual(self.reg.validateur.valider("mcp", mcp, "fat09").statut, "REJECTED")


class EssaiReprise(unittest.TestCase):
    def test_fat10_factory_restauree_depuis_la_sauvegarde(self):
        pol = yaml.safe_load((FACTORY / "policies" / "backup.yaml").read_text(encoding="utf-8"))
        dest = Path(pol["destination"])
        archives = sorted(dest.glob(pol["archive_pattern"])) if dest.is_dir() else []
        if not archives:
            self.skipTest("aucune sauvegarde sur ce poste")
        import importlib.util
        spec = importlib.util.spec_from_file_location("factory_backup", FACTORY / "scripts" / "factory_backup.py")
        outil = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(outil)
        r = sauvegarde.tester_restauration(archives[-1], outil.revalider)
        self.assertEqual(r.statut, "OK", r.details)


if __name__ == "__main__":
    unittest.main()
