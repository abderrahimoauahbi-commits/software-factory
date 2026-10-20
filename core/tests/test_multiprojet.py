"""J10 — même cœur, manifests différents, piles différentes = même gouvernance (guide §18, §31).

Deux projets fictifs de piles distinctes (Python / TypeScript-Node) sont évalués par le MÊME Policy Engine, le MÊME
validateur et le MÊME moteur d'états. Leurs différences de comportement ne viennent QUE de leurs manifests.
"""
import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import CORE, FACTORY, habiliter
from noyau.approbation import Magasin
from noyau.politique import ALLOW, DENY, Moteur, ProjetPolitique
from noyau.registre import charger, valider_manifest

FIX = CORE / "tests" / "fixtures"


def _y(p):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


class MemeCoeurDeuxPiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = charger(FACTORY)
        cls.docs = {"project-a": _y(FIX / "project-a.factory.yaml"), "project-b": _y(FIX / "project-b.factory.yaml")}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        reg = copy.deepcopy(self.reg)
        for a in ("backend", "frontend"):                       # habilités en mémoire pour l'essai
            reg.objets["agents"][a]["lifecycle"] = "APPROVED"
        projets, self.racines, self.espaces = {}, {}, {}
        for ident, doc in self.docs.items():
            racine, espace = t / ident, t / f"espace-{ident}"
            for r in (racine, espace):
                for d in ("src", "app", "test"):
                    (r / d).mkdir(parents=True, exist_ok=True)
                (r / "id.txt").write_text(f"id: {ident}\n", encoding="utf-8")
            m = copy.deepcopy(doc["project"])
            if ident == "project-a":
                m["quality"]["gates"] = {"unit_tests": {"command": "python -m unittest"}}
            projets[ident] = ProjetPolitique(ident, racine, m, [], [{"file": "id.txt", "pattern": f"^id: {ident}$"}])
            self.racines[ident], self.espaces[ident] = racine, espace
        p = FACTORY / "policies"
        self.moteur = Moteur(regles=_y(p / "policy-engine.yaml"), classes=_y(p / "command-classes.yaml"),
                             liste_blanche=_y(p / "command-whitelist.yaml")["allowed"],
                             confiance=_y(CORE / "schemas" / "trust.yaml"), racine_scope=_y(p / "root-scope.yaml"),
                             registre=reg, projets=projets, approbations=Magasin(t / "appro"))
        habiliter(self.moteur, "backend", "frontend", projets=("project-a", "project-b"))   # habilités pour l'essai

    def tearDown(self):
        self.tmp.cleanup()

    def demande(self, projet, agent, action="write", chemin=None, commande=None, scope=None):
        return {"actor": {"type": "agent", "id": agent}, "project_id": projet, "action": action,
                "ticket": {"id": f"T-{projet}", "project_id": projet, "criticality": "C2",
                           "scope": {"paths": scope or ["src/", "app/", "test/"]}},
                "execution": {"id": "EX", "worktree": str(self.espaces[projet])},
                "resource": {"kind": "path", "path": chemin, "environment": "LOCAL"}, "command": commande}

    def test_les_deux_manifests_sont_valides(self):
        for ident, doc in self.docs.items():
            with self.subTest(projet=ident):
                self.assertEqual(valider_manifest(self.reg, doc, ident).statut, "VALID")

    def test_les_piles_sont_bien_differentes(self):
        a, b = (self.docs[i]["project"]["stack"]["languages"] for i in ("project-a", "project-b"))
        self.assertFalse(set(a) & set(b))

    def test_commandes_derivees_du_manifest(self):
        cas = [("project-a", "backend", ["python", "-m", "unittest"], ALLOW),
               ("project-a", "backend", ["npm", "test"], DENY),
               ("project-b", "frontend", ["npm", "test"], ALLOW),
               ("project-b", "frontend", ["python", "-m", "unittest"], DENY)]
        for projet, agent, cmd, attendu in cas:
            with self.subTest(projet=projet, commande=cmd):
                d = self.demande(projet, agent, action="execute", commande=cmd)
                self.assertEqual(self.moteur.decider(d).decision, attendu, self.moteur.decider(d).motifs)

    def test_chemins_derives_du_manifest(self):
        self.assertEqual(self.moteur.decider(self.demande("project-a", "backend", chemin="src/x.py")).decision, ALLOW)
        self.assertEqual(self.moteur.decider(self.demande("project-b", "frontend", chemin="app/x.ts")).decision, ALLOW)
        self.assertEqual(self.moteur.decider(self.demande("project-a", "backend", chemin="app/x.ts")).decision, DENY)
        self.assertEqual(self.moteur.decider(self.demande("project-b", "frontend", chemin="dist/x.js")).decision, DENY)

    def test_agents_propres_a_chaque_projet(self):
        self.assertEqual(self.moteur.decider(self.demande("project-b", "backend", chemin="app/x.ts")).decision, DENY)
        self.assertEqual(self.moteur.decider(self.demande("project-a", "frontend", chemin="src/x.py")).decision, DENY)

    def test_isolation_dans_les_deux_sens(self):
        for de, vers in (("project-a", "project-b"), ("project-b", "project-a")):
            with self.subTest(de=de, vers=vers):
                agent = "backend" if de == "project-a" else "frontend"
                d = self.demande(de, agent, action="read", chemin=str(self.racines[vers] / "src" / "x"))
                self.assertEqual(self.moteur.decider(d).decision, DENY)
                d = self.demande(de, agent)
                d["execution"]["worktree"] = str(self.espaces[vers])
                d["resource"]["path"] = "src/x"
                self.assertEqual(self.moteur.decider(d).decision, DENY)

    def test_meme_gouvernance(self):
        # La production, le réseau et l'approbation sont refusés à l'agent quelle que soit la pile.
        for projet, agent in (("project-a", "backend"), ("project-b", "frontend")):
            for action in ("network", "deploy", "approve", "merge"):
                with self.subTest(projet=projet, action=action):
                    self.assertEqual(self.moteur.decider(self.demande(projet, agent, action=action)).decision, DENY)


if __name__ == "__main__":
    unittest.main()
