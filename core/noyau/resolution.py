"""Résolution d'un ticket en contrat d'exécution (ADR-0022 v2 ; modèle canonique GMAO v1.0 § 4).

Un ticket qui porte `control_profile` est un contrat d'exécution. Pour lui, à partir du ticket (lu dans le dépôt du
projet), du manifest, des registres et des politiques versionnés, la résolution donne :

- le VERDICT : READY, ou BLOCKED avec chaque motif ; un doute bloque, rien ne débloque par défaut ;
- le PROFIL D'EXÉCUTION : droits = intersection de la politique, du rôle, de l'habilitation, du manifest et du ticket
  (le ticket ne fait que restreindre) ; le Policy Engine est consulté tel quel (run_ticket), sans rien consommer ;
- le PROMPT EFFECTIF, parties A à H dans l'ordre du profil de prompt ; la consigne de sécurité du runtime est ajoutée
  APRÈS, par le fournisseur d'exécution, et prévaut ;
- l'INSTANTANÉ : version et empreinte de chaque élément utilisé, figé au démarrage (provenance).

Lecture seule : rien n'est écrit. Le module ne connaît aucun projet, outil ni fournisseur (ADR-0003).
"""
from __future__ import annotations

import copy
import dataclasses
import datetime as _dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import sections as _sections
from .approbation import empreinte
from .validation import VALID, chemin_relatif_sur

READY, BLOCKED = "READY", "BLOCKED"
A_COMPLETER = "TO_COMPLETE"
TERMINES = ("MERGED", "RELEASED", "CLOSED")          # une dépendance bloquante dans un de ces états est satisfaite
FERMES = ("CLOSED", "CANCELLED")
APPROUVEES = ("APPROVED", "AVAILABLE", "ACTIVE")
RETIRES = ("DEPRECATED", "REMOVED")
PAR_LE_PROJET = "project"     # version d'outil fixée par les fichiers de dépendances du projet, non par la Factory
NIVEAUX = ("C0", "C1", "C2", "C3", "C4")


def version_conforme(observee, epinglee) -> bool:
    """Version épinglée = préfixe par composants (« 1.93 » couvre « 1.93.1 », pas « 1.930 ») ; « project » : toute
    version déclarée par le projet convient (le projet la fixe lui-même)."""
    if epinglee == PAR_LE_PROJET:
        return bool(observee)
    o, e = str(observee).strip().lstrip("v"), str(epinglee).strip().lstrip("v")
    return o == e or o.startswith(e + ".")


def a_completer(obj, prefixe: str = "") -> list[str]:
    """Chemins des champs dont la valeur (ou un élément) est TO_COMPLETE."""
    if isinstance(obj, dict):
        return [c for k, v in obj.items() for c in a_completer(v, f"{prefixe}.{k}" if prefixe else str(k))]
    if isinstance(obj, list):
        return [c for i, v in enumerate(obj) for c in a_completer(v, f"{prefixe}[{i}]")]
    return [prefixe] if obj == A_COMPLETER else []


def _sha(p: Path | None) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p is not None and Path(p).is_file() else None


def _g(d, chemin, defaut=None):
    for k in chemin.split("."):
        if not isinstance(d, dict) or k not in d:
            return defaut
        d = d[k]
    return d


def _niveau(c) -> int:
    return NIVEAUX.index(c) if c in NIVEAUX else 99


