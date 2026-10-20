# ADR-0004 — Moteur de validation : verdicts et règles déclarées par les schémas

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0004 |
| Statut | accepté (dans le cadre du jalon J2 approuvé par le prompt de construction v1.1, APR-0003) |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Rédaction | agent de construction (Claude Opus 5.5) |
| À ratifier | extensions de schéma ci-dessous, avec celles de l'ADR-0002, dans les Executable Schemas v1.1 |

## Contexte

Les Executable Schemas §30 listent les contrôles à faire avant d'accepter un objet et ne connaissent qu'un
échec, VALIDATION_FAILED. Le guide d'utilisation §14 attend trois issues distinctes : VALID, INVALID
(projet sans `id`) et REJECTED (version incompatible, criticité C5).

## Décisions

1. **Trois verdicts.** `VALID` ; `INVALID` = objet incomplet ou mal référencé ; `REJECTED` = objet qui
   contredit le contrat. INVALID et REJECTED valent tous deux VALIDATION_FAILED ; un REJECTED l'emporte.

   | Code | Verdict | Contrôle §30 |
   |---|---|---|
   | VERSION_INCOMPATIBLE | REJECTED | VERSION_COMPATIBILITY — autre majeure, ou mineure plus récente que la version supportée |
   | IDENTITY_MISSING | INVALID | IDENTITY |
   | REQUIRED_MISSING | INVALID | (structure) |
   | ENUM_VALUE | REJECTED | ENUMS, CRITICALITY, DATA_CLASSIFICATION |
   | REFERENCE_UNKNOWN | INVALID | REFERENCES |
   | POLICY_WEAKENING | REJECTED | PERMISSIONS, SECURITY (valeurs obligatoires, Executable Schemas §34) |
   | SECRET_IN_CLEAR | REJECTED | SECURITY |
   | LIMIT_EXCEEDED | REJECTED | BUDGET (borne déclarée par le schéma ; au plus 3 tentatives selon le Playbook v3.2 §8.6 — note du 16/10/2026 : à l'adoption du Playbook v3.3, la borne devient celle de la politique d'exécution, à ratifier dans les Executable Schemas v1.1, voir NE1) |
   | FACTORY_VERSION_INCOMPATIBLE | REJECTED | VERSION_COMPATIBILITY (version de Factory exigée) |
   | SCHEMA_UNKNOWN | REJECTED | — |

2. **Règles déclarées par les schémas, pas codées.** Nouvelles clés de schéma :
   `references` (chemin → registre), `mandatory` (valeur qu'un objet ne peut pas changer sans exception
   approuvée), `limits` (bornes), `version_fields` (versions de Factory exigées par l'objet). Le moteur ne
   connaît aucun type d'objet.
3. **`WAITING_HUMAN`** n'invalide pas : la valeur est relevée comme décision attendue. Elle empêchera en
   revanche l'entrée dans un état exécutable quand le State Engine existera (J4).
4. **Validation en deux passes** du registre : lecture de toutes les fiches, puis validation avec les
   références contre l'ensemble.

## Non couvert par J2 (à venir)

SCOPE, DEPENDENCIES, APPROVALS et EVIDENCE du §30 dépendent du Policy Engine, du State Engine et des
portes humaines (J3, J4). Un affaiblissement couvert par une **exception approuvée** est aujourd'hui rejeté
sans exception possible : la prise en compte des exceptions viendra avec le Policy Engine.

## Conséquences

- Les fiches et le brouillon de manifest du registre sont tous VALID (106 verdicts).
- Le Bootstrap s'appuie sur ce moteur via le registre ; son résultat est inchangé (empreinte identique).
