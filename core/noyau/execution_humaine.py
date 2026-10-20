"""Exécution humaine des actions réservées (ADR-0017 D38, I7 ; Playbook v3.3 §17, étape G2) : l'agent prépare,
l'humain approuve et exécute.

Un plan d'exécution humaine est une DEMANDE de décision (contexte HUMAN_EXECUTION_PLAN) : étapes exactes
(argv sans shell, répertoire absolu), projet, motif. L'exécuteur :

- n'exécute que les étapes du contexte APPROUVÉ par la commande humaine, à l'empreinte près, jamais une commande
  fournie au moment de l'exécution (I7) ;
- vérifie l'enregistrement humain (forme, empreintes, rôle admis, âge) ;
- n'exécute un plan qu'une fois (usage unique, constaté au journal) ;
- s'arrête à la première étape en échec ; trace chaque étape au journal (code, empreinte de la sortie masquée).

Le refus dans une session d'agent et l'exigence d'une console sont des gardes PROCÉDURALES appliquées par la CLI ;
la séparation réelle de l'executor est l'étape G3 (service d'autorité, executor séparé).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

from .approbation import CANAL, TYPE, empreinte, empreinte_enregistrement
from .masquage import masquer

KIND = "HUMAN_EXECUTION_PLAN"
ACTION_ETAPE, ACTION_PLAN = "étape de plan d'exécution humaine", "exécution de plan d'exécution humaine"


class RefusPlan(Exception):
    """Plan non préparé ou non exécuté (forme, approbation, usage unique)."""


def _etapes_valides(etapes) -> list[dict]:
    if not isinstance(etapes, list) or not etapes:
        raise RefusPlan("un plan contient au moins une étape")
    out = []
    for i, e in enumerate(etapes, 1):
        argv, cwd = (e or {}).get("argv"), (e or {}).get("cwd")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise RefusPlan(f"étape {i} : argv doit être une liste non vide de chaînes")
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            raise RefusPlan(f"étape {i} : répertoire absolu exigé")
        out.append({"argv": list(argv), "cwd": cwd})
    return out


def demande(plan: dict, roles: list[str], maintenant: _dt.datetime | None = None) -> dict:
    """Demande d'approbation d'un plan préparé par l'agent."""
    if not plan.get("title") or not plan.get("project_id") or not plan.get("reason"):
        raise RefusPlan("titre, projet et motif exigés")
    ctx = {"kind": KIND, "title": str(plan["title"]), "project_id": str(plan["project_id"]),
           "reason": str(plan["reason"]), "rule": plan.get("rule"), "steps": _etapes_valides(plan.get("steps")),
           "requested_at": (maintenant or _dt.datetime.now(_dt.timezone.utc)).isoformat(timespec="seconds")}
    ctx["plan_id"] = f"PLAN-{empreinte(ctx)[:8]}"
    lignes = [f"  {i}. [{s['cwd']}] {' '.join(s['argv'])}" for i, s in enumerate(ctx["steps"], 1)]
    return {"context": ctx, "context_sha256": empreinte(ctx), "roles": sorted(roles),
            "purpose": f"EXÉCUTION HUMAINE {ctx['plan_id']} — {ctx['title']} (projet {ctx['project_id']}). "
                       f"Motif : {ctx['reason']}. Étapes exactes :\n" + "\n".join(lignes)}


def executes(journal) -> set[str]:
    """Empreintes de contexte des plans déjà exécutés (ou tentés) : usage unique."""
    if journal is None or not Path(journal.chemin).is_file():
        return set()
    out = set()
    for ligne in Path(journal.chemin).read_text(encoding="utf-8").splitlines():
        e = json.loads(ligne)
        if e.get("action") == ACTION_PLAN and e.get("plan_sha256"):
            out.add(e["plan_sha256"])
    return out


