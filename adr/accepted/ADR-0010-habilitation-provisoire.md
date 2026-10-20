# ADR-0010 — Habilitation provisoire d'un agent pour le pilote de la phase 1 (contradiction C-17)

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0010 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | choix « Habilitation provisoire C1 (Recommandé) » du Factory Owner, 15/10/2026 |
| Rédaction | agent de construction (Claude Opus 5.5) |

## Contexte

Contradiction C-17 (ADR-0009) : la phase 1 exige des tickets pilotes exécutés par des agents ; la règle 19 et le
§12.6 interdisent un agent non évalué ; l'évaluation est en phase 2.

## Décision

1. **Un** agent (rôle `backend`) reçoit une habilitation **provisoire** : plafond **C1**, projet `gestionfil`,
   du 2026-10-15 au 2026-11-14. Sa fiche reste `DISCOVERED` (il n'est pas évalué) et porte
   `provisional_habilitation` avec le statut `REQUESTED`.
2. L'habilitation ne vaut que si **l'humain** l'approuve par la commande d'approbation (W1) ; l'approbation est liée
   au contexte exact (agent, plafond, projets, dates) ; toute modification de la fiche l'invalide.
3. Le Policy Engine applique le **plus bas** des deux plafonds (fiche, habilitation) ; refuse hors projet, après
   expiration, au-delà de 30 jours, au-delà de C1, ou si l'approbateur n'est pas le Factory Owner
   (`policies/policy-engine.yaml`, `provisional_habilitation`).
4. Chaque ticket pilote passe par la plateforme d'exécution (périmètre, gates, preuves) et par la revue humaine.
5. Les 10 tickets pilotes ne valent critère de passage que s'ils sont livrés **sans incident de sécurité**.

## Conséquences

- Le choix du rôle (`backend`) est révisable : remplacer la demande par celle d'un autre rôle avant approbation.
- L'évaluation formelle de l'agent reste due en phase 2 ; l'habilitation provisoire expire d'elle-même.

## Amendement du 2026-10-15 — rôle révisé avant approbation

Le premier ticket pilote retenu (T-GF-001) n'ajoute que des tests : le rôle habilité provisoirement devient
**`qa`** (plafond C1 dans sa fiche) au lieu de `backend`, comme le permettait la section « Conséquences ».
La demande `AR-HAB-backend.json` (jamais approuvée) est remplacée par `audit/approvals/requests/AR-HAB-qa.json`.
Le manifest et `AGENT_CONTEXT.md` ont été installés dans le dépôt GestionFil avec l'accord du Factory Owner ;
ses `paths` sont validés (APPROVED). Le démarrage de T-GF-001 est refusé (BLOCKED) tant que l'habilitation n'est
pas approuvée par la commande humaine : un « valide » écrit dans la conversation ne vaut pas approbation (W1).
