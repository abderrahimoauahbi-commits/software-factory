"""Tests du registre : le registre réel est valide, et le validateur rejette ce qu'il doit rejeter."""
import ast
import unittest
from pathlib import Path

from tests.aide import BOOTSTRAP, CORE, FACTORY
from noyau.registre import charger, transition_valide


class RegistreReel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = charger(FACTORY)

    def test_aucune_erreur_de_validation(self):
        self.assertEqual([f"{e.fichier} : {e.message}" for e in self.reg.erreurs], [])

    def test_aucune_version_inventee(self):
        # ADR-0022 v2 (F-3) : version épinglée sur le relevé du Bootstrap (majeure.mineure), « project » (fixée par le
        # projet) ou « * » (non épinglée : un ticket qui exige l'outil est BLOCKED) ; jamais une version inventée.
        for t in self.reg.objets["tools"].values():
            self.assertRegex(str(t["version"]), r"^(\*|project|\d+\.\d+)$", t["id"])
            self.assertIsNone(t["update"]["current_version"], t["id"])

    def test_rien_d_actif_sans_approbation(self):
        for type_ in ("mcp", "agents", "models"):
            for o in self.reg.objets[type_].values():
                self.assertNotIn(o["lifecycle"], ("ACTIVE", "DEPLOYED", "AUTHORIZED_FOR_PROJECT"), o["id"])

    def test_mcp_production_refusee(self):
        for o in self.reg.objets["mcp"].values():
            self.assertEqual(o["production"], {"read": False, "write": False, "delete": False}, o["id"])

    def test_transitions(self):
        self.assertTrue(transition_valide(self.reg, "ticket", "READY_TO_MERGE", "HUMAN_APPROVAL"))
        self.assertTrue(transition_valide(self.reg, "ticket", "QA", "IN_PROGRESS"))      # boucle de correction (S3)
        self.assertFalse(transition_valide(self.reg, "ticket", "DRAFT", "MERGED"))
        self.assertTrue(transition_valide(self.reg, "execution", "RUNNING", "SECURITY_STOP"))
        self.assertFalse(transition_valide(self.reg, "execution", "INTERRUPTED", "COMPLETED"))

    def test_validateur_rejette(self):
        mauvais = {"schema_version": "1.0", "id": "x", "name": "x", "version": "*", "type": "cli",
                   "lifecycle": "INVENTE", "capabilities": [], "compatibility": {}, "permissions": {},
                   "security": {}, "evaluation": {}, "approval": {}, "health": {},
                   "update": {}, "notes": "postgres://u:motdepasse@hote/base"}
        v = self.reg.validateur.valider("tool", mauvais, "test")
        codes = {(d.code, d.chemin) for d in v.defauts}
        self.assertIn(("ENUM_VALUE", "lifecycle"), codes)
        self.assertIn(("SECRET_IN_CLEAR", "notes"), codes)
        self.assertEqual(v.statut, "REJECTED")
        del mauvais["approval"]
        v = self.reg.validateur.valider("tool", mauvais, "test")
        self.assertIn(("REQUIRED_MISSING", "approval"), {(d.code, d.chemin) for d in v.defauts})

    def test_chaque_fiche_a_un_verdict_valid(self):
        self.assertTrue(self.reg.verdicts)
        self.assertEqual([f"{v.source} {v.statut}" for v in self.reg.verdicts if v.statut != "VALID"], [])

    def test_tickets_charges_et_valides(self):
        # T-FACTORY-020 : les tickets des projets font partie du registre validé.
        self.assertTrue(self.reg.objets["tickets"])
        sources = {v.source for v in self.reg.verdicts}
        self.assertTrue(any("/tickets/" in s for s in sources))

    def test_ticket_workflow_inconnu(self):
        # « bugfix » pour « bug-fix » passait (15/10/2026).
        ticket = dict(next(iter(self.reg.objets["tickets"].values())))
        for champ, valeur in (("workflow_id", "bugfix"), ("project_id", "projet-invente")):
            v = self.reg.validateur.valider("ticket", {**ticket, champ: valeur}, "test")
            self.assertIn(("REFERENCE_UNKNOWN", champ), {(d.code, d.chemin) for d in v.defauts})
        v = self.reg.validateur.valider("ticket", {**ticket, "dependencies": {"tickets": ["T-INVENTE"]}}, "test")
        self.assertIn("REFERENCE_UNKNOWN", {d.code for d in v.defauts})


class CoeurGenerique(unittest.TestCase):
    """Executable Schemas §36 : aucun nom de projet, d'outil ou de fournisseur dans le cœur partagé ni dans les
    contrôles du Bootstrap (les adaptateurs, eux, sont propres à un outil par construction)."""
    DOSSIERS = [CORE / "noyau", BOOTSTRAP / "check"]
    INTERDITS = ["gestionfil", "gestionpoly", "rustc", "cargo", "npm", "psql", "postgres", "playwright", "claude",
                 "anthropic", "openai", "vscode", "react", "axum", "github", "git ", "\"git\""]

    def test_noyau_sans_nom_specifique(self):
        fichiers = sorted(f for d in self.DOSSIERS for f in d.glob("*.py"))
        self.assertGreaterEqual(len(fichiers), 8, "dossiers du cœur introuvables")
        for f in fichiers:
            arbre = ast.parse(f.read_text(encoding="utf-8"))
            # Seules les chaînes de code comptent : la documentation peut citer des exemples.
            docs = {id(n.body[0].value) for n in ast.walk(arbre)
                    if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                    and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
            for n in ast.walk(arbre):
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                    for mot in self.INTERDITS:
                        with self.subTest(fichier=f.name, mot=mot):
                            self.assertNotIn(mot, n.value.lower())


if __name__ == "__main__":
    unittest.main()
