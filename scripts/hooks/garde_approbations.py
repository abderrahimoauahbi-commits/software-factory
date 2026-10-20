"""Garde PreToolUse de l'agent d'exécution (fermeture de W1, policies/human-approval.yaml).

Projection de la politique Factory dans le runtime d'agent (Master §55) : refuse toute action d'agent qui
écrirait dans audit/approvals/human/ ou lancerait la commande d'approbation humaine. Lit le JSON de l'événement
sur l'entrée standard ; refus = code 2 et motif sur la sortie d'erreur (+ décision JSON). Ne fait rien d'autre :
ce n'est pas le Policy Engine.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[2]
PROTEGE = (FACTORY / "audit" / "approvals" / "human").resolve()
MOTS = ("factory_approve", "approvals/human", "approvals\\human")
OUTILS_ECRITURE = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
OUTILS_COMMANDE = {"Bash", "PowerShell"}


def refuser(motif: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": motif}}))   # ASCII : lisible quel que soit l'encodage de la console
    print(motif.encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr)
    return 2


def dans_protege(chemin: str) -> bool:
    try:
        Path(os.path.realpath(chemin)).relative_to(PROTEGE)
        return True
    except ValueError:
        return False


def main() -> int:
    try:
        evt = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return refuser("garde W1 : événement illisible, refus par défaut")
    outil, entree = evt.get("tool_name"), evt.get("tool_input") or {}
    if outil in OUTILS_ECRITURE:
        chemin = entree.get("file_path") or entree.get("notebook_path") or ""
        if chemin and dans_protege(chemin):
            return refuser("garde W1 : un agent n'écrit jamais une approbation humaine (audit/approvals/human)")
    if outil in OUTILS_COMMANDE:
        commande = str(entree.get("command", "")).replace("\\\\", "\\")
        if any(m in commande for m in MOTS):
            return refuser("garde W1 : la commande d'approbation et les approbations sont réservées à l'humain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
