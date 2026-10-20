"""Environment Manager, registre des ressources et base jetable (Master Evolution Prompt v4 §11, §12, §37, §38).

Les essais « réels » créent de vrais clusters privés (sous un répertoire temporaire, 127.0.0.1, port libre) ; ils
sont sautés si le serveur de base n'est pas installé. Aucun ne touche l'instance du poste.
"""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import yaml

from tests.aide import FACTORY

from fournisseurs.postgresql_jetable import PostgresJetable
from noyau.audit import Journal
from noyau.environnements import Gestionnaire, RefusEnvironnement
from noyau.ressources import Registre, RefusRessource, Ressource

CYCLE = yaml.safe_load((FACTORY / "core" / "schemas" / "lifecycles.yaml").read_text(encoding="utf-8"))["environment"]
PROFILS = {"LOCAL_TEST": {"disposable": True, "criticality": "C1", "retention_hours": 24},
           "PRODUCTION": {"disposable": False, "criticality": "C4"}}
PG = PostgresJetable()


class FauxFournisseur:
    """Ressource « mémoire » dont l'identité peut être falsifiée pour l'essai."""
    id, kind = "faux", "database"

    def __init__(self):
        self.vivantes, self.resets, self.identites = set(), [], {}

    def creer(self, dossier, spec, env):
        rid = f"sys-{len(self.vivantes) + 1}"
        self.vivantes.add(rid)
        dd = str(Path(dossier) / "data")
        Path(dd).mkdir()
        (Path(dossier) / "serveur.log").write_text("journal", encoding="utf-8")
        self.identites[rid] = {"system_identifier": rid, "data_directory": dd}
        return {"connection": {"host": "127.0.0.1", "port": rid, "data_dir": dd}, "identity": self.identites[rid]}

    def identite(self, r):
        if r.connection["port"] not in self.vivantes:
            raise ConnectionError("injoignable")
        return self.identites[r.connection["port"]]

    def reinitialiser(self, r):
        self.resets.append(r.id)

    def detruire(self, r):
        self.vivantes.discard(r.connection["port"])

    def variables(self, r):
        return {"DB_PORT": str(r.connection["port"])}


def gestionnaire(racine: Path, f, journal=None):
    reg = Registre(racine / "resources", {f.id: f}, racine / "envs")
    return Gestionnaire(racine / "envs", PROFILS, CYCLE, reg, {f.kind: f}, journal), reg


