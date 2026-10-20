# Reprise après sinistre de la Factory (jalon J8, Playbook §14.4–14.5)

Scénario couvert : **la Factory est détruite** (dossier supprimé, disque perdu, corruption, falsification).
Outil : `scripts/factory_backup.py` ; politique : `policies/backup.yaml` ; restauration pas à pas :
`docs/operations/restauration-factory.md`.

## Objectifs

| Indicateur | Valeur | Source |
|---|---|---|
| **RPO** (perte de données admise) | cible `WAITING_HUMAN` ; en attendant, le Bootstrap alerte au-delà de **24 h** (F-BACKUP) | `bootstrap/bootstrap.yaml` |
| **RTO** (durée de reprise) | **mesuré** par `drill` : restauration + `factory check` + suite de tests du cœur | `compliance/evidence/D2/drill-*.json` |
| Copie hors poste | `WAITING_HUMAN` — sans elle, la perte du poste reste un risque non couvert | `policies/backup.yaml` |

## Ordre de reconstruction

```text
Factory détruite → archive vérifiée → restauration dans un répertoire neuf → registre et schémas → politiques
→ journal d'audit (chaîne vérifiée, tête comparée à l'ancre de l'archive) → agents et MCP (rien d'actif) →
connaissance et ADR → cartes des projets → factory check READY → bascule → événement d'audit de reprise
```

## Procédure

1. **Choisir l'archive** la plus récente sur `F:/software-factory-backups` et la vérifier :
   `python -P scripts/factory_backup.py verify <archive>` puis `Get-FileHash` contre le `.sha256`.
2. **Exercer avant de basculer** : `python -P scripts/factory_backup.py drill <archive>`. La copie restaurée
   doit passer `factory check` et la suite de tests du cœur ; la durée affichée est le RTO.
3. **Restaurer** (acte humain) dans un répertoire neuf, jamais par-dessus : voir `restauration-factory.md`.
4. **Contrôler l'intégrité de l'audit** : `factory state check` → chaîne intacte ; la tête doit égaler
   `meta.audit_head` du manifeste de l'archive. Une tête différente = journal réécrit : incident.
5. **Basculer**, relancer `factory check`, consigner la reprise (événement d'audit : archive, raison, RTO).

## Test périodique

- À chaque jalon accepté : `backup` puis `drill` ; conserver les sorties dans `compliance/evidence/D2/`.
- Planification automatique (proposition, **à poser par l'humain**, hors Factory) : tâche planifiée Windows
  lançant `python -P <FACTORY_ROOT>\scripts\factory_backup.py backup` chaque jour.

## Ce que la reprise ne couvre pas

- Perte du poste entier tant qu'aucune copie hors poste n'existe.
- Historique Git (aucun commit à ce jour).
- Fichiers hors Factory : projets, configuration de l'agent, réglages de l'IDE.
