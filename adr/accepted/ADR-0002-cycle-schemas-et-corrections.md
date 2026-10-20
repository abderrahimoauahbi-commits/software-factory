# ADR-0002 — Cycle opérationnel, schémas exécutables et corrections du socle

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0002 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | Factory Owner, « ok » du 2026-10-15 appliqué aux options recommandées (APR-0001) |
| Rédaction | agent de construction (Claude Opus 5.5) — rédige, ne décide pas |
| Remplace en partie | ADR-0001 §1 (emplacement des brouillons de projet) |
| Traçabilité | K6 : EXC-0001 épuisée le 16/10/2026, remplacée par EXC-0003 (exception de construction bornée, attestée par la commande humaine HA-20261016T164016-06fa3814) ; à son gel, l'ADR-0017 (D37, mode construction) remplacera en partie K6 |

## Contexte

Trois documents normatifs sont arrivés après l'ADR-0001 : « Cycle opérationnel complet », « State Machines &
Contracts v1.0 » et « Executable Schemas v1.0 ». Leur comparaison avec le Playbook v3.2 a révélé des
contradictions (K1–K6, S1–S6) et des écarts du squelette (F-01–F-05). Le Factory Owner a validé les
propositions. Les Executable Schemas v1.0, arrivés en dernier, font foi là où ils tranchent.

## Décisions

### Cycle opérationnel

| Réf. | Problème | Décision |
|---|---|---|
| K1 | Numérotation des modes incohérente (M0–M16 contre M0–M19) | La liste `PHASES` des Executable Schemas §2 (20 phases) fait foi ; les numéros M ne servent plus |
| K2 | Place de la validation humaine | Deux niveaux : cycle du **besoin** et cycle du **ticket** (`READY_TO_MERGE → HUMAN_APPROVAL → MERGED`, Executable Schemas) |
| K3 | Revue C4 sans revue senior | Revue senior requise en C3 **et** C4 (Playbook §12.3) |
| K4 | « DB réel » non défini | Classement par **environnement** de chaque ressource (Executable Schemas `ENVIRONMENT`), pas par machine : une base locale peut être `PRODUCTION` |
| K5 | `BOOTSTRAP_BLOCKED` bloque tout | Prérequis **par phase** : une phase de lecture n'exige pas ceux de l'exécution |
| K6 | « L'agent ne modifie pas la Factory » contre construction de la Factory | La Factory est un projet (`registry/projects/software-factory`) ; l'agent n'y écrit que sous exception (EXC-0001), limitée, temporaire, auditée |

### Machines d'états et schémas

| Réf. | Problème | Décision |
|---|---|---|
| S1 | Une liste d'états commune ou une par type | Une machine **par type** (`core/schemas/lifecycles.yaml`), en tables de transitions |
| S2 | `AUTHORIZED_FOR_PROJECT` n'est pas un état global | La fiche MCP porte l'état global ; l'autorisation par projet a sa propre machine (`mcp_project_authorization`) |
| S3 | Boucle de correction absente (`CHANGES_REQUESTED`) | Portée par des **transitions** `revue/QA → IN_PROGRESS` (motif `changes_requested`), sans état nouveau |
| S4 | Modèle sans retrait | `RETIRED` (désormais dans les Executable Schemas) |
| S5 | Machine Factory linéaire | Issues alternatives de `CHECKING` ; `RECOVERY` ramène à `CHECKING` |
| S6 | Le Playbook parle de « worktree » et de « branche » | Ce sont des capacités (`ISOLATED_WORKSPACE`, `SOURCE_CONTROL`) ; à reformuler dans la prochaine version du Playbook (proposition, §15.4) |

### Corrections du squelette

| Réf. | Correction |
|---|---|
| F-01 | `pilot_project` retiré de `factory.yaml` : aucun projet n'y est nommé |
| F-02 | `runtime: python` remplacé par `critical_capabilities` ; Python et PyYAML sont des outils du registre |
| F-03 | Brouillons de projet déplacés vers `registry/projects/<id>/` ; `projects/` reste réservé (Playbook §16.1) |
| F-04 | Registres `capabilities` ajoutés ; adaptateurs déclarés par les fiches d'outils (`detection.adapter`) |
| F-05 | Bootstrap piloté par capacité → outil → adaptateur ; aucun nom d'outil dans son cœur |

## Extensions des Executable Schemas v1.0 (à ratifier dans la v1.1)

1. Énumérations `EVIDENCE_KIND` (VERIFIED, DECLARED, UNVERIFIABLE, HUMAN_REQUIRED) et `SEVERITY`
   (INFO à CRITICAL) : exigées par les instructions du Bootstrap CHECK.
2. Schémas `capability` et `adapter` : cités (§20, §21, §27) sans être définis.
3. Champs de l'étape 1 de l'instruction de construction absents du schéma `tool` : `owner`, `license`,
   `documentation`, `review_date`, `lifecycle_history`, plus `detection` (spécification de l'adaptateur).
4. `quality.gates` dans le manifest : la commande **déclarée** de chaque gate.
5. Cycle de vie des skills sans état d'entrée pour une skill **externe** : aucune skill n'est inscrite en v1 ;
   le Bootstrap signale les skills observées comme non enregistrées.

## Conséquences

- Le registre ne contient aucune version : le Bootstrap les détecte et les cite comme preuves.
- Les outils adoptés le 15/10/2026 sont `APPROVED` par transition `factory_owner_initial_adoption`, avec
  une évaluation formelle due (`evaluation.status: PENDING`).
- Aucun MCP, agent, modèle ni skill n'est actif.

## Risques

- Les extensions non ratifiées peuvent diverger de la v1.1 : elles sont listées ici pour faciliter la migration.
- L'adoption initiale sans Lab des outils de base est un écart assumé de la phase 1 (Playbook §17).
