"""ADR-0022 v2 (modèle canonique GMAO v1.0) : ticket-contrat, résolution READY/BLOCKED, Policy Engine (R40, R41),
contexte par sections, profils de contrôle et de prompt, instantané, prompt effectif A à H, exécution gardée.
Les registres et politiques réels sont lus ; projet, référence d'épinglage et tickets sont des doubles (dossiers
temporaires, jamais un projet réel)."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY
from tests.test_execution import Base
from noyau import resolution as R
from noyau import sections as S

APPROUVES = ["policies/control-profiles.yaml", "registry/prompts/execution-standard.yaml",
             "registry/prompts/execution-standard/A-systeme.md", "registry/prompts/roles/backend.md",
             "registry/prompts/roles/qa.md"]
VB = yaml.safe_load((FACTORY / "registry/agents/backend.yaml").read_text(encoding="utf-8"))["version"]
PROFILS = yaml.safe_load((FACTORY / "policies/control-profiles.yaml").read_text(encoding="utf-8"))
ENVS = set(yaml.safe_load((FACTORY / "policies/autonomy.yaml").read_text(encoding="utf-8"))["profiles"])


def _sha(rel):
    return hashlib.sha256((FACTORY / rel).read_bytes()).hexdigest()


def ticket_c(**k):
    t = {"schema_version": "1.1", "id": "T-1", "version": 1, "project_id": "project-a", "workflow_id": "feature",
         "title": "Doubler", "objective": "doubler une valeur", "expected_result": "double(2) == 4",
         "requester": "Factory Owner", "state": "READY", "criticality": "C2", "criticality_justification": "logique",
         "classification": {"domain": "calcul", "wave": 1, "flow": None, "business_priority": "sans objet"},
         "agent": {"role": {"id": "backend", "version": VB}, "authorization": {"required_level": "C2", "required_domains": ["calcul"]}},
         "execution": {"agent_id": "backend", "environment_profile": "LOCAL_SANDBOX"},
         "skills": [], "tools": [], "mcp": [],
         "context": {"specification": ["RG-1"], "design": ["docs/conception.md#2-calcul-du-double"], "adr": [],
                     "related_tickets": []},
         "prompt": {"profile": {"id": "execution-standard", "version": "1.0.0"}, "instructions": ["garder la signature"],
                    "forbidden_actions": ["ne pas toucher aux tests existants"]},
         "scope": {"paths": ["src/"]}, "inputs": {"required": ["src/calcul.py"], "optional": []},
         "outputs": {"required": ["src/calcul.py modifié"]},
         "dependencies": {"tickets": [], "informational": [], "decisions": []},
         "specification": {"acceptance_criteria": ["double(2) == 4"], "business_rules": ["RG-1"], "stop_conditions": [],
                           "block_conditions": ["signature imposée incompatible"]},
         "quality": {"required_gates": ["unit_tests"], "required_tests": ["tests/test_calcul.py"]},
         "control_profile": {"id": "AUTONOME_RELU", "version": "1.0"}, "governance": {"ticket_decisions": []},
         "approvals": {"required": [], "status": "PENDING"}, "evidence": {"required": [], "collected": []},
         "budget": {"max_attempts": 3}}
    for cle, v in k.items():
        cible, *reste = cle.split("__")
        if reste:
            t[cible] = dict(t[cible], **{reste[0]: v})
        else:
            t[cle] = v
    return t


class Contrat(Base):
    def setUp(self):
        super().setUp()
        (self.depot / "docs").mkdir()
        (self.depot / "docs" / "conception.md").write_text(
            "# Conception\n\n## 1. Généralités\n\ntexte\n\n## 2. Calcul du double\n\nLe double vaut 2 × x.\n\n"
            "### 2.1 Détail\n\ndétail\n\n## 3. Autre\n\nautre\n", encoding="utf-8")
        (self.depot / "docs" / "spec.md").write_text(
            "# Spécification\n\n| Règle | Énoncé |\n|---|---|\n| RG-1 | le double est exact |\n| RG-10 | autre |\n",
            encoding="utf-8")
        m = self.moteur.projets["project-a"].manifest
        m["paths"]["read"] = list(m["paths"]["read"]) + ["docs/"]
        m["context"] = {"specification": "docs/spec.md"}
        reg = self.moteur.registre
        reg.validateur.index["projects"] = set(reg.validateur.index["projects"]) | {"project-a"}
        reg.objets["agents"]["backend"]["domains"] = {"project-a": ["calcul"]}
        self.reference = {"id": "HA-essai", "context": {"files": {rel: _sha(rel) for rel in APPROUVES}}}
        self.tickets, self.decisions, self.adr = {}, {}, set()

    def src(self, **k):
        d = dict(racine_factory=FACTORY, registre=self.moteur.registre, moteur=self.moteur, projet_id="project-a",
                 reference_epinglage=self.reference, statut_epinglage="PINNED", empreinte_politique="f" * 64,
                 profils_controle=PROFILS, profils_environnement=ENVS, decisions=self.decisions,
                 adr_acceptes=self.adr, inventaire={}, manifest_sha256="m" * 64)
        d.update(k)
        return R.Sources(**d)

    def resoudre(self, t, **k):
        return R.resoudre(t, None, self.tickets, self.src(**k))

    def motif(self, r, texte):
        self.assertTrue(any(texte in m for m in r.motifs), (texte, r.statut, r.motifs))

    # ------------------------------------------------------------------ verdict READY et contenu
    def test_contrat_complet_ready(self):
        r = self.resoudre(ticket_c())
        self.assertEqual((r.statut, r.motifs), (R.READY, []))
        self.assertEqual(r.profil["permissions"]["write"], ["src/"])
        self.assertEqual((r.profil["role"]["ref"], r.profil["role"]["reviewer"]), (f"backend@{VB}", "qa"))
        s = r.instantane
        self.assertEqual((s["control_profile"]["ref"], s["prompt_profile"]["ref"]), ("AUTONOME_RELU@1.0", "execution-standard@1.0.0"))
        self.assertEqual(s["policy_decision"]["decision"], "ALLOW")
        self.assertEqual([c["ref"] for c in s["context"]], ["RG-1", "docs/conception.md#2-calcul-du-double"])
        self.assertTrue(all(len(c["sha256"]) == 64 for c in s["context"]))
        self.assertEqual(s["prompt_sha256"], hashlib.sha256(r.prompt.encode("utf-8")).hexdigest())
        self.assertEqual(s["role"]["prompt_sha256"], _sha("registry/prompts/roles/backend.md"))

    def test_prompt_parties_a_a_h_dans_l_ordre(self):
        p = self.resoudre(ticket_c()).prompt
        positions = [p.index(f"## {x}.") for x in "ABCDEFGH"]
        self.assertEqual(positions, sorted(positions))
        for attendu in ("Le double vaut 2 × x.", "| RG-1 | le double est exact |", "garder la signature",
                        "ne pas toucher aux tests existants", "signature imposée incompatible",
                        "conditions d'arrêt du Playbook § 9.6"):
            self.assertIn(attendu, p)
        self.assertNotIn("RG-10 | autre", p)                                    # identifiant exact, pas un préfixe
        self.assertNotIn("détail\n\n## 3", p)

    # ------------------------------------------------------------------ BLOCKED
    def test_ticket_non_normalise(self):
        r = self.resoudre({"id": "T-1", "schema_version": "1.0"})
        self.motif(r, "ticket non normalisé")

    def test_to_complete(self):
        r = self.resoudre(ticket_c(scope={"paths": "TO_COMPLETE"}, expected_result="TO_COMPLETE"))
        self.assertIn("scope.paths : TO_COMPLETE", r.motifs)
        self.assertIn("expected_result : TO_COMPLETE", r.motifs)

    def test_plafond_du_role_et_profil_qui_ne_s_abaisse_pas(self):
        r = self.resoudre(ticket_c(criticality="C3", control_profile={"id": "C3", "version": "1.0"},
                                   agent__authorization={"required_level": "C3", "required_domains": ["calcul"]}))
        self.motif(r, "au-delà du plafond du rôle backend (C2)")
        self.motif(self.resoudre(ticket_c(control_profile={"id": "AUTONOME", "version": "1.0"})), "hors du profil AUTONOME")

    def test_approbation_par_l_epinglage(self):
        self.reference["context"]["files"].pop("policies/control-profiles.yaml")
        self.motif(self.resoudre(ticket_c()), "absent de la référence d'épinglage")
        self.reference["context"]["files"]["registry/prompts/roles/backend.md"] = "0" * 64
        self.motif(self.resoudre(ticket_c()), "modifié depuis la référence")
        r = self.resoudre(ticket_c(), reference_epinglage=None, statut_epinglage="UNPINNED")
        self.motif(r, "aucune référence d'épinglage approuvée")
        self.motif(r, "UNPINNED")

    def test_versions_exigees(self):
        r = self.resoudre(ticket_c(agent__role={"id": "backend", "version": "9.9.9"},
                                   control_profile={"id": "AUTONOME_RELU", "version": "0.1"},
                                   prompt__profile={"id": "execution-standard", "version": "2.0.0"}))
        for attendu in ("rôle backend : version 9.9.9 demandée", "profil de contrôle AUTONOME_RELU : version 0.1",
                        "profil de prompt execution-standard : version 2.0.0"):
            self.motif(r, attendu)

    def test_domaine_workflow_et_identite_du_role(self):
        r = self.resoudre(ticket_c(classification={"domain": "ailleurs", "wave": 1},
                                   agent__authorization={"required_level": "C2", "required_domains": ["ailleurs"]},
                                   workflow_id="release", execution={"agent_id": "qa", "environment_profile": "INCONNU"}))
        for attendu in ("domaine 'ailleurs' non autorisé", "workflow 'release' non autorisé",
                        "execution.agent_id 'qa' ≠ agent.role 'backend'", "environment_profile 'INCONNU' inconnu"):
            self.motif(r, attendu)

    def _outils(self, **versions):
        outils = self.moteur.registre.objets["tools"]
        for ident, v in versions.items():
            outils[ident] = dict(outils[ident], version=v)
        self.moteur.projets["project-a"].manifest["tools"]["allowed"] = list(versions)

    def test_outils_epingles_et_observes(self):
        self._outils(python="3.14", node="project")
        t = ticket_c(tools=["python", "node"])
        r = self.resoudre(t, inventaire={"python": "3.14.2", "node": "24.13.0"})
        self.assertEqual((r.statut, r.motifs), (R.READY, []))
        self.assertEqual([e["observed"] for e in r.instantane["tools"]], ["3.14.2", "24.13.0"])
        for inventaire, attendu in (({"python": "3.140.1", "node": "1"}, "version 3.140.1 observée, 3.14 exigée"),
                                    ({"node": "1"}, "python : absent"), ({"python": "", "node": "1"}, "version illisible")):
            self.motif(self.resoudre(t, inventaire=inventaire), attendu)
        self.motif(self.resoudre(ticket_c(tools=["python"], tool_versions={"python": "3.13"}),
                                 inventaire={"python": "3.14.2"}), "3.13 exigée")
        self._outils(python="*")
        r = self.resoudre(ticket_c(tools=["python"]), inventaire=None)
        self.motif(r, "version non épinglée au registre")
        self.motif(r, "présence non vérifiée")

    def test_version_conforme(self):
        self.assertTrue(R.version_conforme("1.93.1", "1.93"))
        self.assertTrue(R.version_conforme("v2.55.0.windows.4", "2.55"))
        self.assertFalse(R.version_conforme("1.930", "1.93"))
        self.assertFalse(R.version_conforme("1.92.0", "1.93"))
        self.assertTrue(R.version_conforme("0.8.1", "project"))
        self.assertFalse(R.version_conforme("", "project"))

    def test_skills(self):
        self.motif(self.resoudre(ticket_c(skills=[{"id": "inconnue", "version": "1.0.0"}])), "skill 'inconnue' inconnue")
        reg = self.moteur.registre.objets
        reg["skills"] = dict(reg.get("skills") or {}, essai={"id": "essai", "version": "1.0.0", "lifecycle": "APPROVED"})
        r = self.resoudre(ticket_c(skills=[{"id": "essai", "version": "1.0.0"}]))
        self.motif(r, "skill essai non autorisée au rôle backend")
        reg["agents"]["backend"]["skills"] = [{"id": "essai", "version": "1.0.0"}]
        self.assertEqual(self.resoudre(ticket_c(skills=[{"id": "essai", "version": "1.0.0"}])).statut, R.READY)

    def test_policy_engine_r40_r41(self):
        d = {"actor": {"type": "agent", "id": "backend"}, "project_id": "project-a", "action": "run_ticket",
             "resource": {"kind": "ticket", "id": "T-1", "environment": "LOCAL"}}
        t = ticket_c()
        self.assertEqual(self.moteur.decider(dict(d, ticket=t)).decision, "ALLOW")
        refus = self.moteur.decider(dict(d, ticket=ticket_c(classification={"domain": "ailleurs"})))
        self.assertEqual((refus.decision, refus.regle), ("DENY", "R40"))
        refus = self.moteur.decider(dict(d, ticket=ticket_c(skills=[{"id": "absente", "version": "1"}])))
        self.assertEqual((refus.decision, refus.regle), ("DENY", "R41"))
        v1 = {"id": "T-1", "project_id": "project-a", "criticality": "C2", "objective": "x", "scope": {"paths": ["src/"]}}
        self.assertEqual(self.moteur.decider(dict(d, ticket=v1)).decision, "ALLOW")   # ticket v1 : sans objet

    def test_contexte_gouverne(self):
        r = self.resoudre(ticket_c(context={"specification": ["RG-99"], "design": ["docs/conception.md#absente",
                                                                                   "id.txt", "../hors.md"],
                                            "adr": [], "related_tickets": ["T-9"]}))
        for attendu in ("RG-99 : section ou identifiant introuvable", "#absente : section ou identifiant introuvable",
                        "id.txt : document hors des chemins lisibles", "../hors.md : chemin hors de la racine",
                        "ticket lié T-9 inconnu"):
            self.motif(r, attendu)
        del self.moteur.projets["project-a"].manifest["context"]
        self.motif(self.resoudre(ticket_c()), "spécification non déclarée par le manifest")

    def test_gates_perimetre_dependances_decisions(self):
        self.tickets = {"T-0": (None, {"id": "T-0", "state": "IN_PROGRESS"})}
        self.decisions = {"P-1": "OPEN", "P-2": "APPROVED"}
        r = self.resoudre(ticket_c(quality={"required_gates": ["inexistante"], "required_tests": []},
                                   scope={"paths": ["docs/"]},
                                   dependencies={"tickets": ["T-0", "T-9"], "informational": ["T-8"],
                                                 "decisions": ["P-1", "P-2", "P-3"]}))
        for attendu in ("gate 'inexistante' absente du manifest", "docs/ hors des chemins d'écriture du manifest",
                        "dépendance T-0 non terminée (IN_PROGRESS)", "dépendance T-9 : ticket inconnu",
                        "dépendance informative T-8", "décision P-1 : OPEN", "décision P-3 : inconnue"):
            self.motif(r, attendu)
        self.assertFalse(any("P-2" in m for m in r.motifs))
        self.tickets["T-0"][1]["state"] = "MERGED"
        r = self.resoudre(ticket_c(dependencies={"tickets": ["T-0"], "decisions": ["P-2"]}))
        self.assertEqual((r.statut, r.motifs), (R.READY, []))

    def test_budget_seulement_plus_restrictif(self):
        r = self.resoudre(ticket_c(budget={"max_attempts": 2, "time_limit_minutes": 60}))
        self.assertEqual((r.statut, r.profil["budget"]), (R.READY, {"max_attempts": 2, "time_limit_minutes": 60}))
        self.motif(self.resoudre(ticket_c(budget={"max_attempts": 5})), "budget.max_attempts 5")

    def test_decision_humaine_et_exception_d_amorcage(self):
        t = ticket_c(control_profile={"id": "DECISION_HUMAINE", "version": "1.0"}, criticality="C0",
                     agent={}, execution={}, scope={"paths": []}, quality={"required_gates": [], "required_tests": []},
                     context={"specification": [], "design": [], "adr": [], "related_tickets": []})
        r = self.resoudre(t)
        self.assertEqual((r.statut, r.motifs), (R.READY, []))
        self.assertIsNone(r.profil["role"])
        self.assertEqual([l for l in r.prompt.splitlines() if l.startswith("## ")], ["## F. F", "## H. H"])
        self.motif(self.resoudre(dict(t, agent={"role": {"id": "backend", "version": VB}})), "aucun rôle ne doit être désigné")
        e = dict(t, control_profile={"id": "EXCEPTION_AMORCAGE", "version": "1.0"}, criticality="C1")
        self.motif(self.resoudre(e), "ADR-0020 non accepté")
        self.adr.add("ADR-0020")
        self.assertEqual(self.resoudre(e).statut, R.READY)

    # ------------------------------------------------------------------ lecture sur place, exécution gardée
    def test_tickets_lus_sur_place_et_lecture_gouvernee(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "docs" / "tickets").mkdir(parents=True)
            (Path(d) / "docs" / "tickets" / "T-1.yaml").write_text(yaml.safe_dump(ticket_c()), encoding="utf-8")
            (Path(d) / "docs" / "tickets" / "T-2.yaml").write_text("id: autre\n", encoding="utf-8")
            tickets, erreurs = R.tickets_du_projet(Path(d), {"tickets": {"path": "docs/tickets"}}, lambda p: True)
            self.assertEqual((list(tickets), len(erreurs)), (["T-1"], 1))
            self.assertIn("hors des chemins lisibles", R.tickets_du_projet(Path(d), {"tickets": {"path": "docs/tickets"}},
                                                                           lambda p: False)[1][0])
            self.assertEqual(R.tickets_du_projet(Path(d), {})[1], ["emplacement des tickets non déclaré par le manifest (tickets.path)"])

    def test_plateforme_exige_une_resolution_ready(self):
        t = ticket_c()
        r = self.resoudre(t)
        vue = R.vue_execution(t, r.profil["permissions"]["write"], r.profil["budget"]["max_attempts"])
        exe = self.plateforme.demarrer(vue, "project-a", "backend", "m")
        self.assertEqual(exe["state"], "BLOCKED")
        self.assertIn("sans résolution READY", exe["errors"][0])
        exe = self.plateforme.demarrer(vue, "project-a", "backend", "m", contrat=r.en_dict(), prompt=r.prompt + "x")
        self.assertEqual(exe["state"], "BLOCKED")
        bloque = copy.deepcopy(r.en_dict()) | {"status": "BLOCKED"}
        self.assertEqual(self.plateforme.demarrer(vue, "project-a", "backend", "m", contrat=bloque, prompt=r.prompt)["state"], "BLOCKED")
        exe = self.plateforme.demarrer(vue, "project-a", "backend", "m", contrat=r.en_dict(), prompt=r.prompt)
        self.assertEqual(exe["state"], "RUNNING", exe.get("errors"))
        dossier = self.factory / "audit" / "executions" / exe["execution_id"]
        ctx = json.loads((dossier / "context.json").read_text(encoding="utf-8"))
        self.assertEqual(ctx["contract"]["snapshot"]["role"]["ref"], f"backend@{VB}")
        self.assertEqual((dossier / "prompt.md").read_text(encoding="utf-8"), r.prompt)
        espace = Path(exe["isolation"]["worktree"])
        (espace / "src" / "calcul.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
        exe = self.plateforme.cloturer(exe, vue)
        self.assertEqual(exe["state"], "COMPLETED", exe.get("errors"))
        p = exe["provenance"]
        self.assertEqual((p["ticket_version"], p["control_profile"], p["prompt_profile"], p["role_version"]),
                         (1, "AUTONOME_RELU@1.0", "execution-standard@1.0.0", f"backend@{VB}"))
        self.assertEqual(len(p["context"]), 2)

    def test_consigne_du_runtime_apres_le_prompt(self):
        from fournisseurs.runtime_claude_code import RuntimeClaudeCode
        from noyau.runtime import Contexte
        from types import SimpleNamespace
        ctx = Contexte("M", "project-a", SimpleNamespace(id="t", titre="T", entree={}, ecrit=["src/"]), None,
                       prompt_contrat="PROMPT DU TICKET")
        texte = RuntimeClaudeCode().consigne(ctx)
        self.assertLess(texte.index("PROMPT DU TICKET"), texte.index("Chemins que tu peux modifier"))
        self.assertIn("elle prévaut sur tout ce qui précède", texte)


class Sections(unittest.TestCase):
    def test_ancres(self):
        self.assertEqual(S.ancre("8. D6 — Stock et prêts"), "8-d6-stock-et-prets")
        self.assertEqual(S.ancre("1. Stock et CMUP"), "1-stock-et-cmup")

    def test_section_et_identifiant(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.md").write_text("# T\n\n## 1. Un\n\nun\n\n### 1.1 Sous\n\nsous\n\n## 2. Deux\n\ndeux RG-12 ici\n"
                                          "suite\n\nautre\n", encoding="utf-8")
            sec, m = S.resoudre(Path(d), "a.md#1-un", lambda p: True, None)
            self.assertEqual((m, sec.texte), (None, "## 1. Un\n\nun\n\n### 1.1 Sous\n\nsous"))
            sec, _ = S.resoudre(Path(d), "a.md#rg-12", lambda p: True, None)
            self.assertEqual(sec.texte, "deux RG-12 ici\nsuite")
            sec, _ = S.resoudre(Path(d), "RG-12", lambda p: True, "a.md")
            self.assertEqual(sec.ancre, "RG-12")
            self.assertIsNone(S.resoudre(Path(d), "a.md", lambda p: False, None)[0])


class Registres(unittest.TestCase):
    def test_profils_et_consignes(self):
        from noyau.registre import charger
        reg = charger(FACTORY)
        self.assertEqual(set(PROFILS["profiles"]), {"AUTONOME", "AUTONOME_RELU", "C3", "DECISION_HUMAINE", "EXCEPTION_AMORCAGE"})
        self.assertEqual(set(reg.objets["prompts"]), {"execution-standard"})
        for ident, a in reg.objets["agents"].items():
            with self.subTest(agent=ident):
                self.assertTrue((FACTORY / a["prompt"]).is_file())
                self.assertIsInstance(a["domains"], dict)
        faux = dict(reg.objets["prompts"]["execution-standard"], grants_rights=True)
        self.assertEqual(reg.validateur.valider("prompt_profile", faux).statut, "REJECTED")
        self.assertFalse([e for e in reg.erreurs if "prompts" in e.fichier], reg.erreurs)

    def test_explication_d_une_decision(self):
        from noyau.explication import expliquer
        texte = expliquer({"kind": "HUMAN_DECISION", "project_id": "p", "decision_id": "P-1", "question": "Q ?",
                           "proposed_answer": "oui"})
        self.assertIn("la décision P-1 du projet p : Q ? — réponse : oui", texte)
        self.assertIn("aucun droit nouveau", texte)


if __name__ == "__main__":
    unittest.main()
