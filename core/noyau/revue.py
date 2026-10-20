"""Revue humaine d'un ticket (T-FACTORY-018, ADR-0012, décision W1).

Une revue de code n'est une preuve que si elle émane d'un acte que l'agent ne peut pas imiter : la commande humaine
`scripts/factory_approve.py`, lancée sur une demande de revue. La demande porte le contexte exact relu (ticket,
exécution, branche, base, fichiers, empreinte du diff complet, preuves des gates). La preuve REVIEW qui en découle
renvoie à l'enregistrement humain (`approval_ref`) ; le moteur d'états le relit et le revérifie : une preuve REVIEW
fabriquée par l'agent, sans enregistrement humain valide pour CE ticket, ne compte pas.

Décisions : APPROUVE → APPROVED (la revue autorise la suite) ; REFUSE → CHANGES_REQUESTED (retour en cours).
"""
from __future__ import annotations

import hashlib

from .approbation import CANAL, TYPE, Magasin, Verification, canonique, empreinte, empreinte_enregistrement

KIND = "CODE_REVIEW"
DECISIONS = {"APPROVED": "APPROVED", "REJECTED": "CHANGES_REQUESTED"}


def contexte(ticket: dict, exe: dict, diff: str, fichier_diff: str) -> dict:
    """Ce que la revue couvre — et rien d'autre. Tout changement (diff, preuve, branche) change l'empreinte."""
    iso = exe.get("isolation") or {}
    return {
        "kind": KIND,
        "project_id": exe.get("project_id"),
        "ticket_id": ticket.get("id"),
        "ticket_criticality": ticket.get("criticality"),
        "execution_id": exe.get("execution_id"),
        "author": (exe.get("agent") or {}).get("id"),
        "branch": iso.get("branch"),
        "base": iso.get("base"),
        "changes": sorted(exe.get("changes") or []),
        # Différences d'extraction écartées (ADR-0013) : montrées à l'humain avec leur empreinte, jamais cachées.
        "extraction_unchanged": {f: ((exe.get("isolation") or {}).get("extraction_differences") or {}).get(f)
                                 for f in sorted(exe.get("extraction_unchanged") or [])},
        # Fichiers produits par les gates (caches, rapports) : listés avec leur empreinte, hors du diff relu.
        "gate_outputs": {f: (exe.get("post_gates") or {}).get(f) for f in sorted(exe.get("gate_outputs") or [])},
        "diff_file": fichier_diff,
        "diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "evidence": sorted(({"id": p["id"], "type": p["type"], "result": p["result"], "hash": p["hash"]}
                            for p in exe.get("evidence") or []), key=lambda p: p["id"]),
    }


def verifier(magasin: Magasin, ident: str | None, ticket: dict, roles_admis: list[str]) -> tuple[Verification, dict | None]:
    """Enregistrement humain de revue valide pour CE ticket ? (sans contrôle d'âge : une revue ne périme pas,
    c'est l'empreinte du diff qui la lie au code relu)."""
    if not ident:
        return Verification(False, "revue sans enregistrement humain (approval_ref)"), None
    e = magasin.lire(ident)
    if e is None:
        return Verification(False, f"enregistrement de revue {ident} introuvable"), None
    if e.get("kind") != TYPE or e.get("channel") != CANAL:
        return Verification(False, "enregistrement qui n'émane pas de la commande humaine"), None
    if e.get("record_sha256") != empreinte_enregistrement(e):
        return Verification(False, "enregistrement modifié après sa création"), None
    ctx = e.get("context") or {}
    if ctx.get("kind") != KIND:
        return Verification(False, "l'enregistrement n'est pas une revue de code"), None
    if e.get("context_sha256") != empreinte(ctx):
        return Verification(False, "contexte de revue incohérent avec son empreinte"), None
    if ctx.get("ticket_id") != ticket.get("id") or ctx.get("project_id") != ticket.get("project_id"):
        return Verification(False, "revue d'un autre ticket : pas d'héritage de revue"), None
    if e.get("approver_role") not in roles_admis:
        return Verification(False, f"rôle {e.get('approver_role')!r} non habilité à relire"), None
    if e.get("decision") not in DECISIONS:
        return Verification(False, f"décision de revue inconnue : {e.get('decision')!r}"), None
    return Verification(True, f"revue humaine {ident} ({e.get('approver_role')}, {DECISIONS[e['decision']]})"), e


def octets_enregistrement(e: dict) -> bytes:
    """Forme exacte écrite par la commande humaine : l'artefact de la preuve en est la copie à l'octet près."""
    return canonique(e).encode("utf-8")
