# ADR-0007 — Moteur d'états, journal d'audit chaîné, preuves et portes humaines (J5)

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0007 |
| Statut | accepté (dans le cadre du jalon J5 autorisé par « valide et continue », 15/10/2026) |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Rédaction | agent de construction (Claude Opus 5.5) |

## Décisions

1. **Moteur d'états** (`core/noyau/etats.py`) : contrat de transition des Executable Schemas §22 — état de
   départ, table du cycle (`lifecycles.yaml`), conditions nommées et exigences (`policies/transitions.yaml`),
   preuves vérifiées, criticité, approbation humaine liée au contexte. Résultats : APPLIED, REFUSED,
   WAITING_HUMAN. Le moteur ne connaît que le **vocabulaire** des exigences (champs, preuves, relecteur ≠
   auteur, porte humaine, criticité maximale, provenance, tentatives, décision du Policy Engine).
2. **Toute tentative est auditée**, appliquée ou refusée (§31).
3. **Journal chaîné** (`core/noyau/audit.py`, `audit/journal.jsonl`) : `prev_hash` + `event_hash` ;
   modification, suppression, insertion, permutation détectées et localisées ; écriture refusée sur un journal
   compromis ou contenant un secret. L'ancien `audit/events.jsonl` (24 événements, non chaîné) est **figé** ;
   son empreinte est ancrée dans l'événement d'ouverture. La tête de chaîne est consignée **hors du journal**
   dans chaque sauvegarde : une réécriture complète recalculée change la tête et se voit.
4. **Preuves** (`core/noyau/preuves.py`) : commande, code de sortie entier, horodatage, artefact dont l'empreinte
   se vérifie, marquage immuable ; « tests passed » et toute déclaration sont rejetés ; une preuve ne se fabrique
   qu'à partir d'une commande réellement exécutée ; un artefact n'est jamais écrasé.
5. **Portes humaines** (`core/noyau/portes.py`) : ouvertes par le moteur avec la demande lisible par la commande
   humaine ; PENDING jusqu'à une approbation valide pour le même contexte ; EXPIRED à échéance ; aucune
   approbation héritée d'un autre ticket, projet ou périmètre ; la résolution est tracée en ajout seul.
6. **Bootstrap** : nouveau constat critique F-AUDIT (intégrité de la chaîne). **Sauvegarde** : refusée si le
   journal est rompu ; la restauration d'essai revérifie la chaîne.

## Limites

- Le moteur d'états n'est pas encore appelé par un orchestrateur : il s'utilise par code (CLI au J6).
- L'intégrité du journal est **détectée**, pas empêchée : un acteur qui peut écrire le fichier peut le casser ;
  l'ancre externe (sauvegarde) et les règles de refus côté agent restent nécessaires.
- Les exigences par transition couvrent les tickets et les exécutions ; les autres cycles n'ont que la table.