def tickets_du_projet(racine_projet: Path, manifest: dict, lisible=None) -> tuple[dict[str, tuple[Path, dict]], list[str]]:
    """Tickets lus SUR PLACE, à l'emplacement que déclare le manifest (`tickets.path`), seulement s'il est lisible au
    sens du manifest (correction 2 du § 9) ; aucune copie dans la Factory."""
    rel = (manifest.get("tickets") or {}).get("path")
    if not chemin_relatif_sur(rel):
        return {}, ["emplacement des tickets non déclaré par le manifest (tickets.path)"]
    if lisible is not None and not lisible(rel.rstrip("/") + "/"):
        return {}, [f"emplacement des tickets {rel} hors des chemins lisibles du manifest"]
    dossier = Path(racine_projet) / rel
    if not dossier.is_dir():
        return {}, [f"dossier des tickets introuvable : {rel}"]
    tickets, erreurs = {}, []
    for f in sorted(dossier.glob("*.yaml")):
        try:
            t = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            erreurs.append(f"{f.name} : YAML illisible ({str(e).splitlines()[0]})")
            continue
        if not isinstance(t, dict) or t.get("id") != f.stem:
            erreurs.append(f"{f.name} : id absent ou différent du nom de fichier")
            continue
        tickets[f.stem] = (f, t)
    return tickets, erreurs


@dataclass
class Sources:
    """Ce que la résolution lit. `inventaire.get(outil)` : version observée (None = absent, "" = illisible) ; None =
    non vérifié. `decisions` : identifiant → état de la demande « factory decide » (OPEN, APPROVED, REJECTED…)."""
    racine_factory: Path
    registre: object                     # noyau.registre.Registre
    moteur: object                       # noyau.politique.Moteur
    projet_id: str
    reference_epinglage: dict | None
    statut_epinglage: str                # PINNED | BLOCKED | UNPINNED
    empreinte_politique: str
    profils_controle: dict               # policies/control-profiles.yaml
    profils_environnement: set           # profils d'autonomy.yaml
    decisions: dict = field(default_factory=dict)
    adr_acceptes: set = field(default_factory=set)
    inventaire: object | None = None
    manifest_sha256: str | None = None


@dataclass
class Resolution:
    ticket_id: str
    statut: str = READY
    motifs: list[str] = field(default_factory=list)
    profil: dict = field(default_factory=dict)
    prompt: str = ""
    instantane: dict = field(default_factory=dict)
    point_humain: str | None = None       # APPROVAL_REQUIRED du Policy Engine : point humain au démarrage

    def bloquer(self, motif: str):
        self.statut = BLOCKED
        self.motifs.append(motif)

    def en_dict(self) -> dict:
        return {"ticket_id": self.ticket_id, "status": self.statut, "reasons": self.motifs,
                "human_gate_at_start": self.point_humain, "execution_profile": self.profil,
                "prompt_sha256": self.instantane.get("prompt_sha256"), "snapshot": self.instantane}


# --------------------------------------------------------------------------------------------- vérifications
def _fichier_approuve(src: Sources, rel: str, quoi: str, r: Resolution) -> str | None:
    """Empreinte du fichier ; motif s'il ne figure pas, à cette empreinte, dans la référence d'épinglage approuvée."""
    sha = _sha(Path(src.racine_factory) / rel)
    fichiers = ((src.reference_epinglage or {}).get("context") or {}).get("files") or {}
    if sha is None:
        r.bloquer(f"{quoi} : fichier introuvable ({rel})")
    elif not fichiers:
        r.bloquer(f"{quoi} : aucune référence d'épinglage approuvée par l'humain")
    elif fichiers.get(rel) is None:
        r.bloquer(f"{quoi} : {rel} absent de la référence d'épinglage approuvée (approbation humaine requise)")
    elif fichiers[rel] != sha:
        r.bloquer(f"{quoi} : {rel} modifié depuis la référence d'épinglage approuvée")
    return sha


def _liste(ticket: dict, chemin: str, r: Resolution, requis: bool = True) -> list:
    v = _g(ticket, chemin)
    if v is None and not requis:
        return []
    if not isinstance(v, list):
        if v != A_COMPLETER:
            r.bloquer(f"{chemin} : liste attendue (une liste vide signifie « aucun »)")
        return []
    return v


def _ref(v) -> tuple[str | None, str | None]:
    """{id, version} (forme du modèle canonique) ou « id@version »."""
    if isinstance(v, dict):
        return v.get("id"), (str(v["version"]) if v.get("version") is not None else None)
    if isinstance(v, str) and v.strip():
        i, _, ver = v.strip().partition("@")
        return i or None, ver or None
    return None, None


