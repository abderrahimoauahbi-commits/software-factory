"""Policy Engine v1 (jalon J4) : demande → ALLOW | DENY | APPROVAL_REQUIRED, refus par défaut.

Modèle évalué : QUI + QUOI + PROJET + TICKET + CRITICITÉ + ENVIRONNEMENT + RESSOURCE + ACTION + CHEMIN + OUTIL +
MCP + APPROBATION + CONFIANCE. Les règles viennent des données (policies/*.yaml, core/schemas/trust.yaml, registre,
manifest du projet) ; ce module n'en contient aucune.

Ordre : structure → confiance → acteur → projet → ticket → criticité → environnement → ressource (chemin, commande,
MCP…) → approbation → ALLOW explicite. Le premier refus l'emporte ; aucune règle ne permet = DENY.
"""
from __future__ import annotations

import datetime as _dt
import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .approbation import Magasin, contexte, empreinte
from .masquage import masquer
from .validation import chemin_relatif_sur

NIVEAUX = ["C0", "C1", "C2", "C3", "C4"]
ALLOW, DENY, APPROVAL_REQUIRED = "ALLOW", "DENY", "APPROVAL_REQUIRED"
DENY_ABSOLUTE, DENY_BY_POLICY = "DENY_ABSOLUTE", "DENY_BY_POLICY"   # nature d'un refus (ADR-0017 D11)


def niveau(c) -> int:
    return NIVEAUX.index(c) if c in NIVEAUX else -1


def contexte_habilitation(agent_id: str, hab: dict) -> dict:
    """Contexte exact d'une habilitation provisoire : toute modification de la fiche l'invalide."""
    return {"kind": "AGENT_PROVISIONAL_HABILITATION", "agent": agent_id, "max_criticality": hab.get("max_criticality"),
            "projects": sorted(hab.get("projects") or []), "requested_at": str(hab.get("requested_at")),
            "expires_at": str(hab.get("expires_at"))}


def contexte_habilitation_definitive(agent_id: str, hab: dict) -> dict:
    """Contexte exact d'une habilitation définitive (G4) : liée aux preuves d'évaluation ; toute modification de la
    fiche, de la suite ou du rapport l'invalide."""
    ev = hab.get("evaluation") or {}
    return {"kind": "AGENT_HABILITATION", "agent": agent_id, "max_criticality": hab.get("max_criticality"),
            "projects": sorted(hab.get("projects") or []), "model": hab.get("model"),
            "evaluation": {"suite_sha256": ev.get("suite_sha256"), "report_sha256": ev.get("report_sha256")},
            "granted_at": str(hab.get("granted_at")), "expires_at": str(hab.get("expires_at"))}


@dataclass
class Decision:
    decision: str
    regle: str
    motifs: list[str] = field(default_factory=list)
    criticite_effective: str | None = None
    empreinte_contexte: str | None = None
    approbation_requise: dict | None = None
    empreinte_demande: str | None = None
    nature: str | None = None            # DENY seulement : DENY_ABSOLUTE | DENY_BY_POLICY (catalogue, ADR-0017 D11)
    explication: dict | None = None      # catalogue des règles (ADR-0017 D30) : nom, pourquoi, risque, frontière, exception
    exceptions: list[str] | None = None  # exceptions de politique appliquées (PEX-…, ADR-0017 D12, I5)

    def en_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ProjetPolitique:
    id: str
    racine: Path
    manifest: dict                       # bloc « project » du manifest
    sensibles: list[str] = field(default_factory=list)       # chemins sensibles de la carte du projet
    marqueurs: list[dict] = field(default_factory=list)      # marqueurs d'identité (espace isolé du même projet)
    espace: dict = field(default_factory=dict)               # carte « workspace » : copy_from_root (T-FACTORY-020)


