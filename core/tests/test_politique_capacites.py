"""Policy Engine — action use_capability (ADR-0016, règles R30–R39), avec le vrai moteur et la vraie politique
(policies/autonomy.yaml) sur le projet pilote enregistré. Le fournisseur de ressources est un double dont
l'identité peut être falsifiée ; les vérifications d'identité passent par le vrai registre des ressources."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tests.aide import FACTORY, habiliter
from tests.test_environnements import FauxFournisseur

from noyau import contexte
from noyau.ressources import Registre, Ressource


class Capacites(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        racine = Path(self.tmp.name)
        self.f = FauxFournisseur()
        self.envs = racine / "envs"
        self.reg = Registre(racine / "resources", {self.f.id: self.f}, self.envs)
        self.m, _ = contexte.moteur(FACTORY, ressources=self.reg)
        self.jetable = self._ressource("gf-test-db", "LOCAL_TEST")

    def tearDown(self):
        self.tmp.cleanup()

    def _ressource(self, rid, profil, owner="factory", disposable=True, projet="gestionfil", **plus):
        dossier = self.envs / rid
        dossier.mkdir(parents=True, exist_ok=True)
        brut = self.f.creer(dossier, {}, None)
        r = Ressource(rid, "database", projet, rid, profil, owner, disposable, provider=self.f.id,
                      connection=brut["connection"], identity=brut["identity"], **plus)
        return self.reg.enregistrer(r)

    def demande(self, cap="DATABASE_MIGRATION", rid="gf-test-db", agent="database", crit="C1", **plus):
        d = {"actor": {"type": "agent", "id": agent}, "project_id": "gestionfil", "action": "use_capability",
             "capability": cap, "resource": {"id": rid},
             "ticket": {"id": "T-E1", "project_id": "gestionfil", "criticality": crit}, "execution": {"id": "EX"}}
        d.update(plus)
        return self.m.decider(d)

    def assertRegle(self, dec, decision, regle):
        self.assertEqual((dec.decision, dec.regle), (decision, regle), dec.motifs)

    def assertRefus(self, dec, regle):
        """Refus attendu ; un agent non évalué est arrêté plus tôt (R04) dès que la ressource n'est pas jetable."""
        self.assertEqual(dec.decision, "DENY", dec.motifs)
        self.assertIn(dec.regle, ("R04", regle), dec.motifs)

    # ------------------------------------------------------------------ permis
    def test_ressource_jetable_tout_permis_sans_humain(self):
        for cap in ("DATABASE_MIGRATION", "DATABASE_SCHEMA_CHANGE", "DATABASE_RESET", "DATABASE_DROP", "DATABASE_SEED",
                    "DATABASE_WRITE", "DATABASE_READ"):
            with self.subTest(cap=cap):
                self.assertRegle(self.demande(cap), "ALLOW", "R35")      # agent non évalué : le bail le borne

    # ------------------------------------------------------------------ refus
    def test_politique_suspendue(self):
        self.m.autonomie = dict(self.m.autonomie, status="suspended")
        self.assertRefus(self.demande(), "R30")
        habiliter(self.m, "database")
        self.assertRegle(self.demande(), "DENY", "R30")

    def test_sans_registre_des_ressources(self):
        m, _ = contexte.moteur(FACTORY)
        d = self.demande()
        self.assertEqual(m.decider({"actor": {"type": "agent", "id": "database"}, "project_id": "gestionfil",
                                    "action": "use_capability", "capability": "DATABASE_MIGRATION",
                                    "resource": {"id": "gf-test-db"},
                                    "ticket": {"id": "T", "project_id": "gestionfil", "criticality": "C1"}}).decision,
                         "DENY")
        self.assertEqual(d.decision, "ALLOW")

    def test_nom_trompeur_non_enregistre(self):
        self.assertRefus(self.demande(rid="gestionfil_test"), "R32")

    def test_ressource_d_un_autre_projet(self):
        self._ressource("autre-db", "LOCAL_TEST", projet="software-factory")
        self.assertRegle(self.demande(rid="autre-db"), "DENY", "R32")

    def test_ressource_detruite(self):
        self.reg.marquer("gf-test-db", "DESTROYED")
        self.assertRefus(self.demande(), "R32")

    def test_capacite_inconnue_ou_mauvais_genre(self):
        self.assertRegle(self.demande("DATABASE_GOD_MODE"), "DENY", "R31")
        self.assertRegle(self.demande("VCS_COMMIT_LOCAL"), "DENY", "R31")

    def test_production_toujours_refusee(self):
        self._ressource("prod-db", "PRODUCTION", owner="external", disposable=False, classification="CONFIDENTIAL")
        # Agent réellement non habilité : indépendant des habilitations provisoires approuvées dans la vraie Factory.
        agents = self.m.registre.objets["agents"]
        agents["database"] = {k: v for k, v in agents["database"].items() if k != "provisional_habilitation"}
        for cap in ("DATABASE_READ", "DATABASE_DROP"):
            with self.subTest(cap=cap):
                self.assertRegle(self.demande(cap, "prod-db"), "DENY", "R04")   # agent non évalué hors jetable
        habiliter(self.m, "database")
        self.assertRegle(self.demande("DATABASE_READ", "prod-db"), "DENY", "R09")

    def test_profil_non_declare_par_le_projet(self):
        self._ressource("dev-db", "DEV_SHARED", owner="external", disposable=False)
        habiliter(self.m, "database")
        self.assertRegle(self.demande("DATABASE_READ", "dev-db"), "DENY", "R33")

    def test_destructif_hors_ressource_jetable(self):
        self._ressource("reelle-db", "LOCAL_TEST", owner="external", disposable=False)
        habiliter(self.m, "database")
        self.assertRegle(self.demande("DATABASE_DROP", "reelle-db"), "DENY", "R36")

    def test_identite_falsifiee(self):
        r = self.reg.obtenir("gf-test-db")
        self.f.identites[r.connection["port"]] = {"system_identifier": "autre", "data_directory": "x"}
        self.assertRegle(self.demande(), "DENY", "R37")
        self.f.vivantes.clear()                                              # injoignable ≠ supposée bonne
        self.assertRegle(self.demande(), "DENY", "R37")

    def test_donnees_sensibles_approbation(self):
        self._ressource("conf-db", "LOCAL_TEST", classification="CONFIDENTIAL")
        d = self.demande("DATABASE_READ", "conf-db")
        self.assertRegle(d, "APPROVAL_REQUIRED", "R38")
        self.assertIsNotNone(d.approbation_requise)

    def test_capacite_non_declaree_par_la_fiche(self):
        self.assertRegle(self.demande("DATABASE_DROP", agent="qa"), "DENY", "R39")
        self.assertRegle(self.demande("DATABASE_READ", agent="qa"), "ALLOW", "R35")

    def test_ticket_c0_et_abaissement(self):
        self.assertRegle(self.demande(crit="C0"), "DENY", "R07")
        self.assertRegle(self.demande("DATABASE_READ", crit="C0"), "ALLOW", "R35")
        self.assertRegle(self.demande(crit="C2", criticality="C1"), "DENY", "R07")

    def test_acteurs_et_agent_inconnu(self):
        self.assertRegle(self.demande(agent="inconnu"), "DENY", "R04")
        d = self.m.decider({"actor": {"type": "system", "id": "x"}, "project_id": "gestionfil",
                            "action": "use_capability", "capability": "DATABASE_READ", "resource": {"id": "gf-test-db"}})
        self.assertEqual(d.decision, "DENY")

    def test_niveau_a0_lecture_seule(self):
        p = self.m.projets["gestionfil"]
        p.manifest = dict(p.manifest, autonomy={"level": "A0"})
        self.assertRegle(self.demande(), "DENY", "R34")
        self.assertRegle(self.demande("DATABASE_READ"), "ALLOW", "R35")
        p.manifest = dict(p.manifest, autonomy={"level": "A1"})
        self.assertRegle(self.demande(), "APPROVAL_REQUIRED", "R38")

    def test_demande_ne_peut_pas_se_declarer_jetable(self):
        """La nature jetable vient du registre, jamais de la demande."""
        self._ressource("reelle2-db", "LOCAL_TEST", owner="external", disposable=False)
        d = self.demande("DATABASE_DROP", "reelle2-db", resource={"id": "reelle2-db", "disposable": True,
                                                                  "owner": "factory"})
        self.assertEqual(d.decision, "DENY")


if __name__ == "__main__":
    unittest.main()
