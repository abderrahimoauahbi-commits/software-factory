"""Garde PreToolUse : projection de l'autorité de la session dans le runtime d'agent (ADR-0017 annexe E « Hook du
bail », étapes G1 et G4).

Branchée par le runtime de la Factory dans les réglages engendrés pour CHAQUE session d'agent (jamais dans les
réglages d'un dépôt) ; son argument est le fichier de projection de la session :
{"lease": id|null, "actor": id, "execution": id, "leases_dir": chemin,
 "authority": null | {"kind": "TICKET_EXECUTION", "execution_id", "worktree", "scope": [chemins], "executions_dir"}}.

Deux autorités possibles pour écrire ou commander :
- un BAIL (ressources jetables) : authentique, actif, non expiré, de cet acteur et de cette exécution ; capacité
  FILESYSTEM_WRITE pour écrire ; relu à chaque appel (révocation, expiration, politique) ;
- une EXÉCUTION DE TICKET autorisée par le Policy Engine (run_ticket) : exécution encore en cours (contexte écrit,
  résultat pas encore écrit) ; toute écriture dans l'espace isolé ET dans le périmètre du ticket — le contrôle J13 de
  fin d'exécution devient préventif.
Outils de lecture : laissés aux règles de permission. Tout autre outil, projection illisible, aucune autorité :
refus par défaut. Chaque refus est ajouté à `<projection>.refus.jsonl` (tentatives mesurées par l'évaluation).

Ce n'est pas le Policy Engine ni une frontière L2 : IMPLEMENTED tant que les preuves de l'annexe E (vraie session,
acteur non coopératif) n'ont pas été produites et revues ; le fichier de projection est modifiable par le compte (L1).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[2]
for _p in (FACTORY / "core",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

LECTURE = {"Read", "Glob", "Grep"}
ECRITURE = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
COMMANDE = {"Bash", "PowerShell"}


def refuser(motif: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": motif}}))
    print(motif.encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr)
    return 2


def _dans_perimetre(chemin: str, autorite: dict) -> str | None:
    """Motif de refus si le fichier écrit sort de l'espace isolé ou du périmètre du ticket, sinon None."""
    if not chemin:
        return "écriture sans chemin"
    espace = Path(os.path.realpath(autorite.get("worktree") or ""))
    cible = Path(os.path.realpath(chemin if os.path.isabs(chemin) else espace / chemin))
    try:
        rel = cible.relative_to(espace).as_posix()
    except ValueError:
        return f"écriture hors de l'espace isolé : {chemin}"
    for p in autorite.get("scope") or []:
        p = str(p)
        if rel == p.rstrip("/") or (p.endswith("/") and rel.startswith(p)) or rel.startswith(p.rstrip("/") + "/"):
            return None
    return f"écriture hors du périmètre du ticket ({', '.join(autorite.get('scope') or [])}) : {rel}"


def _execution_active(autorite: dict) -> str | None:
    d = Path(autorite.get("executions_dir") or "") / str(autorite.get("execution_id") or "")
    if not autorite.get("execution_id") or not (d / "context.json").is_file():
        return "exécution de ticket inconnue"
    if (d / "execution.json").is_file():
        return "exécution de ticket terminée"
    return None


def decider(evt: dict, projection: dict, gestionnaire) -> str | None:
    """→ motif de refus, ou None si l'appel peut se poursuivre (sous les autres règles de la session)."""
    outil = evt.get("tool_name")
    if outil in LECTURE:
        return None
    if outil not in ECRITURE | COMMANDE:
        return f"garde du bail : outil {outil!r} non projeté, refus par défaut"
    bail = projection.get("lease")
    autorite = projection.get("authority") or {}
    ticket = autorite.get("kind") == "TICKET_EXECUTION"
    if ticket:
        motif = _execution_active(autorite)
        if motif:
            return f"garde du bail : {motif}"
    if outil in ECRITURE and ticket:         # fichiers : le périmètre du ticket fait foi, bail ou non
        entree = evt.get("tool_input") or {}
        motif = _dans_perimetre(str(entree.get("file_path") or entree.get("notebook_path") or ""), autorite)
        return f"garde du bail : {motif}" if motif else None
    if bail:                                 # commandes (et écritures sans ticket) : le bail fait foi
        ok, motif = gestionnaire.verifier_session(str(bail), projection.get("actor"), projection.get("execution"),
                                                  "FILESYSTEM_WRITE" if outil in ECRITURE else None)
        return None if ok else f"garde du bail : {motif}"
    if ticket:
        return None                          # commandes : bornées par les outils permis de la session (gates)
    return f"garde du bail : aucun bail ni exécution de ticket pour cette session, {outil} refusé"


def gestionnaire_reel(projection: dict):
    import yaml
    from fournisseurs.cablage import cle_de_service
    from noyau.baux import GestionnaireCapacites
    from noyau.contexte import empreinte_politique
    cycles = yaml.safe_load((FACTORY / "core" / "schemas" / "lifecycles.yaml").read_text(encoding="utf-8"))
    return GestionnaireCapacites(Path(projection["leases_dir"]), None, cycles["capability_lease"], {},
                                 cle=cle_de_service(), empreinte_politique=empreinte_politique(FACTORY))


def tracer_refus(chemin_projection: Path, evt: dict, motif: str) -> None:
    entree = evt.get("tool_input") or {}
    ligne = {"at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"), "tool": evt.get("tool_name"),
             "path": entree.get("file_path") or entree.get("notebook_path"),
             "command": str(entree.get("command") or "")[:200] or None, "reason": motif}
    try:
        with open(chemin_projection.with_suffix(".refus.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except OSError:
        pass                                 # la trace ne conditionne jamais le refus


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        evt = json.loads(sys.stdin.read() or "{}")
        projection = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        if not isinstance(evt, dict) or not isinstance(projection, dict):
            raise ValueError
    except (IndexError, OSError, ValueError):
        return refuser("garde du bail : événement ou projection illisible, refus par défaut")
    if evt.get("tool_name") in LECTURE:
        return 0
    try:
        gestion = gestionnaire_reel(projection) if projection.get("lease") and projection.get("leases_dir") else None
        motif = decider(evt, projection, gestion)
    except Exception as e:                                   # toute erreur de la garde est un refus
        motif = f"garde du bail : erreur de vérification ({type(e).__name__}), refus par défaut"
    if motif:
        tracer_refus(Path(argv[0]), evt, motif)
        return refuser(motif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
