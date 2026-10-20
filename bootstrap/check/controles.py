"""Contrôles du mode CHECK, pilotés par le registre et le manifest (aucun outil nommé ici).

Ordre (politique root-scope) : Factory → ROOT_SCOPE → capacités → inventaires → MCP → sécurité → qualité.
"""
from __future__ import annotations

import hashlib
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from adaptateurs import ADAPTATEURS
from noyau.audit import Journal
from noyau.commandes import Executeur
from noyau.modele import Constat
from noyau.perimetre import AccesRefuse, Perimetre, Racine, canonique, resoudre_racine
from noyau.registre import Registre, charger


@dataclass
class Contexte:
    racine_factory: Path
    config: dict
    registre: Registre
    perimetre: Perimetre
    executeur: Executeur
    racine_projet: Path | None
    projet: dict | None          # carte d'enregistrement
    manifest: dict | None        # bloc « project » du manifest (ou du brouillon)
    manifest_source: str | None  # PROJECT | DRAFT | None


class Collecte:
    def __init__(self):
        self.constats: list[Constat] = []
        self.observations: dict = {}

    def ajouter(self, **k) -> Constat:
        c = Constat(**k)
        self.constats.append(c)
        return c


def _yaml(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


# =============================================================================== préparation
def preparer(racine_factory: Path, id_projet: str | None, col: Collecte) -> Contexte | None:
    bloque = lambda d: _cfg_bloque(config, d)
    config = _yaml(racine_factory / "bootstrap" / "bootstrap.yaml")
    factory = _yaml(racine_factory / "factory.yaml")
    politique = _yaml(racine_factory / "policies" / "root-scope.yaml")
    liste = _yaml(racine_factory / "policies" / "command-whitelist.yaml")

    # --- Factory : identité, Playbook, schémas, registre
    lectures_identite: list[str] = []
    racine_f, rejets = resoudre_racine("FACTORY_ROOT", str(racine_factory),
                                       [{"file": "factory.yaml", "pattern": r"^\s*id: software-factory"}],
                                       lectures_identite)
    col.ajouter(id="F-ROOT", domaine="factory", element="FACTORY_ROOT", critique=True, bloque=bloque("root_scope"),
                statut="READY" if racine_f else "BLOCKED", nature="VERIFIED", gravite="INFO" if racine_f else "CRITICAL",
                detail=str(racine_f.chemin) if racine_f else "; ".join(rejets))
    if racine_f is None:
        return None
    pb = racine_factory / factory["playbook"]["path"]
    empreinte = hashlib.sha256(pb.read_bytes()).hexdigest() if pb.is_file() else None
    conforme = empreinte == factory["playbook"]["sha256"]
    col.ajouter(id="F-PLAYBOOK", domaine="factory", element="Playbook normatif", critique=True,
                bloque=bloque("factory"), statut="READY" if conforme else "BLOCKED", nature="VERIFIED",
                gravite="INFO" if conforme else "CRITICAL",
                detail=f"v{factory['factory']['standard_version']}, empreinte {'conforme' if conforme else 'DIFFÉRENTE'}")
    registre = charger(racine_factory)
    col.ajouter(id="F-REGISTRY", domaine="factory", element="Registre et schémas", critique=True,
                bloque=bloque("factory"), statut="READY" if not registre.erreurs else "BLOCKED", nature="VERIFIED",
                gravite="INFO" if not registre.erreurs else "CRITICAL",
                detail=(f"{sum(len(v) for v in registre.objets.values())} fiches valides" if not registre.erreurs
                        else f"VALIDATION_FAILED : {len(registre.erreurs)} erreur(s)"))
    journal = Journal(racine_factory / "audit" / "journal.jsonl").verifier()
    col.ajouter(id="F-AUDIT", domaine="factory", element="Journal d'audit chaîné", critique=True,
                bloque=bloque("factory"), statut="READY" if journal.valide else "BLOCKED", nature="VERIFIED",
                gravite="INFO" if journal.valide else "CRITICAL",
                detail=(f"{journal.evenements} événements, chaîne intacte, tête {journal.tete[:12]}…" if journal.valide
                        else f"chaîne rompue à la ligne {journal.rupture + 1} : {journal.motif}"))
    col.observations["registre"] = {
        "fiches": {k: len(v) for k, v in registre.objets.items()},
        "erreurs": [f"{e.fichier} : {e.message}" for e in registre.erreurs],
        "en_attente_humaine": sorted(set(registre.attentes))}

    # --- Projet : carte, racine, manifest
    racines = {"FACTORY_ROOT": racine_f}
    projet = manifest = source = None
    racine_projet = None
    if id_projet:
        projet = registre.get("projects", id_projet)
        if projet is None:
            col.ajouter(id="P-ROOT", domaine="root_scope", element=f"projet {id_projet}", critique=True,
                        bloque=bloque("root_scope"), statut="BLOCKED", nature="VERIFIED", gravite="HIGH",
                        detail="projet non enregistré (registry/projects)", action_humaine="PROJECT_ROOT_REQUIRED")
        else:
            res = projet["root"]
            r, rejets = resoudre_racine("PROJECT_ROOT", res["path"], res["resolution"].get("identity_markers", []),
                                        lectures_identite)
            col.ajouter(id="P-ROOT", domaine="root_scope", element="PROJECT_ROOT", critique=True,
                        bloque=bloque("root_scope"), statut="READY" if r else "BLOCKED", nature="VERIFIED",
                        gravite="INFO" if r else "CRITICAL",
                        detail=str(r.chemin) if r else "ROOT_RESOLUTION_FAILED : " + "; ".join(rejets),
                        action_humaine=None if r else "chemin à fournir ou valider (WAITING_HUMAN)")
            if r:
                r.sensibles = list(projet.get("sensitive_paths", []))
                racines["PROJECT_ROOT"] = r
                racine_projet = r.chemin

    fichiers_hors = [canonique(f) for f in politique["outside_roots_files_approved"]["files"]]
    col.observations["lectures_identite"] = lectures_identite
    perimetre = Perimetre(racines=racines, motifs_fichiers_sensibles=politique["sensitive_file_patterns"],
                          noms_repertoires_sensibles=politique["sensitive_dir_names"],
                          jamais_parcourus=politique["never_traverse"], fichiers_hors_racines=fichiers_hors)
    executeur = Executeur(autorisees=liste["allowed"], jokers=liste.get("placeholders", {}), perimetre=perimetre,
                          delai=config["commands"]["timeout_seconds"], environnement=config["commands"]["environment"],
                          options_repertoire=liste.get("directory_options", {}))

    if racine_projet is not None:
        dans_projet = racine_projet / projet["manifest"]["path"]
        if dans_projet.is_file():
            manifest, source = (_yaml_garde(perimetre, dans_projet) or {}).get("project"), "PROJECT"
        elif projet["manifest"].get("draft"):
            manifest = (_yaml(racine_factory / projet["manifest"]["draft"]) or {}).get("project")
            source = "DRAFT"
        nom_contexte = config.get("agent_context_file", "AGENT_CONTEXT.md")
        present = perimetre.existe(racine_projet / nom_contexte)
        col.ajouter(id="P-CONTEXT", domaine="root_scope", element=f"Contexte agent ({nom_contexte})", critique=False,
                    bloque=["EXECUTION"], statut="READY" if present else "WARNING", nature="VERIFIED",
                    gravite="INFO" if present else "MEDIUM",
                    detail="présent" if present else "absent du projet (Master §44, §52)",
                    action_humaine=None if present else "rédiger AGENT_CONTEXT.md dans le projet (WAITING_HUMAN)")
        col.observations["racines"] = {"FACTORY_ROOT": str(racine_f.chemin), "PROJECT_ROOT": str(racine_projet),
                                       "WORKTREE_ROOT": None,
                                       "note": "CHECK hors exécution : aucun espace isolé n'est en cours"}
        col.ajouter(id="P-MANIFEST", domaine="root_scope", element="Manifest du projet", critique=False,
                    bloque=["EXECUTION"], statut="READY" if source == "PROJECT" else "WARNING",
                    nature="VERIFIED" if source == "PROJECT" else "DECLARED",
                    gravite="INFO" if source == "PROJECT" else "MEDIUM",
                    detail=("manifest présent dans le projet" if source == "PROJECT" else
                            "manifest absent du projet : brouillon de la Factory utilisé"),
                    action_humaine=None if source == "PROJECT" else "copier le manifest dans le projet (WAITING_HUMAN)")
    return Contexte(racine_factory, config, registre, perimetre, executeur, racine_projet, projet, manifest, source)


def _cfg_bloque(config: dict, domaine: str) -> list[str]:
    return list(config.get("blocks_by_domain", {}).get(domaine, []))


def _yaml_garde(perimetre: Perimetre, chemin: Path):
    return yaml.safe_load(perimetre.lire_texte(chemin))


# =============================================================================== système
def controler_systeme(ctx: Contexte, col: Collecte):
    seuil = ctx.config["system"]["disk_free_warning_gb"]
    vus = set()
    for r in ctx.perimetre.racines.values():
        lecteur = r.chemin.anchor
        if lecteur in vus:
            continue
        vus.add(lecteur)
        libre = shutil.disk_usage(lecteur).free / 1024 ** 3
        col.ajouter(id=f"S-DISK-{lecteur[:1]}", domaine="system", element=f"Espace libre {lecteur}",
                    statut="READY" if libre >= seuil else "WARNING", nature="VERIFIED",
                    gravite="INFO" if libre >= seuil else "MEDIUM", detail=f"{libre:.1f} Go libres (seuil {seuil} Go)")
    col.observations["systeme"] = {"os": platform.platform(), "machine": platform.machine(),
                                   "python": platform.python_version()}


# =============================================================================== capacités
def _approuve(ctx: Contexte, outil: dict) -> bool:
    return outil.get("lifecycle") in ctx.config["approved_tool_states"]


def detecter_outil(ctx: Contexte, ident: str, cache: dict) -> dict:
    if ident in cache:
        return cache[ident]
    outil = ctx.registre.get("tools", ident)
    spec = (outil or {}).get("detection") or {}
    fonction = ADAPTATEURS.get(spec.get("adapter"))
    if fonction is None:
        obs = {"present": None, "version": None, "nature": "UNVERIFIABLE",
               "detail": f"adaptateur inconnu : {spec.get('adapter')}", "donnees": {}}
    else:
        try:
            obs = fonction(ctx, spec)
        except AccesRefuse as e:
            obs = {"present": None, "version": None, "nature": "UNVERIFIABLE", "detail": f"lecture refusée : {e}",
                   "donnees": {}}
    cache[ident] = obs
    return obs


def controler_capacites(ctx: Contexte, col: Collecte):
    cache: dict = {}
    critiques = set(_yaml(ctx.racine_factory / "factory.yaml").get("critical_capabilities", []))
    requises, optionnelles = set(), set()
    outils_projet = None
    if ctx.manifest:
        requises = set(ctx.manifest.get("capabilities", {}).get("required", []))
        optionnelles = set(ctx.manifest.get("capabilities", {}).get("optional", []))
        t = ctx.manifest.get("tools", {})
        outils_projet = set(t.get("required", [])) | set(t.get("allowed", []))
    for cap in sorted(critiques | requises | optionnelles):
        fiche = ctx.registre.get("capabilities", cap)
        critique = cap in critiques
        domaine = "factory" if critique else "capability"
        bloque = _cfg_bloque(ctx.config, "capability_critical" if critique else "capability_required")
        if fiche is None:
            col.ajouter(id=f"C-{cap}", domaine=domaine, element=cap, critique=critique or cap in requises,
                        bloque=bloque, statut="BLOCKED", nature="VERIFIED", gravite="HIGH",
                        detail="capacité absente du registre")
            continue
        impl = fiche.get("implementations", [])
        ecartes = []
        if outils_projet is not None and not critique:
            ecartes = [t for t in impl if t not in outils_projet]
            impl = [t for t in impl if t in outils_projet]
        trouves, details = [], []
        if ecartes:
            details.append("hors outils du projet : " + ", ".join(
                f"{t} ({(ctx.registre.get('tools', t) or {}).get('lifecycle', '?')})" for t in ecartes))
        for t in impl:
            obs = detecter_outil(ctx, t, cache)
            approuve = _approuve(ctx, ctx.registre.get("tools", t))
            etiquette = f"{t} {obs.get('version') or ''}".strip()
            if obs["present"]:
                trouves.append((t, approuve, obs))
                details.append(f"{etiquette} ({'approuvé' if approuve else 'NON approuvé'})")
            else:
                details.append(f"{t} : {obs['detail'] or 'absent'}")
        if any(a for _, a, _ in trouves):
            statut, gravite = "READY", "INFO"
            nature = "VERIFIED" if any(o["nature"] == "VERIFIED" for _, a, o in trouves if a) else "DECLARED"
        elif trouves:
            statut, gravite, nature = "WARNING", "MEDIUM", "VERIFIED"
        elif cap in optionnelles and not critique:
            statut, gravite, nature = "DEGRADED", "MEDIUM", "VERIFIED"
        else:
            statut, gravite, nature = "BLOCKED", "HIGH", "VERIFIED"
        # Vérification propre à la capacité (adaptateur de la fiche), dans le projet ciblé.
        verif = fiche.get("verification")
        if verif and statut == "READY" and ctx.racine_projet is not None:
            obs = ADAPTATEURS[verif["adapter"]](ctx, verif)
            col.observations.setdefault("verifications", {})[cap] = obs
            if not obs["present"]:
                statut, gravite = "FAILED", "HIGH"
            details.append(f"vérification : {obs['detail']}")
        col.ajouter(id=f"C-{cap}", domaine=domaine, element=cap, critique=critique or cap in requises,
                    bloque=bloque if cap not in optionnelles else [], statut=statut, nature=nature, gravite=gravite,
                    detail=" ; ".join(details) or "aucune implémentation déclarée pour ce projet")
    col.observations["outils"] = {t: {k: v for k, v in o.items() if k != "donnees"} | {
        "chemin": o.get("donnees", {}).get("chemin")} for t, o in cache.items()}
    # Outils exigés nommément par le manifest.
    if ctx.manifest:
        for t in ctx.manifest.get("tools", {}).get("required", []):
            fiche = ctx.registre.get("tools", t)
            obs = detecter_outil(ctx, t, cache) if fiche else None
            ok = bool(fiche and obs and obs["present"] and _approuve(ctx, fiche))
            col.ajouter(id=f"T-{t}", domaine="capability", element=f"outil exigé : {t}", critique=True,
                        bloque=["EXECUTION"], statut="READY" if ok else ("BLOCKED" if not fiche or not (obs or {}).get("present") else "WARNING"),
                        nature=(obs or {}).get("nature", "VERIFIED"), gravite="INFO" if ok else "HIGH",
                        detail=(f"{(obs or {}).get('version') or 'présent'} — {fiche.get('lifecycle')}" if fiche and obs
                                and obs["present"] else ("absent du registre" if not fiche else (obs or {}).get("detail", ""))))


# =============================================================================== inventaires d'outils
def controler_inventaires(ctx: Contexte, col: Collecte):
    for ident, outil in sorted(ctx.registre.objets["tools"].items()):
        inv = outil.get("inventory")
        if not inv or not _approuve(ctx, outil):
            continue
        try:
            obs = ADAPTATEURS[inv["adapter"]](ctx, inv)
        except AccesRefuse as e:
            obs = {"present": None, "nature": "UNVERIFIABLE", "detail": str(e), "donnees": {}}
        col.observations.setdefault("inventaires", {})[ident] = obs
        d = obs.get("donnees", {})
        if "regles" in d:                       # agent d'exécution : permissions
            _permissions_agent(ctx, col, ident, d)
        if "protections_w1" in d:               # fermeture de W1, vérifiée par l'adaptateur du runtime
            p = d["protections_w1"]
            manque = [k for k, v in p.items() if v is False]
            col.ajouter(id=f"F-W1-{ident}", domaine="factory", element=f"{ident} : protection des approbations humaines",
                        bloque=["EXECUTION"], statut="READY" if not manque else "WARNING", nature="DECLARED",
                        gravite="INFO" if not manque else "HIGH",
                        detail=("règles et garde configurées — portée : " + p.get("portee", "") +
                                " ; application non vérifiable par le CHECK (configuration, pas exécution)")
                        if not manque else "manque : " + ", ".join(manque),
                        action_humaine=None if not manque else "configurer les refus W1 (policies/human-approval.yaml)")


def _permissions_agent(ctx: Contexte, col: Collecte, ident: str, d: dict):
    bloque = _cfg_bloque(ctx.config, "agent_permissions")
    col.ajouter(id=f"A-{ident}-DENY", domaine="agent_permissions", element=f"{ident} : règles de refus",
                bloque=bloque, statut="READY" if d["regles"]["deny"] else "FAILED", nature="VERIFIED",
                gravite="INFO" if d["regles"]["deny"] else "HIGH",
                detail=f"{d['regles']['deny']} deny, {d['regles']['ask']} ask, {d['regles']['allow']} allow",
                action_humaine=None if d["regles"]["deny"] else "définir les refus (production, secrets, destructif)")
    col.ajouter(id=f"A-{ident}-BYPASS", domaine="agent_permissions", element=f"{ident} : contournement des permissions",
                bloque=bloque, statut="READY" if d["contournement_interdit"] else "WARNING", nature="VERIFIED",
                gravite="INFO" if d["contournement_interdit"] else "MEDIUM",
                detail="interdit" if d["contournement_interdit"] else "non interdit par la configuration")
    for i, r in enumerate(d["regles_risquees"]):
        col.ajouter(id=f"A-{ident}-RISK-{i + 1}", domaine="agent_permissions", element=f"{ident} : règle risquée",
                    bloque=bloque, statut="WARNING", nature="VERIFIED", gravite="MEDIUM",
                    detail=f"{r['regle']} — {r['pourquoi']}", action_humaine="restreindre ou retirer (WAITING_HUMAN)")
    hotes = [h for e in (ctx.manifest or {}).get("environments", []) if e.get("type") == "PRODUCTION"
             for h in e.get("hosts", [])]
    if hotes:
        protege = d["regles"]["deny"] > 0 or bool(d["hooks"])
        col.ajouter(id=f"A-{ident}-PROD", domaine="production_protection", element="Protection de la production",
                    critique=True, bloque=_cfg_bloque(ctx.config, "production_protection"),
                    statut="UNKNOWN" if protege else "FAILED", nature="VERIFIED" if not protege else "UNVERIFIABLE",
                    gravite="HIGH", detail=(f"hôtes de production déclarés : {len(hotes)} ; "
                                            + ("règles ou hooks présents, couverture non prouvée" if protege
                                               else "aucune règle ni hook ne les protège")),
                    action_humaine="garde de production (hook PreToolUse) : WAITING_HUMAN")
    for k, libelle in (("agents_projet", "agents"), ("skills_projet", "skills")):
        type_ = "agents" if k == "agents_projet" else "skills"
        inconnus = [n for n in d.get(k, []) if ctx.registre.get(type_, n) is None]
        if inconnus:
            col.ajouter(id=f"A-{ident}-{type_.upper()}", domaine="agent_permissions",
                        element=f"{libelle} du projet non enregistrés", bloque=["EXECUTION"], statut="WARNING",
                        nature="VERIFIED", gravite="MEDIUM", detail=", ".join(inconnus),
                        action_humaine="inscrire au registre ou retirer (UNAPPROVED)")


# =============================================================================== MCP
def controler_mcp(ctx: Contexte, col: Collecte):
    declares = []
    for ident, obs in col.observations.get("inventaires", {}).items():
        declares += [dict(m, via=ident) for m in obs.get("donnees", {}).get("mcp_declares", [])]
        for g in obs.get("donnees", {}).get("greffons_actifs", []):
            for mid, m in ctx.registre.objets["mcp"].items():
                if (m.get("observation") or {}).get("provided_by_plugin") == g:
                    declares.append({"nom": mid, "portee": f"greffon utilisateur {g} (tous projets)",
                                     "actif": True, "descripteur": g, "via": ident})
    autorises = set((ctx.manifest or {}).get("mcp", {}).get("allowed", []))
    vus = set()
    for i, m in enumerate(declares, 1):
        fiche = None
        for mid, f in ctx.registre.objets["mcp"].items():
            motifs = (f.get("observation") or {}).get("match", [])
            if mid == m["nom"] or any(x in m["descripteur"] for x in motifs):
                fiche = f
                break
        vus.add(fiche["id"] if fiche else None)
        approuve = bool(fiche and fiche["id"] in autorises and fiche.get("lifecycle") in ("APPROVED", "AVAILABLE"))
        if m["actif"] is False:
            statut, gravite = "WARNING", "LOW"
        elif approuve:
            statut, gravite = "READY", "INFO"
        else:
            statut, gravite = ("FAILED" if m["actif"] else "UNKNOWN"), "HIGH"
        col.ajouter(id=f"M-{i:02d}", domaine="mcp", element=f"MCP {m['nom']}", bloque=_cfg_bloque(ctx.config, "mcp"),
                    statut=statut, nature="VERIFIED" if m["actif"] is not None else "UNVERIFIABLE", gravite=gravite,
                    detail=(f"{'UNAPPROVED' if not approuve else 'approuvé'} — portée : {m['portee']} ; "
                            f"actif : {'oui' if m['actif'] else ('non' if m['actif'] is False else 'inconnu')} ; "
                            f"fiche : {fiche['id'] + ' (' + fiche['lifecycle'] + ')' if fiche else 'non enregistré'}"),
                    action_humaine=None if approuve else "désactiver ou faire évaluer (Security Owner)")
    for mid, f in ctx.registre.objets["mcp"].items():
        if not (f.get("observation") or {}).get("observable_locally", True) and not f.get("slot"):
            col.ajouter(id=f"M-{mid}", domaine="mcp", element=f"MCP {mid}", bloque=[], statut="UNKNOWN",
                        nature="UNVERIFIABLE", gravite="MEDIUM",
                        detail="activation invisible dans les fichiers locaux", action_humaine="vérifier dans le compte")


# =============================================================================== sécurité (sans lecture de contenu)
def controler_secrets(ctx: Contexte, col: Collecte):
    if ctx.racine_projet is None:
        return
    # Inventaire des fichiers par l'adaptateur de la capacité de contrôle de version (aucun outil nommé ici).
    fiche = ctx.registre.get("capabilities", ctx.config.get("file_inventory_capability", "SOURCE_CONTROL")) or {}
    spec = fiche.get("file_inventory") or {}
    obs = ADAPTATEURS[spec["adapter"]](ctx, spec) if spec.get("adapter") in ADAPTATEURS else {"donnees": {}}
    suivis, ignores = obs["donnees"].get("tracked", []), obs["donnees"].get("ignored", [])
    sensibles_suivis = [f for f in suivis if ctx.perimetre.est_sensible(ctx.racine_projet / f)]
    sensibles_ignores = [f for f in ignores if ctx.perimetre.est_sensible(ctx.racine_projet / f.rstrip("/"))]
    bloque = _cfg_bloque(ctx.config, "secrets")
    col.ajouter(id="X-TRACKED", domaine="secrets", element="Fichiers sensibles suivis par Git", bloque=bloque,
                statut="READY" if not sensibles_suivis else "FAILED", nature="VERIFIED",
                gravite="INFO" if not sensibles_suivis else "HIGH",
                detail=("aucun" if not sensibles_suivis else "SENSITIVE_TRACKED — contenu non lu, noms seulement : "
                        + ", ".join(sensibles_suivis)),
                action_humaine=None if not sensibles_suivis else "retirer de l'historique et invalider (WAITING_HUMAN)")
    col.ajouter(id="X-IGNORED", domaine="secrets", element="Fichiers sensibles présents, exclus de Git",
                bloque=[], statut="WARNING" if sensibles_ignores else "READY", nature="VERIFIED",
                gravite="MEDIUM" if sensibles_ignores else "INFO",
                detail=("contenu non lu : " + ", ".join(sensibles_ignores)) if sensibles_ignores else "aucun",
                action_humaine=("interdire leur lecture aux agents (règles de refus)" if sensibles_ignores else None))
    col.observations["fichiers_sensibles"] = {"suivis": sensibles_suivis, "ignores": sensibles_ignores}


# =============================================================================== qualité
def controler_qualite(ctx: Contexte, col: Collecte):
    if not ctx.manifest:
        return
    q = ctx.manifest.get("quality", {})
    gates = q.get("gates", {})
    bloque = _cfg_bloque(ctx.config, "quality")
    for g in q.get("required", []):
        spec = gates.get(g) or {}
        commande = spec.get("command")
        if not commande:
            col.ajouter(id=f"Q-{g}", domaine="quality", element=f"gate {g}", bloque=bloque, statut="FAILED",
                        nature="DECLARED", gravite="HIGH", detail=spec.get("note") or "aucune commande déclarée",
                        action_humaine="choisir et faire évaluer un outil")
            continue
        exe = shutil.which(commande.split()[0])
        col.ajouter(id=f"Q-{g}", domaine="quality", element=f"gate {g}", bloque=bloque,
                    statut="READY" if exe else "FAILED", nature="DECLARED", gravite="INFO" if exe else "HIGH",
                    detail=f"CONFIGURED : « {commande} » (dans {spec.get('cwd', '.')}) — déclarée, non exécutée"
                           + ("" if exe else " ; exécutable absent"))
    ci = [p for p in ctx.config.get("ci_locations", []) if (ctx.racine_projet / p).exists()] if ctx.racine_projet else []
    col.ajouter(id="Q-CI", domaine="quality", element="Intégration continue", bloque=[],
                statut="READY" if ci else "DEGRADED", nature="VERIFIED", gravite="INFO" if ci else "MEDIUM",
                detail=", ".join(ci) if ci else "aucune configuration de CI (la CI est la source de vérité, règle 11)")


# =============================================================================== dépôt
def controler_depot(ctx: Contexte, col: Collecte):
    obs = col.observations.get("verifications", {}).get("SOURCE_CONTROL")
    if not obs or not obs.get("present"):
        return
    d = obs["donnees"]
    if d.get("en_avance"):
        col.ajouter(id="G-UNPUSHED", domaine="source_control", element="Commits non publiés", bloque=[],
                    statut="WARNING", nature="VERIFIED", gravite="HIGH" if d["en_avance"] > 20 else "MEDIUM",
                    detail=f"{d['en_avance']} commit(s) sans copie distante sur {d['branche']} (Playbook §14.4)",
                    action_humaine="publier (action humaine)")
    if d.get("modifies"):
        col.ajouter(id="G-DIRTY", domaine="source_control", element="Modifications non commitées", bloque=[],
                    statut="WARNING", nature="VERIFIED", gravite="LOW", detail=f"{d['modifies']} fichier(s)")
    col.ajouter(id="G-HOOKS", domaine="source_control", element="Hooks Git", bloque=[],
                statut="READY" if d.get("hooks_actifs") or d.get("hooks_path") else "WARNING", nature="VERIFIED",
                gravite="INFO" if d.get("hooks_actifs") or d.get("hooks_path") else "LOW",
                detail=", ".join(d.get("hooks_actifs") or []) or d.get("hooks_path") or "aucun hook actif")


def controler_sauvegarde(ctx: Contexte, col: Collecte):
    """Âge de la dernière sauvegarde (D2, J8) : liste des archives seulement, jamais leur contenu."""
    import datetime as _dt
    import fnmatch as _fn
    import re as _re
    politique_p = ctx.racine_factory / "policies" / "backup.yaml"
    if not politique_p.is_file():
        return
    pol = _yaml(politique_p)
    dest = Path(pol["destination"])
    seuil = ctx.config.get("backup", {}).get("age_warning_hours", 24)
    noms = []
    if dest.is_dir():
        ctx.perimetre.racines.setdefault("BACKUP_ROOT", Racine("BACKUP_ROOT", canonique(dest)))
        noms = [n for n in ctx.perimetre.lister(dest) if _fn.fnmatch(n, pol.get("archive_pattern", "*.zip"))]
    dates = []
    for n in noms:
        m = _re.search(r"(\d{8}T\d{6})", n)
        if m and (dest / (n + ".sha256")).is_file():
            dates.append(_dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M%S"))
    if not dates:
        col.ajouter(id="F-BACKUP", domaine="factory", element="Sauvegarde de la Factory", bloque=[],
                    statut="DEGRADED", nature="VERIFIED", gravite="HIGH",
                    detail=f"aucune archive avec empreinte dans {dest}", action_humaine="lancer une sauvegarde (D2)")
        return
    age = (_dt.datetime.now() - max(dates)).total_seconds() / 3600
    col.ajouter(id="F-BACKUP", domaine="factory", element="Sauvegarde de la Factory", bloque=[],
                statut="READY" if age <= seuil else "WARNING", nature="VERIFIED",
                gravite="INFO" if age <= seuil else "MEDIUM",
                detail=(f"{len(dates)} archive(s) ; la plus récente a {age:.1f} h (seuil {seuil} h) ; intégrité : "
                        "« factory_backup.py verify » ; copie hors poste : " + str(pol.get("offsite_copy"))),
                action_humaine=None if age <= seuil else "sauvegarder (RPO)")


def executer(racine_factory: Path, id_projet: str | None) -> tuple[Contexte | None, Collecte]:
    col = Collecte()
    ctx = preparer(racine_factory, id_projet, col)
    if ctx is None:
        return None, col
    for etape in (controler_systeme, controler_capacites, controler_inventaires, controler_mcp, controler_secrets,
                  controler_qualite, controler_depot, controler_sauvegarde):
        etape(ctx, col)
    return ctx, col
