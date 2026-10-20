"""Exceptions de politique (ADR-0017 D12, I5, F8 ; étape G1).

Les approbations sont des doubles de la commande humaine, écrits dans un dossier temporaire : le test prouve la
vérification et l'application, pas la création, qui reste un acte humain W1."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from tests.aide import FACTORY

from noyau import contexte
from noyau.approbation import CANAL, TYPE, canonique, empreinte_enregistrement
from noyau.audit import Journal
from noyau.derogations import USAGE, GestionnaireExceptions, RefusException, controle_i5

LECTURE = {"actor": {"type": "system", "id": "bootstrap"}, "project_id": "gestionfil", "action": "read",
           "resource": {"path": "zzz.txt"}}                                    # R24 : hors des chemins lisibles
SUPPRESSION = {"actor": {"type": "agent", "id": "backend"}, "project_id": "gestionfil", "action": "delete",
               "ticket": {"id": "T-X", "project_id": "gestionfil", "criticality": "C1"},
               "resource": {"path": "backend/src/main.rs"}}                    # R03, puis R04 (non habilité)


class Horloge:
    t = dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.t


class Exceptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, _ = contexte.moteur(FACTORY)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.h = Horloge()
        self.journal = Journal(d / "journal.jsonl")
        self.humain = d / "human"
        self.humain.mkdir()
        self.m = copy.copy(self.base)
        self.m.exceptions = GestionnaireExceptions(self.humain, self.journal, self.h)
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def approuver(self, demande, role=None, decision="APPROVED", quand=None, **alterations):
        self.n += 1
        e = {"kind": TYPE, "channel": CANAL, "id": f"HA-T{self.n:03d}", "decision": decision,
             "approver_role": role or demande["roles"][0], "context": demande["context"],
             "context_sha256": demande["context_sha256"], "request": "AR-x.json",
             "created_at": (quand or self.h.t).isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        e.update(alterations)
        (self.humain / f"{e['id']}.json").write_text(canonique(e), encoding="utf-8")
        return demande["context"]["exception_id"]

    def demande(self, d, regle, heures=1, usages=1, motif="analyse ponctuelle"):
        return self.m.exceptions.demande(regle, d, heures, usages, motif, self.m.catalogue)

    def test_sans_exception_le_refus_reste(self):
        dec = self.m.decider(LECTURE)
        self.assertEqual((dec.decision, dec.regle, dec.nature, dec.exceptions), ("DENY", "R24", "DENY_BY_POLICY", None))

    def test_exception_approuvee_leve_sa_regle_pour_sa_portee(self):
        ident = self.approuver(self.demande(LECTURE, "R24"))
        dec = self.m.decider(LECTURE)
        self.assertEqual((dec.decision, dec.exceptions), ("ALLOW", [ident]))
        autre = dict(LECTURE, resource={"path": "yyy.txt"})                     # autre portée : aucune exception
        self.assertEqual(self.m.decider(autre).regle, "R24")

    def test_seule_la_regle_exceptee_est_levee(self):
        self.approuver(self.demande(SUPPRESSION, "R03"))
        dec = self.m.decider(SUPPRESSION)
        self.assertEqual(dec.decision, "DENY")
        self.assertEqual(dec.regle, "R04")                                      # la règle suivante s'applique
        self.assertTrue(dec.exceptions)

    def test_i5_a_la_demande(self):
        with self.assertRaisesRegex(RefusException, "I5"):
            self.demande(LECTURE, "R24", heures=25)                             # capacité : 24 h
        with self.assertRaisesRegex(RefusException, "I5"):
            self.demande(LECTURE, "R24", usages=2)                              # capacité : 1 usage
        with self.assertRaisesRegex(RefusException, "DENY_BY_POLICY"):
            self.demande(LECTURE, "R23")                                        # refus absolu : jamais
        with self.assertRaisesRegex(RefusException, "exceptable"):
            self.demande(LECTURE, "R25")

    def test_i5_a_l_usage_role_et_capacite_courante(self):
        d = self.demande(LECTURE, "R24")
        self.approuver(d, role="reviewer_senior")                              # rôle non admis pour R24
        self.assertEqual(self.m.decider(LECTURE).decision, "DENY")
        self.approuver(d)
        m = copy.copy(self.m)
        cat = copy.deepcopy(self.m.catalogue)
        cat["rules"]["R24"]["exception"]["exceptable"] = False                 # capacité retirée depuis
        m.catalogue = cat
        self.assertEqual(m.decider(LECTURE).decision, "DENY")

    def test_enregistrement_altere_ou_refuse_ignore(self):
        d = self.demande(LECTURE, "R24")
        self.approuver(d, decision="REJECTED")
        self.approuver(d, record_sha256="0" * 64)
        self.approuver(d, channel="fichier")
        faux = copy.deepcopy(d)
        faux["context"]["scope"]["resource"]["path"] = "autre.txt"             # portée changée après la demande
        self.approuver(faux)
        self.assertEqual(self.m.decider(LECTURE).decision, "DENY")

    def test_expiration(self):
        self.approuver(self.demande(LECTURE, "R24", heures=1))
        self.assertEqual(self.m.decider(LECTURE).decision, "ALLOW")
        self.h.t += dt.timedelta(hours=1, seconds=1)
        self.assertEqual(self.m.decider(LECTURE).decision, "DENY")

    def test_usage_consomme_seulement_par_l_appelant_qui_execute(self):
        ident = self.approuver(self.demande(LECTURE, "R24"))
        for _ in range(3):
            self.assertEqual(self.m.decider(LECTURE).decision, "ALLOW")         # qualification : rien consommé
        self.assertEqual(self.m.decider(LECTURE, consommer=True).decision, "ALLOW")
        usages = [json.loads(x) for x in self.journal.chemin.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(u["action"], u["exception_id"]) for u in usages], [(USAGE, ident)])
        self.assertEqual(self.m.decider(LECTURE).decision, "DENY")             # 1 usage au plus
        self.assertTrue(self.journal.verifier().valide)

    def test_revocation(self):
        ident = self.approuver(self.demande(LECTURE, "R24"))
        self.m.exceptions.revoquer(ident, "plus nécessaire", {"type": "agent", "id": "x"})
        self.assertEqual(self.m.decider(LECTURE).decision, "DENY")

    def test_journal_compromis_aucune_exception(self):
        self.approuver(self.demande(LECTURE, "R24"))
        self.m.exceptions.revoquer("PEX-autre", "essai", {"type": "system", "id": "t"})
        lignes = self.journal.chemin.read_text(encoding="utf-8").replace("essai", "ESSAI")
        self.journal.chemin.write_text(lignes, encoding="utf-8")
        self.assertEqual(self.m.decider(LECTURE).decision, "DENY")

    def test_seules_r03_et_r24_sont_exceptables(self):
        exceptables = {r for r, v in self.m.catalogue["rules"].items()
                       if not controle_i5({"rule": r, "duration_hours": 1, "max_uses": 1}, self.m.catalogue)}
        self.assertEqual(exceptables, {"R03", "R24"})


if __name__ == "__main__":
    unittest.main()
