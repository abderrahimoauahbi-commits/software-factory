"""Capacité exigée par une opération SQL d'agent (cablage._classer_sql) : une destruction de données cachée dans un
fichier de migration exige DATABASE_DROP (faille relevée le 17/10/2026, préparation de la suite database)."""
import tempfile
import unittest
from pathlib import Path

from tests.aide import FACTORY  # noqa: F401  (chemins d'import)

from fournisseurs.cablage import _classer_sql


class ClassementSql(unittest.TestCase):
    def fichier(self, texte):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name) / "m.sql"
        p.write_text(texte, encoding="utf-8")
        return str(p)

    def test_migration_ordinaire(self):
        f = self.fichier("-- 2026-10-17f — index\nBEGIN;\nCREATE INDEX IF NOT EXISTS ix ON t (lower(nom));\n"
                         "DROP INDEX IF EXISTS ancien_ix;\nCOMMIT;\n")
        self.assertEqual(_classer_sql(None, f), "DATABASE_MIGRATION")

    def test_destruction_cachee_dans_un_fichier(self):
        for texte in ("BEGIN; DROP TABLE alerte CASCADE; COMMIT;", "truncate  alerte;",
                      "ALTER TABLE t ADD c int;\nDrop\n  Schema s cascade;", "DROP DATABASE x;", "DROP OWNED BY r;"):
            with self.subTest(texte=texte):
                self.assertEqual(_classer_sql(None, self.fichier(texte)), "DATABASE_DROP")

    def test_commentaire_ne_compte_pas(self):
        f = self.fichier("-- ne jamais faire DROP TABLE ici\n/* ni TRUNCATE alerte */\nCREATE VIEW v AS SELECT 1;\n")
        self.assertEqual(_classer_sql(None, f), "DATABASE_MIGRATION")

    def test_fichier_illisible_exige_le_plus_haut(self):
        self.assertEqual(_classer_sql(None, "C:/inexistant/x.sql"), "DATABASE_DROP")

    def test_sql_en_ligne_inchange(self):
        self.assertEqual(_classer_sql("DROP TABLE x", None), "DATABASE_DROP")
        self.assertEqual(_classer_sql("CREATE TABLE x (a int)", None), "DATABASE_SCHEMA_CHANGE")
        self.assertEqual(_classer_sql("SELECT 1", None), "DATABASE_READ")


if __name__ == "__main__":
    unittest.main()
