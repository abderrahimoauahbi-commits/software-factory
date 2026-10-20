"""J13 — plateforme d'exécution sur de VRAIS dépôts Git temporaires (jamais un projet réel)."""
import copy
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import CORE, FACTORY, habiliter
from noyau.approbation import CANAL, TYPE, Magasin, canonique, empreinte, empreinte_enregistrement
from noyau.audit import Journal
from noyau.etats import Machine
from noyau.execution import Plateforme
from noyau.politique import Moteur, ProjetPolitique
from noyau.portes import Portes
from noyau.registre import charger


def _y(p):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


REG = charger(FACTORY)


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=essai", "-c", "user.email=essai@exemple.invalid", *args], cwd=cwd,
                   check=True, capture_output=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.depot, self.espaces, self.factory = t / "depot", t / "espaces", t / "factory"
        (self.depot / "src").mkdir(parents=True)
        (self.depot / "tests").mkdir()
        (self.depot / "id.txt").write_text("id: project-a\n", encoding="utf-8")
        (self.depot / "README.md").write_text("doc\n", encoding="utf-8")
        (self.depot / "src" / "calcul.py").write_text("def double(x):\n    return 2 * x\n", encoding="utf-8")
        (self.depot / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.depot / "tests" / "test_calcul.py").write_text(
            "import sys, unittest\nsys.path.insert(0, 'src')\nimport calcul\n\n"
            "class T(unittest.TestCase):\n    def test_double(self):\n        self.assertEqual(calcul.double(2), 4)\n",
            encoding="utf-8")
        git(self.depot, "init", "-q", "-b", "main")
        git(self.depot, "add", "-A")
        git(self.depot, "commit", "-qm", "initial")
        m = _y(CORE / "tests" / "fixtures" / "project-a.factory.yaml")["project"]
        m["paths"] = {"read": ["src/", "tests/", "README.md"], "write": ["src/", "tests/"], "forbidden": [".env"]}
        m["quality"] = {"required": ["unit_tests"], "gates": {"unit_tests": {"command": "python -m unittest discover -s tests"}}}
        reg = copy.deepcopy(REG)
        reg.objets["agents"]["backend"]["lifecycle"] = "APPROVED"
        p = FACTORY / "policies"
        self.moteur = Moteur(regles=_y(p / "policy-engine.yaml"), classes=_y(p / "command-classes.yaml"),
                             liste_blanche=_y(p / "command-whitelist.yaml")["allowed"],
                             confiance=_y(CORE / "schemas" / "trust.yaml"), racine_scope=_y(p / "root-scope.yaml"),
                             registre=reg, projets={"project-a": ProjetPolitique(
                                 "project-a", self.depot, m, [], [{"file": "id.txt", "pattern": "^id: project-a$"}])},
                             approbations=Magasin(self.factory / "appro"))
        habiliter(self.moteur, "backend", projets=("project-a",))
        a = self.factory / "audit"
        self.machine = Machine(cycles=_y(CORE / "schemas" / "lifecycles.yaml"), exigences=_y(p / "transitions.yaml"),
                               types_preuve=_y(CORE / "schemas" / "enums.yaml")["EVIDENCE_TYPE"],
                               racine_preuves=self.factory / "preuves", journal=Journal(a / "journal.jsonl"),
                               portes=Portes(a / "gates", a / "requests"), approbations=Magasin(self.factory / "appro"),
                               roles_par_niveau=_y(p / "policy-engine.yaml")["approval_roles"],
                               roles_revue=_y(p / "human-approval.yaml")["review_roles"])
        config = _y(p / "execution.yaml")
        config["workspaces_root"] = str(self.espaces)
        self.plateforme = Plateforme(self.factory, self.moteur, self.machine, config, _y(p / "root-scope.yaml"))

    def tearDown(self):
        subprocess.run(["git", "worktree", "prune"], cwd=self.depot, capture_output=True)
        self.tmp.cleanup()

    def ticket(self, crit="C2", portee=("src/",)):
        return {"id": "T-1", "project_id": "project-a", "criticality": crit, "objective": "doubler",
                "scope": {"paths": list(portee)}}


