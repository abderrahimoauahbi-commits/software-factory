"""Clé de service provisoire L1 des baux (ADR-0017 D7, hors cérémonie D36) : lecture, refus par défaut, identifiant.

Le chemin est redirigé vers un dossier temporaire : la vraie clé n'est jamais lue ni écrite par ces tests."""
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fournisseurs import cablage


class CleDeService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / cablage.FICHIER_CLE
        self.patch = mock.patch.object(cablage, "chemin_cle", lambda: self.p)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_absente_illisible_ou_trop_courte_aucune_cle(self):
        self.assertIsNone(cablage.cle_de_service())
        self.p.write_text("pas de l'hexadécimal", encoding="utf-8")
        self.assertIsNone(cablage.cle_de_service())
        self.p.write_text(secrets.token_hex(16), encoding="ascii")          # 16 octets : trop courte
        self.assertIsNone(cablage.cle_de_service())

    def test_lecture_et_identifiant_public(self):
        cle = secrets.token_bytes(32)
        self.p.write_text(cle.hex() + "\n", encoding="ascii")
        self.assertEqual(cablage.cle_de_service(), cle)
        ident = cablage.identifiant_cle(cle)
        self.assertTrue(ident.startswith("L1-") and len(ident) == 15)
        self.assertNotIn(ident[3:], cle.hex())                            # l'identifiant ne révèle pas la clé
        self.assertNotEqual(ident, cablage.identifiant_cle(secrets.token_bytes(32)))


if __name__ == "__main__":
    unittest.main()
