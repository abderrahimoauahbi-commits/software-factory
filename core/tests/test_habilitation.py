"""Habilitation définitive d'un agent (Playbook v3.3 §12.6 ; étape G4) : état du registre ET approbation humaine W1 du
bloc `habilitation`, lié aux preuves d'évaluation. Enregistrements fabriqués dans un dossier temporaire (doubles de
la commande humaine) : le test prouve la vérification, jamais la création d'une décision."""
import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from tests.aide import FACTORY, habilitation_de_test

from noyau import contexte
from noyau.approbation import CANAL, TYPE, Magasin, canonique, empreinte, empreinte_enregistrement
from noyau.politique import contexte_habilitation_definitive

LECTURE = {"actor": {"type": "agent", "id": "backend"}, "project_id": "gestionfil", "action": "read",
           "ticket": {"id": "T-X", "project_id": "gestionfil", "criticality": "C1"},
           "resource": {"path": "backend/src/main.rs"}}
ECRITURE_C2 = dict(LECTURE, action="write", ticket={"id": "T-X", "project_id": "gestionfil", "criticality": "C2"})


class HabilitationDefinitive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, _ = contexte.moteur(FACTORY)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.humain = Path(self.tmp.name)
        self.m = copy.copy(self.base)
        self.m.registre = copy.copy(self.base.registre)
        self.m.registre.objets = dict(self.base.registre.objets, agents=dict(self.base.registre.objets["agents"]))
        self.m.approbations = Magasin(self.humain)
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def fiche(self, **hab):
        h = dict(habilitation_de_test("C2", ("gestionfil",)), **hab)
        self.m.registre.objets["agents"]["backend"] = dict(self.m.registre.objets["agents"]["backend"],
                                                           lifecycle="APPROVED", habilitation=h)
        return h

    def approuver(self, hab, role="factory_owner", decision="APPROVED"):
        self.n += 1
        ctx = contexte_habilitation_definitive("backend", hab)
        e = {"kind": TYPE, "channel": CANAL, "id": f"HA-T{self.n:03d}", "decision": decision, "approver_role": role,
             "context": ctx, "context_sha256": empreinte(ctx), "request": "AR-HABDEF-x.json",
             "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        (self.humain / f"{e['id']}.json").write_text(canonique(e), encoding="utf-8")

    def regle(self, d):
        return self.m.decider(d).regle

    def test_etat_approuve_sans_habilitation_refuse(self):
        self.m.registre.objets["agents"]["backend"] = dict(self.m.registre.objets["agents"]["backend"],
                                                           lifecycle="APPROVED")
        self.assertEqual(self.regle(LECTURE), "R04")

    def test_habilitation_non_approuvee_refusee(self):
        h = self.fiche()
        self.assertEqual(self.regle(LECTURE), "R04")
        self.approuver(h, decision="REJECTED")
        self.assertEqual(self.regle(LECTURE), "R04")
        self.approuver(h, role="reviewer_senior")                          # rôle non admis
        self.assertEqual(self.regle(LECTURE), "R04")

    def test_habilitation_approuvee_passe_le_controle_de_l_agent(self):
        self.approuver(self.fiche())
        self.assertNotEqual(self.regle(LECTURE), "R04")

    def test_plafond_de_l_habilitation_borne_la_criticite(self):
        self.approuver(self.fiche(max_criticality="C1"))
        d = self.m.decider(ECRITURE_C2)
        self.assertEqual(d.regle, "R08")
        self.assertIn("C1", d.motifs[0])

    def test_preuves_modifiees_apres_approbation(self):
        h = self.fiche()
        self.approuver(h)
        self.fiche(evaluation={"suite_sha256": "a" * 64, "report_sha256": "c" * 64})
        self.assertEqual(self.regle(LECTURE), "R04")

    def test_sans_preuve_autre_projet_ou_expiree(self):
        jour = dt.date.today()
        for hab in ({"evaluation": {}}, {"projects": ["autre-projet"]},
                    {"granted_at": (jour - dt.timedelta(days=40)).isoformat(),
                     "expires_at": (jour - dt.timedelta(days=1)).isoformat()},
                    {"expires_at": (jour + dt.timedelta(days=200)).isoformat()}):          # plus long que 92 jours
            with self.subTest(hab=hab):
                self.approuver(self.fiche(**hab))
                self.assertEqual(self.regle(LECTURE), "R04")


if __name__ == "__main__":
    unittest.main()
