"""Rapport du CHECK au contrat de sortie universel (State Machines & Contracts §28), en JSON et en Markdown.

Tout texte passe une dernière fois par le masquage avant écriture.
"""
from __future__ import annotations

import json
from pathlib import Path

from noyau.masquage import masquer
from noyau.modele import GRAVITE, etat_factory, etat_phase, maintenant

PHASES_EVALUEES = ["PROJECT_ANALYSIS", "EXECUTION"]

# Vocabulaire du Master Package §56 : KNOWN = vérifié, DECLARED = déclaré, UNKNOWN = invérifiable. Les états
# DISCOVERED / TESTED / APPROVED / ACTIVE sont ceux du registre et figurent dans le détail des constats.
MASTER = {"VERIFIED": "KNOWN", "DECLARED": "DECLARED", "UNVERIFIABLE": "UNKNOWN", "HUMAN_REQUIRED": "UNKNOWN"}


def construire(ctx, col, id_projet: str | None, version_bootstrap: str) -> dict:
    constats = col.constats
    etat_f = etat_factory(constats)
    phases = {p: etat_phase(constats, p) for p in PHASES_EVALUEES}
    attentes = [c for c in constats if c.action_humaine]
    trouvailles = [c for c in constats if c.statut != "READY"]
    trouvailles.sort(key=lambda c: (-GRAVITE.index(c.gravite), c.id))
    suivant = "PROJECT_ANALYSIS" if phases["PROJECT_ANALYSIS"] == "READY" else None
    statut = "SUCCESS" if etat_f == "READY" and all(v == "READY" for v in phases.values()) else (
        "BLOCKED" if etat_f == "BLOCKED" else "PARTIAL")
    executeur = ctx.executeur if ctx else None
    return {
        "schema_version": "1.0",
        "result": {
            "status": statut, "phase": "BOOTSTRAP_CHECK", "project_id": id_projet, "ticket_id": None,
            "execution_id": None,
            "summary": (f"Factory {etat_f} ; analyse du projet {phases['PROJECT_ANALYSIS']} ; "
                        f"exécution d'agents {phases['EXECUTION']}."),
            "findings": [{"id": c.id, "severity": c.gravite, "description": f"{c.element} — {c.detail}",
                          "evidence": c.nature} for c in trouvailles],
            "decisions": [], "risks": [],
            "artifacts": [], "tests": [],
            "unresolved": [f"{c.id} : {c.action_humaine}" for c in attentes],
            "next_phase": suivant,
            "human_action_required": bool(attentes) or phases["PROJECT_ANALYSIS"] != "READY",
        },
        "bootstrap": {
            "version": version_bootstrap, "mode": "CHECK", "timestamp": maintenant(),
            "factory_state": etat_f, "phase_readiness": phases,
            "manifest_source": ctx.manifest_source if ctx else None,
            "constats": [c.en_dict() | {"master_status": MASTER[c.nature]} for c in constats],
            "observations": col.observations,
            "preuves_commandes": [p.__dict__ for p in (executeur.journal if executeur else [])],
            "lectures": ([f"{x} (identité)" for x in col.observations.get("lectures_identite", [])]
                         + (ctx.perimetre.lectures if ctx else [])),
            "refus": (ctx.perimetre.refus if ctx else []),
            "garanties": ["aucune écriture hors bootstrap/reports", "aucune commande hors liste blanche",
                          "aucun fichier sensible ouvert", "aucun serveur MCP démarré", "aucune connexion réseau "
                          "ou base de données par le Bootstrap"],
        },
    }


def _md(r: dict) -> str:
    b, res = r["bootstrap"], r["result"]
    l = [f"# FACTORY BOOTSTRAP CHECK — {res['project_id'] or 'Factory seule'}", "",
         f"{b['timestamp']} · Bootstrap {b['version']} · mode {b['mode']} · résultat **{res['status']}**", "",
         f"| Factory | Analyse du projet | Exécution d'agents | Manifest |", "|---|---|---|---|",
         f"| **{b['factory_state']}** | **{b['phase_readiness']['PROJECT_ANALYSIS']}** | "
         f"**{b['phase_readiness']['EXECUTION']}** | {b['manifest_source'] or '—'} |", "",
         "## Constats", "", "| Id | Élément | État | Preuve | Master §56 | Gravité | Détail |",
         "|---|---|---|---|---|---|---|"]
    for c in b["constats"]:
        detail = c["detail"].replace("|", "\\|")
        l.append(f"| {c['id']} | {c['element']} | {c['statut']} | {c['nature']} | {c['master_status']} | "
                 f"{c['gravite']} | {detail} |")
    if res["unresolved"]:
        l += ["", "## En attente d'une décision humaine", ""] + [f"- {u}" for u in res["unresolved"]]
    l += ["", "## Preuves d'exécution", "", "| Commande | Code | Résultat |", "|---|---|---|"]
    for p in b["preuves_commandes"]:
        l.append(f"| `{p['source']}` | {p['exit_code']} | {p['result']} |")
    l += ["", "## Lectures", ""] + [f"- {x}" for x in b["lectures"]]
    if b["refus"]:
        l += ["", "## Accès refusés par le périmètre (non effectués)", ""] + [f"- {x}" for x in b["refus"]]
    l += ["", "## Garanties", ""] + [f"- {g}" for g in b["garanties"]]
    return "\n".join(l) + "\n"


def ecrire(r: dict, repertoire: Path) -> list[Path]:
    repertoire.mkdir(parents=True, exist_ok=True)
    horodatage = r["bootstrap"]["timestamp"][:19].replace(":", "").replace("-", "")
    base = repertoire / f"check-{r['result']['project_id'] or 'factory'}-{horodatage}"
    j, m = base.with_suffix(".json"), base.with_suffix(".md")
    j.write_text(masquer(json.dumps(r, ensure_ascii=False, indent=2, default=str)), encoding="utf-8", newline="\n")
    m.write_text(masquer(_md(r)), encoding="utf-8", newline="\n")
    return [j, m]
