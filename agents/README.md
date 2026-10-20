# agents

Définitions des agents (rôle, limites, outils, MCP, criticité max, relecteur) : `registry/agents/` (épinglé).

## `evaluations/` — suites d'évaluation par rôle (Playbook v3.3 §12.6, étape G4)

Une suite par rôle et par projet : tâches de référence, pièges (injection, périmètre ambigu, permission manquante),
régressions ; seuils par criticité. Format vérifié par `core/noyau/evaluation.py` (`valider_suite`).

```bash
python -P factory.py eval plan agents/evaluations/<suite>.yaml --agent <rôle>    # lecture seule
python -P factory.py eval run  agents/evaluations/<suite>.yaml --agent <rôle> --modele <id>   # HUMAIN seul
python -P factory.py eval report  compliance/evidence/evaluations/<campagne>
python -P factory.py eval request compliance/evidence/evaluations/<campagne>     # demande W1
python -P factory.py eval apply   compliance/evidence/evaluations/<campagne>     # après approbation humaine
```

L'habilitation n'existe qu'après approbation humaine de la demande ; le Policy Engine la vérifie à chaque décision.
