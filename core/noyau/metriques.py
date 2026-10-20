"""Métriques d'une mission (Master Evolution Prompt v4 §57) : utile, pas « autonomie à tout prix ».

Calculées à partir des événements réels du graphe, des décisions du Superviseur et des durées mesurées par
l'orchestrateur — jamais à partir de ce que déclarent les agents.
"""
from __future__ import annotations


def _taux(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def calculer(orch) -> dict:
    g, sup = orch.graphe, orch.superviseur
    evts = g.evenements
    taches = list(g.taches.values())
    reussies = [t for t in taches if t.etat == "SUCCEEDED"]
    terminees = [t for t in taches if t.etat in ("SUCCEEDED", "CANCELLED", "BLOCKED")]
    echecs = [e for e in evts if e.get("to_state") == "FAILED"]
    taches_en_echec = {e["task_id"] for e in echecs}
    recuperees = [i for i in taches_en_echec if g.taches[i].etat == "SUCCEEDED"]
    humaines = {e["task_id"] for e in evts if e.get("to_state") == "WAITING_HUMAN"}
    qualite = [e for e in echecs if "QUALITY_GATE_FAILED" in (e.get("reason") or "")]
    securite = [e for e in echecs if any(c in (e.get("reason") or "") for c in ("SECURITY", "SECRET", "POLICY_DENIED"))]
    durees = [d for v in orch.durees.values() for d in v]
    lancees = sum(len(v) for v in orch.durees.values())
    actifs = orch.organisation.effectif()
    utilises = len({t.assigne for t in taches if t.assigne})
    return {
        "AUTONOMY_RATE": _taux(len([t for t in reussies if t.id not in humaines]), len(taches)),
        "TASK_SUCCESS_RATE": _taux(len(reussies), len(terminees) or len(taches)),
        "RECOVERY_RATE": _taux(len(recuperees), len(taches_en_echec)),
        "HUMAN_INTERVENTION_RATE": _taux(len(humaines) + orch.interventions_humaines, len(taches)),
        "RETRY_RATE": _taux(sum(t.tentatives for t in taches), lancees),
        "QUALITY_FAILURE_RATE": _taux(len(qualite), lancees),
        "SECURITY_FAILURE_RATE": _taux(len(securite), lancees),
        "AVERAGE_TASK_DURATION": round(sum(durees) / len(durees), 3) if durees else None,
        "COST_PER_TASK": round(sup.jetons / lancees, 1) if lancees else None,
        "COST_PER_MISSION": sup.jetons,
        "TOOL_CALLS": sup.appels,
        "AGENT_UTILIZATION": _taux(utilises, actifs),
        "PARALLELISM": max(orch.paralleles) if orch.paralleles else 0,
        "TASKS_RUN": lancees,
        "FAILURES": len(echecs),
    }
