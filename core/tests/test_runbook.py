"""J11 : le manuel d'exploitation ne cite aucune commande inventée (guide §32)."""
import importlib.util
import re
import shlex
import unittest

from tests.aide import FACTORY

RUNBOOK = FACTORY / "docs" / "operations" / "runbook.md"


def _cli():
    spec = importlib.util.spec_from_file_location("factory_cli", FACTORY / "factory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def commandes():
    texte = RUNBOOK.read_text(encoding="utf-8")
    for bloc in re.findall(r"```bash\n(.*?)```", texte, re.S):
        for ligne in bloc.splitlines():
            ligne = ligne.split("#")[0].strip()
            if ligne:
                yield ligne


class Runbook(unittest.TestCase):
    def test_procedures_exigees_presentes(self):
        texte = RUNBOOK.read_text(encoding="utf-8").lower()
        for rubrique in ("démarrer", "contrôle de santé", "ajouter un outil", "retirer un outil", "ajouter un agent",
                         "mettre à jour un modèle", "ajouter un mcp", "révoquer", "créer un projet", "bloquer",
                         "rollback", "restaurer", "incident", "incident de sécurité", "mettre à jour la factory"):
            with self.subTest(rubrique=rubrique):
                self.assertIn(rubrique, texte)

    def test_aucune_commande_inventee(self):
        parseur = _cli().parseur()
        vues = 0
        for ligne in commandes():
            mots = shlex.split(ligne)
            with self.subTest(commande=ligne):
                if mots[0] == "factory":
                    try:
                        parseur.parse_args(mots[1:])
                    except SystemExit:
                        self.fail(f"commande factory inexistante : {ligne}")
                elif mots[:2] == ["python", "-P"]:
                    script = FACTORY / mots[2]
                    self.assertTrue(script.is_file(), f"script absent : {mots[2]}")
                    if len(mots) > 3 and not mots[3].startswith(("audit/", "ARCHIVE")):
                        self.assertIn(f'"{mots[3]}"', script.read_text(encoding="utf-8"), f"opération inconnue : {mots[3]}")
                else:
                    self.fail(f"commande hors CLI et scripts de la Factory : {ligne}")
                vues += 1
        self.assertGreater(vues, 10)


if __name__ == "__main__":
    unittest.main()