def _lisible(src: Sources, projet):
    chemins = projet.manifest.get("paths")
    if not isinstance(chemins, dict):
        return lambda p: False
    interdits = list(chemins.get("forbidden") or []) + list(projet.sensibles)
    return lambda p: src.moteur._dans(p.rstrip("/"), chemins.get("read") or []) and not src.moteur._sensible(p.rstrip("/"), interdits)


def resoudre(ticket: dict, chemin_ticket: Path | None, tickets: dict[str, tuple[Path, dict]], src: Sources,
             maintenant: _dt.datetime | None = None) -> Resolution:
    r = Resolution(ticket_id=str(ticket.get("id")))
    if "control_profile" not in ticket:
        r.bloquer("ticket non normalisé : contrat d'exécution absent (control_profile, ADR-0022 v2)")
        return r
    # Les dépendances d'un ticket de projet sont des tickets du PROJET (lus sur place), pas du registre de la Factory.
    v = src.registre.validateur
    v = dataclasses.replace(v, index=dict(v.index, tickets=set(v.index.get("tickets") or ()) | set(tickets)))
    verdict = v.valider("ticket", ticket, str(chemin_ticket or ticket.get("id")))
    if verdict.statut != VALID:
        for d in verdict.defauts:
            if A_COMPLETER not in d.message:
                r.bloquer(f"schéma : {d.code} {d.chemin} — {d.message}")
    for c in a_completer(ticket):
        r.bloquer(f"{c} : TO_COMPLETE")
    if ticket.get("project_id") != src.projet_id:
        r.bloquer(f"project_id {ticket.get('project_id')!r} ≠ {src.projet_id!r}")
    if ticket.get("state") in FERMES:
        r.bloquer(f"ticket fermé ({ticket.get('state')})")
    if not isinstance(ticket.get("version"), int):
        r.bloquer("version du ticket absente (entier attendu)")
    for champ in ("expected_result", "classification.domain"):
        if _g(ticket, champ) in (None, ""):
            r.bloquer(f"{champ} absent")
    if src.statut_epinglage != "PINNED":
        r.bloquer(f"épinglage de la gouvernance {src.statut_epinglage} : lancement refusé (nouvelle référence à approuver)")
    projet = src.moteur.projets.get(src.projet_id)
    if projet is None:
        r.bloquer(f"projet {src.projet_id!r} sans manifest lisible")
        return r
    manifest, crit, lisible = projet.manifest, ticket.get("criticality"), _lisible(src, projet)
    domaine = _g(ticket, "classification.domain")
    s = {"resolved_at": (maintenant or _dt.datetime.now(_dt.timezone.utc)).isoformat(timespec="seconds"),
         "ticket": {"id": ticket.get("id"), "version": ticket.get("version"),
                    "file_sha256": _sha(chemin_ticket) if chemin_ticket else empreinte(ticket)},
         "manifest_sha256": src.manifest_sha256, "policy_fingerprint": src.empreinte_politique,
         "pin_reference": (src.reference_epinglage or {}).get("id")}

    # --- Profil de contrôle (F-5)
    cp_id, cp_ver = _ref(ticket.get("control_profile"))
    cp = (src.profils_controle.get("profiles") or {}).get(cp_id)
    if cp is None:
        r.bloquer(f"profil de contrôle {cp_id!r} inconnu (policies/control-profiles.yaml)")
        cp = {}
    else:
        if cp_ver != str(cp.get("version")):
            r.bloquer(f"profil de contrôle {cp_id} : version {cp_ver} demandée, {cp.get('version')} en vigueur")
        s["control_profile"] = {"ref": f"{cp_id}@{cp.get('version')}", "file": "policies/control-profiles.yaml",
                                "file_sha256": _fichier_approuve(src, "policies/control-profiles.yaml", "profils de contrôle", r)}
        if crit not in (cp.get("criticalities") or []):
            r.bloquer(f"criticité {crit} hors du profil {cp_id} ({', '.join(cp.get('criticalities') or [])}) : "
                      "un profil ne s'abaisse jamais")
        adr = cp.get("requires_accepted_adr")
        if adr and adr not in src.adr_acceptes:
            r.bloquer(f"profil {cp_id} : {adr} non accepté")
    avec_agent = bool(cp.get("agent_execution"))

    # --- Rôle, habilitation, Policy Engine (F-1, F-6)
    agent = None
    plafond = None
    role_id, role_ver = _ref(_g(ticket, "agent.role"))
    if cp and not avec_agent:
        if role_id is not None or _g(ticket, "execution.agent_id"):
            r.bloquer(f"profil {cp_id} sans exécution d'agent : aucun rôle ne doit être désigné")
    elif cp:
        agent = src.registre.get("agents", role_id) if role_id else None
        if agent is None:
            r.bloquer(f"rôle {role_id!r} inconnu du registre (agent.role)")
        else:
            s["role"] = {"ref": f"{role_id}@{agent.get('version')}", "file": f"registry/agents/{role_id}.yaml",
                         "file_sha256": _sha(Path(src.racine_factory) / f"registry/agents/{role_id}.yaml")}
            if role_ver != str(agent.get("version")):
                r.bloquer(f"rôle {role_id} : version {role_ver} demandée, {agent.get('version')} au registre")
            if _g(ticket, "execution.agent_id") != role_id:
                r.bloquer(f"execution.agent_id {_g(ticket, 'execution.agent_id')!r} ≠ agent.role {role_id!r}")
            if ticket.get("workflow_id") not in (agent.get("workflows") or []):
                r.bloquer(f"rôle {role_id} : workflow {ticket.get('workflow_id')!r} non autorisé (workflows)")
            domaines_role = (agent.get("domains") or {}).get(src.projet_id) if isinstance(agent.get("domains"), dict) else None
            requis = _liste(ticket, "agent.authorization.required_domains", r, requis=False) or [domaine]
            for d in requis:
                if d not in (domaines_role or []):
                    r.bloquer(f"rôle {role_id} : domaine {d!r} non autorisé pour le projet {src.projet_id} (domains)")
            niveau_exige = _g(ticket, "agent.authorization.required_level")
            if niveau_exige is not None and niveau_exige != crit:
                r.bloquer(f"agent.authorization.required_level {niveau_exige} ≠ criticité {crit}")
            habilite, plafond = src.moteur.plafond_habilite(agent, src.projet_id)
            if not habilite:
                r.bloquer(f"rôle {role_id} : {plafond}")
                plafond = None
            elif _niveau(crit) > _niveau(plafond):
                r.bloquer(f"criticité {crit} au-delà du plafond du rôle {role_id} ({plafond})")

    # --- Skills, outils, MCP (F-2, F-3, F-6)
    regles = src.moteur.regles
    role_skills = {(_ref(x)[0]) for x in (agent or {}).get("skills") or []}
    s["skills"], instructions_skills = [], []
    for x in _liste(ticket, "skills", r):
        i, v = _ref(x)
        fiche = src.registre.get("skills", i)
        if fiche is None:
            r.bloquer(f"skill {i!r} inconnue du registre")
            continue
        if v != str(fiche.get("version")):
            r.bloquer(f"skill {i} : version {v} demandée, {fiche.get('version')} au registre")
        if fiche.get("lifecycle") not in APPROUVEES:
            r.bloquer(f"skill {i} : état {fiche.get('lifecycle')} (non approuvée)")
        if agent is not None and i not in role_skills:
            r.bloquer(f"skill {i} non autorisée au rôle {agent['id']}")
        e = {"ref": f"{i}@{fiche.get('version')}", "file_sha256": _sha(Path(src.racine_factory) / f"registry/skills/{i}.yaml")}
        if fiche.get("instructions"):
            e["instructions"] = fiche["instructions"]
            e["instructions_sha256"] = _fichier_approuve(src, fiche["instructions"], f"instructions de la skill {i}", r)
            p = Path(src.racine_factory) / fiche["instructions"]
            if p.is_file():
                instructions_skills.append((e["ref"], p.read_text(encoding="utf-8")))
        s["skills"].append(e)

    outils_projet = manifest.get("tools") or {}
    outils_projet = set(outils_projet.get("required") or []) | set(outils_projet.get("allowed") or [])
    exiges = ticket.get("tool_versions") or {}
    s["tools"] = []
    for i in _liste(ticket, "tools", r):
        fiche = src.registre.get("tools", i)
        if fiche is None:
            r.bloquer(f"outil {i!r} inconnu du registre")
            continue
        epinglee = str(fiche.get("version"))
        if fiche.get("lifecycle") not in (regles.get("approved_tool_states") or ()):
            r.bloquer(f"outil {i} : état {fiche.get('lifecycle')} (non approuvé)")
        if i not in outils_projet:
            r.bloquer(f"outil {i} non autorisé par le manifest du projet (tools)")
        if epinglee in ("*", "", "None"):
            r.bloquer(f"outil {i} : version non épinglée au registre (ADR-0022, F-3)")
        voulue = str(exiges.get(i) or epinglee)
        observee = None if src.inventaire is None else src.inventaire.get(i)
        if src.inventaire is None:
            r.bloquer(f"outil {i} : présence non vérifiée (inventaire du Bootstrap)")
        elif observee is None:
            r.bloquer(f"outil {i} : absent (poste ou dépendances du projet)")
        elif observee == "":
            r.bloquer(f"outil {i} : présent, version illisible : conformité invérifiable")
        elif voulue not in ("*", "", "None") and not version_conforme(observee, voulue):
            r.bloquer(f"outil {i} : version {observee} observée, {voulue} exigée")
        s["tools"].append({"ref": f"{i}@{epinglee}", "required": voulue, "observed": observee})

    mcp_projet = set((manifest.get("mcp") or {}).get("allowed") or [])
    s["mcp"] = []
    for i in _liste(ticket, "mcp", r):
        fiche = src.registre.get("mcp", i)
        if fiche is None or fiche.get("lifecycle") not in (regles.get("approved_mcp_states") or ()) or i not in mcp_projet:
            r.bloquer(f"MCP {i!r} inconnu, non approuvé ou non autorisé par le projet")
            continue
        s["mcp"].append({"ref": f"{i}@{fiche.get('version')}"})

    # --- Contexte par sections, lecture gouvernée (F-7)
    s["context"], textes = [], []
    contexte = ticket.get("context")
    if not isinstance(contexte, dict):
        if contexte != A_COMPLETER:
            r.bloquer("context : dictionnaire attendu (specification, design, adr, related_tickets)")
        contexte = {}
    spec = (manifest.get("context") or {}).get("specification")
    for genre in ("specification", "design", "adr"):
        for ref in _liste(contexte, genre, r, requis=False):
            sec, motif = _sections.resoudre(projet.racine, ref, lisible, spec)
            if motif:
                r.bloquer(f"contexte : {motif}")
            else:
                s["context"].append(sec.en_dict())
                textes.append(sec)
    for t in _liste(contexte, "related_tickets", r, requis=False):
        if t not in tickets:
            r.bloquer(f"contexte : ticket lié {t} inconnu du projet")

    # --- Périmètre : intersection ticket ∩ manifest
    chemins = manifest.get("paths")
    ecriture = []
    portee = _liste(ticket, "scope.paths", r)
    if avec_agent:
        if not isinstance(chemins, dict):
            r.bloquer("chemins du manifest non validés (PROPOSED) ou absents : aucune lecture ni écriture possible")
        if not portee and _g(ticket, "scope.paths") != A_COMPLETER:
            r.bloquer("périmètre vide : rien ne peut être exécuté")
        interdits = list((chemins or {}).get("forbidden") or []) + list(projet.sensibles)
        for p in portee:
            if not chemin_relatif_sur(p):
                r.bloquer(f"périmètre : {p!r} sort de la racine du projet")
            elif not src.moteur._dans(p.rstrip("/"), (chemins or {}).get("write") or []):
                r.bloquer(f"périmètre : {p} hors des chemins d'écriture du manifest")
            elif src.moteur._sensible(p.rstrip("/"), interdits):
                r.bloquer(f"périmètre : {p} interdit ou sensible")
            else:
                ecriture.append(p)

    # --- Gates, tests, critères
    gates_manifest = (manifest.get("quality") or {}).get("gates") or {}
    gates = _liste(ticket, "quality.required_gates", r)
    for g in gates:
        if not (gates_manifest.get(g) or {}).get("command"):
            r.bloquer(f"gate {g!r} absente du manifest du projet (quality.gates)")
    if avec_agent and "TEST" in (cp.get("evidence_required") or []) and not gates:
        r.bloquer("aucune gate : la preuve TEST exigée par le profil est impossible")
    criteres = _liste(ticket, "specification.acceptance_criteria", r)
    if avec_agent and not criteres:
        r.bloquer("aucun critère d'acceptation")

    # --- Environnement (profil d'autonomy.yaml), budget
    env = _g(ticket, "execution.environment_profile")
    if avec_agent and env not in src.profils_environnement:
        r.bloquer(f"execution.environment_profile {env!r} inconnu (policies/autonomy.yaml)")
    budget_profil = (cp.get("budget") or {}).get("max_attempts")
    budget = _g(ticket, "budget.max_attempts", budget_profil) if avec_agent else budget_profil
    if avec_agent and (not isinstance(budget, int) or budget_profil is None or not 1 <= budget <= budget_profil):
        r.bloquer(f"budget.max_attempts {budget!r} : entier entre 1 et {budget_profil} (profil {cp_id})")
        budget = budget_profil

    # --- Dépendances bloquantes, informatives, décisions humaines (factory decide)
    for dep in _liste(ticket, "dependencies.tickets", r):
        if dep not in tickets:
            r.bloquer(f"dépendance {dep} : ticket inconnu du projet")
        elif tickets[dep][1].get("state") not in TERMINES:
            r.bloquer(f"dépendance {dep} non terminée ({tickets[dep][1].get('state')})")
    for dep in _liste(ticket, "dependencies.informational", r, requis=False):
        if dep not in tickets:
            r.bloquer(f"dépendance informative {dep} : ticket inconnu du projet")
    s["decisions"] = []
    for dec in _liste(ticket, "dependencies.decisions", r, requis=False):
        etat = src.decisions.get(dec)
        if etat != "APPROVED":
            r.bloquer(f"décision {dec} : {'inconnue de factory decide' if etat is None else etat}")
        s["decisions"].append({"id": dec, "status": etat})

    # --- Profil de prompt (F-4) et consigne du rôle
    pp = None
    if avec_agent:
        pp_id, pp_ver = _ref(_g(ticket, "prompt.profile"))
        pp = src.registre.get("prompts", pp_id) if pp_id else None
        if pp is None:
            r.bloquer(f"profil de prompt {pp_id!r} inconnu (registry/prompts)")
        else:
            s["prompt_profile"] = {"ref": f"{pp_id}@{pp.get('version')}",
                                   "file_sha256": _fichier_approuve(src, f"registry/prompts/{pp_id}.yaml", "profil de prompt", r)}
            if pp_ver != str(pp.get("version")):
                r.bloquer(f"profil de prompt {pp_id} : version {pp_ver} demandée, {pp.get('version')} au registre")
            if pp.get("lifecycle") in RETIRES:
                r.bloquer(f"profil de prompt {pp_id} retiré ({pp.get('lifecycle')})")
            for part, rel in (pp.get("templates") or {}).items():
                _fichier_approuve(src, rel, f"gabarit {part} du profil de prompt", r)
        if agent is not None:
            if agent.get("prompt"):
                s["role"]["prompt_sha256"] = _fichier_approuve(src, agent["prompt"], f"consigne du rôle {agent['id']}", r)
            else:
                r.bloquer(f"rôle {agent['id']} sans consigne (prompt)")

    # --- Policy Engine, tel quel et sans rien consommer (R04, R05, R08, R25, R40, R41…) : confirmation finale d'un
    # ticket que les contrôles précédents n'ont pas bloqué.
    if agent is not None and ecriture and r.statut == READY:
        d = src.moteur.decider({
            "actor": {"type": "agent", "id": agent["id"]}, "project_id": src.projet_id, "action": "run_ticket",
            "ticket": vue_execution(ticket, ecriture, budget),
            "resource": {"kind": "ticket", "id": ticket.get("id"), "environment": "LOCAL"}})
        if d.decision == "DENY":
            r.bloquer(f"Policy Engine {d.regle} : {'; '.join(d.motifs)}")
        elif d.decision == "APPROVAL_REQUIRED":
            r.point_humain = f"{d.regle} : {'; '.join(d.motifs)}"
        s["policy_decision"] = {"decision": d.decision, "rule": d.regle}

    interdits_ticket = list(_g(ticket, "prompt.forbidden_actions") or [])
    r.profil = {
        "ticket": {"id": ticket.get("id"), "version": ticket.get("version"), "criticality": crit, "domain": domaine,
                   "workflow_id": ticket.get("workflow_id")},
        "role": ({"ref": s.get("role", {}).get("ref"), "ceiling": plafond,
                  "reviewer": (agent.get("review") or {}).get("preferred_reviewer")} if agent else None),
        "control_profile": ({"ref": s.get("control_profile", {}).get("ref"), "review": cp.get("review"),
                             "human_points": list(cp.get("human_points") or []) + list(_g(ticket, "governance.ticket_decisions") or []),
                             "evidence_required": cp.get("evidence_required"), "transitional_rule": cp.get("transitional_rule"),
                             "rollback_ref": (src.profils_controle.get("common") or {}).get("rollback_ref")} if cp else None),
        "environment_profile": env,
        "budget": {"max_attempts": budget, "time_limit_minutes": _g(ticket, "budget.time_limit_minutes")},
        "permissions": {"write": ecriture, "read": list((chemins or {}).get("read") or []),
                        "forbidden": list((chemins or {}).get("forbidden") or []) + list(projet.sensibles),
                        "forbidden_actions": interdits_ticket,
                        "rule": "intersection politique ∩ rôle ∩ habilitation ∩ manifest ∩ ticket ; le ticket ne fait que restreindre"},
        "skills": [e["ref"] for e in s["skills"]], "tools": [e["ref"] for e in s["tools"]],
        "mcp": [e["ref"] for e in s["mcp"]], "gates": list(gates),
    }
    r.prompt = prompt_effectif(src, ticket, projet, agent, pp, cp, r.profil, textes, instructions_skills)
    limite = ((pp or {}).get("limits") or {}).get("max_chars")
    if limite and len(r.prompt) > limite:
        r.bloquer(f"prompt effectif de {len(r.prompt)} caractères, au-delà de la limite du profil ({limite})")
    s["prompt_sha256"] = hashlib.sha256(r.prompt.encode("utf-8")).hexdigest()
    r.instantane = s
    return r


