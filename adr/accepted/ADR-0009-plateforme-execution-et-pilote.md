# ADR-0009 — Plateforme d'exécution v1, correction de généricité, préalables du ticket pilote

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0009 |
| Statut | accepté pour la plateforme (« valide et continue », 15/10/2026) ; **contradiction C-17 en attente** |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Rédaction | agent de construction (Claude Opus 5.5) |

## Constat de phase

Le critère de passage de la phase 1 (Playbook §17) — « un projet pilote livre 10 tickets C1/C2 avec audit complet,
sans incident de sécurité » — **n'est pas atteint** : aucun ticket pilote n'a été exécuté. §17.2 règle 1 interdit de
démarrer la phase 2. La suite est donc la pièce manquante de la phase 1 : la plateforme d'exécution minimale.

## Décisions (J13)

1. **Plateforme d'exécution v1** (`core/noyau/execution.py`, `policies/execution.yaml`) : action `run_ticket` du
   Policy Engine → AUTHORIZED (≤ 3 tentatives) → RESERVED → espace isolé + branche `factory/<ticket>/<exécution>`
   hors de tout dépôt → PREPARED → enveloppe de contexte → RUNNING ; clôture : diff réel **comparé au périmètre du
   ticket et aux chemins d'écriture du projet** (débordement = `SCOPE_VIOLATION`, échec), gates du manifest
   exécutés dans l'espace isolé avec preuves réelles, provenance complète, enregistrement en écriture exclusive.
2. La plateforme ne supprime, ne pousse, ne fusionne rien ; elle n'exécute que ses opérations déclarées et les
   gates du manifest.
3. **Généricité corrigée** : les opérations de l'espace isolé sont des gabarits de la politique ; l'option
   « répertoire » d'un exécutable vient de la politique (`directory_options`) ; l'inventaire des fichiers passe par
   l'adaptateur de la capacité SOURCE_CONTROL. Le test de généricité interdit désormais aussi le nom de l'outil de
   contrôle de version dans le cœur (il avait laissé passer deux écarts depuis J1).

## Contradiction à trancher (C-17)

Le Playbook exige à la fois : (a) en phase 1, des tickets exécutés par des **agents** sur le projet pilote ;
(b) règle 19 et §12.6, qu'**aucun agent** ne soit habilité sans évaluation réussie — l'évaluation étant en phase 2.
Options : (1) habilitation **provisoire** d'un agent limitée à C1, décidée par le Factory Owner, auditée, avec
revue humaine de chaque ticket ; (2) avancer une évaluation minimale du rôle avant le pilote ; (3) exécuter les
10 tickets pilotes par l'humain, l'agent ne faisant que proposer. **Décision humaine requise.**

## Préalables du premier ticket pilote (aucun n'est du ressort de l'agent)

1. Décision C-17.
2. Manifest `factory.yaml` et `AGENT_CONTEXT.md` copiés dans le dépôt du projet pilote ; `paths` validés
   (aujourd'hui `PROPOSED`).
3. Emplacement des espaces isolés (`workspaces_root`) confirmé.
4. Autorisation de créer un espace isolé et une branche dans le dépôt du projet pilote (modification de ses
   métadonnées de contrôle de version).
5. Choix d'un premier ticket C1, sans base de données ni production.