class Pipeline(Base):
    def test_execution_complete(self):
        t = self.ticket()
        exe = self.plateforme.demarrer(t, "project-a", "backend", "modele-essai")
        self.assertEqual(exe["state"], "RUNNING", exe.get("errors"))
        espace = Path(exe["isolation"]["worktree"])
        self.assertTrue(str(espace).startswith(str(self.espaces)))
        self.assertTrue((self.factory / "audit" / "executions" / exe["execution_id"] / "context.json").is_file())
        # L'agent travaille DANS l'espace isolé, dans son périmètre.
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "COMPLETED", exe.get("errors"))
        self.assertEqual(exe["changes"], ["src/calcul.py"])
        self.assertEqual({p["type"] for p in exe["evidence"]}, {"ARTIFACT", "TEST"})
        self.assertTrue(all(exe["provenance"][k] not in (None, "") for k in exe["provenance"]))
        # Le dépôt principal n'a pas été touché ; le journal est intact.
        statut = subprocess.run(["git", "status", "--porcelain"], cwd=self.depot, capture_output=True, text=True)
        self.assertEqual(statut.stdout.strip(), "")
        self.assertTrue(self.machine.journal.verifier().valide)

    def test_branche_dediee(self):
        exe = self.plateforme.demarrer(self.ticket(), "project-a", "backend", "m")
        branche = subprocess.run(["git", "branch", "--show-current"], cwd=exe["isolation"]["worktree"],
                                 capture_output=True, text=True).stdout.strip()
        self.assertEqual(branche, exe["isolation"]["branch"])
        self.assertTrue(branche.startswith("factory/T-1/EX-"))


class Gates(Base):
    def test_gate_dans_un_sous_dossier_et_gates_du_ticket(self):
        (self.depot / "front").mkdir()
        (self.depot / "front" / "verif.py").write_text(
            "import pathlib, sys\nsys.exit(0 if pathlib.Path('verif.py').is_file() else 9)\n", encoding="utf-8")
        git(self.depot, "add", "-A")
        git(self.depot, "commit", "-qm", "front")
        q = self.moteur.projets["project-a"].manifest["quality"]
        q["gates"]["front_tests"] = {"command": "python verif.py", "cwd": "front"}
        q["gates"]["casse"] = {"command": "python -c raise"}
        q["required"] = ["unit_tests", "casse"]                      # le projet exigerait un gate cassé…
        t = self.ticket()
        t["quality"] = {"required_gates": ["front_tests"]}         # … le ticket ne demande que le sien
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        (Path(exe["isolation"]["worktree"]) / "src" / "calcul.py").write_text(
            "def double(x):\n    return x + x\n", encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "COMPLETED", exe.get("errors"))
        # Seul le gate du ticket a tourné, dans son sous-dossier ; le gate cassé du projet n'a pas été lancé.
        self.assertEqual([p["id"].rsplit("-", 1)[-1] for p in exe["evidence"] if p["type"] == "TEST"], ["front_tests"])

    def test_gate_du_ticket_non_declare(self):
        t = self.ticket()
        t["quality"] = {"required_gates": ["inexistant"]}
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        (Path(exe["isolation"]["worktree"]) / "src" / "calcul.py").write_text("x = 1\n", encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "FAILED")


