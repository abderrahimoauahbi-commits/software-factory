"""J5 : journal d'audit chaîné (ajout seul, falsification détectée) et preuves (déclaration ≠ preuve)."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import CORE, FACTORY
from noyau import preuves
from noyau.audit import AuditRefuse, Journal
from noyau.commandes import Executeur
from noyau.perimetre import Perimetre, Racine, canonique

TYPES = yaml.safe_load((CORE / "schemas" / "enums.yaml").read_text(encoding="utf-8"))["EVIDENCE_TYPE"]


class JournalChaine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.j = Journal(Path(self.tmp.name) / "journal.jsonl")
        for i in range(4):
            self.j.ajouter(actor={"type": "agent", "id": "a"}, action=f"action {i}", result="OK")

    def tearDown(self):
        self.tmp.cleanup()

    def lignes(self):
        return self.j.chemin.read_text(encoding="utf-8").splitlines()

    def ecrire(self, lignes):
        self.j.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def test_chaine_intacte(self):
        v = self.j.verifier()
        self.assertTrue(v.valide)
        self.assertEqual(v.evenements, 4)

    def test_modification_detectee(self):
        l = self.lignes()
        e = json.loads(l[1])
        e["result"] = "FALSIFIE"
        l[1] = json.dumps(e, ensure_ascii=False, sort_keys=True)
        self.ecrire(l)
        v = self.j.verifier()
        self.assertFalse(v.valide)
        self.assertEqual(v.rupture, 1)

    def test_suppression_detectee(self):
        l = self.lignes()
        del l[1]
        self.ecrire(l)
        self.assertEqual(self.j.verifier().rupture, 1)

    def test_permutation_detectee(self):
        l = self.lignes()
        l[1], l[2] = l[2], l[1]
        self.ecrire(l)
        self.assertFalse(self.j.verifier().valide)

    def test_reecriture_complete_recalculee_detectee_par_ancrage(self):
        # Un faussaire qui recalcule toute la chaîne change la tête : l'ancre conservée ailleurs le révèle.
        tete = self.j.verifier().tete
        l = self.lignes()
        e = json.loads(l[0])
        e["result"] = "FALSIFIE"
        self.j.chemin.write_text("", encoding="utf-8")       # le faussaire repart d'un journal vide
        j2 = Journal(self.j.chemin)
        j2.ajouter(**{k: v for k, v in e.items() if k not in ("prev_hash", "event_hash")})
        self.assertNotEqual(j2.verifier().tete, tete)

    def test_ecriture_refusee_sur_journal_compromis(self):
        l = self.lignes()
        del l[0]
        self.ecrire(l)
        with self.assertRaises(AuditRefuse):
            self.j.ajouter(actor={"type": "agent", "id": "a"}, action="x", result="OK")

    def test_secret_refuse(self):
        with self.assertRaises(AuditRefuse):
            self.j.ajouter(actor={"type": "agent", "id": "a"}, action="x", result="OK",
                           note="postgres://u:motdepasse@hote/base")

    def test_champs_requis(self):
        with self.assertRaises(AuditRefuse):
            self.j.ajouter(action="x", result="OK")


class Preuves(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name) / "preuves"
        p = Perimetre({"R": Racine("R", canonique(self.tmp.name))}, [], [], [], [])
        self.e = Executeur(autorisees=[["git", "--version"]], jokers={}, perimetre=p)

    def tearDown(self):
        self.tmp.cleanup()

    def reelle(self, ident="EV-1", type_="TEST"):
        return preuves.enregistrer_commande(self.e.lancer(["git", "--version"]), type_, ident, self.racine, "agent:qa")

    def test_preuve_reelle_valide(self):
        p = self.reelle()
        v = preuves.verifier(p, TYPES, self.racine)
        self.assertTrue(v.valide, v.motif)
        self.assertEqual(p["exit_code"], 0)

    def test_declaration_n_est_pas_une_preuve(self):
        for faux in ({"type": "TEST", "result": "SUCCESS", "source": "l'agent dit : tests passed"},
                     {"type": "DECLARATION", "id": "x"}, "tests passed", None):
            with self.subTest(preuve=str(faux)[:40]):
                self.assertFalse(preuves.verifier(faux, TYPES, self.racine).valide)

    def test_sans_code_de_sortie(self):
        p = self.reelle()
        p["exit_code"] = "0"
        self.assertFalse(preuves.verifier(p, TYPES, self.racine).valide)

    def test_resultat_incoherent(self):
        p = self.reelle()
        p["exit_code"] = 1
        self.assertFalse(preuves.verifier(p, TYPES, self.racine).valide)

    def test_artefact_modifie(self):
        p = self.reelle()
        (self.racine / p["artifact_ref"]).write_text("autre sortie", encoding="utf-8")
        self.assertIn("modifié", preuves.verifier(p, TYPES, self.racine).motif)

    def test_artefact_hors_du_repertoire(self):
        p = self.reelle()
        p["artifact_ref"] = "../ailleurs.log"
        self.assertFalse(preuves.verifier(p, TYPES, self.racine).valide)

    def test_aucune_preuve_sans_execution(self):
        refusee = self.e.lancer(["git", "push"])
        with self.assertRaises(ValueError):
            preuves.enregistrer_commande(refusee, "TEST", "EV-2", self.racine, "agent:qa")

    def test_artefact_jamais_ecrase(self):
        self.reelle("EV-3")
        with self.assertRaises(FileExistsError):
            self.reelle("EV-3")


if __name__ == "__main__":
    unittest.main()
