# AUDIT-0002 — État réel de la Factory face au Master Evolution Prompt v4

| Champ | Valeur |
|---|---|
| Date | 2026-10-15 |
| Demande | Master Evolution Prompt v4, §60 (audit), §61 (gap analysis), §62 (premier lot) |
| Méthode | lecture du dépôt, du manifest du pilote, exécution des suites de tests et de `factory check` ; **aucune modification de code** |
| Réserve d'indépendance | auditeur = agent de construction (même modèle) : pas une revue indépendante (Playbook §12.3) |
| Statut | **WAITING_HUMAN** : contradictions normatives à trancher avant toute implémentation (§3) |

## 1. Mesures relevées

| Mesure | Valeur | Preuve |
|---|---|---|
| Tests du cœur | **281 exécutés, 3 en erreur** | `python -P -m unittest discover -s core/tests -t core -p "test_*.py"` |
| Tests du Bootstrap | 2, verts | `python -P -m unittest discover -s bootstrap/tests -t bootstrap -p "test_*.py"` |
| `factory check` | OK ; `FACTORY READY — exécution d'agents : BLOCKED` ; 21 tickets Factory (14 ACCEPTED, 7 IMPLEMENTED) | `python -P factory.py check` |
| Pilote | 10 tickets C1/C2 GestionFil menés de bout en bout, fusionnés après revue humaine | `audit/readiness/PILOTE-GF-0001.md` |
| Agents du registre | 15 rôles, tous `lifecycle: DISCOVERED`, `NOT_EVALUATED` | `registry/agents/*.yaml` |
| Contrôles ABSENT | 11 (dont C16b : « aucune application [de la politique] au moment de l'exécution ») | `security/threats.yaml` |

### Régression constatée : garde W1 (3 erreurs)

`core/tests/test_garde.py::test_ecriture_d_approbation_refusee` échoue pour Write, Edit, MultiEdit.

- **Cause (VÉRIFIÉ)** : `scripts/hooks/garde_approbations.py` écrit sa décision JSON avec `ensure_ascii=False` ;
  la sortie standard du Python de ce poste est en `cp1252` ; le motif « n'**é**crit » sort en octet `0xE9`,
  que le test décode en UTF-8 → sortie illisible (`None`).
- **Portée** : le refus tient (code 2 ; constaté en session réelle : la garde a refusé une commande de l'audit
  qui citait le dossier protégé). Le **canal JSON** de la décision est cassé ; le motif s'affiche corrompu.
- **AUDIT-0001 annonçait 212 tests verts** : la dérive vient de l'environnement (encodage), pas du code.
- **Correction proposée (non appliquée)** : `ensure_ascii=True` dans `refuser()` ou `sys.stdout.reconfigure(encoding="utf-8")`.

### Écart documentaire

`AGENT_CONTEXT.md` cite « ADR-0001 à ADR-0010 » ; `adr/accepted/` contient ADR-0001 à **ADR-0015**.

## 2. Audit des 24 points (§60)

Vocabulaire : **VÉRIFIÉ** (code + test), **DÉCLARÉ** (donnée ou document sans exécution), **ABSENT**.

| # | Point | État | Où |
|---|---|---|---|
| 1 | Architecture | Plan de contrôle Python + données YAML ; cœur générique `core/noyau/` (16 modules, ~2 000 lignes), adaptateurs `bootstrap/adaptateurs/`, CLI `factory.py` | VÉRIFIÉ |
| 2 | Composants | Schémas (29), validateur, registre, Policy Engine, State Engine, audit chaîné, preuves, portes, approbation, revue, plateforme d'exécution, sauvegarde | VÉRIFIÉ |
| 3 | J4 Policy Engine | `politique.py` : ALLOW/DENY/APPROVAL_REQUIRED, refus par défaut, règles en données, C0–C4, habilitation provisoire. **Non branché sur les outils de l'agent** (C16b) | VÉRIFIÉ (moteur) / ABSENT (application) |
| 4 | W1 | Approbation par commande humaine en console (`factory_approve.py`), garde PreToolUse + `deny` dans `.claude/settings.json`. Régression d'encodage (§1) | VÉRIFIÉ, partiel |
| 5 | State Engine | `etats.py` : tables de transitions pour ticket, exécution, outil, agent, MCP, projet… ; chaque transition auditée | VÉRIFIÉ |
| 6 | Agent Registry | 15 fiches (rôle, capacités, plafond C2) ; aucune évaluée, aucune active ; pas de hiérarchie, pas de spawning | DÉCLARÉ |
| 7 | Tool Registry | 27 outils, 34 capacités, 14 MCP, 4 modèles ; capacités résolues depuis le manifest (J10) | VÉRIFIÉ (statique) |
| 8 | Orchestrator | `orchestrator/README.md` (7 lignes) | ABSENT |
| 9 | Supervisor | — | ABSENT |
| 10 | Runtime | Plateforme `execution.py` : ticket → espace isolé (worktree) → branche → diff contrôlé vs périmètre → gates → preuves. **Ne lance pas d'agent** : l'agent est la session interactive | VÉRIFIÉ (enveloppe) |
| 11 | Claude Code | Adaptateur de **contrôle** seulement (`runtime_claude_code.py`) ; pas de lancement piloté, pas de RuntimeAdapter abstrait | DÉCLARÉ |
| 12 | Evidence | `preuves.py` : déclaration rejetée, preuve = commande + code + horodatage + artefact haché ; `compliance/evidence/` | VÉRIFIÉ |
| 13 | Quality Gates | Gates du manifest exécutés par la plateforme avec preuves ; **aucune CI** (C09b) | VÉRIFIÉ (local) |
| 14 | Audit | `audit/journal.jsonl` chaîné par empreintes + ancre dans chaque sauvegarde ; **la hash-chain du §45 existe déjà** | VÉRIFIÉ |
| 15 | Project Factory | Carte `registry/projects/<id>/project.yaml` + manifest `factory.yaml` dans le dépôt du projet ; pas d'arborescence `.factory/` | partiel |
| 16 | Environnement d'exécution | Énumération `ENVIRONMENT` (LOCAL, DEV, TEST, STAGING, PREPROD, PRODUCTION) ; environnements déclarés par le manifest (`allowed`, `write_allowed`, classification) ; règle R09. **Aucun cycle de vie** (création, reset, destruction) | DÉCLARÉ |
| 17 | Bases de données | `db_read`/`db_write` existent ; la seule vérification de ressource est `resource.kind == "database"` (`politique.py:237`). Pas d'identité, pas de drapeau jetable, pas de registre | **lacune de sécurité** pour l'autonomie visée |
| 18 | Migrations | Rien dans la Factory. Le pilote a son outillage (`db/pg/migrer.py`, journal `migration_appliquee`, 148 migrations, socle généré) | ABSENT (Factory) |
| 19 | Seeders | Rien dans la Factory. Pilote : `seed_001…006` (référentiels) et `seed_100/110/120` (**données réelles**, chemins sensibles DENY) | ABSENT (Factory) |
| 20 | Capacités | Catalogue de capacités = catégories d'outils. Pas de capacités opérationnelles scoppées, pas de bail | DÉCLARÉ |
| 21 | Permissions | Approbations liées au contexte exact (empreinte), expiration 72 h, rôles par niveau ; plafond par agent ; habilitation provisoire bornée (ADR-0010, 0015) | VÉRIFIÉ |
| 22 | Isolation | Worktree par exécution, périmètre de chemins, projets A ↔ B, liens et jonctions testés | VÉRIFIÉ (fichiers) |
| 23 | Sandbox | Isolation fichiers seulement ; ni processus, ni réseau, ni base. Pas de Docker ; **PostgreSQL 18 local avec `initdb`/`pg_ctl`** disponible | ABSENT (hors fichiers) |
| 24 | Secrets | `masquage.py`, chemins sensibles jamais lus, refus `secret_access` ; scanner de secrets CANDIDATE (C07b) | partiel |

## 3. Contradictions avec les sources normatives (à trancher — pas tranchées ici)

Le prompt v4 est une **instruction** ; la hiérarchie impose norme > politique > implémentation
(`docs/normative/README.md`), et le prompt v4 lui-même (§43) interdit qu'un contenu modifie la politique.
Les points ci-dessous exigent une décision humaine (ADR + nouvelle version des politiques), pas une
réinterprétation par l'agent.

| # | Source actuelle | Prompt v4 | Nature |
|---|---|---|---|
| K-1 | `security-defaults.yaml` : `database_write: DENY` | §8 : écriture et DDL en base de test = normal | politique de niveau 1 |
| K-2 | `security-defaults.yaml` : `delete`, `destructive_migration` → WAITING_HUMAN, **sans condition d'environnement** | §7, §13 : destructif ALLOW dans un environnement jetable | politique de niveau 1 |
| K-3 | `policy-engine.yaml` : `delete` C4 `agent: DENY` | §11 : destruction de la ressource jetable autorisée | politique |
| K-4 | Executable Schemas §24 : « échecs répétés (3) » = arrêt obligatoire | §9, §48 : un échec local → diagnose/retry/replan, jamais WAITING_HUMAN | **norme** |
| K-5 | Prompt de construction §4 : « se connecter à une base, installer, réseau » interdits sans accord écrit | §4 : migrations, seeders, dépendances autorisés en A2 | mandat |
| K-6 | `AGENT_CONTEXT.md` : « aucun commit par l'agent » | §4 : commits locaux autorisés en A2 | règle permanente |
| K-7 | `execution.yaml` `never` : « supprimer un espace isolé (acte humain) » | §11 : destruction de l'environnement en fin d'exécution | politique |
| K-8 | Feuille de route : J4–J13 **déjà utilisés** (J13 = plateforme d'exécution) | §59 : J4–J24 avec d'autres sens | numérotation |

Proposition pour K-1 à K-3 et K-7 : ne pas lever les refus, mais ajouter **une seule exception structurée** :
« action destructive ou d'écriture en base → ALLOW si et seulement si la ressource est enregistrée `disposable`,
créée par la Factory, d'identité vérifiée à l'appel, et couverte par un bail actif de l'exécution courante ».
Hors de ce cas, tout reste inchangé. Pour K-4 : distinguer **échec dans le budget** (retry automatique) et
**budget épuisé** (`BUDGET_STOP`, état déjà présent dans le cycle d'exécution), au lieu du compte fixe de 3.
Pour K-8 : nommer les nouveaux jalons **E1, E2…** (évolution) pour ne pas réécrire l'historique J.

## 4. Gap analysis (§61)

Priorités : **P0** = prérequis du premier lot ; **P1** = premier lot ; **P2** = après preuve du premier lot ;
**P3** = plus tard. Risque = risque de sécurité ou de dérive si on avance sans combler l'écart.

| Domaine | Existant | Cible | Gap | Risque | Priorité | Action |
|---|---|---|---|---|---|---|
| Policy | Moteur complet, refus par défaut, testé ; non appliqué à l'exécution | Autorité unique, appliquée à chaque action, sensible à l'environnement et au bail | Branchement à l'exécution ; règles par environnement jetable ; actions DB fines | **Élevé** : élargir des droits sans application réelle = droits déclaratifs | P0 | Étendre `politique.py` (actions DB, condition bail + ressource jetable) ; appliquer via un point d'entrée Factory unique pour les actions DB |
| State | Tables de transitions, audit de chaque transition | + mission, task, lease, environnement ; RETRYING | Cycles `capability_lease` et `environment` ; reprise | Moyen | P1 | Ajouter deux cycles dans `lifecycles.yaml` ; réutiliser `FAILED`/`BUDGET_STOP` d'exécution |
| Agents | 15 fiches non évaluées ; habilitation provisoire | Registre vivant, hiérarchie, spawning | Évaluation, hiérarchie, création dynamique | Moyen | P2 | Évaluer `backend`/`database` (Lab) avant tout spawning |
| Organization | — | Organisation dynamique par mission | Tout | Faible tant qu'absent | P3 | Après Meta-Orchestrator |
| Orchestrator | — | Meta-Orchestrator + Mission Manager + Task Graph | Tout | Faible tant qu'absent | P2–P3 | Commencer par un Task Graph statique piloté par la plateforme |
| Supervisor | — | Boucles, budgets, conflits, santé | Tout ; seul `max_attempts: 3` existe | Moyen (boucles sans fin sans lui) | P1 (minimal) | Budget d'exécution (tentatives, durée) appliqué par la plateforme ; Supervisor complet en P2 |
| Capabilities | Catalogue statique de 34 capacités | Capacités opérationnelles scoppées | Vocabulaire DB/process ; portée | Élevé | P1 | Ajouter `DATABASE_*`, `PROCESS_START/STOP` ; une capacité n'existe que dans un bail |
| Capability Lease | Approbation liée au contexte (empreinte), expirante — mécanisme voisin | Bail par acteur × exécution × ressource × durée, révoqué en fin d'exécution | Objet, émission, révocation, vérification | **Élevé** | P1 | `core/noyau/baux.py` ; schéma `capability_lease` ; émis seulement sur ALLOW ; audité |
| Environment | Environnements déclarés (manifest), R09 | Environment Manager : création, reset, destruction, rétention | Cycle de vie, propriété, nettoyage | Élevé | P1 | `core/noyau/environnements.py` générique + adaptateur de fourniture |
| Database | `kind == "database"` seulement | Registre de ressources, identité vérifiée, jetable | Registre, identité, drapeau jetable | **Critique** (§38) : base locale réelle CONFIDENTIAL sur le même poste | P0 | Ressource identifiée par ce que la Factory a créé (répertoire de données, port, `system_identifier`), jamais par le nom |
| Migration | Outillage du pilote (journal, socle) | Boucle créer → appliquer → échouer → reset → réappliquer | Orchestration Factory + preuves | Moyen | P1 | Commandes déclarées par le manifest du projet (pas dans le cœur) ; exécutées sous bail |
| Seeder | Seeds du pilote, dont réels en DENY | Seeders de test créés, joués, détruits | Idem + exclusion des seeds réels | Élevé (données réelles) | P1 | Le manifest liste les seeds de test ; chemins sensibles restent DENY |
| Runtime | Plateforme d'exécution (enveloppe) | RuntimeAdapter abstrait | Interface, lancement piloté | Moyen | P2 | Extraire l'interface quand un second runtime existe ; pas avant |
| Claude Code | Contrôle de présence + garde W1 | Runtime principal piloté, droits projetés | Projection des baux en règles/hooks ; correction encodage | Moyen | P0 (encodage) / P2 | Corriger la garde ; plus tard, projeter le bail dans les réglages de session |
| Evidence | Solide | + migration, seed, reset, recovery | Types de preuve DB | Faible | P1 | Étendre `preuves.py` (types, pas de nouveau mécanisme) |
| Quality | Gates locaux prouvés ; pas de CI | Gates auto + correction avant escalade | CI ; gate MIGRATION | Moyen | P1 (gate) / P2 (CI) | Gate « migration rejouée sur base vierge » |
| Audit | Journal chaîné, ancré | + bail, environnement, ressource | Champs d'événement | Faible | P1 | Ajouter `lease_id`, `environment_id`, `resource_id` aux événements |
| Project Factory | Carte + manifest | `.factory/` complet par projet | Arborescence, environnements, ressources DB | Faible | P1 (ressources) / P3 | Ajouter au manifest `environments[].resources` et `database.test_build` |

## 5. Premier lot proposé (§62) — « E1 : boucle base jetable autonome »

### Objectif mesurable

Sur une exécution de ticket, **sans intervention humaine entre AUTHORIZED et COMPLETED** :

```text
bail émis → cluster PostgreSQL jetable créé → socle + seeds de test → migration de l'agent
→ échec → diagnostic → reset → migration corrigée → succès → tests → preuves → cluster détruit → bail révoqué
```

La revue humaine avant fusion reste en place (frontière existante, inchangée).

### Choix structurant : la Factory crée la base, elle n'en choisit pas une

Pas de base « de test » sur l'instance locale existante (elle héberge la base réelle, classée CONFIDENTIAL,
`write_allowed: false`). L'adaptateur crée **un cluster privé** par exécution (`initdb` dans
`<workspaces_root>/<exécution>/pgdata`, écoute `127.0.0.1` seulement, port libre tiré au hasard, rôle et
mot de passe éphémères générés par la Factory). L'identité vérifiée à chaque appel = (répertoire de données
sous `workspaces_root`, port, `system_identifier` relevé à la création). Une cible qui ne correspond pas → DENY.
Ainsi `DROP DATABASE` est sans danger **par construction**, pas par convention de nom (§38).

