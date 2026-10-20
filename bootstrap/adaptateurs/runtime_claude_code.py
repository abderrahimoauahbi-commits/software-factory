"""Inventaire de la configuration d'un agent d'exécution de type « Claude Code » (lecture seule).

Adaptateur propre à un outil : c'est permis ici, et seulement ici (Executable Schemas §20, §36).
Fichiers lus :
  - réglages utilisateur et ~/.claude.json : hors racines, approuvés un par un (APR-0001), clé par clé ;
  - réglages et .mcp.json du PROJET : dans la racine, sauf fichiers déclarés sensibles par la carte du projet.
Aucune valeur n'est recopiée : seulement des noms, des compteurs et des descripteurs masqués.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from noyau.masquage import masquer
from noyau.perimetre import AccesRefuse

REGLAGES_UTILISATEUR = Path("~/.claude/settings.json")
ETAT_UTILISATEUR = Path("~/.claude.json")


def _obs(**k):
    from . import observation
    return observation(**k)


def _json(ctx, chemin: Path, hors_racine: bool, refus: list[str]):
    try:
        return json.loads(ctx.perimetre.lire_texte(chemin, hors_racine_ok=hors_racine, max_octets=50_000_000))
    except FileNotFoundError:
        return None
    except AccesRefuse as e:
        refus.append(str(e))
        return None
    except ValueError:
        refus.append(f"{chemin} : JSON illisible")
        return None


def _descripteur(serveur: dict) -> str:
    """Commande et arguments, ou adresse, MASQUÉS : sert à reconnaître le serveur, jamais à le lancer."""
    if not isinstance(serveur, dict):
        return ""
    morceaux = [str(serveur.get("command", "")), *map(str, serveur.get("args", []) or []), str(serveur.get("url", ""))]
    return masquer(" ".join(m for m in morceaux if m)) or ""


def inventaire(ctx, spec: dict) -> dict:
    refus: list[str] = []
    utilisateur = _json(ctx, REGLAGES_UTILISATEUR, True, refus) or {}
    etat = _json(ctx, ETAT_UTILISATEUR, True, refus) or {}
    projet, projet_local, mcp_projet = {}, None, {}
    if ctx.racine_projet is not None:
        projet = _json(ctx, ctx.racine_projet / ".claude" / "settings.json", False, refus) or {}
        projet_local = _json(ctx, ctx.racine_projet / ".claude" / "settings.local.json", False, refus)
        mcp_projet = (_json(ctx, ctx.racine_projet / ".mcp.json", False, refus) or {}).get("mcpServers", {})

    regles = {"allow": [], "ask": [], "deny": []}
    contournement_interdit = False
    hooks = []
    for source in (utilisateur, projet, projet_local or {}):
        perms = source.get("permissions", {}) or {}
        for k in regles:
            regles[k].extend(perms.get(k, []) or [])
        contournement_interdit |= perms.get("disableBypassPermissionsMode") == "disable"
        hooks.extend((source.get("hooks") or {}).keys())

    risquees = []
    for regle in regles["allow"]:
        for r in ctx.config.get("risky_permission_patterns", []):
            if re.search(r["pattern"], regle):
                risquees.append({"regle": masquer(regle), "pourquoi": r["why"]})

    declares = []
    for nom, s in (etat.get("mcpServers") or {}).items():
        declares.append({"nom": nom, "portee": "utilisateur (~/.claude.json)", "actif": True,
                         "descripteur": _descripteur(s)})
    if ctx.racine_projet is not None:
        cle_projet = str(ctx.racine_projet).replace("\\", "/")
        for chemin, conf in (etat.get("projects") or {}).items():
            if chemin.replace("\\", "/").lower() == cle_projet.lower():
                for nom, s in (conf.get("mcpServers") or {}).items():
                    declares.append({"nom": nom, "portee": "projet, local (~/.claude.json)", "actif": True,
                                     "descripteur": _descripteur(s)})
    for nom, s in (utilisateur.get("mcpServers") or {}).items():
        declares.append({"nom": nom, "portee": "réglages utilisateur (clé non documentée)", "actif": None,
                         "descripteur": _descripteur(s)})
    actives = None if projet_local is None else set(projet_local.get("enabledMcpjsonServers", []) or [])
    tous = bool((projet_local or {}).get("enableAllProjectMcpServers") or projet.get("enableAllProjectMcpServers"))
    for nom, s in mcp_projet.items():
        actif = True if tous else (None if actives is None else nom in actives)
        declares.append({"nom": nom, "portee": "projet (.mcp.json)", "actif": actif, "descripteur": _descripteur(s)})

    greffons = sorted(k for k, v in (utilisateur.get("enabledPlugins") or {}).items() if v)
    agents, skills = [], []
    if ctx.racine_projet is not None:
        for sous, cible in (("agents", agents), ("skills", skills)):
            d = ctx.racine_projet / ".claude" / sous
            if d.is_dir():
                try:
                    cible.extend(n.removesuffix(".md") for n in ctx.perimetre.lister(d))
                except AccesRefuse as e:
                    refus.append(str(e))

    # Fermeture de W1 (policies/human-approval.yaml) : la configuration de projet de la FACTORY doit refuser à
    # l'agent l'écriture des approbations humaines et la commande d'approbation, et poser la garde PreToolUse.
    reglages_factory = _json(ctx, ctx.racine_factory / ".claude" / "settings.json", False, refus) or {}
    refus_factory = ((reglages_factory.get("permissions") or {}).get("deny") or [])
    commandes_hooks = [h.get("command", "") for groupe in ((reglages_factory.get("hooks") or {}).get("PreToolUse") or [])
                       for h in groupe.get("hooks", [])]
    protections_w1 = {
        "ecriture_approbations_refusee": any("approvals/human" in r for r in refus_factory),
        "commande_approbation_refusee": any("factory_approve" in r for r in refus_factory),
        "garde_pretooluse": any("garde_approbations" in c for c in commandes_hooks),
        "contournement_interdit": (reglages_factory.get("permissions") or {}).get("disableBypassPermissionsMode") == "disable",
        "portee": "sessions ouvertes dans FACTORY_ROOT (réglages de projet)",
    }

    return _obs(present=True, nature="VERIFIED", detail="configuration inventoriée (clés seulement)",
                protections_w1=protections_w1,
                regles={k: len(v) for k, v in regles.items()}, regles_risquees=risquees,
                contournement_interdit=contournement_interdit, hooks=sorted(set(hooks)),
                greffons_actifs=greffons, mcp_declares=declares,
                reglages_projet_locaux_lus=projet_local is not None,
                agents_projet=sorted(agents), skills_projet=sorted(skills), refus=refus)
