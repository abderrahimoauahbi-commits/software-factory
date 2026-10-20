"""Jalon E1 — premier lot du Master Evolution Prompt v4 (§62), sur le projet pilote, SANS intervention humaine :

    agent → environnement LOCAL_TEST jetable → bail de capacités → base de test (socle réel du pilote)
    → migration → seeder → tests → échec → diagnostic → reset → correction → succès → preuves → destruction

Ce qui est réel : cluster PostgreSQL privé, socle du pilote, SQL exécuté, empreintes d'identité, baux, VRAI Policy
Engine et vraie politique (policies/autonomy.yaml, règles R30–R39, ADR-0016), journal chaîné, preuves hachées,
méta-orchestrateur, superviseur. Ce qui est simulé : l'agent — un runtime scripté dont les erreurs sont volontaires.
Essai sauté si le serveur de base ou le dépôt du pilote est absent. Avec FACTORY_E1_PREUVES=<dossier>, le bilan,
le journal et les preuves y sont copiés.
"""
import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from fournisseurs import cablage
from fournisseurs.postgresql_jetable import PostgresJetable
from noyau import contexte, graphe as G
from noyau import preuves as P
from noyau.audit import Journal
from noyau.baux import GestionnaireCapacites
from noyau.environnements import Gestionnaire
from noyau.mission import Plan
from noyau.orchestrateur import ALLOW, DENY, LECTURE, MetaOrchestrateur
from noyau.organisation import Organisation
from noyau.ressources import Registre
from noyau.runtime import ResultatTache as R, RuntimeScripte, Runtimes
from noyau.superviseur import Budget, Superviseur

PG = PostgresJetable()
CLE = __import__("secrets").token_bytes(32)          # clé jetable de test : aucune clé réelle n'existe
CARTE = yaml.safe_load((FACTORY / "registry/projects/gestionfil/project.yaml").read_text(encoding="utf-8"))
PILOTE = Path(CARTE["root"]["path"])
TYPES_PREUVE = yaml.safe_load((FACTORY / "core/schemas/enums.yaml").read_text(encoding="utf-8"))["EVIDENCE_TYPE"]
def _y(rel):
    return yaml.safe_load((FACTORY / rel).read_text(encoding="utf-8"))


@unittest.skipUnless(PG.disponible()[0] and (PILOTE / "db/pg/socle/schema.sql").is_file(),
                     "serveur de base ou socle du pilote absent")