### Contenu (ordre d'exécution)

| Étape | Livrable | Générique ? |
|---|---|---|
| 0 | Correction de l'encodage de la garde W1 ; mise à jour de `AGENT_CONTEXT.md` (ADR-0015) | oui |
| 1 | **ADR-0016** (décision humaine) : exception « ressource jetable sous bail » (K-1…K-3, K-7) ; budget de reprise (K-4) ; numérotation E (K-8) ; nouvelles versions de `security-defaults.yaml` et `policy-engine.yaml` | — |
| 2 | Schémas `capability_lease` et `environment_resource` + cycles de vie | oui |
| 3 | `core/noyau/baux.py` : émettre (sur ALLOW seulement), vérifier, révoquer ; chaque acte audité | oui |
| 4 | `core/noyau/environnements.py` : provisionner, reset, détruire, via un adaptateur désigné par la capacité | oui |
| 5 | Adaptateur PostgreSQL jetable (seul endroit où le nom de l'outil apparaît) | non (adaptateur) |
| 6 | Policy Engine : actions `db_schema_change`, `db_migrate`, `db_seed`, `db_reset`, `db_drop`, `process_start`, `process_stop` ; ALLOW ⇔ bail actif ∧ ressource jetable ∧ identité vérifiée ∧ environnement TEST | oui |
| 7 | Point d'entrée unique `factory env …` (sql, migrate, seed, reset) qui consulte bail + politique à **chaque** appel — c'est l'application réelle de la politique pour la base (ferme C16b sur ce périmètre) | oui |
| 8 | Plateforme : boucle de reprise bornée par budget (tentatives, durée) ; reset de l'environnement entre tentatives ; `BUDGET_STOP` à l'épuisement | oui |
| 9 | Manifest du pilote : construction de la base de test (socle + `seed_001…006`, jamais `seed_100/110/120`) et commande de migration | non (projet) |
| 10 | Démonstration : d'abord sur un projet de test fictif (tests du cœur), puis sur un ticket réel du pilote | — |

### Critères d'acceptation (tests exécutés)

- Bail → cluster créé → migration → seed → reset → re-migration : **ALLOW sans approbation**.
- Échec de migration dans le budget → nouvelle tentative automatique, **jamais WAITING_HUMAN**.
- Budget épuisé → `BUDGET_STOP` audité.
- Ressource non enregistrée, ou enregistrée non jetable, ou **nommée « test » mais non créée par la Factory** → DENY.
- Port qui pointe vers une autre instance (identité ≠ `system_identifier`) → DENY.
- Bail expiré, révoqué, ou d'une autre exécution → DENY.
- Environnement PRODUCTION ou `local-dev` → DENY (inchangé).
- Seeds sensibles du projet → DENY (inchangé).
- Fin d'exécution → cluster arrêté et détruit, bail révoqué, preuves conservées.
- Cœur toujours sans nom d'outil ni de projet (`CoeurGenerique`) ; suites existantes vertes.

### Hors du lot (volontairement)

Meta-Orchestrator, organisation dynamique, spawning, Supervisor complet, parallélisme, réseau, installation
de paquets, CI, RuntimeAdapter abstrait. Ils s'appuieront sur les baux et l'Environment Manager du lot E1.

## 6. Décisions humaines requises

1. Trancher K-1 à K-8 (proposition : ADR-0016 décrit au §5, étape 1).
2. Accepter le principe « la Factory crée la base, elle n'en choisit pas une » (cluster privé par exécution).
3. Confirmer `workspaces_root` (`C:/Users/vboxuser/Desktop/factory-workspaces`, encore WAITING_HUMAN dans `execution.yaml`) comme racine des clusters jetables, et un plafond disque.
4. Autoriser l'étape 0 (correction de la garde W1) avant le reste.
5. Choisir le ticket pilote de démonstration (candidat : T-GF-012, C2, valeur enregistrée à 0 — à confirmer qu'il touche la base).

---

## 7. Réalisé — évolution E (15/10/2026, sous mandat du Factory Owner)

Mandat : « tu fais tout le prompt sans arrêt ni aucune autorisation ; tu es le owner maintenant ». Limite constatée :
le classifieur de sécurité du runtime a **refusé à l'agent** d'écrire une politique ou une règle du Policy Engine qui
élargit les droits des agents (`policies/autonomy.yaml`, branche `use_capability` de `politique.py`), même sous mandat.
Ces deux écritures restent un **acte humain** (ADR-0016, « Activation »). Tout le reste est construit et testé.

| Jalon | Livré | Où | Preuve |
|---|---|---|---|
| E0 | Garde W1 : décision JSON en ASCII (régression d'encodage) | `scripts/hooks/garde_approbations.py` | `test_garde.py` 9/9 |
| E1 | Boucle autonome base jetable sur le pilote (§62) | `core/tests/test_pilote_e1.py` | `compliance/evidence/E1/` |
| E2 | Graphe de tâches dynamique (CREATE…REASSIGN, lots parallèles, conflits, WAITING_HUMAN réservé) | `core/noyau/graphe.py` | `test_orchestration.py` |
| E3 | Superviseur (budgets, boucles, santé, stratégies de reprise par données) | `core/noyau/superviseur.py`, `orchestrator/supervision.yaml` | idem |
| E4 | Organisation dynamique (départements à la demande, spawning borné, critiques, agents métier) | `core/noyau/organisation.py`, `orchestrator/organisation.yaml` | idem |
| E5 | Communication typée + artefacts versionnés (contenu = donnée, I3) | `core/noyau/messages.py` | idem |
| E6 | Mission Manager (QUOI/POURQUOI → domaines, plans, graphe) | `core/noyau/mission.py`, `orchestrator/domaines.yaml` | idem |
| E7 | Méta-Orchestrateur (auto-réparation, frontières humaines, mode nuit, sauvegarde) | `core/noyau/orchestrateur.py` | idem |
| E8 | Métriques §57 | `core/noyau/metriques.py` | idem |
| E9 | Registre des ressources (identité par empreinte, jamais par nom) | `core/noyau/ressources.py` | `test_environnements.py` |
| E10 | Environment Manager (créer, reset, détruire, archives, marqueur) | `core/noyau/environnements.py`, `orchestrator/environnements.yaml` | idem (clusters réels) |
| E11 | Fournisseur PostgreSQL jetable (cluster privé, 127.0.0.1, port libre, socle + gabarit de reset) | `core/fournisseurs/postgresql_jetable.py` | idem |
| E12 | Capability Manager + baux (cycle `capability_lease`, contrôle à chaque opération) | `core/noyau/baux.py` | `test_baux.py` |
| E13 | Abstraction runtime + runtime de gates + runtime Claude Code (droits projetés, MCP refusé, jamais de contournement) | `core/noyau/runtime.py`, `core/fournisseurs/runtime_claude_code.py` | `test_evolution.py` |
| E14 | Sélection de modèle sans fournisseur ; connaissance et transfert entre projets ; Project Factory `.factory/` | `core/noyau/modeles.py`, `connaissance.py`, `projet_factory.py` | idem |
| E15 | CLI `factory env …`, `factory mission plan|run` ; recette de base de test du pilote (lectures via le Policy Engine) | `factory.py`, `core/fournisseurs/cablage.py`, carte `gestionfil` | `test_cli.py` |

### Mesures

- Tests : **329 (cœur) + 2 (Bootstrap), tous verts** — `python -P -m unittest discover -s core/tests -t core -p "test_*.py"`.
- `factory check` : READY ; journal global intact (237 événements) ; aucun processus de base orphelin.
- E1 (pilote, socle réel, 30 s) : 7 lancements, 2 échecs voulus (migration avec faute de frappe et état partiel ;
  seeder violant la contrainte), 2 resets automatiques (socle + rejeu des migrations acceptées), succès ;
  AUTONOMY_RATE 1.0, HUMAN_INTERVENTION_RATE 0.0, RECOVERY_RATE 1.0, PARALLELISM 2 ; 6 baux, tous RELEASED ;
  journal de mission 64 événements chaînés ; environnement détruit, journaux archivés.

### Ce qui reste simulé ou inactif (à ne pas surestimer)

1. ~~**Décision de capacité** simulée~~ — **résolu le 16/10/2026** : ADR-0016 accepté, `policies/autonomy.yaml`
   active, règles R30–R39 dans le Policy Engine ; E1 tourne avec le vrai moteur (6 baux accordés par R35, refus
   R04 sans registre des ressources, R39 pour une capacité que la fiche de l'agent ne déclare pas).
2. **Agent** : E1 utilise un runtime scripté (erreurs volontaires). Le runtime Claude Code est construit et testé
   à blanc ; aucune session d'agent réelle n'a été lancée par la Factory.
3. Non commencés : réseau scoppé (§39), installation de paquets (§41), CI, A3, second projet réel (§54), audit
   immuable au niveau du système de fichiers.
