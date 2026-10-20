# AI Software Factory

Plan de contrôle générique, commun à tous les projets. Les projets en sont des **instances** : ils
s'adaptent à la Factory par leur manifest, la Factory ne se spécialise pour aucun d'eux.

Références normatives : [Playbook v3.2](docs/playbook/playbook-v3.2.md) · Executable Schemas v1.0
(`core/schemas/`) · [ADR-0001](adr/accepted/ADR-0001-socle-de-la-factory.md) ·
[ADR-0002](adr/accepted/ADR-0002-cycle-schemas-et-corrections.md).

Version du standard **3.2** · schémas **1.0** · implémentation **0.1.0** · phase **1 — MVP** (Playbook §17)

## État

| Élément | État |
|---|---|
| Schémas exécutables (`core/schemas/`) | construits |
| Registry v1 (`registry/`) — capacités, outils, MCP, modèles, rôles d'agents, workflows, projets | construit ; **rien n'y est actif** sans évaluation |
| Bootstrap v1 (`bootstrap/`) — mode CHECK | construit et testé ; SETUP et REPAIR : cible |
| Policy Engine (`core/noyau/politique.py`, `policies/`) | construit et testé (ALLOW / DENY / APPROVAL_REQUIRED, refus par défaut) ; **non branché sur l'agent** |
| Sauvegarde (`scripts/factory_backup.py`) | sauvegarde vérifiée et restaurée sur `F:` ; copie hors poste : décision humaine |
| Audit (`audit/`) — approbations, portes humaines, journal en ajout seul | amorcé |
| États, audit chaîné, preuves, portes humaines, CLI, reprise, FAT, multi-projets, runbook | construits et testés (ADR-0007, ADR-0008) |
| Auto-audit | `audit/self-audit/AUDIT-0001.md` : **construite, non opérationnelle pour exécuter des agents** |
| Orchestrator, Quality Gates en CI, évaluation des agents, Lab, Discovery, métriques | cible (phase 2+) |

Un dossier marqué « cible » n'est **pas** actif (Playbook §17.2 règle 4).

## Commandes

```bash
factory check                                    # Factory seule : validation, journal, Bootstrap (Windows : factory.cmd)
factory validate [FICHIER --type T]              # 0 VALID · 1 INVALID · 2 REJECTED
factory bootstrap check --projet <id>            # 0 READY · 1 DEGRADED · 2 BLOCKED
factory registry list [TYPE] [--etat E]
factory policy check DEMANDE.json                # 0 ALLOW · 1 APPROVAL_REQUIRED · 2 DENY
factory state check                              # journal chaîné, cycles, tickets, portes en attente
python -P scripts/factory_backup.py backup       # sauvegarde vérifiée (D2)
python -P scripts/factory_approve.py DEMANDE     # approbation : HUMAIN SEULEMENT, dans sa console
python -P -m unittest discover -s core/tests -t core -p "test_*.py"
python -P -m unittest discover -s bootstrap/tests -t bootstrap -p "test_*.py"
```

Seule dépendance : PyYAML (ADR-0001). Détails : [bootstrap/README.md](bootstrap/README.md).

## Règles qui ne se discutent pas ici

- La Factory n'est liée à aucun projet, pile, fournisseur d'IA, IDE ni MCP (Executable Schemas §36).
- Sécurité refusée par défaut (`policies/security-defaults.yaml`) ; production jamais pour un agent.
- Aucun secret dans ce dépôt, les contextes agents, les tickets ou les rapports.
- Décisions importantes : un ADR ; ce qui attend un humain : `WAITING_HUMAN` ; l'absence de réponse
  n'est jamais un accord.
