"""Policy Engine v1 (J4) : cas nominaux et surtout adversariaux. Défaut : DENY ; seules trois décisions existent."""
import copy
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import CORE, FACTORY, habiliter
from noyau.approbation import CANAL, TYPE, Magasin, canonique, contexte, empreinte, empreinte_enregistrement
from noyau.politique import ALLOW, APPROVAL_REQUIRED, DENY, Moteur, ProjetPolitique
from noyau.registre import charger


def _y(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


REGISTRE = charger(FACTORY)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.racine_a, self.espace_a, self.racine_b = t / "projet-a", t / "espace-a", t / "projet-b"
        for r, ident in ((self.racine_a, "project-a"), (self.espace_a, "project-a"), (self.racine_b, "project-b")):
            (r / "src").mkdir(parents=True)
            (r / "marque.txt").write_text(f"id: {ident}\n", encoding="utf-8")
        self.approbations = t / "approbations"
        self.approbations.mkdir()
        m = _y(CORE / "tests" / "fixtures" / "project-a.factory.yaml")["project"]
        m["agents"]["allowed"] = ["agent-test"]
        m["mcp"]["allowed"] = ["mcp-test"]
        m["quality"]["gates"] = {"unit_tests": {"command": "python -m unittest"}, "build": {"command": "cargo test"}}
        reg = copy.deepcopy(REGISTRE)
        reg.objets["agents"]["backend"]["lifecycle"] = "APPROVED"                      # max C2
        test = copy.deepcopy(reg.objets["agents"]["backend"])
        test.update(id="agent-test", lifecycle="APPROVED")
        test["permissions"]["max_criticality"] = "C4"
        reg.objets["agents"]["agent-test"] = test
        mcp = copy.deepcopy(reg.objets["mcp"]["dbhub"])
        mcp.update(id="mcp-test", lifecycle="APPROVED")
        reg.objets["mcp"]["mcp-test"] = mcp
        mb = copy.deepcopy(m)
        mb["id"] = "project-b"
        marqueurs = [{"file": "marque.txt", "pattern": "^id: project-a$"}]
        self.moteur = Moteur(
            regles=_y(FACTORY / "policies" / "policy-engine.yaml"),
            classes=_y(FACTORY / "policies" / "command-classes.yaml"),
            liste_blanche=_y(FACTORY / "policies" / "command-whitelist.yaml")["allowed"],
            confiance=_y(CORE / "schemas" / "trust.yaml"), racine_scope=_y(FACTORY / "policies" / "root-scope.yaml"),
            registre=reg,
            projets={"project-a": ProjetPolitique("project-a", self.racine_a, m, ["secrets/"], marqueurs),
                     "project-b": ProjetPolitique("project-b", self.racine_b, mb, [],
                                                  [{"file": "marque.txt", "pattern": "^id: project-b$"}])},
            approbations=Magasin(self.approbations))
        habiliter(self.moteur, "backend", projets=("project-a", "project-b"))                # max C2
        habiliter(self.moteur, "agent-test", plafond="C4", projets=("project-a", "project-b"))

    def tearDown(self):
        self.tmp.cleanup()

    def demande(self, **k):
        d = {"actor": {"type": "agent", "id": "backend"}, "project_id": "project-a", "action": "write",
             "ticket": {"id": "T-1", "project_id": "project-a", "criticality": "C2", "scope": {"paths": ["src/"]}},
             "execution": {"id": "EX-1", "worktree": str(self.espace_a)},
             "resource": {"kind": "path", "path": "src/a.py", "environment": "LOCAL"}}
        for cle, v in k.items():
            d[cle] = v
        return d

    def decider(self, d, attendu, regle=None):
        r = self.moteur.decider(d)
        self.assertIn(r.decision, (ALLOW, DENY, APPROVAL_REQUIRED))
        self.assertEqual(r.decision, attendu, f"{r.regle} {r.motifs}")
        if regle:
            self.assertEqual(r.regle, regle, r.motifs)
        return r

    def approuver(self, d, effective, role="project_owner", decision="APPROVED", quand=None, ident="HA-1", **alter):
        """Joue le rôle de l'humain : crée l'enregistrement comme le fait scripts/factory_approve.py."""
        ctx = contexte(d, effective)
        e = {"kind": TYPE, "channel": CANAL, "id": ident, "decision": decision, "approver_role": role,
             "context": ctx, "context_sha256": empreinte(ctx),
             "created_at": (quand or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds")}
        e.update(alter)
        e["record_sha256"] = empreinte_enregistrement(e)
        (self.approbations / f"{ident}.json").write_text(canonique(e), encoding="utf-8")
        return ident


class Nominal(Base):
    def test_lecture_dans_les_chemins(self):
        self.decider(self.demande(action="read", resource={"kind": "path", "path": "src/a.py"}), ALLOW)

    def test_ecriture_dans_espace_isole_et_ticket(self):
        self.decider(self.demande(), ALLOW, "R99")

    def test_commande_de_gate_declaree(self):
        self.decider(self.demande(action="execute", command=["python", "-m", "unittest"]), ALLOW)

    def test_commande_de_lecture_c0(self):
        self.decider(self.demande(action="execute", command=["git", "status", "--short", "--branch"]), ALLOW)

    def test_mcp_approuve_et_autorise(self):
        self.decider(self.demande(action="use_mcp", mcp="mcp-test", resource={"kind": "mcp"}), ALLOW)

    def test_humain_habilite_change_la_politique(self):
        """Identité et rôle fournis par le contexte d'appel authentifié (ADR-0017 D24), pas par la requête."""
        d = {"actor": {"type": "human", "id": "o"}, "action": "change_policy"}
        r = self.moteur.decider(d, appelant={"type": "human", "id": "o", "role": "factory_owner"})
        self.assertEqual((r.decision, r.regle), (ALLOW, "R01"), r.motifs)

    def test_identite_humaine_declaree_par_la_requete_refusee(self):
        """Trou S1 : se déclarer humain et factory_owner dans la requête ne suffit jamais."""
        d = {"actor": {"type": "human", "id": "o", "role": "factory_owner"}, "action": "change_policy"}
        r = self.decider(d, DENY, "R01")
        self.assertIn("contexte d'appel", " ".join(r.motifs))
        autre = self.moteur.decider(d, appelant={"type": "human", "id": "quelqu'un d'autre", "role": "factory_owner"})
        self.assertEqual((autre.decision, autre.regle), (DENY, "R01"))

    def test_role_pris_du_contexte_jamais_de_la_requete(self):
        d = {"actor": {"type": "human", "id": "o", "role": "factory_owner"}, "action": "change_policy"}
        r = self.moteur.decider(d, appelant={"type": "human", "id": "o", "role": "reviewer_senior"})
        self.assertEqual((r.decision, r.regle), (DENY, "R01"), r.motifs)


class Perimetre(Base):
    def test_sortie_par_remontee(self):
        for p in ("../projet-b/src/x.py", "src/../../projet-b/x", "..\\x"):
            with self.subTest(chemin=p):
                self.decider(self.demande(resource={"kind": "path", "path": p}), DENY, "R22")

    def test_chemin_absolu_hors_racine(self):
        self.decider(self.demande(resource={"kind": "path", "path": str(Path(self.tmp.name) / "ailleurs.txt")}),
                     DENY, "R22")

    def test_acces_a_un_autre_projet(self):
        d = self.demande(action="read", resource={"kind": "path", "path": str(self.racine_b / "src" / "x.py")})
        self.decider(d, DENY, "R22")

    def test_lien_vers_l_exterieur(self):
        lien = self.espace_a / "src" / "lien"
        try:
            os.symlink(self.racine_b, lien, target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name != "nt":
                self.skipTest("création de lien non permise sur ce poste")
            # Jonction Windows : aucune élévation de privilège requise, même effet d'évasion.
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(lien), str(self.racine_b)], capture_output=True)
            if r.returncode != 0:
                self.skipTest("ni lien ni jonction possibles sur ce poste")
        self.assertTrue(lien.exists())
        self.decider(self.demande(resource={"kind": "path", "path": "src/lien/x.py"}), DENY, "R22")
        self.decider(self.demande(action="read", resource={"kind": "path", "path": "src/lien/x.py"}), DENY, "R22")

    def test_fichiers_sensibles(self):
        for p in (".env", "src/.env", "secrets/cle.txt", "backups/base.sql", "src/id.pem"):
            with self.subTest(chemin=p):
                self.decider(self.demande(action="read", resource={"kind": "path", "path": p}), DENY, "R23")

    def test_ecriture_hors_ticket(self):
        d = self.demande(resource={"kind": "path", "path": "tests/t.py"})   # dans paths.write, hors ticket
        self.decider(d, DENY, "R25")

    def test_ecriture_hors_chemins_du_projet(self):
        d = self.demande(resource={"kind": "path", "path": "docs/x.md"})
        d["ticket"]["scope"]["paths"] = ["src/", "docs/"]
        self.decider(d, DENY, "R25")

    def test_lecture_hors_chemins(self):
        self.decider(self.demande(action="read", resource={"kind": "path", "path": "outils/x.sh"}), DENY, "R24")

    def test_ecriture_sans_espace_isole(self):
        self.decider(self.demande(execution={"id": "EX-1"}), DENY, "R20")

    def test_espace_isole_d_un_autre_projet(self):
        self.decider(self.demande(execution={"id": "EX-1", "worktree": str(self.racine_b)}), DENY, "R20")


class Criticite(Base):
    def test_c2_ne_fait_pas_du_c4(self):
        self.decider(self.demande(action="delete"), DENY, "R03")

    def test_au_dela_du_maximum_de_l_agent(self):
        d = self.demande()
        d["ticket"]["criticality"] = "C3"
        self.decider(d, DENY, "R08")

    def test_abaissement_refuse(self):
        d = self.demande(actor={"type": "agent", "id": "agent-test"}, criticality="C1")
        d["ticket"]["criticality"] = "C3"
        self.decider(d, DENY, "R07")

    def test_ticket_c0_lecture_seule(self):
        d = self.demande()
        d["ticket"]["criticality"] = "C0"
        self.decider(d, DENY, "R07")

    def test_sans_ticket(self):
        self.decider(self.demande(ticket=None), DENY, "R06")

    def test_ticket_d_un_autre_projet(self):
        d = self.demande()
        d["ticket"]["project_id"] = "project-b"
        self.decider(d, DENY, "R06")

    def test_criticite_inventee(self):
        d = self.demande()
        d["ticket"]["criticality"] = "C5"
        self.decider(d, DENY, "R07")


class Environnement(Base):
    def test_production_interdite_meme_en_lecture(self):
        for action in ("read", "write"):
            with self.subTest(action=action):
                d = self.demande(action=action, resource={"kind": "path", "path": "src/a.py", "environment": "PRODUCTION"})
                self.decider(d, DENY, "R09")

    def test_base_de_production(self):
        d = self.demande(action="db_write", resource={"kind": "database", "id": "base", "environment": "PRODUCTION"})
        self.decider(d, DENY, "R09")

    def proteger_local(self):
        for e in self.moteur.projets["project-a"].manifest["environments"]:
            if e["type"] == "LOCAL":
                e["write_allowed"] = False

    def test_r09_la_base_locale_reste_protegee(self):
        # Environnement LOCAL non inscriptible (il protège une base aux données possiblement réelles).
        self.proteger_local()
        d = self.demande(action="db_write", resource={"kind": "database", "id": "base", "environment": "LOCAL"})
        self.decider(d, DENY, "R09")
        self.decider(self.demande(action="execute", command=["python", "-m", "unittest"]), DENY, "R09")

    def test_r09_fichier_de_l_espace_isole_gouverne_par_les_chemins(self):
        self.proteger_local()
        self.decider(self.demande(), ALLOW)                                          # src/ : chemins ∩ ticket ∩ espace
        self.decider(self.demande(resource={"kind": "path", "path": "tests/t.py", "environment": "LOCAL"}), DENY, "R25")
        self.decider(self.demande(execution={"id": "EX-1"}), DENY, "R20")             # toujours un espace isolé
        self.decider(self.demande(resource={"kind": "path", "path": ".env", "environment": "LOCAL"}), DENY, "R23")

    def test_environnement_non_declare(self):
        self.decider(self.demande(resource={"kind": "path", "path": "src/a.py", "environment": "STAGING"}), DENY, "R09")

    def test_actions_reservees_a_l_humain(self):
        for action in ("network", "deploy", "push", "merge", "delete"):
            with self.subTest(action=action):
                self.decider(self.demande(action=action), DENY, "R03")


class Confiance(Base):
    def test_agent_sans_pouvoir(self):
        for action in ("approve", "grant", "change_policy"):
            with self.subTest(action=action):
                self.decider(self.demande(action=action), DENY, "R01")

    def test_humain_sans_role(self):
        d = {"actor": {"type": "human", "id": "x"}, "action": "change_policy"}
        r = self.moteur.decider(d, appelant={"type": "human", "id": "x", "role": "reviewer_senior"})
        self.assertEqual((r.decision, r.regle), (DENY, "R01"), r.motifs)

    def test_agent_inconnu_ou_non_habilite(self):
        self.decider(self.demande(actor={"type": "agent", "id": "inexistant"}), DENY, "R04")
        self.decider(self.demande(actor={"type": "agent", "id": "qa"}), DENY, "R04")   # DISCOVERED

    def test_agent_non_autorise_par_le_projet(self):
        habiliter(self.moteur, "frontend", projets=("project-a", "project-b"))
        self.decider(self.demande(actor={"type": "agent", "id": "frontend"}), DENY, "R05")

    def test_projet_inconnu(self):
        # G4 : l'habilitation d'un agent est liée à ses projets ; hors d'eux, il est refusé avant le contrôle du projet.
        self.decider(self.demande(project_id="project-z"), DENY, "R04")
        self.decider({"actor": {"type": "system", "id": "bootstrap"}, "project_id": "project-z", "action": "read",
                      "resource": {"path": "src/a.py"}}, DENY, "R05")

    def test_demandes_malformees(self):
        for d in ({}, {"action": "write"}, {"actor": {"type": "robot", "id": "x"}, "action": "write"},
                  self.demande(action="tout_faire"), "pas un objet", None):
            with self.subTest(demande=str(d)[:40]):
                self.decider(d, DENY)

    def test_erreur_interne_donne_deny(self):
        self.decider(self.demande(ticket=["liste", "au lieu d'un objet"]), DENY)


class Commandes(Base):
    def test_commandes_interdites(self):
        for cmd in (["rm", "-rf", "src"], ["git", "push"], ["git", "reset", "--hard"], ["curl", "http://x"],
                    ["psql", "-c", "drop table t"], ["python", "-m", "unittest", "--dangerously-skip-permissions"],
                    ["claude", "mcp", "list"]):
            with self.subTest(commande=cmd):
                self.decider(self.demande(action="execute", command=cmd), DENY, "R13")

    def test_commande_inconnue_et_shell(self):
        for cmd in (["inconnu"], ["python", "x.py;", "rm"], ["python", "$(evil)"], [], None, "chaine"):
            with self.subTest(commande=cmd):
                self.decider(self.demande(action="execute", command=cmd), DENY, "R13")

    def test_outil_hors_projet(self):
        self.decider(self.demande(action="execute", command=["cargo", "test"]), DENY, "R14")

    def test_executable_ambigu_refuse(self):
        # Deux fiches (aucune ne porte le nom de l'exécutable) pour le même exécutable : refus plutôt que deviner.
        reg = self.moteur.registre.objets["tools"]
        for ident in ("outil-x1", "outil-x2"):
            o = copy.deepcopy(reg["python"])
            o["id"] = ident
            o["detection"] = {"adapter": "executable_present", "executable": "outilx"}
            reg[ident] = o
        self.moteur.projets["project-a"].manifest["quality"]["gates"]["x"] = {"command": "outilx run"}
        self.decider(self.demande(action="execute", command=["outilx", "run"]), DENY, "R14")

    def test_outil_hors_ticket(self):
        d = self.demande(action="execute", command=["python", "-m", "unittest"])
        d["ticket"]["tools"] = ["git"]
        self.decider(d, DENY, "R14")


class Mcp(Base):
    def test_mcp_non_approuve(self):
        self.moteur.projets["project-a"].manifest["mcp"]["allowed"].append("dbhub")
        self.decider(self.demande(action="use_mcp", mcp="dbhub", resource={"kind": "mcp"}), DENY, "R15")

    def test_mcp_non_autorise_par_le_projet(self):
        self.moteur.projets["project-a"].manifest["mcp"]["allowed"] = []
        self.decider(self.demande(action="use_mcp", mcp="mcp-test", resource={"kind": "mcp"}), DENY, "R15")

    def test_mcp_hors_ticket(self):
        d = self.demande(action="use_mcp", mcp="mcp-test", resource={"kind": "mcp"})
        d["ticket"]["mcp"] = []
        self.decider(d, DENY, "R15")

    def test_mcp_inconnu(self):
        self.decider(self.demande(action="use_mcp", mcp="fantome", resource={"kind": "mcp"}), DENY, "R15")


class Approbations(Base):
    def c3(self, **k):
        d = self.demande(actor={"type": "agent", "id": "agent-test"}, **k)
        d["ticket"]["criticality"] = "C3"
        return d

    def test_c3_sans_approbation(self):
        r = self.decider(self.c3(), APPROVAL_REQUIRED, "R12")
        self.assertEqual(r.approbation_requise["criticality"], "C3")
        self.assertEqual(r.approbation_requise["context_sha256"], r.empreinte_contexte)

    def test_absence_de_reponse_n_est_pas_un_accord(self):
        self.decider(self.c3(approval_id=None), APPROVAL_REQUIRED)

    def test_c3_avec_approbation_valide(self):
        d = self.c3()
        d["approval_id"] = self.approuver(d, "C3")
        self.decider(d, ALLOW, "R12")

    def test_contexte_modifie_invalide_l_approbation(self):
        d = self.c3()
        d["approval_id"] = self.approuver(d, "C3")
        d["resource"]["path"] = "src/autre.py"
        self.decider(d, APPROVAL_REQUIRED)

    def test_approbation_d_un_autre_ticket(self):
        autre = self.c3()
        autre["ticket"]["id"] = "T-2"
        ident = self.approuver(autre, "C3")
        self.decider(self.c3(approval_id=ident), APPROVAL_REQUIRED)

    def test_enregistrement_falsifie(self):
        d = self.c3()
        d["approval_id"] = self.approuver(d, "C3")
        f = self.approbations / f"{d['approval_id']}.json"
        e = json.loads(f.read_text(encoding="utf-8"))
        e["approver_role"] = "factory_owner"
        f.write_text(canonique(e), encoding="utf-8")
        self.decider(d, APPROVAL_REQUIRED)

    def test_role_non_habilite(self):
        d = self.c3()
        d["approval_id"] = self.approuver(d, "C3", role="data_owner")
        self.decider(d, APPROVAL_REQUIRED)

    def test_approbation_expiree(self):
        d = self.c3()
        d["approval_id"] = self.approuver(d, "C3", quand=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10))
        self.decider(d, APPROVAL_REQUIRED)

    def test_refus_humain(self):
        d = self.c3()
        d["approval_id"] = self.approuver(d, "C3", decision="REJECTED")
        self.decider(d, APPROVAL_REQUIRED)

    def test_ancienne_fiche_ecrite_par_l_agent(self):
        d = self.c3()
        d["approval_id"] = self.approuver(d, "C3", kind="EXCEPTION", channel="agent-transcription")
        self.decider(d, APPROVAL_REQUIRED)

    def test_identifiant_piege(self):
        self.decider(self.c3(approval_id="../../etc/passwd"), APPROVAL_REQUIRED)

    def test_commit_controle(self):
        d = self.demande(action="commit", resource={"kind": "vcs"})
        self.decider(d, APPROVAL_REQUIRED)
        d["approval_id"] = self.approuver(d, "C2")
        self.decider(d, ALLOW)

    def test_c4_ecriture_avec_approbation_mais_pas_le_commit(self):
        d = self.demande(actor={"type": "agent", "id": "agent-test"})
        d["ticket"]["criticality"] = "C4"
        self.decider(d, APPROVAL_REQUIRED)
        d["approval_id"] = self.approuver(d, "C4", role="factory_owner")
        self.decider(d, ALLOW)
        c = self.demande(actor={"type": "agent", "id": "agent-test"}, action="commit", resource={"kind": "vcs"})
        c["ticket"]["criticality"] = "C4"
        self.decider(c, DENY, "R11")

    def test_lecture_permise_meme_en_c4(self):
        d = self.demande(actor={"type": "agent", "id": "agent-test"}, action="read")
        d["ticket"]["criticality"] = "C4"
        self.decider(d, ALLOW)


class HabilitationProvisoire(Base):
    """C-17 : un agent non évalué n'agit que sous habilitation provisoire approuvée par l'humain, plafonnée (C1, puis C2 : ADR-0015)."""

    def preparer(self, **modifs):
        from noyau.politique import contexte_habilitation
        agent = self.moteur.registre.objets["agents"]["qa"]                    # DISCOVERED, max C1 par sa fiche
        agent["permissions"]["max_criticality"] = "C2"
        hab = {"max_criticality": "C1", "projects": ["project-a"], "requested_at": dt.date.today().isoformat(),
               "expires_at": (dt.date.today() + dt.timedelta(days=30)).isoformat()}
        hab.update(modifs)
        agent["provisional_habilitation"] = hab
        self.moteur.projets["project-a"].manifest["agents"]["allowed"].append("qa")
        return contexte_habilitation("qa", hab)

    def approuver_hab(self, ctx, role="factory_owner"):
        e = {"kind": TYPE, "channel": CANAL, "id": "HA-HAB", "decision": "APPROVED", "approver_role": role,
             "context": ctx, "context_sha256": empreinte(ctx),
             "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        (self.approbations / "HA-HAB.json").write_text(canonique(e), encoding="utf-8")

    def ecrire_c1(self, projet="project-a"):
        d = self.demande(actor={"type": "agent", "id": "qa"}, project_id=projet)
        d["ticket"]["criticality"] = "C1"
        return d

    def test_sans_approbation_refuse(self):
        self.preparer()
        self.decider(self.ecrire_c1(), DENY, "R04")

    def test_approuvee_permet_c1(self):
        self.approuver_hab(self.preparer())
        self.decider(self.ecrire_c1(), ALLOW)

    def test_plafond_c1_meme_si_la_fiche_dit_c2(self):
        self.approuver_hab(self.preparer())
        d = self.ecrire_c1()
        d["ticket"]["criticality"] = "C2"
        self.decider(d, DENY, "R08")

    def test_autre_projet_refuse(self):
        self.approuver_hab(self.preparer())
        self.moteur.projets["project-b"].manifest["agents"]["allowed"].append("qa")
        d = self.ecrire_c1("project-b")
        d["ticket"]["project_id"] = "project-b"
        self.decider(d, DENY, "R04")

    def test_fiche_modifiee_apres_approbation(self):
        ctx = self.preparer()
        self.approuver_hab(ctx)
        self.moteur.registre.objets["agents"]["qa"]["provisional_habilitation"]["projects"].append("project-b")
        self.decider(self.ecrire_c1(), DENY, "R04")

    def test_c2_approuvee_permet_c2(self):
        # ADR-0015 : plafond relevé à C2 (15/10/2026).
        self.approuver_hab(self.preparer(max_criticality="C2"))
        d = self.ecrire_c1()
        d["ticket"]["criticality"] = "C2"
        self.decider(d, ALLOW)

    def test_plafond_au_dela_de_c2_refuse(self):
        for niveau in ("C3", "C4"):
            self.approuver_hab(self.preparer(max_criticality=niveau))
            self.decider(self.ecrire_c1(), DENY, "R04")

    def test_c1_approuvee_ne_vaut_pas_c2(self):
        # Relever la fiche à C2 sans nouvelle approbation : l'ancienne (C1) ne vaut plus rien.
        self.approuver_hab(self.preparer())
        self.moteur.registre.objets["agents"]["qa"]["provisional_habilitation"]["max_criticality"] = "C2"
        self.decider(self.ecrire_c1(), DENY, "R04")

    def test_expiree_ou_trop_longue(self):
        self.approuver_hab(self.preparer(expires_at=(dt.date.today() - dt.timedelta(days=1)).isoformat()))
        self.decider(self.ecrire_c1(), DENY, "R04")
        self.approuver_hab(self.preparer(expires_at=(dt.date.today() + dt.timedelta(days=90)).isoformat()))
        self.decider(self.ecrire_c1(), DENY, "R04")

    def test_role_non_habilite(self):
        self.approuver_hab(self.preparer(), role="project_owner")
        self.decider(self.ecrire_c1(), DENY, "R04")


class CommandeHumaine(unittest.TestCase):
    def test_refus_hors_console_humaine(self):
        script = FACTORY / "scripts" / "factory_approve.py"
        avant = set((FACTORY / "audit" / "approvals").rglob("*"))
        r = subprocess.run([sys.executable, "-P", str(script), "demande.json"], input="project_owner\n",
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("REFUS", r.stderr)
        self.assertEqual(set((FACTORY / "audit" / "approvals").rglob("*")), avant)


if __name__ == "__main__":
    unittest.main()