class EnvironnementsGeneriques(unittest.TestCase):
    def test_cycle_complet_et_archives(self):
        with tempfile.TemporaryDirectory() as d:
            f = FauxFournisseur()
            j = Journal(Path(d) / "j.jsonl")
            g, reg = gestionnaire(Path(d), f, j)
            e = g.creer("exec-1-test", "projet-a", "EX-1", "LOCAL_TEST", [{"kind": "database", "name": "db"}])
            self.assertEqual(e.state, "READY")
            rid = e.resources[0]
            self.assertEqual(reg.verifier_identite(rid), (True, "identité vérifiée"))
            self.assertEqual(g.variables("exec-1-test"), {"DB_PORT": "sys-1"})
            g.reinitialiser("exec-1-test")
            self.assertEqual(f.resets, [rid])
            bilan = g.detruire("exec-1-test")
            self.assertTrue(bilan["destroyed"])
            self.assertFalse((Path(d) / "envs" / "exec-1-test").exists())
            self.assertTrue((Path(bilan["archive"]) / "serveur.log").is_file())       # preuves conservées
            self.assertEqual(reg.obtenir(rid).state, "DESTROYED")
            self.assertTrue(j.verifier().valide)

    def test_profil_durable_jamais_cree(self):
        with tempfile.TemporaryDirectory() as d:
            g, _ = gestionnaire(Path(d), FauxFournisseur())
            with self.assertRaises(RefusEnvironnement):
                g.creer("prod-1", "projet-a", "EX-1", "PRODUCTION", [])
            with self.assertRaises(RefusEnvironnement):
                g.creer("../evasion", "projet-a", "EX-1", "LOCAL_TEST", [])

    def test_ressource_externe_jamais_jetable_et_nom_trompeur(self):
        with tempfile.TemporaryDirectory() as d:
            reg = Registre(Path(d) / "r", {}, Path(d) / "envs")
            with self.assertRaises(RefusRessource):
                reg.enregistrer(Ressource("base-test", "database", "projet-a", "local-dev", "LOCAL_TEST", "external",
                                          True, identity={"x": 1}))
            # Une base nommée « …_test » déclarée par le projet reste externe et non jetable.
            reg.enregistrer(Ressource("projet_a_test", "database", "projet-a", "local-dev", "DEV_SHARED", "external",
                                      False, classification="CONFIDENTIAL", identity={"x": 1}, provider="absent"))
            ok, motif = reg.verifier_identite("projet_a_test")
            self.assertFalse(ok)
            self.assertFalse(reg.obtenir("projet_a_test").disposable)

    def test_identite_falsifiee_refusee_et_rien_n_est_detruit(self):
        with tempfile.TemporaryDirectory() as d:
            f = FauxFournisseur()
            g, reg = gestionnaire(Path(d), f)
            a = g.creer("env-a-1", "projet-a", "EX-1", "LOCAL_TEST", [{"kind": "database"}])
            b = g.creer("env-b-1", "projet-a", "EX-2", "LOCAL_TEST", [{"kind": "database"}])
            ra = reg.obtenir(a.resources[0])
            # La fiche A pointe maintenant vers le serveur B (même nom, autre identité).
            falsifiee = replace(ra, connection=dict(ra.connection, port=reg.obtenir(b.resources[0]).connection["port"]))
            (Path(d) / "resources" / f"{ra.id}.json").write_text(json.dumps(falsifiee.__dict__), encoding="utf-8")
            ok, motif = reg.verifier_identite(ra.id)
            self.assertFalse(ok)
            self.assertIn("system_identifier", motif)
            with self.assertRaises(RefusEnvironnement):
                g.reinitialiser("env-a-1")
            bilan = g.detruire("env-a-1")
            self.assertFalse(bilan["destroyed"])
            self.assertIn("sys-2", f.vivantes)                                       # B intact

    def test_destruction_exige_le_marqueur(self):
        with tempfile.TemporaryDirectory() as d:
            g, _ = gestionnaire(Path(d), FauxFournisseur())
            g.creer("env-m-1", "projet-a", "EX-1", "LOCAL_TEST", [{"kind": "database"}])
            (Path(d) / "envs" / "env-m-1" / ".factory-environment").write_text('{"environment_id": "autre"}')
            with self.assertRaises(RefusEnvironnement):
                g.detruire("env-m-1")


