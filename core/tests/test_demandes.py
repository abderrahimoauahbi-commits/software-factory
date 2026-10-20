"""Demandes de décision humaine (ADR-0017 I8 ; étape G1) : dédoublonnées, sous quota, incohérentes refusées."""
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from noyau.approbation import canonique, empreinte
from noyau.demandes import RefusDemande, deposer, ouvertes


def demande(n):
    ctx = {"kind": "TEST", "n": n}
    return {"context": ctx, "context_sha256": empreinte(ctx), "roles": ["factory_owner"]}


class Demandes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.req = Path(self.tmp.name) / "requests"
        self.hum = Path(self.tmp.name) / "records"

    def tearDown(self):
        self.tmp.cleanup()

    def test_dedoublonnage_par_empreinte_quel_que_soit_le_nom(self):
        p1, c1 = deposer(self.req, "AR-A.json", demande(1), self.hum, 5)
        p2, c2 = deposer(self.req, "AR-B.json", demande(1), self.hum, 5)
        self.assertEqual((p1, c1, c2), (p2, True, False))
        self.assertEqual(len(list(self.req.glob("AR-*.json"))), 1)

    def test_quota_des_demandes_ouvertes(self):
        for i in range(3):
            deposer(self.req, f"AR-{i}.json", demande(i), self.hum, 3)
        with self.assertRaisesRegex(RefusDemande, "quota"):
            deposer(self.req, "AR-9.json", demande(9), self.hum, 3)
        self.hum.mkdir()                                     # une décision humaine (refus compris) libère une place
        (self.hum / "HA-T1.json").write_text(canonique({"context_sha256": demande(0)["context_sha256"],
                                                        "decision": "REJECTED"}), encoding="utf-8")
        self.assertEqual(len(ouvertes(self.req, self.hum)), 2)
        self.assertTrue(deposer(self.req, "AR-9.json", demande(9), self.hum, 3)[1])

    def test_incoherente_ou_nom_invalide(self):
        faux = dict(demande(1), context_sha256="0" * 64)
        with self.assertRaisesRegex(RefusDemande, "incohérente"):
            deposer(self.req, "AR-X.json", faux, self.hum, 5)
        for nom in ("../AR-X.json", "AR-x/../y.json", "HA-1.json", "AR-.txt"):
            with self.assertRaisesRegex(RefusDemande, "nom"):
                deposer(self.req, nom, demande(2), self.hum, 5)

    def test_quota_de_la_factory(self):
        pol = yaml.safe_load((FACTORY / "policies" / "human-approval.yaml").read_text(encoding="utf-8"))
        self.assertEqual(pol["max_open_requests"], 20)


if __name__ == "__main__":
    unittest.main()
