"""Garde du bail (ADR-0017 annexe E « Hook du bail », étape G1) : appels coopératifs simulés, clés jetables.

Ces tests établissent IMPLEMENTED ; ENFORCED exige une vraie session et un acteur non coopératif (annexe E)."""
import datetime as dt
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from fournisseurs.runtime_claude_code import RuntimeClaudeCode
from noyau.baux import GestionnaireCapacites
from noyau.graphe import Tache
from noyau.organisation import Membre
from noyau.runtime import Contexte

GARDE = FACTORY / "scripts" / "hooks" / "garde_bail.py"
_spec = importlib.util.spec_from_file_location("garde_bail", GARDE)
garde = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(garde)

CYCLE = yaml.safe_load((FACTORY / "core" / "schemas" / "lifecycles.yaml").read_text(encoding="utf-8"))["capability_lease"]
CLE = secrets.token_bytes(32)


class Politique:
    defaut = "ALLOW"

    def decider(self, d):
        return {"decision": self.defaut, "regle": "RX", "motifs": [], "empreinte_contexte": "x"}


class Horloge:
    t = dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.t


def evt(outil, **entree):
    return {"tool_name": outil, "tool_input": entree}


class GardeDuBail(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.h = Horloge()
        self.gc = GestionnaireCapacites(Path(self.tmp.name) / "leases", Politique(), CYCLE,
                                        {"max_duration_s": 600}, horloge=self.h, cle=CLE, empreinte_politique="p1")
        self.b, s = self.gc.demander({"type": "agent", "id": "database"}, "projet-a",
                                     {"id": "M-1/t1", "project_id": "projet-a", "criticality": "C1"}, {"id": "M-1/t1"},
                                     None, ["FILESYSTEM_WRITE", "TEST"], ["workspace"])
        self.assertEqual(s["decision"], "ALLOW")
        self.proj = {"lease": self.b.id, "actor": "database", "execution": "M-1/t1"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_lecture_laissee_aux_permissions(self):
        self.assertIsNone(garde.decider(evt("Read", file_path="x"), {"lease": None}, None))

    def test_ecriture_et_commande_sous_bail(self):
        self.assertIsNone(garde.decider(evt("Edit", file_path="a.py"), self.proj, self.gc))
        self.assertIsNone(garde.decider(evt("Bash", command="npm test"), self.proj, self.gc))

    def test_sans_bail_ou_outil_inconnu_refuse(self):
        self.assertIn("aucun bail", garde.decider(evt("Write"), dict(self.proj, lease=None), self.gc))
        self.assertIn("non projeté", garde.decider(evt("WebFetch"), self.proj, self.gc))
        self.assertIn("non projeté", garde.decider(evt("mcp__x__y"), self.proj, self.gc))

    def test_revocation_refuse_l_appel_suivant(self):
        self.assertIsNone(garde.decider(evt("Bash", command="npm test"), self.proj, self.gc))
        self.gc.revoquer(self.b.id, "révocation par le superviseur")
        self.assertIn("REVOKED", garde.decider(evt("Bash", command="npm test"), self.proj, self.gc))

    def test_expiration_et_changement_de_politique(self):
        self.h.t += dt.timedelta(seconds=601)
        self.assertIn("EXPIRED", garde.decider(evt("Edit"), self.proj, self.gc))
        gc2 = GestionnaireCapacites(self.gc.racine, Politique(), CYCLE, {}, cle=CLE, empreinte_politique="p2")
        b, _ = self.gc.demander({"type": "agent", "id": "database"}, "projet-a", {"id": "M-1/t1"}, {"id": "M-1/t1"},
                                None, ["TEST"], ["workspace"])
        self.assertIn("INVALIDATED", garde.decider(evt("Bash"), dict(self.proj, lease=b.id), gc2))

    def test_autre_acteur_autre_execution_capacite_absente(self):
        self.assertIn("autre acteur", garde.decider(evt("Edit"), dict(self.proj, actor="qa"), self.gc))
        self.assertIn("autre exécution", garde.decider(evt("Edit"), dict(self.proj, execution="M-2/t1"), self.gc))
        b, _ = self.gc.demander({"type": "agent", "id": "database"}, "projet-a", {"id": "M-1/t1"}, {"id": "M-1/t1"},
                                None, ["TEST"], ["workspace"])
        self.assertIn("FILESYSTEM_WRITE", garde.decider(evt("Write"), dict(self.proj, lease=b.id), self.gc))
        self.assertIsNone(garde.decider(evt("Bash"), dict(self.proj, lease=b.id), self.gc))

    def test_bail_altere_refuse(self):
        f = self.gc._fiche(self.b.id)
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["actor"]["id"] = "qa"
        f.write_text(json.dumps(doc), encoding="utf-8")
        self.assertIn("non authentifié", garde.decider(evt("Edit"), dict(self.proj, actor="qa"), self.gc))


class AutoriteDExecutionDeTicket(unittest.TestCase):
    """G4 : une exécution de ticket autorisée (run_ticket) permet d'écrire dans l'espace ET le périmètre du ticket."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.espace = d / "espace"
        (self.espace / "frontend" / "tests").mkdir(parents=True)
        self.exes = d / "executions"
        (self.exes / "EX-1").mkdir(parents=True)
        (self.exes / "EX-1" / "context.json").write_text("{}", encoding="utf-8")
        self.proj = {"lease": None, "actor": "qa", "execution": "C/t",
                     "authority": {"kind": "TICKET_EXECUTION", "execution_id": "EX-1", "worktree": str(self.espace),
                                   "scope": ["frontend/tests/"], "executions_dir": str(self.exes)}}

    def tearDown(self):
        self.tmp.cleanup()

    def ecrire(self, chemin):
        return garde.decider(evt("Write", file_path=chemin), self.proj, None)

    def test_ecriture_dans_le_perimetre(self):
        self.assertIsNone(self.ecrire(str(self.espace / "frontend" / "tests" / "a.test.ts")))
        self.assertIsNone(self.ecrire("frontend/tests/sous/b.test.ts"))
        self.assertIsNone(garde.decider(evt("Bash", command="npm test"), self.proj, None))

    def test_ecriture_hors_perimetre_ou_hors_espace(self):
        self.assertIn("hors du périmètre", self.ecrire(str(self.espace / "frontend" / "src" / "lib" / "utils.ts")))
        self.assertIn("hors du périmètre", self.ecrire(str(self.espace / "frontend" / "tests-bis" / "x.ts")))
        self.assertIn("hors de l'espace", self.ecrire(str(Path(self.tmp.name) / "ailleurs.txt")))
        self.assertIn("hors de l'espace", self.ecrire(str(self.espace / ".." / "x.txt")))
        self.assertIn("sans chemin", self.ecrire(""))

    def test_execution_terminee_ou_inconnue(self):
        (self.exes / "EX-1" / "execution.json").write_text("{}", encoding="utf-8")
        self.assertIn("terminée", self.ecrire("frontend/tests/a.ts"))
        self.assertIn("terminée", garde.decider(evt("Bash", command="npm test"), self.proj, None))
        self.proj["authority"]["execution_id"] = "EX-9"
        self.assertIn("inconnue", self.ecrire("frontend/tests/a.ts"))

    def test_bail_et_execution_de_ticket_ensemble(self):
        # Rôle database : fichiers par l'exécution de ticket (périmètre), commandes de base par le bail.
        gc = GestionnaireCapacites(Path(self.tmp.name) / "leases", Politique(), CYCLE, {"max_duration_s": 600},
                                   cle=CLE, empreinte_politique="p1")
        b, _ = gc.demander({"type": "agent", "id": "qa"}, "projet-a", {"id": "T", "project_id": "projet-a"},
                           {"id": "EX-1"}, "env-1", ["DATABASE_MIGRATION"], ["env-1-db-1"])
        proj = dict(self.proj, lease=b.id, execution="EX-1")
        self.assertIsNone(garde.decider(evt("Write", file_path="frontend/tests/m.sql"), proj, gc))   # sans FS_WRITE
        self.assertIn("hors du périmètre", garde.decider(evt("Write", file_path="db/x.sql"), proj, gc))
        self.assertIsNone(garde.decider(evt("Bash", command="python -P factory.py env sql"), proj, gc))
        gc.revoquer(b.id, "fin")
        self.assertIn("REVOKED", garde.decider(evt("Bash", command="x"), proj, gc))
        (self.exes / "EX-1" / "execution.json").write_text("{}", encoding="utf-8")
        self.assertIn("terminée", garde.decider(evt("Write", file_path="frontend/tests/m.sql"), proj, gc))

    def test_refus_trace_en_processus(self):
        p = Path(self.tmp.name) / "proj-lease.json"
        p.write_text(json.dumps(self.proj), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-P", str(GARDE), str(p)], capture_output=True, text=True, timeout=120,
                           env=env, input=json.dumps(evt("Write", file_path=str(self.espace / "db" / "seed.sql"))))
        self.assertEqual(r.returncode, 2)
        refus = [json.loads(x) for x in p.with_suffix(".refus.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual((refus[0]["tool"], refus[0]["path"]), ("Write", str(self.espace / "db" / "seed.sql")))
        ok = subprocess.run([sys.executable, "-P", str(GARDE), str(p)], capture_output=True, text=True, timeout=120,
                            env=env, input=json.dumps(evt("Write", file_path="frontend/tests/a.test.ts")))
        self.assertEqual(ok.returncode, 0)


class GardeEnProcessus(unittest.TestCase):
    """La garde réelle : sans clé de service (aucune n'existe), aucun appel d'écriture ne passe."""

    def lancer(self, evenement, projection: Path | None):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        args = [sys.executable, "-P", str(GARDE)] + ([str(projection)] if projection else [])
        return subprocess.run(args, input=json.dumps(evenement), capture_output=True, text=True, timeout=120, env=env)

    def test_refus_par_defaut(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "proj.json"
            p.write_text(json.dumps({"lease": "lease-0123456789abcdef", "actor": "database", "execution": "M/t",
                                     "leases_dir": d}), encoding="utf-8")
            self.assertEqual(self.lancer(evt("Read", file_path="x"), p).returncode, 0)
            r = self.lancer(evt("Edit", file_path="x"), p)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertEqual(self.lancer(evt("Edit"), None).returncode, 2)               # projection absente
            p.write_text("{", encoding="utf-8")
            self.assertEqual(self.lancer(evt("Read"), p).returncode, 2)                  # projection illisible


class ProjectionParLeRuntime(unittest.TestCase):
    def test_reglages_et_projection_de_session(self):
        with tempfile.TemporaryDirectory() as d:
            esp = Path(d) / "espace"
            esp.mkdir()
            rt = RuntimeClaudeCode(a_blanc=True, baux=Path(d) / "leases")
            t = Tache("t1", "impl", "database", capacites=["FILESYSTEM_WRITE"])
            ctx = Contexte("M-1", "projet-a", t, Membre("specialist-database-1", "database", "SPECIALIST"),
                           espace=str(esp), bail="lease-0123456789abcdef")
            argv = json.loads(rt.executer(ctx).sortie)
            reglages = json.loads(Path(argv[argv.index("--settings") + 1]).read_text(encoding="utf-8"))
            bloc = reglages["hooks"]["PreToolUse"][0]
            self.assertEqual(bloc["matcher"], "*")
            commandes = [h["command"] for h in bloc["hooks"]]
            self.assertTrue(any("garde_approbations.py" in c for c in commandes))
            garde_bail = next(c for c in commandes if "garde_bail.py" in c)
            projection = Path(garde_bail.rsplit('"', 2)[-2])
            self.assertEqual(json.loads(projection.read_text(encoding="utf-8")),
                             {"lease": "lease-0123456789abcdef", "actor": "database", "execution": "M-1/t1",
                              "leases_dir": (Path(d) / "leases").as_posix(), "authority": None})


if __name__ == "__main__":
    unittest.main()
