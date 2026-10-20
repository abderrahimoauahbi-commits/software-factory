"""J5 : moteur d'états — contrat de transition, preuves, relecteur ≠ auteur, provenance, portes humaines."""
import datetime as dt
import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import CORE, FACTORY
from noyau import preuves
from noyau.approbation import CANAL, TYPE, Magasin, canonique, empreinte, empreinte_enregistrement
from noyau.audit import Journal
from noyau.commandes import Executeur
from noyau.etats import APPLIED, PROVENANCE, REFUSED, WAITING_HUMAN, Machine
from noyau.perimetre import Perimetre, Racine, canonique as chemin_canonique
from noyau.portes import Portes


def _y(p):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


AGENT = {"type": "agent", "id": "backend"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.racine_preuves, self.appro = t / "preuves", t / "approbations"
        self.appro.mkdir()
        self.m = Machine(cycles=_y(CORE / "schemas" / "lifecycles.yaml"),
                         exigences=_y(FACTORY / "policies" / "transitions.yaml"),
                         types_preuve=_y(CORE / "schemas" / "enums.yaml")["EVIDENCE_TYPE"],
                         racine_preuves=self.racine_preuves, journal=Journal(t / "journal.jsonl"),
                         portes=Portes(t / "portes", t / "demandes"), approbations=Magasin(self.appro),
                         roles_par_niveau=_y(FACTORY / "policies" / "policy-engine.yaml")["approval_roles"],
                         roles_revue=_y(FACTORY / "policies" / "human-approval.yaml")["review_roles"])
        p = Perimetre({"R": Racine("R", chemin_canonique(self.tmp.name))}, [], [], [], [])
        self.e = Executeur(autorisees=[["git", "--version"]], jokers={}, perimetre=p)
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def ticket(self, etat, crit="C2", **k):
        t = {"id": "T-1", "project_id": "project-a", "state": etat, "criticality": crit, "author": "backend",
             "objective": "faire x", "specification": {"acceptance_criteria": ["x marche"]},
             "execution": {"agent_id": "backend"}, "scope": {"included": ["src/"]},
             "provenance": {c: f"valeur-{c}" for c in PROVENANCE}}
        t.update(k)
        return t

    def preuve(self, type_="TEST", relecteur=None):
        self.n += 1
        p = preuves.enregistrer_commande(self.e.lancer(["git", "--version"]), type_, f"EV-{self.n}",
                                         self.racine_preuves, "agent:backend")
        p["verified_by"] = relecteur
        return p

    def approuver(self, objet, depart, vers, role="project_owner"):
        ctx = self.m._contexte("ticket", objet, depart, vers)
        e = {"kind": TYPE, "channel": CANAL, "id": "HA-1", "decision": "APPROVED", "approver_role": role,
             "context": ctx, "context_sha256": empreinte(ctx),
             "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        (self.appro / "HA-1.json").write_text(canonique(e), encoding="utf-8")
        return "HA-1"


class ContratDeTransition(Base):
    def test_transition_nominale_et_audit(self):
        t = self.ticket("DRAFT")
        r = self.m.transitionner("ticket", t, "ANALYSIS", AGENT)
        self.assertEqual(r.statut, APPLIED)
        self.assertEqual(t["state"], "ANALYSIS")
        self.assertTrue(self.m.journal.verifier().valide)
        self.assertIsNotNone(r.evenement)

    def test_transition_hors_table(self):
        t = self.ticket("DRAFT")
        r = self.m.transitionner("ticket", t, "MERGED", AGENT)
        self.assertEqual(r.statut, REFUSED)
        self.assertEqual(t["state"], "DRAFT")

    def test_refus_aussi_audite(self):
        self.m.transitionner("ticket", self.ticket("DRAFT"), "MERGED", AGENT)
        evt = self.m.journal.chemin.read_text(encoding="utf-8").splitlines()[-1]
        self.assertIn('"result": "REFUSED"', evt)

    def test_etat_inconnu(self):
        self.assertEqual(self.m.transitionner("ticket", self.ticket("DRAFT"), "TERMINE", AGENT).statut, REFUSED)

    def test_ready_exige_criteres_d_acceptation(self):
        t = self.ticket("DESIGN", specification={"acceptance_criteria": []})
        self.assertEqual(self.m.transitionner("ticket", t, "READY", AGENT).statut, REFUSED)

    def test_c3_exige_une_justification(self):
        t = self.ticket("DESIGN", crit="C3")
        self.assertEqual(self.m.transitionner("ticket", t, "READY", AGENT).statut, REFUSED)
        t["criticality_justification"] = "touche la valorisation du stock"
        self.assertEqual(self.m.transitionner("ticket", t, "READY", AGENT).statut, APPLIED)


class Preuves(Base):
    def test_implemented_sans_preuve(self):
        self.assertEqual(self.m.transitionner("ticket", self.ticket("IN_PROGRESS"), "IMPLEMENTED", AGENT).statut,
                         REFUSED)

    def test_declaration_de_tests_refusee(self):
        t = self.ticket("QA")
        faux = {"type": "TEST", "result": "SUCCESS", "source": "tests passed"}
        self.assertEqual(self.m.transitionner("ticket", t, "ACCEPTED", AGENT, preuves=[faux]).statut, REFUSED)

    def test_preuve_reelle_acceptee(self):
        t = self.ticket("QA")
        self.assertEqual(self.m.transitionner("ticket", t, "ACCEPTED", AGENT, preuves=[self.preuve()]).statut, APPLIED)

    def test_preuve_en_echec_refusee(self):
        p = self.preuve()
        p.update(exit_code=1, result="FAILURE")
        self.assertEqual(self.m.transitionner("ticket", self.ticket("QA"), "ACCEPTED", AGENT, preuves=[p]).statut,
                         REFUSED)


class Revue(Base):
    def test_auteur_ne_se_relit_pas(self):
        t = self.ticket("CODE_REVIEW")
        r = self.m.transitionner("ticket", t, "QA", AGENT, preuves=[self.preuve("REVIEW", relecteur="backend")])
        self.assertEqual(r.statut, REFUSED)
        self.assertTrue(any("I3" in m for m in r.motifs))

    def test_revue_declaree_par_l_agent_refusee(self):
        # T-FACTORY-018 : un relecteur « humain » écrit par l'agent, sans enregistrement de la commande humaine.
        t = self.ticket("CODE_REVIEW")
        r = self.m.transitionner("ticket", t, "QA", AGENT, preuves=[self.preuve("REVIEW", relecteur="humain:revue")])
        self.assertEqual(r.statut, REFUSED)
        self.assertTrue(any("approval_ref" in m for m in r.motifs))


class RevueHumaine(Base):
    """T-FACTORY-018 / ADR-0012 : la preuve REVIEW est la copie d'un enregistrement de la commande humaine."""

    def revue(self, objet, decision="APPROVED", role="project_owner", ident="HA-R1", ticket_id=None):
        ctx = {"kind": "CODE_REVIEW", "project_id": objet["project_id"], "ticket_id": ticket_id or objet["id"],
               "diff_sha256": "0" * 64}
        e = {"kind": TYPE, "channel": CANAL, "id": ident, "decision": decision, "approver_role": role,
             "context": ctx, "context_sha256": empreinte(ctx),
             "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        (self.appro / f"{ident}.json").write_text(canonique(e), encoding="utf-8")
        self.racine_preuves.mkdir(exist_ok=True)
        octets = canonique(e).encode("utf-8")
        (self.racine_preuves / f"{ident}-review.json").write_bytes(octets)
        return {"id": f"EV-{ident}", "type": "REVIEW", "source": ident, "timestamp": e["created_at"],
                "result": "SUCCESS", "approval_ref": ident, "artifact_ref": f"{ident}-review.json",
                "hash": hashlib.sha256(octets).hexdigest(), "generated_by": "humain:commande-d-approbation",
                "verified_by": f"human:{role}", "immutable": True}

    def test_revue_approuvee(self):
        t = self.ticket("CODE_REVIEW")
        self.assertEqual(self.m.transitionner("ticket", t, "QA", AGENT, preuves=[self.revue(t)]).statut, APPLIED)

    def test_modifications_demandees(self):
        t = self.ticket("CODE_REVIEW")
        p = self.revue(t, decision="REJECTED")
        self.assertEqual(self.m.transitionner("ticket", t, "QA", AGENT, preuves=[p]).statut, REFUSED)
        self.assertEqual(self.m.transitionner("ticket", t, "IN_PROGRESS", AGENT, preuves=[p]).statut, APPLIED)

    def test_retour_en_cours_exige_un_refus(self):
        t = self.ticket("CODE_REVIEW")
        self.assertEqual(self.m.transitionner("ticket", t, "IN_PROGRESS", AGENT, preuves=[self.revue(t)]).statut,
                         REFUSED)

    def test_revue_d_un_autre_ticket(self):
        t = self.ticket("CODE_REVIEW")
        r = self.m.transitionner("ticket", t, "QA", AGENT, preuves=[self.revue(t, ticket_id="T-2")])
        self.assertEqual(r.statut, REFUSED)
        self.assertTrue(any("autre ticket" in m for m in r.motifs))

    def test_role_non_habilite(self):
        t = self.ticket("CODE_REVIEW")
        self.assertEqual(self.m.transitionner("ticket", t, "QA", AGENT, preuves=[self.revue(t, role="developer")]).statut,
                         REFUSED)

    def test_enregistrement_modifie(self):
        t = self.ticket("CODE_REVIEW")
        p = self.revue(t, decision="REJECTED")
        chemin = self.appro / "HA-R1.json"
        chemin.write_text(chemin.read_text(encoding="utf-8").replace("REJECTED", "APPROVED"), encoding="utf-8")
        r = self.m.transitionner("ticket", t, "QA", AGENT, preuves=[p])
        self.assertEqual(r.statut, REFUSED)
        self.assertTrue(any("modifié" in m for m in r.motifs))

    def test_relecteur_de_la_preuve_falsifie(self):
        t = self.ticket("CODE_REVIEW")
        p = self.revue(t)
        p["verified_by"] = "human:factory_owner"
        self.assertEqual(self.m.transitionner("ticket", t, "QA", AGENT, preuves=[p]).statut, REFUSED)

    def test_enregistrement_d_approbation_ordinaire_refuse(self):
        # Une approbation humaine qui n'est pas une revue de code ne vaut pas revue.
        t = self.ticket("CODE_REVIEW")
        p = self.revue(t)
        e = yaml.safe_load((self.appro / "HA-R1.json").read_text(encoding="utf-8"))
        e["context"]["kind"] = "AGENT_PROVISIONAL_HABILITATION"
        e["context_sha256"] = empreinte(e["context"])
        e["record_sha256"] = empreinte_enregistrement(e)
        (self.appro / "HA-R1.json").write_text(canonique(e), encoding="utf-8")
        self.assertEqual(self.m.transitionner("ticket", t, "QA", AGENT, preuves=[p]).statut, REFUSED)


class FusionEtPortes(Base):
    def test_provenance_invalide(self):
        t = self.ticket("READY_TO_MERGE")
        t["provenance"].pop("model")
        r = self.m.transitionner("ticket", t, "MERGED", AGENT, preuves=[self.preuve()])
        self.assertEqual(r.statut, REFUSED)
        self.assertTrue(any("PROVENANCE_INVALID" in m for m in r.motifs))

    def test_c2_fusion_directe(self):
        r = self.m.transitionner("ticket", self.ticket("READY_TO_MERGE"), "MERGED", AGENT, preuves=[self.preuve()])
        self.assertEqual(r.statut, APPLIED)

    def test_c3_pas_de_fusion_directe(self):
        r = self.m.transitionner("ticket", self.ticket("READY_TO_MERGE", "C3"), "MERGED", AGENT, preuves=[self.preuve()])
        self.assertEqual(r.statut, REFUSED)

    def test_c3_porte_humaine_sans_reponse(self):
        t = self.ticket("HUMAN_APPROVAL", "C3")
        r = self.m.transitionner("ticket", t, "MERGED", AGENT, preuves=[self.preuve()])
        self.assertEqual(r.statut, WAITING_HUMAN)
        self.assertEqual(t["state"], "HUMAN_APPROVAL")
        self.assertEqual(self.m.portes.statut(r.porte), "PENDING")
        self.assertTrue((Path(self.tmp.name) / "demandes" / f"AR-{r.porte}.json").is_file())

    def test_c3_porte_humaine_approuvee(self):
        t = self.ticket("HUMAN_APPROVAL", "C3")
        ident = self.approuver(t, "HUMAN_APPROVAL", "MERGED")
        r = self.m.transitionner("ticket", t, "MERGED", AGENT, preuves=[self.preuve()], approval_id=ident)
        self.assertEqual(r.statut, APPLIED)
        self.assertTrue(self.m.portes.resolue(r.porte))

    def test_pas_d_heritage_d_approbation(self):
        autre = self.ticket("HUMAN_APPROVAL", "C3", id="T-2")
        ident = self.approuver(autre, "HUMAN_APPROVAL", "MERGED")
        t = self.ticket("HUMAN_APPROVAL", "C3")
        r = self.m.transitionner("ticket", t, "MERGED", AGENT, preuves=[self.preuve()], approval_id=ident)
        self.assertEqual(r.statut, WAITING_HUMAN)

    def test_changement_de_perimetre_invalide(self):
        t = self.ticket("HUMAN_APPROVAL", "C3")
        ident = self.approuver(t, "HUMAN_APPROVAL", "MERGED")
        t["scope"]["included"].append("db/")
        r = self.m.transitionner("ticket", t, "MERGED", AGENT, preuves=[self.preuve()], approval_id=ident)
        self.assertEqual(r.statut, WAITING_HUMAN)

    def test_porte_expiree(self):
        t = self.ticket("HUMAN_APPROVAL", "C3")
        r = self.m.transitionner("ticket", t, "MERGED", AGENT, preuves=[self.preuve()])
        plus_tard = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)
        self.assertEqual(self.m.portes.statut(r.porte, plus_tard), "EXPIRED")


class Execution(Base):
    def execution(self, etat, tentative=1):
        return {"id": "EX-1", "execution_id": "EX-1", "project_id": "project-a", "state": etat,
                "budget": {"attempt": tentative}}

    def test_interrompue_jamais_terminee(self):
        for depart in ("INTERRUPTED", "TIMEOUT", "SECURITY_STOP"):
            with self.subTest(depart=depart):
                r = self.m.transitionner("execution", self.execution(depart), "COMPLETED", AGENT, preuves=[self.preuve()])
                self.assertEqual(r.statut, REFUSED)

    def test_autorisation_exige_allow(self):
        self.assertEqual(self.m.transitionner("execution", self.execution("REQUESTED"), "AUTHORIZED", AGENT,
                                              decision_politique={"decision": "APPROVAL_REQUIRED"}).statut, REFUSED)
        self.assertEqual(self.m.transitionner("execution", self.execution("REQUESTED"), "AUTHORIZED", AGENT,
                                              decision_politique={"decision": "ALLOW"}).statut, APPLIED)

    def test_trois_tentatives_au_plus(self):
        r = self.m.transitionner("execution", self.execution("REQUESTED", 4), "AUTHORIZED", AGENT,
                                 decision_politique={"decision": "ALLOW"})
        self.assertEqual(r.statut, REFUSED)

    def test_arret_toujours_possible(self):
        r = self.m.transitionner("execution", self.execution("RUNNING"), "SECURITY_STOP", AGENT)
        self.assertEqual(r.statut, APPLIED)


if __name__ == "__main__":
    unittest.main()