@dataclass
class Moteur:
    regles: dict                         # policies/policy-engine.yaml
    classes: dict                        # policies/command-classes.yaml
    liste_blanche: list[list[str]]       # C0 (policies/command-whitelist.yaml)
    confiance: dict                      # core/schemas/trust.yaml
    racine_scope: dict                   # policies/root-scope.yaml (motifs sensibles)
    registre: object                     # noyau.registre.Registre
    projets: dict[str, ProjetPolitique]
    approbations: Magasin
    autonomie: dict = field(default_factory=dict)   # policies/autonomy.yaml (ADR-0016) ; vide = toute capacité DENY
    ressources: object = None                       # noyau.ressources.Registre : seule source de l'identité
    catalogue: dict = field(default_factory=dict)   # policies/rule-catalog.yaml (ADR-0017 D30) ; vide = tout DENY absolu
    exceptions: object = None                       # noyau.derogations.GestionnaireExceptions ; absent = aucune

    # ------------------------------------------------------------------ point d'entrée
    def decider(self, d: dict, appelant: dict | None = None, consommer: bool = False) -> Decision:
        """`appelant` : identité AUTHENTIFIÉE fournie par le code appelant de confiance (ADR-0017 D24), jamais par la
        requête. Une identité humaine déclarée dans le corps de la requête est refusée (R01, refus absolu).

        Exceptions (ADR-0017 F8, I5) : un DENY_BY_POLICY couvert par une exception active de SA règle et de SA portée
        exacte est levé, et l'évaluation REPREND depuis le début sans cette seule règle : toutes les autres restent
        appliquées. `consommer` : l'appelant qui exécute trace un usage de chaque exception appliquée ; la
        qualification seule (`policy check`) ne consomme rien."""
        exemptes, appliquees = set(), []
        while True:
            dec = self._evaluer(d, appelant, frozenset(exemptes))
            if not (dec.decision == DENY and dec.nature == DENY_BY_POLICY and self.exceptions is not None
                    and dec.regle not in exemptes and isinstance(d, dict)):
                break
            try:
                ref = self.exceptions.applicable(dec.regle, d, self.catalogue)
            except Exception:                        # exceptions illisibles : le refus reste
                ref = None
            if not ref:
                break
            exemptes.add(dec.regle)
            appliquees.append(ref)
        if appliquees:
            dec.exceptions = appliquees
            dec.motifs.append("exception(s) de politique appliquée(s) : " + ", ".join(appliquees))
            if consommer and dec.decision == ALLOW:
                for ref in appliquees:
                    self.exceptions.consommer(ref, d, self.catalogue)
        return dec

    def _evaluer(self, d, appelant, exemptes: frozenset) -> Decision:
        try:
            dec = self._decider(d, appelant, exemptes)
        except Exception as e:                       # un moteur de sécurité ne laisse jamais passer sur erreur
            dec = Decision(DENY, "R-ERR", [f"erreur d'évaluation : {type(e).__name__}"])
        dec.empreinte_demande = empreinte(d) if isinstance(d, dict) else None
        dec.motifs = [masquer(m) for m in dec.motifs]
        self._qualifier(dec)
        return dec

    def _qualifier(self, dec: Decision):
        """Nature d'un refus et explication, depuis le catalogue (ADR-0017 D30, D11). Une règle absente du catalogue,
        ou une nature inconnue, donne DENY_ABSOLUTE : le refus par défaut ne s'excepte pas."""
        regle = ((self.catalogue or {}).get("rules") or {}).get(dec.regle)
        if dec.decision == DENY:
            nature = (regle or {}).get("nature")
            dec.nature = nature if nature in (DENY_ABSOLUTE, DENY_BY_POLICY) else DENY_ABSOLUTE
        if regle:
            dec.explication = {"regle": dec.regle, "nom": regle.get("name"), "pourquoi": regle.get("why"),
                               "risque": regle.get("risk"), "frontiere_humaine": regle.get("human_boundary"),
                               "exception": regle.get("exception") if dec.decision == DENY else None}

    # ------------------------------------------------------------------ évaluation
    def _decider(self, d: dict, appelant: dict | None = None, exemptes: frozenset = frozenset()) -> Decision:
        if not isinstance(d, dict):
            return Decision(DENY, "R00", ["demande non structurée"])
        acteur, action = d.get("actor") or {}, d.get("action")
        regle_action = self.regles["actions"].get(action)
        if regle_action is None:
            return Decision(DENY, "R00", [f"action inconnue : {action!r} (refus par défaut)"])
        type_acteur = acteur.get("type")
        if type_acteur not in self.regles["actor_types"] or not acteur.get("id"):
            return Decision(DENY, "R00", ["acteur absent ou de type inconnu"])

        # --- Identité (ADR-0017 D24, trou S1) : une requête peut demander à agir pour un humain, jamais l'affirmer.
        if type_acteur == "human":
            if not isinstance(appelant, dict) or appelant.get("type") != "human" \
                    or appelant.get("id") != acteur.get("id"):
                return Decision(DENY, "R01", ["identité humaine déclarée par la requête : seule une identité "
                                              "authentifiée par le contexte d'appel est admise"])
            acteur = {**acteur, "role": appelant.get("role")}      # le rôle vient du contexte, jamais de la requête

        # --- Confiance (trust.yaml) : les verbes de pouvoir n'appartiennent qu'aux sources autorisées.
        if regle_action.get("power"):
            verbe = regle_action["power"]
            if verbe not in self.confiance["power_verbs"]:
                return Decision(DENY, "R01", [f"verbe de pouvoir {verbe!r} absent du modèle de confiance"])
            sources = self.confiance["power_verbs"][verbe]
            if type_acteur not in sources:
                return Decision(DENY, "R01", [f"{type_acteur} ne peut pas « {action} » (invariants I1, I2)"])
            roles = self.regles["human_power_roles"].get(action, [])
            if acteur.get("role") not in roles:
                return Decision(DENY, "R01", [f"rôle {acteur.get('role')!r} non habilité pour « {action} »"])
            return Decision(ALLOW, "R01", [f"verbe de pouvoir exercé par un humain habilité ({acteur.get('role')})"],
                            criticite_effective=regle_action["criticality"])
        if type_acteur == "human":
            return Decision(DENY, "R02", ["v1 : seules les actions de pouvoir humaines passent par le moteur"])
        if type_acteur == "system" and action != "read":
            return Decision(DENY, "R02", ["un acteur système ne fait que lire"])
        if type_acteur == "agent" and regle_action.get("agent") == "DENY" and "R03" not in exemptes:
            return Decision(DENY, "R03", [f"« {action} » est réservé à l'humain"])

        agent, plafond_provisoire = None, None
        if type_acteur == "agent":
            agent = self.registre.get("agents", acteur["id"])
            if agent is None:
                return Decision(DENY, "R04", [f"agent {acteur['id']!r} inconnu du registre"])
            # G4 : l'état du registre ne suffit pas ; l'habilitation définitive est une approbation humaine W1 liée
            # aux preuves d'évaluation. Son plafond borne la criticité comme celui d'une habilitation provisoire.
            habilite, plafond_hab = self._habilitation(agent, d.get("project_id"))
            if habilite:
                plafond_provisoire = plafond_hab
            elif not (action == "use_capability" and self._ressource_jetable(d)):
                # ADR-0016 (5) : sur une ressource jetable créée par la Factory, le bail borne l'agent ; ailleurs,
                # l'évaluation ou l'habilitation provisoire reste exigée.
                verif, plafond_provisoire = self._habilitation_provisoire(agent, d.get("project_id"))
                if not verif:
                    return Decision(DENY, "R04", [f"agent {acteur['id']!r} non habilité ({agent.get('lifecycle')} : "
                                                  f"{plafond_hab}) ; habilitation provisoire : {plafond_provisoire}"])
            sec = agent.get("security") or {}
            if any(sec.get(k) for k in ("secret_access", "production_access", "destructive_access")):
                return Decision(DENY, "R04", ["agent déclaré avec un accès interdit"])

        # --- Projet (isolation)
        projet = self.projets.get(d.get("project_id"))
        if projet is None:
            return Decision(DENY, "R05", [f"projet {d.get('project_id')!r} non enregistré"])
        if agent is not None:
            m_agents = projet.manifest.get("agents") or {}
            if acteur["id"] not in set(m_agents.get("required", [])) | set(m_agents.get("allowed", [])):
                return Decision(DENY, "R05", [f"agent {acteur['id']!r} non autorisé par le projet"])

        # --- Ticket et criticité
        ticket = d.get("ticket") or {}
        if type_acteur == "agent":
            if not ticket.get("id"):
                return Decision(DENY, "R06", ["aucune action d'agent sans ticket (P04)"])
            if ticket.get("project_id") not in (None, projet.id):
                return Decision(DENY, "R06", ["le ticket appartient à un autre projet"])
        crit_ticket = ticket.get("criticality") or ("C0" if type_acteur == "system" else None)
        if niveau(crit_ticket) < 0:
            return Decision(DENY, "R07", [f"criticité du ticket invalide : {crit_ticket!r}"])
        declaree = d.get("criticality") or crit_ticket
        if niveau(declaree) < 0:
            return Decision(DENY, "R07", [f"criticité déclarée invalide : {declaree!r}"])
        if action == "use_capability":
            if niveau(declaree) < niveau(crit_ticket):
                return Decision(DENY, "R07", [f"abaissement de criticité refusé : {crit_ticket} → {declaree} (P11)"])
            return self._capacite(d, type_acteur, agent, plafond_provisoire, projet, crit_ticket, declaree)
        if niveau(declaree) < niveau(crit_ticket):
            return Decision(DENY, "R07", [f"abaissement de criticité refusé : {crit_ticket} → {declaree} (P11)"])

        intrinseque, motif_cmd = regle_action["criticality"], None
        if intrinseque == "by_command_class":
            intrinseque, motif_cmd = self._classer_commande(d.get("command"), projet)
            if intrinseque is None:
                return Decision(DENY, "R13", [motif_cmd])
        effective = NIVEAUX[max(niveau(crit_ticket), niveau(declaree), niveau(intrinseque))]
        if niveau(crit_ticket) == 0 and action not in ("read", "db_read") and type_acteur == "agent":
            return Decision(DENY, "R07", ["un ticket C0 n'autorise que la lecture"], effective)
        if agent is not None:
            maxi = (agent.get("permissions") or {}).get("max_criticality")
            if plafond_provisoire is not None and niveau(plafond_provisoire) < niveau(maxi):
                maxi = plafond_provisoire                   # habilitation provisoire : plafond plus bas
            if niveau(effective) > niveau(maxi):
                return Decision(DENY, "R08", [f"criticité {effective} au-delà du maximum de l'agent ({maxi})"], effective)

        # --- Environnement
        ressource = d.get("resource") or {}
        env = ressource.get("environment") or "LOCAL"
        envs = [e for e in projet.manifest.get("environments", []) if e.get("type") == env]
        if not envs:
            return Decision(DENY, "R09", [f"environnement {env} non déclaré par le projet"], effective)
        if env == "PRODUCTION" and type_acteur == "agent":
            return Decision(DENY, "R09", ["production interdite à un agent (Executable Schemas §34)"], effective)
        if not any(e.get("allowed") for e in envs):
            return Decision(DENY, "R09", [f"environnement {env} non autorisé par le projet"], effective)
        ecrit = action in self.regles.get("environment_write_actions", ["write", "db_write", "execute", "commit"])
        if ecrit and not any(e.get("write_allowed") for e in envs):
            return Decision(DENY, "R09", [f"écriture interdite dans l'environnement {env}"], effective)

        # --- Ressource
        refus = self._ressource(d, action, projet, ticket, agent, exemptes)
        if refus:
            return Decision(DENY, refus[0], [refus[1]], effective)
        if action in ("read", "db_read"):
            # Lecture permise à tout niveau (Playbook §9.2), une fois périmètre et sensibilité contrôlés.
            return Decision(ALLOW, "R99", [f"lecture permise dans le périmètre ({effective})"], effective)
        if niveau(effective) == 4 and action not in self.regles["c4_agent_with_approval"]:
            return Decision(DENY, "R11", [f"« {action} » en C4 : l'agent prépare, l'humain exécute"], effective)

        # --- Approbation humaine (C3, C4 permis, actions contrôlées)
        controle = bool(regle_action.get("controlled")) or motif_cmd == "controlled"
        if niveau(effective) >= niveau(self.regles["approval_required_from"]) or controle:
            ctx = contexte(d, effective)
            roles = self.regles["approval_roles"]["controlled" if controle and niveau(effective) < 3 else effective]
            verif = self.approbations.verifier(d.get("approval_id"), ctx, roles, self.regles["approval_max_age_hours"])
            requise = {"criticality": effective, "roles": roles, "context_sha256": empreinte(ctx), "context": ctx}
            if not verif.valide:
                return Decision(APPROVAL_REQUIRED, "R12", [verif.motif], effective, empreinte(ctx), requise)
            return Decision(ALLOW, "R12", [verif.motif], effective, empreinte(ctx))
        return Decision(ALLOW, "R99", [f"« {action} » permis en {effective} dans le périmètre"], effective)

    # ------------------------------------------------------------------ capacités et baux (ADR-0016)
    def _ressource_jetable(self, d) -> bool:
        """Ressource jetable créée par la Factory et ACTIVE, selon le registre — jamais selon la demande."""
        if (self.autonomie or {}).get("status") != "active" or self.ressources is None:
            return False
        r = self.ressources.obtenir((d.get("resource") or {}).get("id") or "")
        return bool(r and r.owner == "factory" and r.disposable and r.state == "ACTIVE")

    def _capacite(self, d, type_acteur, agent, plafond_provisoire, projet, crit_ticket, declaree) -> Decision:
        """use_capability : capacité × ressource ENREGISTRÉE × profil × niveau d'autonomie × fiche de l'agent."""
        a = self.autonomie or {}
        if a.get("status") != "active":
            return Decision(DENY, "R30", ["autonomie par capacités non active (policies/autonomy.yaml)"])
        if type_acteur != "agent":
            return Decision(DENY, "R30", ["une capacité ne s'accorde qu'à un agent, par bail"])
        cap = d.get("capability")
        spec = (a.get("capabilities") or {}).get(cap)
        if spec is None:
            return Decision(DENY, "R31", [f"capacité inconnue : {cap!r} (refus par défaut)"])
        lectures = set(a.get("read_capabilities") or [])
        if niveau(crit_ticket) == 0 and cap not in lectures:
            return Decision(DENY, "R07", ["un ticket C0 n'autorise que la lecture"])
        rid = (d.get("resource") or {}).get("id")
        r = self.ressources.obtenir(rid) if (self.ressources is not None and rid) else None
        if r is None:
            return Decision(DENY, "R32", [f"ressource {rid!r} non enregistrée : l'identité ne se déduit jamais d'un nom"])
        if r.project_id != projet.id:
            return Decision(DENY, "R32", ["ressource d'un autre projet (isolation)"])
        if r.state != "ACTIVE":
            return Decision(DENY, "R32", [f"ressource dans l'état {r.state}"])
        if r.kind not in (spec.get("resource") or []):
            return Decision(DENY, "R31", [f"{cap} ne vise pas une ressource de genre {r.kind}"])
        if r.profile == "PRODUCTION":
            return Decision(DENY, "R09", ["production interdite à un agent (Executable Schemas §34)"])
        profil = (a.get("profiles") or {}).get(r.profile)
        if profil is None:
            return Decision(DENY, "R33", [f"profil {r.profile!r} inconnu de la politique"])
        types = set((a.get("profile_environment_types") or {}).get(r.profile) or [])
        if not any(e.get("allowed") and (e.get("profile") == r.profile or e.get("type") in types)
                   for e in projet.manifest.get("environments") or []):
            return Decision(DENY, "R33", [f"le projet ne déclare aucun environnement autorisé pour {r.profile}"])
        effective = NIVEAUX[max(niveau(crit_ticket), niveau(declaree), max(niveau(r.criticality), 0))]
        if agent is not None:
            maxi = (agent.get("permissions") or {}).get("max_criticality")
            if plafond_provisoire is not None and niveau(plafond_provisoire) < niveau(maxi):
                maxi = plafond_provisoire
            if niveau(effective) > niveau(maxi):
                return Decision(DENY, "R08", [f"criticité {effective} au-delà du maximum de l'agent ({maxi})"], effective)
            ouvertes = {c for cat in agent.get("capabilities") or []
                        for c in (a.get("agent_capability_grants") or {}).get(cat, [])}
            if cap not in ouvertes:
                return Decision(DENY, "R39", [f"{cap} non déclarée par la fiche de l'agent {agent.get('id')!r}"], effective)
        niveau_auto = (projet.manifest.get("autonomy") or {}).get("level") or a.get("default_level")
        mode = ((a.get("levels") or {}).get(niveau_auto) or {}).get("mode")
        if mode is None:
            return Decision(DENY, "R34", [f"niveau d'autonomie inconnu : {niveau_auto!r}"], effective)
        if mode == "read_only" and cap not in lectures:
            return Decision(DENY, "R34", [f"niveau {niveau_auto} : lecture seule"], effective)
        approbation = []
        if cap in (profil.get("approval") or []):
            approbation.append(f"{cap} en {r.profile} : approbation humaine")
        elif cap not in (profil.get("allow") or []):
            return Decision(DENY, "R35", [f"{cap} absente de la matrice du profil {r.profile}"], effective)
        jetable = r.owner == "factory" and r.disposable
        if spec.get("destructive") and not jetable:
            if cap not in (profil.get("approval") or []):
                return Decision(DENY, "R36", [f"{cap} destructive hors d'une ressource jetable créée par la Factory"],
                                effective)
        ok, motif = self.ressources.verifier_identite(rid)
        if not ok:
            return Decision(DENY, "R37", [f"identité de {rid} non vérifiée : {motif}"], effective)
        classes = list((a.get("data_classification") or {}).get("order") or [])
        plafond = (a.get("data_classification") or {}).get("autonomous_max")
        if r.classification not in classes or (plafond in classes and
                                                classes.index(r.classification) > classes.index(plafond)):
            approbation.append(f"données {r.classification} : accès sensible (§49)")
        if mode == "approve_writes" and cap not in lectures:
            approbation.append(f"niveau {niveau_auto} : écriture sur approbation")
        if approbation:
            ctx = contexte(d, effective)
            roles = (self.regles["approval_roles"].get(effective) if niveau(effective) >= 3
                     else self.regles["approval_roles"]["controlled"])
            verif = self.approbations.verifier(d.get("approval_id"), ctx, roles, self.regles["approval_max_age_hours"])
            requise = {"criticality": effective, "roles": roles, "context_sha256": empreinte(ctx), "context": ctx}
            if not verif.valide:
                return Decision(APPROVAL_REQUIRED, "R38", approbation + [verif.motif], effective, empreinte(ctx), requise)
            return Decision(ALLOW, "R38", [verif.motif], effective, empreinte(ctx))
        return Decision(ALLOW, "R35", [f"{cap} permis en {r.profile} sur {rid} ({motif})"], effective)

    def plafond_habilite(self, agent: dict, id_projet) -> tuple[bool, str]:
        """(habilité, plafond effectif ou motif) pour un agent et un projet, comme la règle R04/R08 : habilitation
        définitive, sinon provisoire ; le plafond est le plus bas de la fiche et de l'habilitation. Lecture seule."""
        habilite, plafond = self._habilitation(agent, id_projet)
        if not habilite:
            provisoire, plafond_p = self._habilitation_provisoire(agent, id_projet)
            if not provisoire:
                return False, f"non habilité ({agent.get('lifecycle')} : {plafond}) ; habilitation provisoire : {plafond_p}"
            plafond = plafond_p
        maxi = (agent.get("permissions") or {}).get("max_criticality")
        return True, (plafond if niveau(plafond) < niveau(maxi) else maxi)

    # ------------------------------------------------------------------ habilitation provisoire (C-17)
    def _habilitation(self, agent: dict, id_projet) -> tuple[bool, str]:
        """(valide, plafond ou motif). Habilitation définitive (Playbook §12.6, G4) : état approuvé au registre ET
        approbation humaine du bloc `habilitation` (preuves d'évaluation), bornée au projet et dans le temps."""
        if agent.get("lifecycle") not in self.regles["approved_agent_states"]:
            return False, "non évalué"
        regle, hab = self.regles.get("habilitation"), agent.get("habilitation")
        if not regle or not hab:
            return False, "état approuvé sans habilitation approuvée par l'humain"
        plafond = hab.get("max_criticality")
        if niveau(plafond) < 0:
            return False, f"plafond illisible : {plafond!r}"
        if id_projet not in (hab.get("projects") or []):
            return False, f"habilitation non valable pour le projet {id_projet!r}"
        ev = hab.get("evaluation") or {}
        if not (ev.get("suite_sha256") and ev.get("report_sha256")):
            return False, "habilitation sans preuve d'évaluation"
        try:
            fin = _dt.date.fromisoformat(str(hab.get("expires_at")))
            debut = _dt.date.fromisoformat(str(hab.get("granted_at")))
        except ValueError:
            return False, "dates d'habilitation illisibles"
        if (fin - debut).days > regle["max_days"] or _dt.date.today() > fin:
            return False, "habilitation expirée ou plus longue que permis : réévaluation requise"
        verif = self.approbations.trouver(contexte_habilitation_definitive(agent["id"], hab), regle["approver_roles"],
                                          regle["max_days"] * 24)
        return (True, plafond) if verif.valide else (False, verif.motif)

    def _habilitation_provisoire(self, agent: dict, id_projet) -> tuple[bool, str]:
        """(valide, plafond ou motif). Approuvée par l'humain, plafonnée, bornée dans le temps et au projet."""
        hab = agent.get("provisional_habilitation")
        regle = self.regles.get("provisional_habilitation")
        if not hab or not regle:
            return False, "aucune"
        plafond = hab.get("max_criticality")
        if niveau(plafond) < 0 or niveau(plafond) > niveau(regle["criticality_cap"]):
            return False, f"plafond {plafond!r} au-delà de {regle['criticality_cap']}"
        if id_projet not in (hab.get("projects") or []):
            return False, f"non valable pour le projet {id_projet!r}"
        try:
            fin = _dt.date.fromisoformat(str(hab.get("expires_at")))
            debut = _dt.date.fromisoformat(str(hab.get("requested_at")))
        except ValueError:
            return False, "dates illisibles"
        if (fin - debut).days > regle["max_days"] or _dt.date.today() > fin:
            return False, "expirée ou plus longue que permis"
        ctx = contexte_habilitation(agent["id"], hab)
        verif = self.approbations.trouver(ctx, regle["approver_roles"], regle["max_days"] * 24)
        return (True, plafond) if verif.valide else (False, verif.motif)

    # ------------------------------------------------------------------ ressources
    def _ressource(self, d, action, projet, ticket, agent, exemptes: frozenset = frozenset()):
        ressource = d.get("resource") or {}
        if action in ("read", "write", "delete"):
            return self._chemin(d, ressource.get("path"), "read" if action == "read" else "write", projet, ticket,
                                exemptes)
        if action == "execute":
            return self._outil(d.get("command"), projet, ticket)
        if action == "use_mcp":
            return self._mcp(d.get("mcp"), projet, ticket)
        if action in ("db_read", "db_write"):
            return None if ressource.get("kind") == "database" else ("R16", "ressource de base de données attendue")
        if action == "commit":
            return None if (d.get("execution") or {}).get("worktree") else ("R20", "commit hors espace isolé")
        if action == "run_ticket":
            portee = (ticket.get("scope") or {}).get("paths") or []
            if not portee:
                return ("R25", "ticket sans périmètre de chemins : rien ne peut être exécuté")
            return self._contrat_du_ticket(ticket, agent, projet)
        return ("R99", f"aucune règle ne permet « {action} »")

    def _contrat_du_ticket(self, ticket, agent, projet):
        """ADR-0022 v2 (F-6) : domaine du ticket ∈ domaines du rôle pour ce projet (R40) ; chaque skill exigée est
        autorisée au rôle, connue et approuvée (R41). Sans objet pour un ticket qui ne déclare ni domaine ni skill."""
        if agent is None:
            return None
        domaine = (ticket.get("classification") or {}).get("domain")
        if domaine is not None:
            permis = ((agent.get("domains") or {}).get(projet.id) or []) if isinstance(agent.get("domains"), dict) else []
            if domaine not in permis:
                return ("R40", f"domaine {domaine!r} non autorisé au rôle {agent.get('id')} pour le projet {projet.id}")
        role_skills = {s.get("id") if isinstance(s, dict) else s for s in agent.get("skills") or []}
        for s in ticket.get("skills") or []:
            ident = s.get("id") if isinstance(s, dict) else s
            fiche = self.registre.get("skills", ident)
            if ident not in role_skills:
                return ("R41", f"skill {ident!r} non autorisée au rôle {agent.get('id')}")
            if fiche is None or fiche.get("lifecycle") not in ("APPROVED", "AVAILABLE", "ACTIVE"):
                return ("R41", f"skill {ident!r} inconnue ou non approuvée")
        return None

    def _chemin(self, d, chemin, mode, projet, ticket, exemptes: frozenset = frozenset()):
        if not isinstance(chemin, str) or not chemin:
            return ("R21", "chemin absent")
        execution = d.get("execution") or {}
        espace = execution.get("worktree")
        if mode == "write" and not espace:
            return ("R20", "écriture hors d'un espace de travail isolé (un ticket, un espace, une branche)")
        racine = Path(espace) if espace else projet.racine
        if espace:
            erreur = self._espace_du_projet(Path(espace), projet)
            if erreur:
                return ("R20", erreur)
        if os.path.isabs(chemin) or chemin.startswith("\\\\"):
            cible = Path(chemin)
        else:
            if not chemin_relatif_sur(chemin):
                return ("R22", f"chemin qui sort de la racine : {chemin!r}")
            cible = racine / chemin
        reelle = Path(os.path.realpath(cible))          # résout liens et jonctions
        try:
            rel = reelle.relative_to(Path(os.path.realpath(racine))).as_posix()
        except ValueError:
            return ("R22", "chemin hors de la racine du projet ou de l'espace isolé (autre projet, lien, jonction)")
        rel = "" if rel == "." else rel
        chemins = projet.manifest.get("paths") or {}
        if self._sensible(rel, chemins.get("forbidden", []) + projet.sensibles):
            return ("R23", f"chemin interdit ou sensible : {rel or '.'}")
        portee = (ticket.get("scope") or {}).get("paths") or []
        if mode == "read":
            if not (self._dans(rel, chemins.get("read", [])) or self._dans(rel, portee)) and "R24" not in exemptes:
                return ("R24", f"lecture hors des chemins autorisés : {rel or '.'}")
            return None
        if not self._dans(rel, chemins.get("write", [])):
            return ("R25", f"écriture hors des chemins d'écriture du projet : {rel or '.'}")
        if not self._dans(rel, portee):
            return ("R25", f"écriture hors du périmètre du ticket : {rel or '.'}")
        return None

    def _espace_du_projet(self, espace: Path, projet: ProjetPolitique) -> str | None:
        if not espace.is_dir():
            return "espace isolé déclaré introuvable"
        for m in projet.marqueurs:
            f = espace / m["file"]
            if not f.is_file() or not re.search(m["pattern"], f.read_text(encoding="utf-8", errors="replace"), re.M):
                return "l'espace isolé n'appartient pas à ce projet (marqueurs d'identité absents)"
        return None

    @staticmethod
    def _dans(rel: str, liste: list[str]) -> bool:
        for p in liste:
            p = p.replace("\\", "/").rstrip("/")
            if p in ("", ".") or rel == p or rel.startswith(p + "/"):
                return True
        return False

    def _sensible(self, rel: str, interdits: list[str]) -> bool:
        if self._dans(rel, [p for p in interdits if "*" not in p]):
            return True
        if any(fnmatch.fnmatch(rel, p.rstrip("/")) for p in interdits if "*" in p):
            return True
        nom = PurePosixPath(rel).name.lower()
        if any(fnmatch.fnmatch(nom, m.lower()) for m in self.racine_scope.get("sensitive_file_patterns", [])):
            return True
        parties = [x.lower() for x in rel.split("/")]
        return any(n.lower() in parties for n in self.racine_scope.get("sensitive_dir_names", []))

    # ------------------------------------------------------------------ commandes, outils, MCP
    def _classer_commande(self, commande, projet):
        if not isinstance(commande, list) or not commande or not all(isinstance(x, str) and x for x in commande):
            return None, "commande absente ou mal formée (argv attendu)"
        if any(ch in x for x in commande for ch in ";&|<>`$\n"):
            return None, "caractère de shell interdit dans la commande"
        if any(t in commande for t in self.classes.get("forbidden_tokens", [])):
            return None, "option interdite dans la commande"
        for p in self.classes.get("forbidden_prefixes", []):
            if commande[:len(p)] == p:
                return None, f"commande interdite : {' '.join(p)}"
        for p in self.liste_blanche:
            if len(p) == len(commande) and all(a == b or a.startswith("<") for a, b in zip(p, commande)):
                return "C0", None
        for p in self.classes.get("controlled_prefixes", []):
            if commande[:len(p)] == p:
                return "C2", "controlled"
        for g in ((projet.manifest.get("quality") or {}).get("gates") or {}).values():
            declaree = (g or {}).get("command")
            if declaree and commande[:len(declaree.split())] == declaree.split():
                return "C1", None
        return None, f"commande non reconnue : {' '.join(commande)} (refus par défaut, Master §12)"

    def _outil(self, commande, projet, ticket):
        executable = commande[0]
        outils = self.registre.objets["tools"]
        if executable in outils:                     # l'identifiant identique à l'exécutable l'emporte
            outil = outils[executable]
        else:
            candidats = [o for o in outils.values()
                         if ((o.get("detection") or {}).get("command") or [None])[0] == executable
                         or (o.get("detection") or {}).get("executable") == executable]
            if len(candidats) > 1:
                return ("R14", f"exécutable {executable!r} ambigu ({', '.join(o['id'] for o in candidats)}) : refus")
            outil = candidats[0] if candidats else None
        if outil is None:
            return ("R14", f"outil {executable!r} inconnu du registre")
        if outil.get("lifecycle") not in self.regles["approved_tool_states"]:
            return ("R14", f"outil {outil['id']!r} non approuvé ({outil.get('lifecycle')})")
        t = projet.manifest.get("tools") or {}
        if outil["id"] not in set(t.get("required", [])) | set(t.get("allowed", [])):
            return ("R14", f"outil {outil['id']!r} non autorisé par le projet")
        outils_ticket = ticket.get("tools")
        if outils_ticket and outil["id"] not in outils_ticket:
            return ("R14", f"outil {outil['id']!r} hors du ticket")
        return None

    def _mcp(self, ident, projet, ticket):
        fiche = self.registre.get("mcp", ident) if ident else None
        if fiche is None:
            return ("R15", f"MCP {ident!r} inconnu du registre")
        if fiche.get("lifecycle") not in self.regles["approved_mcp_states"]:
            return ("R15", f"MCP {ident!r} non approuvé ({fiche.get('lifecycle')})")
        if ident not in ((projet.manifest.get("mcp") or {}).get("allowed") or []):
            return ("R15", f"MCP {ident!r} non autorisé pour ce projet")
        if ticket.get("mcp") is not None and ident not in ticket.get("mcp"):
            return ("R15", f"MCP {ident!r} hors du ticket")
        prod = fiche.get("production") or {}
        if prod.get("write") or prod.get("delete"):
            return ("R15", "MCP avec écriture ou suppression en production")
        return None