# ---------------------------------------------------------------------------------------------- prompt
def _puces(valeurs) -> list[str]:
    if not isinstance(valeurs, list) or not valeurs:
        return ["- (aucun)"]
    return [f"- {v}" if not isinstance(v, (dict, list)) else
            "- " + yaml.safe_dump(v, allow_unicode=True, default_flow_style=True, width=1000).strip() for v in valeurs]


def _lire(src: Sources, rel: str | None) -> str:
    p = Path(src.racine_factory) / rel if rel else None
    return p.read_text(encoding="utf-8").strip() if p is not None and p.is_file() else ""


def prompt_effectif(src: Sources, ticket, projet, agent, pp, cp, profil, textes, instructions_skills) -> str:
    """Parties A à H, dans l'ordre déclaré par le profil de prompt (modèle canonique § 4.2). Un ticket sans agent
    (décision humaine) n'a que les parties F et H."""
    parties = {}
    if pp is not None:
        parties["A"] = _lire(src, (pp.get("templates") or {}).get("A"))
    if agent is not None:
        parties["B"] = f"Rôle {profil['role']['ref']}.\n\n" + _lire(src, agent.get("prompt"))
    parties["C"] = "\n\n".join(f"### Skill {ref}\n{texte.strip()}" for ref, texte in instructions_skills) or "(aucune skill)"
    m = projet.manifest
    pile = m.get("stack") or {}
    parties["D"] = "\n".join([f"Projet {projet.id} — {m.get('name')} : {m.get('description') or ''}".strip(),
                              f"Langages : {', '.join(pile.get('languages') or []) or '—'} ; cadres : "
                              f"{', '.join(pile.get('frameworks') or []) or '—'}",
                              "Le fichier de contexte du dépôt est chargé par le runtime ; il ne prévaut pas sur ce prompt."])
    parties["E"] = "\n\n".join(f"### {sec.reference} (empreinte {sec.sha256[:12]})\n{sec.texte}" for sec in textes) or "(aucune section citée)"
    parties["F"] = "\n".join([f"Ticket {ticket.get('id')} v{ticket.get('version')} — {ticket.get('title')}",
                              f"Objectif : {ticket.get('objective')}", f"Résultat attendu : {ticket.get('expected_result')}",
                              f"Criticité : {ticket.get('criticality')} ; domaine : {_g(ticket, 'classification.domain')} ; "
                              f"profil de contrôle : {(profil.get('control_profile') or {}).get('ref')}",
                              "Périmètre d'écriture :", *_puces(_g(ticket, "scope.paths")),
                              "Entrées exigées :", *_puces(_g(ticket, "inputs.required")),
                              "Entrées facultatives :", *_puces(_g(ticket, "inputs.optional")),
                              "Sorties attendues :", *_puces(_g(ticket, "outputs.required")),
                              "Instructions du ticket :", *_puces(_g(ticket, "prompt.instructions"))])
    parties["G"] = "\n".join(["Écriture permise (intersection ticket ∩ manifest) :", *_puces(profil["permissions"]["write"]),
                              "Chemins interdits ou sensibles :", *_puces(profil["permissions"]["forbidden"]),
                              "Actions interdites par le ticket :", *_puces(profil["permissions"]["forbidden_actions"]),
                              f"Outils : {', '.join(profil['tools']) or 'aucun'} ; MCP : {', '.join(profil['mcp']) or 'aucun'} ; "
                              f"environnement : {profil.get('environment_profile')} ; tentatives : {profil['budget']['max_attempts']}"])
    parties["H"] = "\n".join(["Critères d'acceptation :", *_puces(_g(ticket, "specification.acceptance_criteria")),
                              "Règles métier :", *_puces(_g(ticket, "specification.business_rules")),
                              "Gates :", *_puces(_g(ticket, "quality.required_gates")),
                              "Tests exigés :", *_puces(_g(ticket, "quality.required_tests")),
                              "Conditions d'arrêt :", *_puces(list((src.profils_controle.get("common") or {}).get("stop_conditions") or [])
                                                             + list(_g(ticket, "specification.stop_conditions") or [])),
                              "Conditions de blocage :", *_puces(_g(ticket, "specification.block_conditions"))])
    ordre = [x.get("part") for x in (pp or {}).get("sections") or []] or ["F", "H"]
    titres = {x.get("part"): x.get("title") for x in (pp or {}).get("sections") or []}
    return "\n\n".join(f"## {p}. {titres.get(p, p)}\n\n{parties[p]}" for p in ordre if p in parties) + "\n"


def vue_execution(ticket: dict, ecriture: list[str], budget) -> dict:
    """Le ticket tel que la plateforme et le Policy Engine le lisent : périmètre réduit à l'intersection, budget du
    profil ; le reste inchangé (les champs lus par le moteur restent où il les lit)."""
    v = copy.deepcopy(ticket)
    v.setdefault("scope", {})["paths"] = list(ecriture)
    v.setdefault("budget", {})["max_attempts"] = budget
    return v
