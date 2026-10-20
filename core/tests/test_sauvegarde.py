"""Sauvegarde (D2) : intégrité, non-écrasement, refus des archives piégées, restauration d'essai."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tests import aide  # noqa: F401
from noyau import sauvegarde

PORTEES = ["factory.yaml", "registry", "docs"]
EXCLUS = [".git/", "**/__pycache__/", "*.pyc", "bootstrap/reports/"]


class Sauvegarde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.src, self.dest = base / "factory", base / "sauvegardes"
        for rel, contenu in {"factory.yaml": "id: x\n", "registry/tools/a.yaml": "id: a\n", "docs/lisez.md": "doc\n",
                             "core/mod.py": "x = 1\n", "core/__pycache__/mod.pyc": "bin", "core/sub/__pycache__/m.pyc": "b",
                             "bootstrap/reports/r.json": "{}", ".git/HEAD": "ref"}.items():
            p = self.src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(contenu, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def faire(self):
        return Path(sauvegarde.sauvegarder(self.src, self.dest, PORTEES, EXCLUS, {"t": 1}).archive)

    def test_sauvegarde_verifiee_et_exclusions(self):
        archive = self.faire()
        self.assertEqual(sauvegarde.verifier(archive).statut, "OK")
        with zipfile.ZipFile(archive) as z:
            noms = set(z.namelist())
        self.assertIn("registry/tools/a.yaml", noms)
        self.assertIn("core/mod.py", noms)
        for exclu in ("core/__pycache__/mod.pyc", "core/sub/__pycache__/m.pyc", "bootstrap/reports/r.json", ".git/HEAD"):
            self.assertNotIn(exclu, noms)

    def test_jamais_d_ecrasement(self):
        # Même contenu, même horodatage forcé : l'outil doit refuser d'écrire sur l'archive existante.
        with mock.patch("noyau.sauvegarde.time.strftime", return_value="20260101T000000"):
            archive = self.faire()
            avant = sauvegarde.sha256_fichier(archive)
            with self.assertRaises(FileExistsError):
                self.faire()
        self.assertEqual(sauvegarde.sha256_fichier(archive), avant)
        self.assertEqual(sauvegarde.verifier(archive).statut, "OK")

    def test_archive_alteree_detectee(self):
        archive = self.faire()
        with open(archive, "ab") as f:
            f.write(b"x")
        self.assertEqual(sauvegarde.verifier(archive).statut, "FAIL")

    def test_contenu_altere_detecte(self):
        archive = self.faire()
        altere = archive.with_name("altere.zip")
        with zipfile.ZipFile(archive) as z, zipfile.ZipFile(altere, "w") as w:
            for n in z.namelist():
                w.writestr(n, b"pirate" if n == "factory.yaml" else z.read(n))
        Path(str(altere) + ".sha256").write_text(f"{sauvegarde.sha256_fichier(altere)}  altere.zip\n", encoding="ascii")
        r = sauvegarde.verifier(altere)
        self.assertEqual(r.statut, "FAIL")
        self.assertTrue(any("altéré" in d for d in r.details))

    def test_portee_exigee_absente_refusee(self):
        with self.assertRaises(sauvegarde.SauvegardeRefusee):
            sauvegarde.sauvegarder(self.src, self.dest, PORTEES + ["audit"], EXCLUS, {})
        self.assertFalse(self.dest.exists() and any(self.dest.iterdir()))

    def test_destination_dans_la_source_refusee(self):
        with self.assertRaises(sauvegarde.SauvegardeRefusee):
            sauvegarde.sauvegarder(self.src, self.src / "sauvegardes", PORTEES, EXCLUS, {})

    def test_restauration_d_essai(self):
        archive = self.faire()
        vus = []
        r = sauvegarde.tester_restauration(archive, lambda racine: vus.append((racine / "factory.yaml").read_text()) or [])
        self.assertEqual(r.statut, "OK", r.details)
        self.assertEqual(vus, ["id: x\n"])
        self.assertIn("restore_seconds", r.mesures)

    def test_revalidation_en_echec_remontee(self):
        r = sauvegarde.tester_restauration(self.faire(), lambda racine: ["registre invalide"])
        self.assertEqual(r.statut, "FAIL")

    def test_exercice_de_reprise(self):
        (self.src / "docs" / "ok.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
        (self.src / "docs" / "ko.py").write_text("import sys; sys.exit(3)\n", encoding="utf-8")
        archive = self.faire()
        bon = sauvegarde.exercice_reprise(archive, [[sys.executable, "{racine}/docs/ok.py"]])
        self.assertEqual(bon.statut, "OK", bon.details)
        self.assertIn("rto_seconds", bon.mesures)
        mauvais = sauvegarde.exercice_reprise(archive, [[sys.executable, "{racine}/docs/ok.py"],
                                                        [sys.executable, "{racine}/docs/ko.py"]])
        self.assertEqual(mauvais.statut, "FAIL")
        self.assertEqual([e["code"] for e in mauvais.mesures["etapes"]], [0, 3])

    def test_archive_piegee_refusee(self):
        piege = self.dest / "piege.zip"
        self.dest.mkdir(parents=True)
        manifeste = {"files": [{"path": "../evade.txt", "size": 1, "sha256": "0" * 64}]}
        with zipfile.ZipFile(piege, "w") as z:
            z.writestr("../evade.txt", "x")
            z.writestr(sauvegarde.MANIFESTE, json.dumps(manifeste))
        Path(str(piege) + ".sha256").write_text(f"{sauvegarde.sha256_fichier(piege)}  piege.zip\n", encoding="ascii")
        r = sauvegarde.tester_restauration(piege)
        self.assertEqual(r.statut, "FAIL")
        self.assertFalse((self.dest.parent / "evade.txt").exists())


if __name__ == "__main__":
    unittest.main()
