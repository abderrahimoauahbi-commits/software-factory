"""CHECK de bout en bout : aucune écriture, aucun secret dans le rapport, aucun fichier sensible lu."""
import json
import os
import unittest
from pathlib import Path

from tests.aide import FACTORY
from check import controles, rapport
from noyau.masquage import contient_secret
from noyau.registre import charger


def instantane(racine: Path) -> dict:
    etat = {}
    for dossier, sous, fichiers in os.walk(racine):
        sous[:] = [s for s in sous if s not in (".git", "__pycache__", "reports")]
        for f in fichiers:
            p = Path(dossier) / f
            st = p.stat()
            etat[str(p)] = (st.st_size, st.st_mtime_ns)
    return etat


class CheckFactory(unittest.TestCase):
    def test_check_sans_ecriture_ni_secret(self):
        avant = instantane(FACTORY)
        ctx, col = controles.executer(FACTORY, None)
        r = rapport.construire(ctx, col, None, "test")
        self.assertEqual(instantane(FACTORY), avant, "le CHECK a modifié la Factory")
        texte = json.dumps(r, ensure_ascii=False, default=str)
        self.assertFalse(contient_secret(texte), "valeur secrète dans le rapport")
        ids = {c.id: c.statut for c in col.constats}
        self.assertEqual(ids["F-REGISTRY"], "READY")
        self.assertEqual(ids["F-PLAYBOOK"], "READY")
        for p in ctx.executeur.journal:
            self.assertTrue(ctx.executeur.autorisee(p.source.split())[0] or p.result == "FAILURE")


def _projets_presents():
    reg = charger(FACTORY)
    return [i for i, c in reg.objets["projects"].items() if c.get("lifecycle", {}).get("role_in_factory") != "self"
            and Path(c["root"]["path"]).is_dir()]


@unittest.skipUnless(_projets_presents(), "aucun projet enregistré présent sur ce poste")
class CheckProjet(unittest.TestCase):
    def test_aucun_sensible_lu_et_projet_intact(self):
        for id_projet in _projets_presents():
            with self.subTest(projet=id_projet):
                ctx, col = controles.executer(FACTORY, id_projet)
                self.assertIsNotNone(ctx.racine_projet)
                for lu in ctx.perimetre.lectures:
                    chemin = Path(lu.removesuffix("/ (liste)"))
                    if ctx.perimetre.dans_perimetre(chemin):
                        self.assertFalse(ctx.perimetre.est_sensible(chemin), f"fichier sensible lu : {lu}")
                r = rapport.construire(ctx, col, id_projet, "test")
                self.assertFalse(contient_secret(json.dumps(r, ensure_ascii=False, default=str)))
                # Aucune commande refusée n'a été exécutée.
                for p in ctx.executeur.journal:
                    if p.extrait and p.extrait.startswith("refusée"):
                        self.assertIsNone(p.exit_code)


if __name__ == "__main__":
    unittest.main()
