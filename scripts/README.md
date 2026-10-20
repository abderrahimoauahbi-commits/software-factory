# scripts

| Script | Qui le lance | Rôle |
|---|---|---|
| `factory_backup.py` | humain ou agent | sauvegarde (`backup`), intégrité (`verify`), restauration d'essai (`restore-test`) — D2, `policies/backup.yaml` |
| `factory_approve.py` | **humain seulement**, dans sa console | crée une approbation liée au contexte exact d'une demande — W1, `policies/human-approval.yaml` ; pour une demande `AR-REV-*`, affiche le diff vérifié : APPROUVE = revue favorable, REFUSE = modifications demandées (ADR-0012) |

Lancer avec `python -P` (PyYAML dans le site utilisateur). La CLI unifiée `factory` viendra au jalon J6.