def approbation_valide(approbations: Path, h: str, roles: list[str], age_max_h: float,
                       maintenant: _dt.datetime) -> dict:
    retenue = None
    for p in sorted(Path(approbations).glob("HA-*.json")) if Path(approbations).is_dir() else []:
        try:
            e = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("context_sha256") != h:
            continue
        if e.get("kind") != TYPE or e.get("channel") != CANAL or e.get("record_sha256") != empreinte_enregistrement(e):
            continue
        if e.get("context_sha256") != empreinte(e.get("context")):
            continue
        if retenue is None or str(e.get("created_at", "")) >= str(retenue.get("created_at", "")):
            retenue = e
    if retenue is None:
        raise RefusPlan("aucune décision humaine pour ce plan (l'absence de réponse n'est jamais un accord)")
    if retenue.get("decision") != "APPROVED":
        raise RefusPlan(f"décision humaine : {retenue.get('decision')}")
    if retenue.get("approver_role") not in roles:
        raise RefusPlan(f"rôle {retenue.get('approver_role')!r} non admis pour une exécution humaine")
    try:
        cree = _dt.datetime.fromisoformat(retenue["created_at"])
    except (KeyError, ValueError):
        raise RefusPlan("date d'approbation illisible")
    if maintenant - cree > _dt.timedelta(hours=age_max_h) or cree > maintenant + _dt.timedelta(minutes=5):
        raise RefusPlan("approbation expirée ou datée du futur : nouvelle demande requise")
    return retenue


def executer(demande_plan: dict, approbations: Path, roles: list[str], age_max_h: float, journal,
             acteur: dict, delai: int = 600, maintenant: _dt.datetime | None = None, lanceur=subprocess.run) -> dict:
    """Exécute les étapes du plan APPROUVÉ. → {"plan_id", "succes", "etapes": [{code, sortie_sha256}]}."""
    ctx = demande_plan.get("context")
    h = demande_plan.get("context_sha256")
    if not isinstance(ctx, dict) or ctx.get("kind") != KIND or h != empreinte(ctx):
        raise RefusPlan("demande incohérente ou d'un autre type")
    etapes = _etapes_valides(ctx.get("steps"))
    if journal is None:
        raise RefusPlan("aucun journal : une exécution humaine doit être tracée")
    if h in executes(journal):
        raise RefusPlan(f"{ctx.get('plan_id')} déjà exécuté : usage unique, nouvelle demande requise")
    maintenant = maintenant or _dt.datetime.now(_dt.timezone.utc)
    appro = approbation_valide(approbations, h, roles, age_max_h, maintenant)
    commun = {"actor": acteur, "project_id": ctx["project_id"], "plan_id": ctx["plan_id"], "plan_sha256": h,
              "approval_refs": [appro.get("id")]}
    journal.ajouter(action=ACTION_PLAN, result="STARTED", from_state="APPROVED", to_state="RUNNING",
                    reasons=[f"{len(etapes)} étape(s) ; approbation {appro.get('id')} ({appro.get('approver_role')})"],
                    **commun)
    resultats, succes = [], True
    for i, s in enumerate(etapes, 1):
        try:
            r = lanceur(s["argv"], cwd=s["cwd"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=delai, shell=False, stdin=subprocess.DEVNULL)
            code, sortie = r.returncode, masquer((r.stdout or "") + (r.stderr or ""))
        except (OSError, subprocess.TimeoutExpired) as e:
            code, sortie = None, f"{type(e).__name__}"
        resultats.append({"etape": i, "code": code, "sortie": sortie[-4000:],
                          "sortie_sha256": hashlib.sha256(sortie.encode("utf-8")).hexdigest()})
        journal.ajouter(action=ACTION_ETAPE, result="SUCCEEDED" if code == 0 else "FAILED", step=i,
                        exit_code=code, output_sha256=resultats[-1]["sortie_sha256"], **{k: v for k, v in commun.items()
                                                                                       if k != "approval_refs"})
        if code != 0:
            succes = False
            break
    journal.ajouter(action=f"fin d'{ACTION_PLAN}", result="SUCCEEDED" if succes else "FAILED", from_state="RUNNING",
                    to_state="SUCCEEDED" if succes else "FAILED",
                    reasons=[f"{len(resultats)}/{len(etapes)} étape(s) exécutée(s)"],
                    **{k: v for k, v in commun.items() if k != "plan_sha256"})
    return {"plan_id": ctx["plan_id"], "succes": succes, "etapes": resultats}