@unittest.skipUnless(PG.disponible()[0], "serveur de base absent")
class QuotasDuResourceBroker(unittest.TestCase):
    """Étape G1 : refus à la création au-delà des quotas ; dépassement en cours d'exécution constaté (détectif)."""

    def gestionnaire(self, d, **quotas):
        f = FauxFournisseur()
        reg = Registre(Path(d) / "resources", {f.id: f}, Path(d) / "envs")
        return Gestionnaire(Path(d) / "envs", PROFILS, CYCLE, reg, {f.kind: f}, quotas=quotas)

    def test_nombre_d_environnements_vivants(self):
        with tempfile.TemporaryDirectory() as d:
            g = self.gestionnaire(d, max_active_environments=1)
            g.creer("exec-1-test", "projet-a", "EX-1", "LOCAL_TEST", [{"kind": "database"}])
            with self.assertRaisesRegex(RefusEnvironnement, "quota atteint"):
                g.creer("exec-2-test", "projet-a", "EX-2", "LOCAL_TEST", [{"kind": "database"}])
            self.assertFalse((Path(d) / "envs" / "exec-2-test").exists())          # rien n'a été créé
            g.detruire("exec-1-test")
            self.assertEqual(g.creer("exec-3-test", "projet-a", "EX-3", "LOCAL_TEST",
                                     [{"kind": "database"}]).state, "READY")

    def test_disque_constate_et_creation_refusee(self):
        with tempfile.TemporaryDirectory() as d:
            g = self.gestionnaire(d, max_disk_mb_per_environment=1, max_disk_mb_total=2)
            e = g.creer("exec-1-test", "projet-a", "EX-1", "LOCAL_TEST", [{"kind": "database"}])
            self.assertEqual(g.depassements(), [])
            (Path(e.root) / "data" / "gros.bin").write_bytes(b"\0" * (3 * 1024 * 1024))
            self.assertGreater(g.occupation_mo(e.id), 2.9)
            constats = g.depassements()
            self.assertTrue(any(c.startswith("exec-1-test") for c in constats))
            self.assertTrue(any(c.startswith("racine") for c in constats))
            with self.assertRaisesRegex(RefusEnvironnement, "quota disque"):
                g.creer("exec-2-test", "projet-a", "EX-2", "LOCAL_TEST", [{"kind": "database"}])

    def test_sans_quota_aucun_plafond_et_quotas_de_la_factory(self):
        with tempfile.TemporaryDirectory() as d:
            g = self.gestionnaire(d)
            for i in range(3):
                g.creer(f"exec-{i}-test", "projet-a", f"EX-{i}", "LOCAL_TEST", [{"kind": "database"}])
        q = yaml.safe_load((FACTORY / "orchestrator" / "environnements.yaml").read_text(encoding="utf-8"))["quotas"]
        self.assertEqual(set(q), {"max_active_environments", "max_disk_mb_per_environment", "max_disk_mb_total",
                                  "min_free_disk_mb"})


class BaseJetableReelle(unittest.TestCase):
    """Deux clusters privés réels : création, SQL destructif, reset, identité croisée, destruction."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        racine = Path(cls.tmp.name)
        cls.reg = Registre(racine / "resources", {PG.id: PG}, racine / "envs")
        cls.g = Gestionnaire(racine / "envs", PROFILS, CYCLE, cls.reg, {PG.kind: PG})
        cls.a = cls.g.creer("pg-a-1", "projet-a", "EX-A", "LOCAL_TEST", [{"kind": "database", "database": "projet_a_test"}])
        cls.b = cls.g.creer("pg-b-1", "projet-a", "EX-B", "LOCAL_TEST", [{"kind": "database", "database": "projet_a_test"}])

    @classmethod
    def tearDownClass(cls):
        for e in ("pg-a-1", "pg-b-1"):
            try:
                cls.g.detruire(e, "fin des essais")
            except Exception:
                pass
        cls.tmp.cleanup()

    def test_1_sql_destructif_puis_reset(self):
        r = self.reg.obtenir(self.a.resources[0])
        self.assertEqual(r.connection["host"], "127.0.0.1")
        self.assertNotEqual(str(r.connection["port"]), "5432")
        x = PG.executer_sql(r, "CREATE TABLE clients(id int); INSERT INTO clients VALUES (1); DROP TABLE clients; "
                               "CREATE TABLE t(x int)")
        self.assertEqual(x.returncode, 0, x.stderr)
        self.g.reinitialiser("pg-a-1")
        y = PG.executer_sql(r, "SELECT count(*) FROM t")
        self.assertNotEqual(y.returncode, 0)                                         # base vierge après reset

    def test_2_meme_nom_autre_identite(self):
        ra, rb = (self.reg.obtenir(e.resources[0]) for e in (self.a, self.b))
        self.assertEqual(ra.connection["database"], rb.connection["database"])     # même nom…
        self.assertNotEqual(ra.identity["system_identifier"], rb.identity["system_identifier"])   # …autre base
        falsifiee = replace(ra, id="faux", connection=dict(ra.connection, port=rb.connection["port"]))
        self.reg.enregistrer(falsifiee)
        ok, motif = self.reg.verifier_identite("faux")
        self.assertFalse(ok, motif)

    def test_3_destruction(self):
        bilan = self.g.detruire("pg-b-1")
        self.assertTrue(bilan["destroyed"], bilan)
        self.assertFalse(Path(self.b.root).exists())


if __name__ == "__main__":
    unittest.main()