class Refus(Base):
    def test_debordement_de_perimetre(self):
        t = self.ticket()
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        espace = Path(exe["isolation"]["worktree"])
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        (espace / "README.md").write_text("modifié hors ticket\n", encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "FAILED")
        self.assertTrue(any("SCOPE_VIOLATION" in e and "README.md" in e for e in exe["errors"]))

    def test_fichier_sensible_cree(self):
        t = self.ticket(portee=("src/",))
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        (Path(exe["isolation"]["worktree"]) / "src" / ".env").write_text("X=1\n", encoding="utf-8")
        self.assertEqual(self.plateforme.cloturer(exe, t)["state"], "FAILED")

    def test_fichier_ignore_par_git_sensible_ou_ordinaire(self):
        # NE3 : un fichier ignoré par git échappe au diff ; un nouveau fichier ignoré SENSIBLE est un débordement,
        # une sortie ignorée ordinaire (build) ne l'est pas.
        (self.depot / ".gitignore").write_text(".env\ndist/\n", encoding="utf-8")
        git(self.depot, "add", ".gitignore")
        git(self.depot, "commit", "-qm", "gitignore")
        t = self.ticket(portee=("src/",))
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        espace = Path(exe["isolation"]["worktree"])
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        (espace / "dist").mkdir()
        (espace / "dist" / "app.js").write_text("// build\n", encoding="utf-8")
        ordinaire = self.plateforme.cloturer(dict(exe), t)
        self.assertEqual(ordinaire["state"], "COMPLETED", ordinaire.get("errors"))
        exe = self.plateforme.demarrer(dict(t, id="T-2"), "project-a", "backend", "m")
        espace = Path(exe["isolation"]["worktree"])
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        (espace / ".env").write_text("SECRET=1\n", encoding="utf-8")                # ignoré par git, hors diff
        exe = self.plateforme.cloturer(exe, dict(t, id="T-2"))
        self.assertEqual(exe["state"], "FAILED")
        self.assertTrue(any("SCOPE_VIOLATION" in e and ".env (ignoré par git)" in e for e in exe["errors"]))

    def test_plantage_d_une_gate_relance_une_fois(self):
        # Un code d'exception du système (0xC0000005 : violation d'accès) est un plantage de l'outil, pas un verdict.
        compteur = self.depot / "tests" / "compteur.txt"
        script = ("import pathlib, sys\np = pathlib.Path('tests/compteur.txt')\nn = int(p.read_text()) if p.exists() "
                  "else 0\np.write_text(str(n + 1))\nsys.exit(0xC0000005 if n == 0 else 0)\n")
        (self.depot / "tests" / "plante.py").write_text(script, encoding="utf-8")
        git(self.depot, "add", "-A")
        git(self.depot, "commit", "-qm", "gate qui plante une fois")
        projet = self.moteur.projets["project-a"]
        projet.manifest["quality"]["gates"]["plante"] = {"command": "python tests/plante.py"}
        self.plateforme.config = dict(self.plateforme.config)
        t = dict(self.ticket(), quality={"required_gates": ["plante"]})
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        (Path(exe["isolation"]["worktree"]) / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n",
                                                                           encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "COMPLETED", exe.get("errors"))
        self.assertEqual(exe["gate_retries"], [{"gate": "plante", "crash_code": 0xC0000005}])
        self.assertFalse(compteur.exists())                       # tout s'est passé dans l'espace isolé

    def test_gate_en_echec(self):
        t = self.ticket()
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        (Path(exe["isolation"]["worktree"]) / "src" / "calcul.py").write_text("def double(x):\n    return 3 * x\n",
                                                                              encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "FAILED")
        self.assertTrue(any("gate unit_tests en échec" in e for e in exe["errors"]))
        self.assertEqual(next(p for p in exe["evidence"] if p["type"] == "TEST")["result"], "FAILURE")

    def test_aucune_modification(self):
        t = self.ticket()
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        self.assertEqual(self.plateforme.cloturer(exe, t)["state"], "FAILED")

    def test_agent_non_habilite(self):
        exe = self.plateforme.demarrer(self.ticket(), "project-a", "qa", "m")
        self.assertEqual(exe["state"], "BLOCKED")
        self.assertFalse(self.espaces.exists() and any(self.espaces.iterdir()))

    def test_c3_sans_approbation(self):
        exe = self.plateforme.demarrer(self.ticket("C3"), "project-a", "backend", "m")
        self.assertEqual(exe["state"], "BLOCKED")                 # backend : max C2

    def test_ticket_sans_perimetre(self):
        self.assertEqual(self.plateforme.demarrer(self.ticket(portee=()), "project-a", "backend", "m")["state"], "BLOCKED")

    def test_quatrieme_tentative_refusee(self):
        t = self.ticket()
        for _ in range(3):
            self.assertEqual(self.plateforme.demarrer(t, "project-a", "backend", "m")["state"], "RUNNING")
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        self.assertEqual(exe["state"], "BLOCKED")
        self.assertTrue(any("tentatives" in e for e in exe["errors"]))

    def test_cloture_hors_running(self):
        exe = self.plateforme.demarrer(self.ticket(), "project-a", "qa", "m")
        self.assertEqual(self.plateforme.cloturer(exe, self.ticket())["state"], "BLOCKED")


