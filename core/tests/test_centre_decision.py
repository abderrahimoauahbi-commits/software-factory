"""Centre de décision L1 et exécution humaine des plans (ADR-0017 D31, D38, I7, I8 ; étape G2).

Les approbations sont des doubles de la commande humaine, écrits dans un dossier temporaire : les tests prouvent la
lecture, la vérification et l'exécution, jamais la création d'une décision, qui reste un acte humain W1."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

from noyau import centre_decision as C
from noyau import execution_humaine as X
from noyau.approbation import CANAL, TYPE, canonique, empreinte, empreinte_enregistrement
from noyau.audit import Journal

T0 = dt.datetime(2026, 10, 17, 12, tzinfo=dt.timezone.utc)
ROLES = ["factory_owner", "project_owner"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.req, self.hum = d / "requests", d / "human"
        self.req.mkdir()
        self.hum.mkdir()
        self.journal = Journal(d / "journal.jsonl")
        self.travail = d / "travail"
        self.travail.mkdir()
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def deposer(self, demande, nom):
        (self.req / nom).write_text(canonique(demande), encoding="utf-8")

    def decider(self, demande, decision="APPROVED", role="factory_owner", quand=T0, **alterations):
        self.n += 1
        e = {"kind": TYPE, "channel": CANAL, "id": f"HA-T{self.n:03d}", "decision": decision, "approver_role": role,
             "context": demande["context"], "context_sha256": demande["context_sha256"], "request": "AR-x.json",
             "created_at": quand.isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        e.update(alterations)
        (self.hum / f"{e['id']}.json").write_text(canonique(e), encoding="utf-8")
        return e["id"]


def simple(n):
    ctx = {"kind": "TEST", "n": n}
    return {"context": ctx, "context_sha256": empreinte(ctx), "roles": ["factory_owner"], "purpose": f"essai {n}"}


class CentreDeDecision(Base):
    def test_etats(self):
        for i in range(4):
            self.deposer(simple(i), f"AR-{i}.json")
        self.decider(simple(1))
        self.decider(simple(2), decision="REJECTED")
        self.decider(simple(3), record_sha256="0" * 64)                     # enregistrement altéré : ignoré
        etats = {e.nom: e.statut for e in C.etats(self.req, self.hum)}
        self.assertEqual(etats, {"AR-0.json": C.OPEN, "AR-1.json": C.APPROVED, "AR-2.json": C.REJECTED,
                                 "AR-3.json": C.OPEN})

    def test_derniere_decision_l_emporte(self):
        self.deposer(simple(1), "AR-1.json")
        self.decider(simple(1), decision="REJECTED", quand=T0)
        self.decider(simple(1), quand=T0 + dt.timedelta(minutes=1))
        self.assertEqual(C.etats(self.req, self.hum)[0].statut, C.APPROVED)

    def test_obsolete_et_execute(self):
        self.deposer(simple(1), "AR-1.json")
        self.deposer(simple(2), "AR-2.json")
        self.decider(simple(2))
        obs = lambda ctx: "changé" if ctx.get("n") == 1 else None
        etats = {e.nom: e for e in C.etats(self.req, self.hum, obs, {simple(2)["context_sha256"]})}
        self.assertEqual((etats["AR-1.json"].statut, etats["AR-1.json"].motif), (C.OBSOLETE, "changé"))
        self.assertEqual(etats["AR-2.json"].statut, C.EXECUTED)

    def test_demande_incoherente(self):
        self.deposer(dict(simple(1), context_sha256="0" * 64), "AR-1.json")
        self.assertEqual(C.etats(self.req, self.hum)[0].statut, C.OBSOLETE)


class ExecutionHumaine(Base):
    def plan(self, *codes):
        etapes = [{"argv": [sys.executable, "-c", f"import sys; print('etape {i}'); sys.exit({c})"],
                   "cwd": str(self.travail)} for i, c in enumerate(codes, 1)]
        return X.demande({"title": "essai", "project_id": "projet-a", "reason": "test", "rule": "R03",
                          "steps": etapes}, ROLES, T0)

    def executer(self, d, **k):
        return X.executer(d, self.hum, ROLES, 24, self.journal, {"type": "human", "id": "console"},
                          maintenant=k.pop("maintenant", T0 + dt.timedelta(minutes=5)), **k)

    def test_forme_du_plan(self):
        with self.assertRaisesRegex(X.RefusPlan, "répertoire absolu"):
            X.demande({"title": "t", "project_id": "p", "reason": "r", "steps": [{"argv": ["x"], "cwd": "rel"}]}, ROLES)
        with self.assertRaisesRegex(X.RefusPlan, "au moins une étape"):
            X.demande({"title": "t", "project_id": "p", "reason": "r", "steps": []}, ROLES)
        with self.assertRaisesRegex(X.RefusPlan, "argv"):
            X.demande({"title": "t", "project_id": "p", "reason": "r", "steps": [{"argv": "rm -rf x",
                                                                                    "cwd": str(self.travail)}]}, ROLES)

    def test_sans_approbation_rien_n_est_execute(self):
        d = self.plan(0)
        with self.assertRaisesRegex(X.RefusPlan, "aucune décision humaine"):
            self.executer(d)
        self.decider(d, decision="REJECTED")
        with self.assertRaisesRegex(X.RefusPlan, "REJECTED"):
            self.executer(d)
        self.assertFalse(self.journal.chemin.exists())                    # aucune trace d'exécution : rien lancé

    def test_role_age_et_alteration(self):
        d = self.plan(0)
        self.decider(d, role="reviewer_senior")
        with self.assertRaisesRegex(X.RefusPlan, "rôle"):
            self.executer(d)
        self.decider(d, quand=T0 - dt.timedelta(hours=30))
        with self.assertRaisesRegex(X.RefusPlan, "rôle"):                 # la plus récente reste la non admise
            self.executer(d)
        autre = self.plan(0, 0)                                           # autre plan, autre empreinte
        self.decider(autre, quand=T0 - dt.timedelta(hours=30))
        with self.assertRaisesRegex(X.RefusPlan, "expirée"):
            self.executer(autre)
        modifie = json.loads(canonique(d))
        modifie["context"]["steps"][0]["argv"][-1] = "print('autre chose')"   # étape changée après approbation
        with self.assertRaisesRegex(X.RefusPlan, "incohérente"):
            self.executer(modifie)

    def test_execution_etapes_exactes_puis_usage_unique(self):
        d = self.plan(0, 0)
        ident = self.decider(d)
        r = self.executer(d)
        self.assertTrue(r["succes"])
        self.assertEqual([s["code"] for s in r["etapes"]], [0, 0])
        self.assertIn("etape 2", r["etapes"][1]["sortie"])
        evts = [json.loads(x) for x in self.journal.chemin.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["result"] for e in evts], ["STARTED", "SUCCEEDED", "SUCCEEDED", "SUCCEEDED"])
        self.assertEqual(evts[0]["approval_refs"], [ident])
        self.assertTrue(self.journal.verifier().valide)
        with self.assertRaisesRegex(X.RefusPlan, "déjà exécuté"):
            self.executer(d)
        self.assertIn(d["context_sha256"], X.executes(self.journal))

    def test_arret_a_la_premiere_etape_en_echec(self):
        d = self.plan(0, 3, 0)
        self.decider(d)
        r = self.executer(d)
        self.assertFalse(r["succes"])
        self.assertEqual([s["code"] for s in r["etapes"]], [0, 3])       # la 3e étape n'est jamais lancée

    def test_le_lanceur_ne_recoit_que_les_etapes_approuvees(self):
        d = self.plan(0)
        self.decider(d)
        recus = []

        class R:
            returncode, stdout, stderr = 0, "", ""

        def lanceur(argv, **k):
            recus.append((argv, k["cwd"], k["shell"]))
            return R()
        self.executer(d, lanceur=lanceur)
        self.assertEqual(recus, [(d["context"]["steps"][0]["argv"], str(self.travail), False)])


if __name__ == "__main__":
    unittest.main()
