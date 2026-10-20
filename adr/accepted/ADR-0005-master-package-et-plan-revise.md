# ADR-0005 — Master Package v3.2, blocs de maturité et plan révisé

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0005 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | « ok applique les recommandations et continue le travail » (APR-0004) |
| Rédaction | agent de construction (Claude Opus 5.5) |

## Contexte

Trois documents reçus : le Master Package v3.2 (deux fichiers au contenu identique), un « Guide
d'implémentation v1.0 » qui décrit une archive de scripts PowerShell non transmise, et une proposition de dix
blocs de maturité (audit de préparation, modèle de menaces, modèle de données, identité et confiance, Policy
Engine exécutable, système de preuves, reprise après sinistre, tests d'acceptation, pilote multi-projets,
manuel d'exploitation).

## Décisions

| Réf. | Décision |
|---|---|
| M1 | Cycles de vie : les Executable Schemas font foi ; les noms du Master `REEVALUATED` et `RETIRED` sont des **synonymes** acceptés et ramenés à `REEVALUATION` et `REMOVED` (`lifecycles.yaml`, clé `aliases`) |
| M2 | Manifest : le format des Executable Schemas fait foi ; ajout de `paths: read / write / forbidden` (Master §11.2), chemins relatifs obligatoires (`PATH_ESCAPE` sinon) ; la priorité de `forbidden` sera appliquée par le Policy Engine |
| M3 | L'implémentation Python reste la référence ; l'archive PowerShell est un **candidat** (`discovery/`), à analyser en lecture seule si son chemin est fourni ; son lancement en `-ExecutionPolicy Bypass` est signalé |
| M4 | Les textes normatifs (Master Package, Executable Schemas) sont à déposer par le Factory Owner dans `docs/normative/` : l'agent ne les recopie pas |
| Plan | Les blocs de maturité sont intégrés : J3 (préparation, menaces, données, confiance) **avant** le Policy Engine (J4) ; reprise après sinistre (J8), tests d'acceptation de la Factory (J9), pilote multi-projets (J10), manuel d'exploitation (J11), auto-audit (J12) |

## Faiblesse découverte et consignée

**W1 — approbation humaine non authentifiée.** Les fiches `audit/approvals` sont écrites par l'agent à partir
des réponses de la session. Un agent compromis pourrait forger une approbation (menace T14). Décision humaine
requise ; proposition pour J5 : une approbation ne vaut que si elle est enregistrée par un acte de l'humain hors
de portée de l'agent (commit signé, commande lancée par l'humain).

## Conséquences

- `core/schemas/relations.yaml` (42 relations) et `core/schemas/trust.yaml` (acteurs, arêtes, invariants)
  deviennent des entrées du Policy Engine.
- `security/threats.yaml` : 16 menaces ; tout contrôle VERIFIED cite un test existant, vérifié par un test.
- Le jalon de reprise après sinistre (J8) ne peut rien démontrer tant que la Factory n'a ni commit ni copie (D2).
