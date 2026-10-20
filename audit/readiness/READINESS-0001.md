# READINESS-0001 — Audit de préparation de la Factory

| Champ | Valeur |
|---|---|
| Date | 2026-10-15 |
| Jalon | J3a (plan révisé, ADR-0005) |
| Méthode | lecture seule ; chaque ligne s'appuie sur une preuve déjà produite (tests, CHECK, fichiers) |
| Légende | **OK** : prouvé · **WARN** : présent mais incomplet · **BLOCK** : manque qui interdit l'activation opérationnelle |

## Matrice

| Domaine | État | Problème | Preuve | Action (jalon) |
|---|---|---|---|---|
| Architecture | WARN | Cœur partagé en place ; Orchestrator, Ticket Factory, Quality Gate Manager absents | `core/README.md`, ADR-0003 | normal en phase 1 (Playbook §17) |
| Schémas et validation | OK | — | 50 tests verts ; 106 verdicts VALID | ratifier les extensions (ADR-0002, 0004, 0005) en v1.1 |
| Registre | WARN | Registres `plugins`, `prompts`, `executions`, `permissions` absents (Master §4.3) | `registry/README.md` | J5 (executions), J6 (prompts, plugins) |
| Contradictions normatives | WARN | Master ↔ Executable Schemas (M1, M2) tranchées ; textes normatifs absents du dépôt (M4) | ADR-0005 | dépôt des documents (humain) |
| Permissions de l'agent de construction | WARN | Écriture limitée à FACTORY_ROOT par EXC-0001 ; aucune garde technique ne l'impose | `policies/exceptions/EXC-0001.yaml` | J4 (Policy Engine) + garde de l'agent (étape VS Code/agent) |
| Policy Engine | BLOCK | Politiques écrites, aucune évaluation exécutable | `policies/` | **J4** |
| Identité et confiance | BLOCK | Acteurs non modélisés ; l'humain n'est identifié que par déclaration | — | **J3c** (ce jalon) |
| Modèle de données | BLOCK | Objets définis, relations non définies | `core/schemas/objects/` | **J3c** (ce jalon) |
| Modèle de menaces | BLOCK | Menaces listées (Playbook §10.1) sans chaîne ni contrôle par étape | — | **J3b** (ce jalon) |
| Agents | BLOCK | 15 rôles DISCOVERED, aucun évalué ni habilité | `registry/agents/` | phase 2 (Playbook §12.6) |
| MCP | BLOCK | 7 MCP actifs non approuvés, 4 d'activation inconnue | rapport CHECK du 15/10/2026 | décision humaine (configuration hors Factory) |
| Sécurité du poste de l'agent | BLOCK | 0 règle de refus ; production non protégée ; contournement des permissions non interdit | rapport CHECK | décision humaine + J4 |
| Secrets | WARN | Aucun secret dans la Factory (test) ; secrets du projet pilote présents hors Git, lisibles par l'agent | rapport CHECK (X-IGNORED) | règles de refus (humain) |
| Bootstrap | OK | CHECK testé, lecture seule prouvée | 2 tests de bout en bout | J7 : `AGENT_CONTEXT.md`, `WORKTREE_ROOT`, vocabulaire §56 |
| Audit | WARN | Journal en ajout seul écrit par scripts ; immuabilité non vérifiée | `audit/events.jsonl` | J5 |
| Preuves | WARN | Preuves de commandes du Bootstrap seulement | `bootstrap/check/rapport.py` | J5 |
| Portes humaines | WARN | Fiches HG/APR ; aucun moteur | `audit/` | J5 |
| CI/CD | BLOCK | Aucune CI ; Quality Gates déclarés non exécutés | rapport CHECK (Q-CI) | phase 1 (Playbook §17) — à planifier après J6 |
| Reprise après sinistre | **BLOCK** | **Aucun commit, aucune copie : la Factory n'existe qu'en un exemplaire** | `git log` → aucun commit | **D2 humain**, puis J8 |
| Multi-projets | WARN | Un projet réel + un manifest fictif de test | `core/tests/fixtures/` | J10 |
| Observabilité | BLOCK | Absente | — | phase 4 |
| Budgets / FinOps | BLOCK | Aucun budget défini (règle absolue 21) | manifest pilote : `WAITING_HUMAN` | décision humaine |

## Verdict

**NOT READY** pour une activation opérationnelle (exécution d'agents sur un projet) ; **READY** pour
poursuivre la construction en lecture et conception (J3), puis le Policy Engine (J4).

Le risque le plus urgent n'est pas technique : c'est l'absence de toute sauvegarde de la Factory (D2).