class RevueHumaine(Base):
    """T-FACTORY-018 / ADR-0012 : demande de revue liée au diff complet ; preuve tirée de l'enregistrement humain."""

    def executer(self, portee=("src/",)):
        t = self.ticket(portee=portee)
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        espace = Path(exe["isolation"]["worktree"])
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        (espace / "src" / "nouveau.py").write_text("VALEUR = 1\n", encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "COMPLETED", exe.get("errors"))
        t["state"] = "CODE_REVIEW"
        return t, exe, espace

    def enregistrer(self, demande, decision="APPROVED", role="project_owner"):
        """Ce que fait la commande humaine (scripts/factory_approve.py) une fois la confirmation tapée."""
        e = {"kind": TYPE, "channel": CANAL, "id": "HA-REV", "decision": decision, "approver_role": role,
             "context": demande["context"], "context_sha256": demande["context_sha256"], "request": "AR",
             "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        (self.factory / "appro").mkdir(parents=True, exist_ok=True)
        with open(self.factory / "appro" / "HA-REV.json", "x", encoding="utf-8") as f:
            f.write(canonique(e))
        return "HA-REV"

    def test_demande_couvre_le_diff_complet(self):
        t, exe, _ = self.executer()
        demande = json.loads(self.plateforme.demander_revue(exe, t).read_text(encoding="utf-8"))
        ctx = demande["context"]
        self.assertEqual(demande["context_sha256"], empreinte(ctx))
        self.assertEqual((ctx["kind"], ctx["ticket_id"], ctx["author"]), ("CODE_REVIEW", "T-1", "backend"))
        diff = (self.factory / "preuves" / ctx["diff_file"]).read_text(encoding="utf-8")
        self.assertIn("+    return x + x", diff)                     # fichier suivi
        self.assertIn("=== nouveau fichier : src/nouveau.py", diff)   # fichier nouveau, contenu compris
        self.assertEqual(hashlib.sha256(diff.encode("utf-8")).hexdigest(), ctx["diff_sha256"])
        self.assertEqual(demande["roles"], _y(FACTORY / "policies" / "human-approval.yaml")["review_roles"])

    def test_revue_approuvee_jusqu_a_qa(self):
        t, exe, _ = self.executer()
        demande = json.loads(self.plateforme.demander_revue(exe, t).read_text(encoding="utf-8"))
        preuve = self.plateforme.preuve_revue(exe, t, self.enregistrer(demande))
        self.assertEqual((preuve["type"], preuve["review_decision"]), ("REVIEW", "APPROVED"))
        r = self.machine.transitionner("ticket", t, "QA", {"type": "agent", "id": "backend"}, preuves=[preuve])
        self.assertEqual(r.statut, "APPLIED", r.motifs)

    def test_code_modifie_apres_la_revue(self):
        t, exe, espace = self.executer()
        demande = json.loads(self.plateforme.demander_revue(exe, t).read_text(encoding="utf-8"))
        ident = self.enregistrer(demande)
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x * 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changé depuis"):
            self.plateforme.preuve_revue(exe, t, ident)

    def test_modifications_demandees(self):
        t, exe, _ = self.executer()
        demande = json.loads(self.plateforme.demander_revue(exe, t).read_text(encoding="utf-8"))
        preuve = self.plateforme.preuve_revue(exe, t, self.enregistrer(demande, decision="REJECTED"))
        agent = {"type": "agent", "id": "backend"}
        self.assertEqual(self.machine.transitionner("ticket", t, "QA", agent, preuves=[preuve]).statut, "REFUSED")
        self.assertEqual(self.machine.transitionner("ticket", t, "IN_PROGRESS", agent, preuves=[preuve]).statut, "APPLIED")

    def test_revue_exige_l_etat_code_review(self):
        t, exe, _ = self.executer()
        t["state"] = "IMPLEMENTED"
        with self.assertRaisesRegex(ValueError, "CODE_REVIEW"):
            self.plateforme.demander_revue(exe, t)

    def test_sans_enregistrement_humain(self):
        t, exe, _ = self.executer()
        self.plateforme.demander_revue(exe, t)
        with self.assertRaisesRegex(ValueError, "introuvable"):
            self.plateforme.preuve_revue(exe, t, "HA-INEXISTANT")


class DifferencesDExtraction(RevueHumaine):
    """T-FACTORY-019 / ADR-0013 : une différence présente dès la création de l'espace (ex. fins de ligne d'un fichier
    jamais renormalisé) n'est pas un changement de l'agent — tant que son contenu ne bouge pas."""

    def setUp(self):
        super().setUp()
        # Hook post-checkout du dépôt de test : il modifie README.md (hors périmètre) à la création de chaque espace,
        # comme le fait une renormalisation de fins de ligne. Déterministe, contrairement au cas réel.
        hook = self.depot / ".git" / "hooks" / "post-checkout"
        hook.write_bytes(b"#!/bin/sh\necho 'ligne ajoutee a l extraction' >> README.md\n")
        hook.chmod(0o755)

    def test_difference_relevee_a_la_creation(self):
        exe = self.plateforme.demarrer(self.ticket(), "project-a", "backend", "m")
        self.assertEqual(exe["state"], "RUNNING", exe.get("errors"))
        self.assertEqual(list(exe["isolation"]["extraction_differences"]), ["README.md"])
        contexte = json.loads((self.factory / "audit" / "executions" / exe["execution_id"] / "context.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(contexte["execution"]["extraction_differences"], exe["isolation"]["extraction_differences"])

    def test_difference_inchangee_ecartee_et_montree(self):
        t, exe, _ = self.executer()
        self.assertEqual(exe["changes"], ["src/calcul.py", "src/nouveau.py"])
        self.assertEqual(exe["extraction_unchanged"], ["README.md"])
        demande = json.loads(self.plateforme.demander_revue(exe, t).read_text(encoding="utf-8"))
        self.assertEqual(list(demande["context"]["extraction_unchanged"]), ["README.md"])
        diff = (self.factory / "preuves" / demande["context"]["diff_file"]).read_text(encoding="utf-8")
        self.assertNotIn("README.md", diff)
        self.assertNotIn("ligne ajoutee a l extraction", diff)

    def test_difference_retouchee_par_l_agent(self):
        t = self.ticket()
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        espace = Path(exe["isolation"]["worktree"])
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        with open(espace / "README.md", "a", encoding="utf-8") as f:
            f.write("et une ligne de l'agent\n")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "FAILED")
        self.assertTrue(any("SCOPE_VIOLATION" in e and "README.md" in e for e in exe["errors"]))


class SortiesDesGates(RevueHumaine):
    """ADR-0013 : les fichiers produits par les gates sont listés à part et figés avec l'espace."""

    def test_sorties_des_gates_hors_du_diff(self):
        t, exe, _ = self.executer()
        self.assertTrue(exe["gate_outputs"])                                  # caches de python -m unittest
        self.assertTrue(all("__pycache__" in f for f in exe["gate_outputs"]))
        self.assertFalse(set(exe["gate_outputs"]) & set(exe["changes"]))
        demande = json.loads(self.plateforme.demander_revue(exe, t).read_text(encoding="utf-8"))
        self.assertEqual(sorted(demande["context"]["gate_outputs"]), exe["gate_outputs"])
        diff = (self.factory / "preuves" / demande["context"]["diff_file"]).read_text(encoding="utf-8")
        self.assertNotIn("__pycache__", diff)

    def test_fichier_ajoute_apres_la_cloture(self):
        t, exe, espace = self.executer()
        (espace / "src" / "ajout_tardif.py").write_text("X = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changé depuis la clôture"):
            self.plateforme.demander_revue(exe, t)

    def test_sortie_de_gate_modifiee_apres_la_cloture(self):
        t, exe, espace = self.executer()
        (espace / exe["gate_outputs"][0]).write_bytes(b"remplace")
        with self.assertRaisesRegex(ValueError, "changé depuis la clôture"):
            self.plateforme.demander_revue(exe, t)


class PreuveDesChangements(RevueHumaine):
    """T-FACTORY-020 : la preuve de clôture décrit chaque fichier de l'agent, nouveaux compris."""

    def test_modifie_et_nouveau(self):
        t, exe, _ = self.executer()
        p = next(p for p in exe["evidence"] if p["id"].endswith("-changes"))
        texte = (self.factory / "preuves" / p["artifact_ref"]).read_text(encoding="utf-8")
        self.assertIn("modifié  +1 -1  src/calcul.py", texte)
        self.assertRegex(texte, r"nouveau  \d+ octets  src/nouveau\.py")
        self.assertNotIn("VALEUR", texte)                        # jamais le contenu d'un fichier nouveau


class DependancesCopiees(Base):
    """T-FACTORY-020 / ADR-0014 : dépendances copiées (jamais liées) depuis la racine du projet."""

    def setUp(self):
        super().setUp()
        (self.depot / ".gitignore").write_text("deps/\n", encoding="utf-8")
        git(self.depot, "add", ".gitignore")
        git(self.depot, "commit", "-qm", "ignore")
        (self.depot / "deps" / "paquet").mkdir(parents=True)
        (self.depot / "deps" / "paquet" / "index.js").write_text("module.exports = 1\n", encoding="utf-8")
        self.projet = self.moteur.projets["project-a"]
        self.projet.espace = {"copy_from_root": ["deps"]}

    def test_copie_dans_l_espace_et_isolee(self):
        t = self.ticket()
        exe = self.plateforme.demarrer(t, "project-a", "backend", "m")
        self.assertEqual(exe["state"], "RUNNING", exe.get("errors"))
        espace = Path(exe["isolation"]["worktree"])
        self.assertTrue((espace / "deps" / "paquet" / "index.js").is_file())
        self.assertFalse((espace / "deps").is_symlink())
        self.assertEqual(exe["isolation"]["copied_dependencies"]["deps"]["files"], 1)
        # Ce qu'on écrit dans la copie ne touche pas le projet.
        (espace / "deps" / "paquet" / "cache.txt").write_text("x", encoding="utf-8")
        self.assertFalse((self.depot / "deps" / "paquet" / "cache.txt").exists())
        # La copie n'est pas un changement de l'agent.
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        exe = self.plateforme.cloturer(exe, t)
        self.assertEqual(exe["state"], "COMPLETED", exe.get("errors"))
        self.assertEqual(exe["changes"], ["src/calcul.py"])

    def test_refus(self):
        (self.depot / "extra").mkdir()
        (self.depot / "extra" / "a.txt").write_text("a\n", encoding="utf-8")       # non suivi, NON ignoré
        cas = {"../dehors": "non relatif", "C:/absolu": "non relatif", ".env": "sensible",
               "absent": "absente", "src": "déjà présente", "extra": "non ignorée"}
        for chemin, motif in cas.items():
            with self.subTest(chemin=chemin):
                self.projet.espace = {"copy_from_root": [chemin]}
                exe = self.plateforme.demarrer(self.ticket(), "project-a", "backend", "m")
                self.assertEqual(exe["state"], "FAILED")
                self.assertTrue(any(motif in e for e in exe.get("errors", [])), exe.get("errors"))
        # Une dépendance non ignorée n'est jamais laissée dans l'espace.
        espaces = [p for p in self.espaces.iterdir() if p.is_dir()]
        self.assertFalse(any((p / "extra").exists() for p in espaces))


if __name__ == "__main__":
    unittest.main()