class PiloteE1(unittest.TestCase):
    maxDiff = None

    def test_boucle_autonome_migration_seeder_tests(self):
        with tempfile.TemporaryDirectory() as d:
            self._derouler(Path(d))

    # ------------------------------------------------------------------------------------------------
    def _derouler(self, racine: Path):
        journal = Journal(racine / "journal.jsonl")
        reg = Registre(racine / "state" / "resources", {PG.id: PG}, racine / "envs")
        envs = Gestionnaire(racine / "envs", _y("orchestrator/environnements.yaml")["profiles"],
                            _y("core/schemas/lifecycles.yaml")["environment"], reg, {PG.kind: PG}, journal)
        socle = cablage.recette_base("gestionfil")                  # lectures soumises au vrai Policy Engine
        debut = dt.datetime.now(dt.timezone.utc)
        env = envs.creer("gestionfil-e1", "gestionfil", "E1", "LOCAL_TEST",
                         [{"kind": "database", "name": "db", "database": "gestionfil_e1", "baseline": socle,
                           "classification": socle["classification"]}])
        try:
            self._mission(racine, journal, reg, envs, env, debut)
        finally:
            if Path(env.root).exists():                          # jamais de cluster orphelin, même en échec
                for rid in env.resources:
                    try:
                        PG.arreter(reg.obtenir(rid))
                    except Exception:
                        pass

    def _mission(self, racine, journal, reg, envs, env, debut):
        rid = env.resources[0]
        res = reg.obtenir(rid)
        self.assertNotEqual(str(res.connection["port"]), "5432")
        construit = (dt.datetime.now(dt.timezone.utc) - debut).total_seconds()

        # 0. Sans le registre des ressources (seule source de l'identité), le vrai moteur refuse : jamais par le nom.
        vrai, _ = contexte.moteur(FACTORY)
        b0, s0 = GestionnaireCapacites(racine / "state" / "leases-vrai", vrai, _y("core/schemas/lifecycles.yaml")
                                       ["capability_lease"], {"max_duration_s": 600}, cle=CLE).demander(
            {"type": "agent", "id": "database"}, "gestionfil", {"id": "E1/migration", "project_id": "gestionfil",
                                                                 "criticality": "C1"}, {"id": "E1/migration"},
            env.id, ["DATABASE_MIGRATION"], [rid])
        self.assertEqual((b0.state, s0["decision"]), ("DENIED", "DENY"))

        politique, _ = contexte.moteur(FACTORY, ressources=reg)     # VRAI Policy Engine, vraie politique
        # Refus attendus du vrai moteur sur la même ressource jetable : capacité non déclarée par la fiche (qa).
        b1, s1 = GestionnaireCapacites(racine / "state" / "leases-refus", politique,
                                       _y("core/schemas/lifecycles.yaml")["capability_lease"], {"max_duration_s": 600}, cle=CLE
                                       ).demander({"type": "agent", "id": "qa"}, "gestionfil",
                                                  {"id": "E1/x", "project_id": "gestionfil", "criticality": "C1"},
                                                  {"id": "E1/x"}, env.id, ["DATABASE_DROP"], [rid])
        self.assertEqual((s1["decision"], b1.decisions[0]["rule"]), ("DENY", "R39"))
        gc = GestionnaireCapacites(racine / "state" / "leases", politique,
                                   _y("core/schemas/lifecycles.yaml")["capability_lease"],
                                   _y("orchestrator/supervision.yaml")["budgets"]["lease"], journal, cle=CLE)
        espace = racine / "espace"
        for sd in ("migrations", "seeds", "tests"):
            (espace / sd).mkdir(parents=True)
        preuves_dir = racine / "preuves"
        acceptees: list[Path] = []
        trace: list[str] = []

        def sql(ctx, capacite, fichier: Path, type_preuve: str):
            """Opération d'AGENT : bail + politique à chaque appel, puis exécution réelle et preuve hachée."""
            dec = gc.autoriser_operation(ctx.bail, {"type": "agent", "id": ctx.tache.role}, "gestionfil",
                                         {"id": f"E1/{ctx.tache.id}", "project_id": "gestionfil", "criticality": "C1"},
                                         {"id": f"E1/{ctx.tache.id}"}, capacite, rid)
            if dec["decision"] != ALLOW:
                return None, R(False, "POLICY_DENIED", "policy", "; ".join(dec["reasons"]))
            x = PG.executer_sql(reg.obtenir(rid), fichier=str(fichier))
            ident = f"E1-{ctx.tache.id}-{len(list(preuves_dir.glob('*.log'))) + 1 if preuves_dir.is_dir() else 1}"
            preuves_dir.mkdir(exist_ok=True)
            log = preuves_dir / f"{ident}.log"
            log.write_text(f"$ psql -f {fichier.name}\ncode={x.returncode}\n{x.stdout}\n{x.stderr}", encoding="utf-8")
            preuve = {"id": ident, "type": type_preuve, "source": f"psql -f {fichier.name}", "command": f"psql -f {fichier.name}",
                      "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                      "exit_code": x.returncode, "result": "SUCCESS" if x.returncode == 0 else "FAILURE",
                      "artifact_ref": log.name, "hash": hashlib.sha256(log.read_bytes()).hexdigest(),
                      "generated_by": f"agent:{ctx.tache.role}", "verified_by": None, "immutable": True}
            self.assertTrue(P.verifier(preuve, TYPES_PREUVE, preuves_dir).valide)
            trace.append(f"{ctx.tache.id}#{ctx.tache.tentatives + 1} {fichier.name} → code {x.returncode}")
            return x, preuve

        migration = espace / "migrations" / "2026-10-15_remise_fournisseur.sql"
        CREER_HISTO = "CREATE TABLE public.remise_historique (code_fournisseur text NOT NULL, remise_pct numeric(5,2) NOT NULL, date_effet text NOT NULL);\n"

        def agent_migration(ctx):
            if ctx.tache.tentatives == 0:                        # erreur volontaire : faute de frappe + état partiel
                migration.write_text(CREER_HISTO + "ALTER TABLE public.fournisseurs ADD COLUMN remise_pct numeric(5,2);\n",
                                     encoding="utf-8")
            else:                                                # correction après diagnostic
                migration.write_text(CREER_HISTO + "ALTER TABLE public.fournisseur ADD COLUMN remise_pct numeric(5,2) "
                                     "NOT NULL DEFAULT 0 CONSTRAINT ck_fournisseur_remise_pct "
                                     "CHECK (remise_pct BETWEEN 0 AND 100);\n", encoding="utf-8")
            x, p = sql(ctx, "DATABASE_MIGRATION", migration, "MIGRATION")
            if x is None:
                return p
            if x.returncode:
                return R(False, "MIGRATION_FAILED", x.stderr.strip().splitlines()[-1][:120], x.stderr.strip()[-300:],
                         preuves=[p])
            acceptees.append(migration)
            return R(True, motif="migration appliquée", preuves=[p], jetons=1200, appels=6,
                     artefacts=[{"id": "migration-remise", "type": "migration", "contenu": migration.read_text()}])

        seeder = espace / "seeds" / "seed_test_remise.sql"

        def agent_seeder(ctx):
            remise = 150 if ctx.tache.tentatives == 0 else 15    # erreur volontaire : viole la contrainte
            seeder.write_text("BEGIN;\nINSERT INTO public.fournisseur (code_fournisseur, nom, remise_pct) VALUES "
                              f"('TEST-F1', 'Fournisseur test 1', 5), ('TEST-F2', 'Fournisseur test 2', {remise});\n"
                              "COMMIT;\n", encoding="utf-8")
            x, p = sql(ctx, "DATABASE_SEED", seeder, "COMMAND")
            if x is None:
                return p
            if x.returncode:
                return R(False, "SEED_FAILED", x.stderr.strip().splitlines()[-1][:120], x.stderr.strip()[-300:], preuves=[p])
            return R(True, motif="données de test chargées", preuves=[p], jetons=600, appels=3,
                     artefacts=[{"id": "seeder-remise", "type": "seeder", "contenu": seeder.read_text()}])

        def agent_tests(ctx):
            t = espace / "tests" / "test_remise.sql"
            t.write_text("DO $$ BEGIN\n"
                         " IF (SELECT count(*) FROM public.fournisseur WHERE code_fournisseur LIKE 'TEST-F%') <> 2 THEN\n"
                         "   RAISE EXCEPTION 'seeder : 2 fournisseurs de test attendus'; END IF;\n"
                         " BEGIN INSERT INTO public.fournisseur (code_fournisseur, nom, remise_pct) VALUES ('TEST-X','x',101);\n"
                         "   RAISE EXCEPTION 'contrainte de remise absente';\n"
                         " EXCEPTION WHEN check_violation THEN NULL; END;\n"
                         "END $$;\n", encoding="utf-8")
            x, p = sql(ctx, "TEST", t, "TEST")
            if x is None:
                return p
            return R(x.returncode == 0, None if x.returncode == 0 else "TEST_FAILED", "tests", x.stderr[-200:],
                     preuves=[p], jetons=400, appels=2)

        def critique_integrite(ctx):
            t = espace / "tests" / "revue_integrite.sql"
            t.write_text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fournisseur'"
                         " AND column_name='remise_pct' AND is_nullable='NO' AND column_default IS NOT NULL) THEN"
                         " RAISE EXCEPTION 'remise_pct nullable ou sans défaut'; END IF; END $$;\n", encoding="utf-8")
            x, p = sql(ctx, "DATABASE_READ", t, "TEST")
            if x is None:
                return p
            return R(x.returncode == 0, None if x.returncode == 0 else "QUALITY_GATE_FAILED", "revue", x.stderr[-200:],
                     preuves=[p], jetons=300, appels=2)

        def reset(strategie, tache):
            """Stratégie RESET_ENVIRONMENT du superviseur : retour au socle, puis rejeu des migrations acceptées."""
            envs.reinitialiser(env.id, "database")
            for m in acceptees:
                x = PG.executer_sql(reg.obtenir(rid), fichier=str(m))
                assert x.returncode == 0, x.stderr
            trace.append(f"RESET ({tache.id}) → socle + {len(acceptees)} migration(s) rejouée(s)")

        def autoriser(tache, membre):
            if set(tache.capacites) <= LECTURE and not tache.ressources and not (tache.entree or {}).get("critic"):
                return {"decision": ALLOW, "motif": "lecture"}
            b, s = gc.demander({"type": "agent", "id": tache.role}, "gestionfil",
                               {"id": f"E1/{tache.id}", "project_id": "gestionfil", "criticality": "C1"},
                               {"id": f"E1/{tache.id}"}, env.id, tache.capacites, [rid])
            return {"decision": s["decision"], "motif": "; ".join(s["reasons"]) or "bail", "bail": s["lease"],
                    "environnement": {"id": env.id}}

        taches = [
            G.Tache("migration", "Migration : remise fournisseur", "database", ecrit=["migrations/"],
                    ressources=[rid], capacites=["DATABASE_MIGRATION", "DATABASE_SCHEMA_CHANGE"], priorite=50),
            G.Tache("seeder", "Seeder de test", "database", ["migration"], ecrit=["seeds/"], ressources=[rid],
                    capacites=["DATABASE_SEED", "DATABASE_WRITE"]),
            G.Tache("tests", "Tests de la migration", "qa", ["seeder"], ecrit=["tests/test_"], ressources=[rid],
                    capacites=["DATABASE_READ", "TEST"]),
            G.Tache("revue-integrite", "Revue adversariale intégrité", "database", ["seeder"],
                    ecrit=["tests/revue_"], capacites=["DATABASE_READ"],
                    entree={"critic": "DATA_INTEGRITY_REVIEWER"}),
            G.Tache("cloture", "Clôture", "planner", ["tests", "revue-integrite"], capacites=["FILESYSTEM_READ"]),
        ]
        plan = Plan("E1", "gestionfil", {"business": "remises fournisseur dans le coût", "technical": "colonne remise_pct"},
                    ["remise entre 0 et 100, défaut 0"], ["base jetable seulement"], ["database", "qa"], ["ACCOUNTING"],
                    [], ["DATA_INTEGRITY_REVIEWER"], {"requested": False}, taches)
        sup_d = _y("orchestrator/supervision.yaml")
        sup = Superviseur(Budget.depuis(sup_d["budgets"]["execution"]), sup_d["recovery"], sup_d["recoverable_failures"])
        agents = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (FACTORY / "registry/agents").glob("*.yaml")}
        m_agents = yaml.safe_load((PILOTE / "factory.yaml").read_text(encoding="utf-8"))["project"]["agents"]
        orga = Organisation(_y("orchestrator/organisation.yaml"), agents,
                            set(m_agents.get("required", [])) | set(m_agents.get("allowed", [])), 8)
        runtime = RuntimeScripte({"migration": [agent_migration], "seeder": [agent_seeder], "tests": [agent_tests],
                                  "revue-integrite": [critique_integrite], "*": [R(True, motif="synthèse")]})
        orch = MetaOrchestrateur(plan, _y("core/schemas/lifecycles.yaml"), sup_d["human_boundaries"], orga, sup,
                                 Runtimes([runtime]), autoriser=autoriser, environnement=reset,
                                 liberer=lambda t: gc.liberer(f"E1/{t.id}"), journal=journal, espace=str(espace))
        bilan = orch.executer()

        # ---------------------------------------------------------------------------------- vérifications
        self.assertEqual(bilan.etat, "SUCCEEDED", (bilan.taches, bilan.bloquees, trace))
        self.assertEqual(bilan.en_attente_humaine, [])
        self.assertEqual(bilan.metriques["HUMAN_INTERVENTION_RATE"], 0.0)
        self.assertEqual(bilan.metriques["FAILURES"], 2)                     # migration + seeder, voulus
        self.assertEqual(bilan.metriques["RECOVERY_RATE"], 1.0)
        self.assertEqual(sum(1 for l in trace if l.startswith("RESET")), 2)
        self.assertEqual(orch.graphe.tache("migration").role, "database")
        baux = [json.loads(p.read_text(encoding="utf-8")) for p in (racine / "state/leases").glob("lease-*.json")]
        self.assertTrue(baux and all(b["state"] in ("RELEASED", "DENIED") for b in baux))   # fin d'exécution
        self.assertFalse(any(b["state"] == "ACTIVE" for b in baux))
        destruction = envs.detruire(env.id, "fin de l'exécution E1")
        self.assertTrue(destruction["destroyed"], destruction)
        self.assertFalse(Path(env.root).exists())
        self.assertTrue(journal.verifier().valide)
        recap = {"jalon": "E1", "date": debut.isoformat(timespec="seconds"), "etat": bilan.etat,
                 "construction_base_s": round(construit, 1), "taches": bilan.taches, "metriques": bilan.metriques,
                 "trace": trace, "baux": [{k: b[k] for k in ("id", "state", "capabilities", "execution_id")} for b in baux],
                 "sans_registre_des_ressources": {"decision": s0["decision"], "regle": b0.decisions[0]["rule"]},
                 "qa_DATABASE_DROP": {"decision": s1["decision"], "regle": b1.decisions[0]["rule"]},
                 "decision_de_capacite": "Policy Engine réel (policies/autonomy.yaml active, ADR-0016 accepté)",
                 "regles_des_baux": sorted({x["rule"] for b in baux for x in b.get("decisions", [])}),
                 "agent": "runtime scripté (erreurs volontaires)", "journal": journal.verifier().__dict__,
                 "destruction": destruction}
        cible = os.environ.get("FACTORY_E1_PREUVES")
        if cible:
            c = Path(cible)
            c.mkdir(parents=True, exist_ok=True)
            (c / "bilan.json").write_text(json.dumps(recap, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            shutil.copy2(racine / "journal.jsonl", c / "journal.jsonl")
            shutil.copytree(preuves_dir, c / "preuves", dirs_exist_ok=True)
            shutil.copytree(espace, c / "espace", dirs_exist_ok=True)


if __name__ == "__main__":
    unittest.main()
