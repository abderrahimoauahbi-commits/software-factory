"""Moteur d'états (jalon J5) : contrat de transition des Executable Schemas §22.

Une transition n'est appliquée que si : l'état courant est l'état de départ ; la table du cycle la contient ;
ses conditions et exigences (policies/transitions.yaml) sont satisfaites, preuves vérifiées comprises ; la
criticité est compatible ; l'approbation humaine requise existe pour CE contexte. Chaque tentative, appliquée
ou refusée, produit un événement d'audit chaîné (§31).

Résultats : APPLIED, REFUSED, WAITING_HUMAN (une porte humaine est ouverte ou en attente).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from . import preuves as _preuves
from . import revue as _revue
from .approbation import Magasin, empreinte
from .audit import Journal
from .portes import Portes
from .validation import valeurs

APPLIED, REFUSED, WAITING_HUMAN = "APPLIED", "REFUSED", "WAITING_HUMAN"
NIVEAUX = ["C0", "C1", "C2", "C3", "C4"]
PROVENANCE = ["project", "ticket", "execution", "agent", "model", "model_version", "factory_version",
              "schema_version", "prompt_version", "tools", "skills", "mcp", "permissions", "branch", "worktree",
              "sandbox", "artifacts", "tests", "reviews", "approvals"]


@dataclass
class Resultat:
    statut: str
    etat: str                                   # état de l'objet après la tentative
    motifs: list[str] = field(default_factory=list)
    evenement: str | None = None
    porte: str | None = None


@dataclass
class Machine:
    cycles: dict                                # core/schemas/lifecycles.yaml
    exigences: dict                             # policies/transitions.yaml
    types_preuve: list[str]                     # enums EVIDENCE_TYPE
    racine_preuves: Path
    journal: Journal
    portes: Portes
    approbations: Magasin
    roles_par_niveau: dict                      # policy-engine.yaml : approval_roles
    age_max_h: int = 72
    roles_revue: list = field(default_factory=list)   # human-approval.yaml : review_roles (vide = aucune revue admise)

    def transitionner(self, cycle: str, objet: dict, vers: str, acteur: dict, preuves: list | None = None,
                      decision_politique: dict | None = None, approval_id: str | None = None) -> Resultat:
        depart = objet.get("state") if isinstance(objet, dict) else None
        motifs = self._controler(cycle, objet, depart, vers, acteur, preuves or [], decision_politique)
        porte = None
        if not motifs:
            besoin_porte = self._porte_requise(cycle, objet, depart, vers)
            if besoin_porte:
                ctx = self._contexte(cycle, objet, depart, vers)
                niveau = objet.get("criticality") if objet.get("criticality") in ("C3", "C4") else "C3"
                roles = self.roles_par_niveau.get(niveau, [])
                verif = self.approbations.verifier(approval_id, ctx, roles, self.age_max_h)
                porte = self.portes.ouvrir(ctx, roles, acteur).get("id")
                if not verif.valide:
                    return self._consigner(Resultat(WAITING_HUMAN, depart, [verif.motif], porte=porte),
                                           cycle, objet, depart, vers, acteur)
                self.portes.resoudre(porte, approval_id)
        if motifs:
            return self._consigner(Resultat(REFUSED, depart, motifs), cycle, objet, depart, vers, acteur)
        return self._consigner(Resultat(APPLIED, vers, ["transition appliquée"], porte=porte),
                               cycle, objet, depart, vers, acteur)

    # ------------------------------------------------------------------ contrôles
    def _controler(self, cycle, objet, depart, vers, acteur, preuves, decision_politique) -> list[str]:
        cyc = self.cycles.get(cycle)
        if not isinstance(objet, dict) or cyc is None:
            return ["objet ou cycle inconnu"]
        if vers not in cyc["states"]:
            return [f"état {vers!r} inconnu du cycle {cycle}"]
        if depart in self.exigences.get("never_success_after", []) and vers in cyc.get("terminal", []) \
                and vers not in cyc.get("any_to", []):
            return [f"une exécution {depart} ne devient jamais {vers} (§7 règle 8)"]
        if depart in cyc.get("terminal", []) and vers not in cyc.get("any_to", []) and not any(
                t["from"] == depart and t["to"] == vers for t in cyc["transitions"]):
            return [f"{depart} est terminal"]
        trans = [t for t in cyc["transitions"] if t["from"] == depart and t["to"] == vers]
        if not trans and vers not in cyc.get("any_to", []):
            return [f"transition {depart} → {vers} absente de la table du cycle {cycle}"]
        motifs = []
        for t in trans[:1]:
            if t.get("condition"):
                cond = self.exigences["conditions"].get(t["condition"])
                if cond is None:
                    return [f"condition {t['condition']!r} sans exigence déclarée (refus par défaut)"]
                motifs += self._exiger(cond, objet, acteur, preuves, decision_politique, condition=True)
        for regle in self.exigences.get("requirements", {}).get(cycle, []):
            if regle["from"] == depart and regle["to"] in (vers, "*"):
                motifs += self._exiger(regle, objet, acteur, preuves, decision_politique)
        return motifs

    def _exiger(self, regle, objet, acteur, preuves, decision_politique, condition=False) -> list[str]:
        motifs = []
        crit = objet.get("criticality")
        for chemin in regle.get("fields", []):
            if not any(v not in (None, "", [], {}) for v in valeurs(objet, chemin)):
                motifs.append(f"champ requis vide : {chemin}")
        for chemin in (regle.get("fields_from") or {}).get(crit, []):
            if not any(v not in (None, "", [], {}) for v in valeurs(objet, chemin)):
                motifs.append(f"{crit} exige : {chemin}")
        if "criticality_max" in regle and (crit not in NIVEAUX or
                                           NIVEAUX.index(crit) > NIVEAUX.index(regle["criticality_max"])):
            motifs.append(f"criticité {crit} au-delà de {regle['criticality_max']} : approbation humaine requise")
        # Seules comptent les preuves vérifiées ET réussies (une revue menée à terme est une preuve REVIEW « SUCCESS » ;
        # sa décision, APPROVED ou CHANGES_REQUESTED, est contrôlée par l'exigence human_review).
        valides = [p for p in preuves
                   if _preuves.verifier(p, self.types_preuve, self.racine_preuves).valide and p.get("result") == "SUCCESS"]
        for t in regle.get("evidence", []):
            if not any(p["type"] == t for p in valides):
                motifs.append(f"preuve {t} valide et réussie absente (une déclaration n'est pas une preuve)")
        if regle.get("reviewer_not_author"):
            auteur = objet.get("author") or (objet.get("execution") or {}).get("agent_id")
            relecteurs = {p.get("verified_by") for p in valides if p["type"] == "REVIEW"}
            if not relecteurs or relecteurs <= {auteur}:
                motifs.append("relecteur absent ou identique à l'auteur (I3)")
        if regle.get("human_review"):
            motifs += self._revue_humaine(regle["human_review"], objet, valides)
        if regle.get("provenance"):
            prov = objet.get("provenance") or {}
            manquants = [c for c in PROVENANCE if prov.get(c) in (None, "")]
            if manquants:
                motifs.append("PROVENANCE_INVALID : " + ", ".join(manquants))
        if "attempts_max" in regle and int((objet.get("budget") or {}).get("attempt", 1)) > regle["attempts_max"]:
            motifs.append(f"tentatives épuisées (> {regle['attempts_max']}) : arrêt obligatoire")
        if regle.get("policy_allow") and (decision_politique or {}).get("decision") != "ALLOW":
            motifs.append("décision du Policy Engine absente ou différente de ALLOW")
        return motifs

    def _revue_humaine(self, decision_attendue, objet, valides) -> list[str]:
        """Au moins une preuve REVIEW adossée à un enregistrement humain valide pour CE ticket, avec la décision
        attendue ; la preuve doit être la copie exacte de l'enregistrement (une revue déclarée ne compte pas)."""
        motifs = []
        for p in (p for p in valides if p["type"] == "REVIEW"):
            verif, e = _revue.verifier(self.approbations, p.get("approval_ref"), objet, self.roles_revue)
            if not verif.valide:
                motifs.append(verif.motif)
                continue
            if p.get("hash") != hashlib.sha256(_revue.octets_enregistrement(e)).hexdigest():
                motifs.append("preuve de revue qui n'est pas la copie de l'enregistrement humain")
            elif p.get("verified_by") != f"human:{e['approver_role']}":
                motifs.append("relecteur de la preuve différent de l'enregistrement humain")
            elif _revue.DECISIONS[e["decision"]] != decision_attendue:
                motifs.append(f"revue humaine : {_revue.DECISIONS[e['decision']]} (attendu : {decision_attendue})")
            else:
                return []
        return motifs or ["revue humaine absente : seule la commande humaine produit une revue (W1)"]

    def _porte_requise(self, cycle, objet, depart, vers) -> bool:
        for t in self.cycles[cycle]["transitions"]:
            if t["from"] == depart and t["to"] == vers and t.get("condition"):
                if (self.exigences["conditions"].get(t["condition"]) or {}).get("human_gate"):
                    return True
        return any(r["from"] == depart and r["to"] in (vers, "*") and r.get("human_gate")
                   for r in self.exigences.get("requirements", {}).get(cycle, []))

    @staticmethod
    def _contexte(cycle, objet, depart, vers) -> dict:
        """Contexte exact d'une transition : une approbation n'est valable que pour lui."""
        return {"cycle": cycle, "object_id": objet.get("id"), "project_id": objet.get("project_id"),
                "criticality": objet.get("criticality"), "from": depart, "to": vers,
                "scope": sorted(((objet.get("scope") or {}).get("included") or []))}

    def _consigner(self, r: Resultat, cycle, objet, depart, vers, acteur) -> Resultat:
        evt = self.journal.ajouter(
            actor={"type": (acteur or {}).get("type"), "id": (acteur or {}).get("id")},
            project_id=(objet or {}).get("project_id") if isinstance(objet, dict) else None,
            ticket_id=(objet or {}).get("id") if cycle == "ticket" and isinstance(objet, dict) else None,
            execution_id=(objet or {}).get("execution_id") if cycle == "execution" and isinstance(objet, dict) else None,
            action=f"transition {cycle}", from_state=depart, to_state=vers, result=r.statut,
            reasons=r.motifs, human_gate=r.porte,
            context_sha256=empreinte(self._contexte(cycle, objet, depart, vers)) if isinstance(objet, dict) else None)
        r.evenement = evt["id"]
        if r.statut == APPLIED and isinstance(objet, dict):
            objet["state"] = vers
        return r
