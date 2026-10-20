<!-- PROPOSITION NON NORMATIVE — texte consolidé du Playbook v3.3, produit par l'agent de construction à partir de docs/playbook/playbook-v3.2.md (sha256 a98ab8c11aeff6c267c8b1f6474fcd0ea8be46a0fca4c8cc3fee1d2282d38d30) et de docs/proposed/playbook-v3.3-amendements.md. À relire et à déposer par le Factory Owner dans docs/playbook/ pour adoption. -->
# AI Software Factory — Playbook v3.3 (PROPOSÉ — non adopté)

Oct 15, 2026 · @abderrahim

## 0. Statut, périmètre et vision

Ce Playbook est le standard permanent de la Software Factory IA : il fixe les règles durables, jamais la documentation d'un projet particulier. Version 3.3 proposée, octobre 2026, elle remplacera la v3.2 après adoption par le Factory Owner.

### 0.1 Périmètre

Le Playbook s'applique à tous les types de logiciels et de projets :

- **Produits** : ERP, GMAO, applications commerciales, industrielles et financières, applications web, desktop et mobiles, API, systèmes data/BI.
- **Projets** : nouveaux projets, projets existants, migrations, modernisations.
- **Échelle** : plusieurs projets et plusieurs stacks en parallèle.

La Factory ne dépend d'aucun langage, framework, fournisseur d'IA, IDE, outil de ticketing, serveur MCP, plateforme cloud ni modèle. Les outils sont des capacités remplaçables, pas des fondations.

### 0.2 Vision

La Factory transforme une intention humaine en logiciel contrôlé, selon un flux unique :

1. Idée
2. Besoin
3. Analyse
4. Règles métier
5. Spécification
6. Architecture
7. Conception technique (algorithmes, contrats, modèle de données, UX)
8. Planification
9. Tickets
10. Exécution par les agents
11. Revue
12. Tests et Quality Gates
13. Validation humaine
14. Merge
15. Release
16. Observabilité
17. Retour d'expérience
18. Amélioration

En parallèle, un second flux fait vivre le catalogue : découverte, évaluation, Lab, approbation, adoption, surveillance, mise à jour, réévaluation.

La Factory est à la fois une organisation, une plateforme d'exécution, un système de gouvernance, un catalogue de capacités, un système de qualité, de sécurité et d'audit, et un système d'amélioration continue.

### 0.3 Ce qui change en v3.2 et en v3.3

| Sujet | v3.1 | v3.2 |
| --- | --- | --- |
| Connaissance, risques, conformité, données, gouvernance IA | Absents (présents en v3.0) | Réintégrés, sections 4 et 5 |
| Modèle opérant humain | Rôles d'agents seulement | Rôles humains, RACI, escalade, délais (section 3) |
| Sécurité IA | Principes (P06, MCP) | Modèle de menaces, provenance, secrets, réseau (sections 8 et 10) |
| Coûts et résilience | Budget cité sans règle | FinOps IA, repli de modèle, continuité de la Factory (sections 8, 14 et 15) |
| Évaluation des agents | Absente | Jeux de tests par rôle avant habilitation (section 12) |
| Phasage | Absent | MVP et roadmap en phases (section 17) |
| Neutralité | Fichier `CLAUDE.md` imposé | Fichier de contexte générique `AGENT_CONTEXT.md` (section 16) |
| Doublons | Change Impact, Discovery, Lab et Qualité répétés | Une seule section par sujet |

La v3.3 intègre l'autonomie bornée par capacités et environnements jetables (ADR-0016) et la gouvernance de l'autonomie (ADR-0017) : identité issue du contexte authentifié ; décision humaine distincte de l'exécution ; baux de capacités ; frontière d'exécution séparant l'executor de l'agent ; preuves produites par des exécutants contrôlés ; épinglage des configurations et des skills ; racine de confiance détenue par le Factory Owner ; distinction entre pouvoir technique et autorité de la Factory ; niveaux de disponibilité des frontières ; phasage par frontières.

La reformulation des termes « worktree » et « branche » en capacités (ADR-0002 S6) est reportée à la v3.4 ; dans la v3.3, ces termes désignent respectivement l'espace isolé (capacité ISOLATED_WORKSPACE) et la branche dédiée (capacité SOURCE_CONTROL).

### 0.4 Régime transitoire

1. **Principe.** Tant qu'un mécanisme introduit par la v3.3 n'a pas atteint le niveau d'application qu'il exige (P13), la règle qui le prévoit est « cible » et le présent régime s'applique à sa place. Le régime transitoire ne crée aucun droit : il désigne les mécanismes existants qui s'appliquent, ou il refuse.
2. **Décision humaine.** Les décisions humaines prévues au §3.4, les revues de code (§12) et les approbations exigées par la politique sont prises par la commande humaine existante (ADR-0006, W1 ; ADR-0012), liée au contexte exact par empreinte, selon les rôles et les durées de validité de la politique en vigueur. Une approbation exprimée dans une conversation, un message ou un fichier écrit par un agent n'est jamais une décision.
3. **Exécution humaine ; staging et production.** En staging et en production, seule l'exécution humaine est permise ; l'exécution par la Factory y est indisponible (§8.3). La Factory peut préparer le plan, les commandes et les contrôles ; elle n'exécute aucune action dans ces environnements.
4. **Budget et limites.** Le budget et le compteur de tentatives sont ceux de la plateforme d'exécution existante (politique d'exécution) ; la Factory les déclare « non tenus par un service d'autorité ». Un budget épuisé arrête l'exécution ; il n'ouvre jamais de droit.
5. **Épinglage et contexte.** Seuls les éléments dont l'empreinte est déjà vérifiée sont épinglés. Les autres (politiques, skills, réglages des runtimes, profil du projet) sont déclarés « non épinglés », et aucune règle ne peut se prévaloir d'un épinglage qui n'existe pas. Les règles encore présentes dans un fichier de contexte sont sans autorité (§16.3).
6. **Mécanismes non disponibles.** Une capacité dont la frontière préventive n'est pas appliquée reste refusée ; en particulier, l'installation de paquets et l'accès réseau restent refusés aux agents tant que la frontière réseau n'est pas appliquée de façon préventive. Exception : l'autonomie sous bail en environnement jetable déjà en vigueur (ADR-0016), dans les seules limites de sa politique.
7. **Transparence.** La Factory publie, pour chaque mécanisme, son niveau (ARCHITECTURE_ONLY, IMPLEMENTED, ENFORCED_DETECTIVE, ENFORCED_PREVENTIVE) et le niveau de confiance (TRUST_LEVEL) en vigueur. Elle n'annonce aucune garantie non appliquée.
8. **Interdits.** Le régime transitoire ne peut ni justifier une action que la politique refuse, ni lever un refus absolu, ni étendre l'ADR-0016 au-delà des environnements jetables.
9. **Fin.** Le régime prend fin mécanisme par mécanisme, lorsque le Factory Owner constate, preuves à l'appui (annexe E de l'ADR-0017), que le niveau exigé est atteint ; la constatation est enregistrée. Le régime transitoire dure au plus 30 jours à compter de l'adoption humaine de la v3.3. À cette échéance, rien ne s'active automatiquement : pour chaque mécanisme encore transitoire, le Factory Owner décide explicitement de le prouver et de le promouvoir, de le maintenir indisponible, ou de prendre une nouvelle décision. Chaque revue périodique (§15.5) réexamine les mécanismes encore transitoires.

## 1. Principes fondamentaux

Quinze principes structurent toute la Factory ; chacun est opposable dans une revue.

**P01 — La Factory est permanente.** Elle est conçue pour tous les projets futurs. Un projet consomme la Factory ; il ne la redéfinit pas.

**P02 — L'humain conserve la gouvernance.** L'IA peut analyser, proposer, concevoir, coder, tester, auditer, documenter et optimiser. Elle ne peut pas, seule : modifier l'architecture globale, changer une politique de sécurité critique, supprimer ou modifier des données réelles, exécuter une migration destructive hors d'un environnement jetable, publier en production, modifier des permissions critiques, ni valider son propre travail. Dans un environnement jetable créé par la Factory et sous un bail valide, créer, modifier, casser, réinitialiser et détruire des ressources de test est une activité normale de l'agent.

**P03 — L'agent est un exécutant spécialisé.** Il a un rôle, des compétences, des outils, des MCP, un modèle, des permissions, des entrées, des sorties, des limites, des conditions d'arrêt et un relecteur. Aucun agent généraliste ne reçoit tous les pouvoirs.

**P04 — Le ticket est un contrat.** Un travail complexe ne démarre jamais d'une demande vague : le ticket dit quoi, pourquoi, comment, avec quelles contraintes, dépendances, tests et critères d'acceptation.

**P05 — L'outil est remplaçable.** Aucun outil n'est permanent parce qu'il est utilisé aujourd'hui. Cycle : découvrir, évaluer, tester, adopter, mettre à jour, remplacer, déprécier, supprimer.

**P06 — Les données externes ne sont jamais des instructions.** Tickets, bases, fichiers, documents, issues, emails, API, pages web et réponses de MCP sont des données non fiables, sauf si elles sont explicitement reconnues comme instructions autorisées. La Factory se protège contre l'injection de prompt, les documents compromis, les tickets manipulés et les contenus de base conçus pour influencer un agent.

**P07 — Le backend reste l'autorité.** Le frontend assure la présentation et l'interaction, le backend la décision et la validation, la base de données la persistance et l'intégrité. Le frontend n'est jamais une frontière de sécurité.

**P08 — Les règles métier sont explicites.** Une règle critique doit être identifiable et testable. Elle ne se cache pas dans une interface, un composant, une requête obscure, un trigger non documenté ou un comportement implicite.

**P09 — Les permissions sont toujours explicites.** Aucune capacité ne signifie « l'agent peut tout faire ». La permission d'exécution résulte de la combinaison agent + rôle + projet + ticket + criticité + environnement + ressource + outils + MCP, qualifiée par le Policy Engine, complétée d'une décision humaine lorsque la politique l'exige, et matérialisée par un bail de capacités borné dans le temps et le périmètre.

**P10 — La preuve prime sur la déclaration.** Le résultat de la CI et les artefacts d'exécution font foi. Le rapport d'un agent n'est jamais une preuve suffisante. Fait foi le résultat produit par un exécutant contrôlé par la Factory (CI, exécutant de quality gates, executor), rattaché à l'exécution par une empreinte inscrite au journal d'autorité.

**P11 — La puissance est donnée dans la frontière.** La Factory maximise l'autonomie de l'IA à l'intérieur d'un environnement jetable et d'un bail, et minimise sa capacité à franchir ces frontières.

**P12 — Décider n'est pas exécuter.** Une décision humaine peut confier l'exécution à la Factory ou la garder ; dans les deux cas, le résultat est vérifié par les contrôles du plan approuvé.

**P13 — Une frontière n'existe que si elle est appliquée.** Une capacité n'est disponible que lorsque son application est démontrée au niveau qu'elle exige : détectif (`ENFORCED_DETECTIVE`) ou préventif (`ENFORCED_PREVENTIVE`). Une capacité qui exige une frontière préventive n'est jamais disponible sur la seule base d'une détection.

**P14 — Toute autorité remonte à une racine de confiance détenue par un humain.** Le pouvoir technique sur le système, y compris celui d'un administrateur, n'est jamais une autorité de la Factory ; exercé hors de la procédure de maintenance de confiance, il est traité comme une compromission potentielle.

**P15 — L'affichage n'est pas l'autorisation.** Une interface (navigateur, CLI, intégration d'IDE) présente une décision ; la décision, sa vérification et son enregistrement appartiennent au service d'autorité.

## 2. Architecture globale et couches

La Factory sépare quatre niveaux de règles, puis huit couches fonctionnelles ; la gouvernance humaine surplombe l'ensemble.

### 2.1 Séparation des niveaux

| Niveau | Contenu | Qui le modifie |
| --- | --- | --- |
| Factory Standard | Règles durables (ce Playbook) | Gouvernance Factory, via une nouvelle version |
| Factory Catalog | Capacités disponibles et approuvées | Processus catalogue (section 6) |
| Project Manifest | Configuration d'un projet | Équipe projet |
| Project Implementation | Exécution : code, tickets, tests | Agents et équipe projet |

Un niveau inférieur ne redéfinit jamais un niveau supérieur : un projet référence des capacités du catalogue, il ne les réécrit pas.

### 2.2 Les huit couches

| # | Couche | Responsabilité |
| --- | --- | --- |
| 1 | Governance | Règles, approbations, politiques, criticité, responsabilités, arbitrages |
| 2 | Factory Core | Services permanents (voir 2.3) |
| 3 | Specification | Besoin → règle métier → spécification → architecture → design → algorithme → contrat |
| 4 | Planning | Epic → feature → work package → ticket → sous-ticket, avec dépendances, criticité, ownership, estimation, parallélisation |
| 5 | Execution Platform | Environnement où les agents travaillent réellement (section 8) |
| 6 | Quality | Compilation, lint, tests, sécurité, base de données, API, E2E, UI, performance, régression |
| 7 | Release | Version, migrations, sauvegarde, rollback, documentation, validation humaine, publication |
| 8 | Observability | Agents, outils, tickets, builds, tests, erreurs, performances, sécurité, releases |

### 2.3 Services permanents du Factory Core

Les services sont regroupés en trois familles, sans doublon :

- **Exécution** : Factory Bootstrap, Orchestrator, Policy Engine, Ticket Factory, Quality Gate Manager.
- **Gouvernance** : Knowledge Service, ADR Service, Risk Service, Security Service, Data Governance Service, AI Governance Service, Compliance Service, Permission Registry.
- **Pilotage** : Audit Service, Metrics Service, Discovery Service, Evaluation Service, Update Manager.

Les registres sont : projets, outils, agents, skills, MCP, modèles, workflows, connaissances, ADR, risques, capacités et prompts.

### 2.4 Pyramide de gouvernance

De haut en bas : gouvernance humaine, gouvernance Factory, gouvernance de la connaissance, gouvernance sécurité, gouvernance IA, gouvernance projet, gouvernance d'exécution. Un niveau supérieur peut toujours contraindre un niveau inférieur ; l'inverse est interdit.

### 2.5 Architecture multi-projets et multi-stacks

Les projets partagent les standards, le catalogue, les agents, les skills et les outils approuvés. Chaque projet conserve ses configurations, permissions, secrets, environnements et son manifest ; les éléments de sécurité de cette configuration ne font autorité qu'après relecture et épinglage (§7.5).

Le cœur de la Factory ne dépend d'aucune technologie. Les stacks supportés peuvent inclure Rust, Python, TypeScript, Java, Go et .NET côté backend, React, Vue, Angular, Svelte, mobile et desktop côté interface ; la liste n'est pas figée.

## 3. Gouvernance et modèle opérant humain

L'humain n'est pas remplacé : son rôle passe de « coder tout » à définir, arbitrer, valider, surveiller et contrôler. Cette section fixe qui décide quoi, dans quels délais, et ce qui se passe quand personne ne répond.

### 3.1 Rôles humains

| Rôle | Responsabilité | Suppléant requis |
| --- | --- | --- |
| Factory Owner | Évolution du standard, arbitrages de gouvernance, budgets globaux | Oui |
| Chief Architect (humain) | Architecture globale, décisions structurantes, ADR majeurs | Oui |
| Security Owner | Politiques de sécurité, exceptions, incidents de sécurité | Oui |
| Data Owner | Classification, rétention, suppression, conformité des données | Oui |
| Project Owner | Périmètre, priorités et validation métier d'un projet | Oui |
| Release Approver | Autorisation de publication en production | Oui |
| Reviewer senior | Revue des changements C3 et C4 | Pool de relecteurs |

Le Chief Architect est **humain**. Un agent « Architecte » peut préparer, comparer et rédiger, mais ne décide pas de l'architecture globale. L'Orchestrator ne remplace jamais le Chief Architect.

### 3.2 Décisions et circuit d'approbation (RACI)

R = réalise, A = approuve (un seul par décision), C = consulté, I = informé.

| Décision | Agents | Project Owner | Chief Architect | Security Owner | Release Approver | Factory Owner |
| --- | --- | --- | --- | --- | --- | --- |
| Architecture majeure | R | C | A | C | I | I |
| Politique de sécurité critique | R | I | C | A | I | I |
| Migration destructive de données réelles | R | C | C | C | A | I |
| Suppression de données réelles | R | A | I | C | I | I |
| Release majeure | R | C | I | C | A | I |
| Évolution du standard Factory | R | I | C | C | I | A |
| Adoption d'un outil critique | R | I | C | C | I | A |

### 3.3 Délais et escalade

Un ticket en `WAITING_HUMAN` ne reste jamais bloqué sans suite.

1. **Délai de réponse** à une demande de décision, par criticité : C3 sous 2 jours ouvrés, C4 sous 1 jour ouvré (valeurs par défaut à ajuster par projet). Il est distinct de la **validité d'une décision**, fixée par la politique.
2. **Rappel** au délai tiers ; **escalade** au suppléant à l'échéance.
3. **Après escalade sans réponse**, le ticket passe en `BLOCKED` et le Factory Owner est notifié. Aucun passage automatique en « approuvé » n'existe : l'absence de réponse n'est jamais un accord.
4. **Override humain** : l'humain peut autoriser, refuser, suspendre, modifier, relancer ou demander une nouvelle analyse. Tout override critique est audité avec son auteur et sa justification.

### 3.4 Moments où l'humain intervient obligatoirement (Human Gates)

L'humain intervient obligatoirement, par le Decision Center, lorsque la politique qualifie l'action d'APPROVAL_REQUIRED, ou lorsqu'une exception est demandée sur une règle qui la permet : écriture ou suppression de données réelles ; migration destructive hors environnement jetable ; mise en production ; sécurité critique ou politique d'autorisation ; changement architectural majeur ; données sensibles ; action métier irréversible ; ambiguïté métier importante. Un échec de build, de test, de migration ou de seeder dans un environnement jetable n'est jamais une raison d'intervention humaine : il se reprend dans le budget. Une décision humaine n'agit que dans l'espace que la politique lui ouvre et ne franchit jamais un refus absolu.

Le système doit pouvoir placer un ticket en `WAITING_HUMAN` et s'arrêter proprement, sans perdre son état.

### 3.5 Responsabilité et audit

Pour chaque action importante, la Factory doit pouvoir répondre : qui a proposé, qui a exécuté, avec quel modèle, quels outils et quelles permissions, qui a revu, qui a approuvé, quelle version, quel résultat. Tout est auditable (section 14).

## 4. Connaissance, ADR et traçabilité

La connaissance est un actif de premier ordre : ce que la Factory apprend d'un projet doit servir aux suivants, avec un propriétaire et un cycle de vie.

### 4.1 Gestion de la connaissance

Arborescence : `knowledge/` avec les sous-dossiers `business`, `architecture`, `technical`, `security`, `operations`, `decisions`, `patterns`, `anti-patterns`, `incidents`, `lessons-learned`.

Types : connaissance métier, d'architecture, technique, opérationnelle, de sécurité.

Cycle de vie : créée, relue, approuvée, publiée, réutilisée, mise à jour, archivée, retirée. Tout élément publié a un propriétaire et une date de prochaine revue.

### 4.2 Architecture Decision Records

Une décision importante est enregistrée dans `adr/` (sous-dossiers `proposed`, `accepted`, `rejected`, `deprecated`).

- **Contenu** : identifiant, titre, contexte, problème, options, analyse, décision, conséquences, risques, propriétaire, date, approbation, statut.
- **Cycle** : proposé, en revue, accepté, actif, remplacé, archivé.
- **Règle** : un ADR remplacé reste consultable et pointe vers son successeur.

### 4.3 Chaîne de traçabilité

Toute information est traçable dans les deux sens, du besoin à l'incident :

1. Besoin
2. Capacité métier
3. Règle métier
4. Spécification
5. ADR
6. Architecture
7. Conception
8. Contrat
9. Planification
10. Ticket
11. Agent (exécution)
12. Code
13. Revue
14. Tests
15. CI/CD
16. Release
17. Opération et observabilité
18. Incident
19. Connaissance et amélioration

### 4.4 Graphe de connaissance

La Factory maintient un graphe global : c'est la source ultime de traçabilité. Pour qu'il soit exploitable, son modèle est défini ici.

| Élément | Règle |
| --- | --- |
| Types de nœuds | Projet, capacité, règle métier, spécification, ADR, ticket, exécution, API, table, service, test, release, incident, risque, contrôle de conformité |
| Identifiants | Stables, uniques dans la Factory, jamais réutilisés (par exemple `PRJ-001/RULE-042`) |
| Relations typées | `satisfait`, `implémente`, `teste`, `dépend_de`, `remplace`, `a_causé`, `couvre`, `approuvé_par` |
| Version | Chaque nœud est versionné ; une relation pointe vers une version précise |
| Complétude | Une règle métier critique sans test lié, ou un ticket sans spécification, lève une alerte de traçabilité |
| Sauvegarde | Le graphe est sauvegardé et restaurable (section 14) |

Le format de stockage reste libre (base de graphes, fichiers versionnés, index) tant que ce modèle est respecté.

## 5. Risques, conformité, données et gouvernance IA

Ces quatre gouvernances, présentes en v3.0 et absentes de la v3.1, sont réintégrées : un ERP industriel ou un système critique ne peut pas s'en passer.

### 5.1 Gestion des risques

Le Risk Registry (`risks/`) classe les risques par domaine : métier, technique, sécurité, opérationnel, données, conformité, IA, projet.

- **Fiche** : identifiant, type, description, cause, impact, probabilité, exposition, mitigation, propriétaire, statut.
- **Cycle** : identifié, évalué, approuvé, mitigé, surveillé, clos.
- **Règle** : un risque accepté l'est par écrit, par son propriétaire, avec une date de réexamen.

### 5.2 Conformité

La Factory doit pouvoir démontrer, et non seulement affirmer, sa conformité à ISO 27001, SOC 2, RGPD, NIS2, aux exigences clients et aux politiques internes.

- **Arborescence** : `compliance/` avec `controls`, `policies`, `evidence`, `audits`.
- **Principe** : chaque contrôle est relié à ses preuves, produites automatiquement quand c'est possible (journaux d'audit, résultats de CI, revues signées).
- **Applicabilité** : chaque projet déclare dans son manifest les référentiels qui s'appliquent à lui.

### 5.3 Gouvernance des données

| Domaine de données | Exemples |
| --- | --- |
| Master Data | Articles, clients, fournisseurs |
| Reference Data | Codes, unités, devises |
| Transactional Data | Commandes, mouvements de stock, écritures |
| Reporting Data | Indicateurs, agrégats |
| Audit Data | Traces d'actions et de décisions |
| AI Data | Jeux d'évaluation, journaux de prompts, contextes |

Capacités attendues : propriétaire, classification, lignage, qualité, rétention, archivage, suppression, chiffrement.

Dimensions de qualité mesurées : complétude, exactitude, cohérence, unicité, validité, actualité.

Règle de protection : une donnée de production ou classée sensible n'est jamais transmise à un modèle ou à un MCP sans autorisation explicite du Data Owner et sans contrôle du lieu de traitement.

### 5.4 Gouvernance IA

Objectif : gouverner les modèles, les prompts et les agents.

- **Registres** : modèles, prompts, benchmarks, évaluations, coûts, sécurité.
- **Cycle d'un modèle** : découverte, benchmark, évaluation, approbation, déploiement, surveillance, réévaluation, retrait.
- **Critères d'évaluation** : raisonnement, code, SQL, architecture, sécurité, exactitude, coût, latence, confidentialité.
- **Repli** : chaque rôle d'agent critique a au moins un modèle de secours approuvé, d'un autre fournisseur si possible.
- **Changement de version** : un changement de version de modèle déclenche une réévaluation avant de reprendre les tâches C2 et plus.

## 6. Catalogue vivant

Le catalogue (`factory/catalog/`) regroupe `tools`, `plugins`, `cli`, `agents`, `skills`, `mcp`, `models` et `workflows`. Chaque élément possède une fiche normalisée ; aucun n'est obligatoire tant qu'il n'a pas été évalué individuellement.

### 6.1 Fiche d'un outil

| Bloc | Champs |
| --- | --- |
| Identité | id, nom, catégorie, type, source officielle, documentation, finalité |
| Statut | statut, version, dernière version, date de dernière vérification |
| Compatibilité | plateformes, compatibilité, dépendances |
| Exploitation | installation, configuration, health check, rollback, politique de mise à jour |
| Permissions | accès réseau, accès fichiers, accès base de données |
| Risque | sécurité, licence, coût, alternatives |
| Évaluation | score, dernière évaluation, prochaine évaluation |

### 6.2 Cycle de vie d'un outil

Découvert, candidat, en évaluation, testé, approuvé, disponible, actif, réévalué, mis à jour. Branches : surveillance (watchlist), rejeté, déprécié, retiré. La découverte d'un outil ne signifie jamais son adoption.

### 6.3 Évaluation

Critères : maturité, stabilité, maintenance, documentation, sécurité, licence, coût, performance, intégration, portabilité, confidentialité, permissions, interopérabilité, dépendance au fournisseur (lock-in), compatibilité avec les projets.

Décisions possibles : adopter, conserver, mettre à jour, remplacer, ajouter, surveiller, rejeter, déprécier, retirer.

### 6.4 Découverte périodique

La Factory recherche périodiquement : nouveaux outils, versions, agents, modèles, MCP, skills, et outils de sécurité, de test, de performance, de base de données, DevOps et d'observabilité. La découverte ne modifie jamais l'environnement actif ; elle crée une proposition d'évaluation.

### 6.5 Factory Lab

Tout nouvel outil dont le risque le justifie passe par le Lab, avant approbation :

1. installation ;
2. compatibilité ;
3. sécurité ;
4. performance ;
5. test de workflow ;
6. intégration ;
7. test de rollback ;
8. rapport et approbation.

### 6.6 Mise à jour d'un outil

Nouvelle version, lecture du changelog, contrôle de sécurité, compatibilité, test au Lab, régression, approbation, mise à jour, health check. Un rollback est prévu pour les outils critiques.

### 6.7 Agents

Chaque agent est défini par : rôle, mission, modèle, skills, outils, MCP, permissions, entrées, sorties, limites, conditions d'arrêt, relecteur, criticité maximale autorisée.

```yaml
agent:
  id: senior-backend
  role: senior_backend
  model: selected_by_policy
  fallback_model: selected_by_policy
  skills: [backend, architecture, testing]
  tools: [compiler, formatter, linter, git]
  mcp: [filesystem, database_read]
  permissions:
    source_write: true
    database_write: false
    production: false
  max_criticality: C3
  review:
    required: true
```

Un agent n'est habilité pour un rôle et une criticité qu'après réussite de son évaluation (section 12.6). « Habilitation » désigne le droit d'agir hors d'un environnement jetable contrôlé. L'autonomie d'un agent sous bail dans un environnement explicitement jetable n'est pas une habilitation générale : elle reste bornée par l'environnement, la capacité, le bail, le périmètre, le budget, la politique et l'identité des ressources.

### 6.8 Skills

Les skills sont indépendantes des agents et réutilisables (par exemple : langage, base de données, sécurité, conception d'API, UX, tests, performance, migration, analyse de données, documentation). Chaque skill précise version, source, périmètre, dépendances, outils nécessaires, compatibilité, sécurité et statut.

### 6.9 MCP

Chaque MCP précise : identifiant, serveur, version, finalité, permissions, identifiants d'accès, lecture/écriture, agents et projets autorisés, accès à la production, sécurité, health check.

Règle : tout MCP touchant la production est en **lecture seule par défaut**. Toute écriture est explicitement autorisée, par projet et par agent.

Une skill, un MCP, un outil ou un modèle n'est chargé dans un runtime gouverné que si son empreinte réellement chargée correspond à celle épinglée dans le Trust Store ; la vérification est faite hors du processus agent.

### 6.10 Modèles

Le Model Registry contient : fournisseur, modèle, version, capacités, taille de contexte, raisonnement, coût, latence, confidentialité, lieu de traitement, disponibilité, rôles recommandés, restrictions.

Le modèle est choisi par la politique selon : complexité, criticité, type de ticket, rôle, coût, latence, confidentialité, contexte.

### 6.11 Catalogue initial

Le catalogue sera constitué catégorie par catégorie : IDE, plugins, agents IA, modèles, skills, MCP, Git et worktrees, spécification, architecture, planification, ticketing, backend, frontend, base de données, tests, E2E, sécurité, détection de secrets, analyse statique, performance, observabilité, documentation, data/BI, migration, sauvegarde, déploiement, CI/CD, supervision.

Pour chaque catégorie : identifier le besoin, rechercher, établir les candidats, évaluer, tester, comparer, choisir, enregistrer, installer, surveiller. L'outil choisi doit rester remplaçable.

## 7. Bootstrap, projet et santé de la Factory

Le Bootstrap est un service permanent de mise en route et de contrôle de santé, pas une simple procédure d'installation. Il détecte, installe si autorisé, configure, vérifie, teste, signale, répare certaines dépendances et bloque quand l'environnement n'est pas conforme.

### 7.1 Périmètre de contrôle

| Domaine | Éléments vérifiés |
| --- | --- |
| IDE | IDE principal, extensions, configuration |
| Contrôle de version | Git, identifiants, hooks, worktrees |
| IA | Agents, modèles, configuration, skills, prompts |
| MCP | Serveurs, versions, permissions, identifiants, santé |
| Développement | Runtimes, gestionnaires de paquets, compilateurs, formateurs, linters, outils de build |
| Base de données | Clients, CLI, outils de migration, d'inspection et de sauvegarde |
| Tests | Unitaires, intégration, E2E, navigateur, visuel, performance |
| Sécurité | Détection de secrets, audit de dépendances, SAST, contrôle des permissions |
| CI/CD | Pipelines, runners, artefacts, contrôles de déploiement |
| Observabilité | Journaux, métriques, traces, suivi d'erreurs |

### 7.2 Trois modes

| Mode | Effet | Exemple |
| --- | --- | --- |
| CHECK | Ne modifie rien : détection, validation, rapport | Rapport de conformité de l'environnement |
| SETUP | Configure et installe ce qui est autorisé | Installation d'un formateur manquant |
| REPAIR | Corrige les anomalies connues et sûres | Réinstallation d'un outil dans la bonne version |

Cas qui ne se réparent pas seuls : identifiant MCP manquant (`BLOCKED`), mauvaise version (mise à jour ou demande), violation de sécurité (`BLOCKED`).

### 7.3 Factory Health

Le Bootstrap produit un état lisible par une machine et par un humain, composant par composant (Factory Core, Git, worktrees, IDE, agents, modèles, skills, MCP, sécurité, base de données, tests, CI/CD), avec le nombre d'erreurs critiques et d'avertissements.

États : `READY`, `WARNING`, `DEGRADED`, `BLOCKED`, `FAILED`, `UNKNOWN`.

La Factory passe de `INITIALIZING` à `CHECKING`, puis à `READY`, `DEGRADED` ou `BLOCKED`. Elle ne déclare jamais `READY` quand une dépendance critique manque.

### 7.4 Project Bootstrap

Après le Factory Bootstrap : manifest du projet, détection de la stack, contrôle des dépendances, des agents, des outils, des MCP, de la sécurité et des tests, puis état de santé du projet. Un projet peut n'utiliser qu'une partie des capacités de la Factory.

### 7.5 Project Manifest

Le manifest du projet est le profil canonique `.factory/project.yaml`, dans le dépôt du projet. Ses sections qui peuvent augmenter l'autorité (environnements, agents, outils, sécurité, autonomie, bases de données, ressources) ne prennent effet qu'après relecture et épinglage ; une modification du dépôt n'augmente jamais à elle seule les droits du projet. Pendant le régime transitoire (§0.4), le manifest `factory.yaml` à la racine du projet reste lu.

Le manifest référence des capacités du catalogue ; il ne redéfinit pas les outils.

```yaml
project:
  id: gestionfil
  name: GestionFil
  factory_version: "3.2"
  criticality_default: C2

stack:
  backend: { language: rust, framework: axum }
  frontend: { language: typescript, framework: react }
  database: { engine: postgresql }

agents:
  required: [architect, backend, frontend, database, security, qa]

tools:
  required: [git, rust, node, postgres, playwright]

mcp:
  allowed: [filesystem, database, browser]

security:
  production_write: false
  data_classification: internal

compliance:
  frameworks: [rgpd]

budget:
  monthly_cap_eur: 500

quality:
  required: [format, lint, test, build, security]
```

### 7.6 Création d'un projet

Créer le projet, choisir la version de la Factory, créer le manifest, lancer le Factory Bootstrap puis le Project Bootstrap, contrôler la santé, lancer la découverte d'outils, puis architecture, planification et exécution.

## 8. Plateforme d'exécution

La plateforme d'exécution est le cœur opérationnel : un agent ne travaille jamais dans un environnement incontrôlé. Elle contrôle dépôt, branche, fichiers, outils, MCP, secrets, permissions, modèle, budget, délai, réseau, journaux, artefacts, tests et arrêt.

### 8.1 Pipeline d'exécution d'un ticket

1. **Policy Engine** : lit la criticité, le projet, le workflow et les permissions applicables.
2. **Sélection** de l'agent, du modèle (avec repli), des outils et des MCP.
3. **Contrôle des permissions** : combinaison agent + rôle + projet + ticket + criticité + outils + MCP.
4. **Réservation du budget** : plafonds de jetons, de coût et de durée.
5. **Création du sandbox** : espace isolé, branche dédiée, secrets limités, réseau selon §8.5.
6. **Exécution** de l'agent, avec journalisation continue.
7. **Collecte des artefacts** : diff, rapports, résultats de tests, journaux.
8. **Quality Gates**, puis revues (section 12).
9. **Fermeture** : libération du sandbox, mise à jour de l'état, écriture dans l'audit.

### 8.2 Contexte d'exécution

Chaque exécution enregistre : `execution_id`, `project_id`, `ticket_id`, `agent_id`, `model_id`, `factory_version`, outils, skills, MCP, permissions, worktree, branche, heures de début et de fin, jetons, coût, artefacts, tests, résultat, revue, plus le **hash de l'image du sandbox** et la **version des prompts** utilisés. La reproduction d'un résultat doit être possible à partir de cet enregistrement.

### 8.3 Isolation

Par défaut : un agent, un worktree isolé, une branche dédiée. Plus le risque est élevé, plus l'isolation est forte. Pour C3 et C4, et pour toute action en staging ou en production, l'exécution passe par un executor séparé de l'agent, dans un autre contexte de sécurité. L'executor ne reçoit qu'une référence de plan approuvé, son empreinte et un contexte d'exécution ; il ne reçoit jamais de commande ni de shell fournis par l'agent ; il récupère les artefacts depuis un store protégé par leur empreinte et ne choisit qu'entre les opérations prévues par le plan. L'agent ne détient jamais les identifiants de ces environnements. Tant que cette frontière n'est pas appliquée de façon préventive, l'exécution par la Factory y est indisponible et l'exécution reste humaine.

L'agent ne modifie jamais : les autres worktrees, les secrets, la production, les données sensibles, les configurations globales.

### 8.4 Secrets

- Les secrets sont fournis par un coffre, à durée courte et au périmètre du ticket ; jamais écrits dans le dépôt, les prompts ou les journaux.
- Un agent n'accède qu'aux secrets que son rôle et son ticket justifient.
- Un secret détecté dans une sortie d'agent déclenche son invalidation et un incident de sécurité.

### 8.5 Réseau

Le sandbox n'a pas d'accès sortant par défaut. L'accès sortant est une capacité nommée (documentation, registre de paquets, fournisseur Git, registre de modèles, registre MCP), limitée en destination, protocole, port, durée, volume et mission. Un registre inconnu est refusé. Tant qu'aucun mécanisme technique n'applique ces limites, la politique réseau est déclarée déclarative. Tout accès web effectué par un agent est journalisé, et son contenu est traité comme donnée non fiable (P06).

### 8.6 Budgets et limites

| Limite | Portée | Effet à l'atteinte |
| --- | --- | --- |
| Jetons et coût par exécution | Ticket | Arrêt propre et rapport |
| Durée maximale | Ticket | Arrêt et escalade |
| Tentatives | Exécution et mission | Budget unique tenu par le service d'autorité ; un échec récupérable se reprend sans intervention humaine ; budget épuisé : arrêt (BUDGET_STOP), puis escalade dans la hiérarchie d'agents, puis décision humaine seulement si une frontière est en jeu |
| Plafond mensuel | Projet | Alerte à 80 %, blocage à 100 % sauf dérogation du Factory Owner |
| Plafond global | Factory | Alerte au Factory Owner |

### 8.7 Reprise sur erreur

Une exécution interrompue (panne, timeout, indisponibilité du modèle) laisse l'état du ticket cohérent : le travail partiel reste sur sa branche, le ticket passe en `BLOCKED` ou repart d'un point de reprise, jamais en `IMPLEMENTED` par défaut. Si le modèle principal est indisponible, l'Orchestrator bascule vers le modèle de repli approuvé pour le rôle, sans dépasser la criticité autorisée pour ce modèle.

### 8.8 Orchestrator

L'Orchestrator lit l'état du projet et du workflow, identifie les tickets prêts, vérifie les dépendances, applique le pipeline 8.1, collecte les résultats, déclenche revues et Quality Gates, bloque si nécessaire, demande la validation humaine et met à jour l'état. Il ne prend aucune décision d'architecture.

### 8.9 Parallélisation

Les tickets sont parallélisés quand ils ne dépendent pas les uns des autres ; un ticket qui dépend de B et de C attend les deux. Le Planner calcule le graphe de dépendances ; deux tickets qui touchent les mêmes fichiers sont sérialisés ou fusionnés avec une revue de conflit.

## 9. Profils de criticité et matrice de pouvoirs

La puissance d'un agent est proportionnelle au risque : plus une opération est irréversible, sensible, financière, destructive ou critique pour la production, moins elle est autonome. À l'inverse, documentation, analyse, tests, code local et refactoring isolé peuvent être fortement automatisés.

### 9.1 Les cinq profils

| Profil | Exemples | Permissions | Contrôles |
| --- | --- | --- | --- |
| C0 — Information | Recherche, analyse, résumé, documentation | Lecture seule | Validation humaine généralement inutile |
| C1 — Développement local | Code local, tests, refactoring isolé | Écriture source et tests, pas de production | Revue avant intégration |
| C2 — Changement applicatif | Nouvelle API, fonctionnalité, UI, logique métier | Écriture source et tests, base de données de développement possible | Revue et Quality Gates |
| C3 — Changement sensible | Sécurité, autorisation, données financières, stock, valorisation, migration, calcul métier critique | Comme C2, isolation renforcée | Revue senior, revue spécialisée (sécurité, base de données), tests de régression, approbation humaine |
| C4 — Opération critique | Production, migration destructive de données réelles, suppression ou changement massif de données réelles, déploiement majeur. Les ressources d'un environnement jetable créé par la Factory, utilisées sous un bail valide, ne relèvent pas de C4 du seul fait d'une opération destructive | L'agent prépare ; un humain décide ; l'exécution est humaine, ou confiée à un executor déterministe qui rejoue exactement le plan approuvé | Approbation humaine obligatoire |

### 9.2 Matrice de pouvoirs

Cette matrice est une politique appliquée par le Policy Engine, pas une convention informelle.

| Capacité | C0 | C1 | C2 | C3 | C4 |
| --- | --- | --- | --- | --- | --- |
| Lecture | Oui | Oui | Oui | Oui | Oui |
| Écriture du code source | Non | Oui | Oui | Oui | Limitée |
| Écriture des tests | Non | Oui | Oui | Oui | Oui |
| Écriture base de données de développement jetable ou désignée par le projet | Non | Oui | Oui | Oui | Contrôlée |
| Écriture base de données de production | Non | Non | Non | Non | Humain |
| Déploiement en production | Non | Non | Non | Non | Humain |
| Suppression de données réelles | Non | Non | Non | Non | Humain |
| Ressources d'un environnement jetable sous bail (créer, modifier, casser, réinitialiser, supprimer) | Non | Oui (bail) | Oui (bail) | Oui (bail) | — |
| Politique de sécurité | Non | Non | Non | Revue | Revue + humain |

Dans cette matrice, « Humain » signifie : décision humaine signée par une identité certifiée. Une politique de projet peut restreindre davantage (par exemple une base locale contenant des données réelles).

### 9.3 Attribution de la criticité

1. Le Planner propose une criticité à la création du ticket, selon des règles du projet (périmètre touché, données, permissions, production).
2. Un agent ne peut **jamais abaisser** la criticité d'un ticket. Il peut proposer de la relever.
3. Une criticité C3 ou C4 est confirmée par un humain avant le démarrage.
4. En cas de doute entre deux niveaux, le plus élevé s'applique.

### 9.4 Pilotage par risque

| Niveau de risque | Approche |
| --- | --- |
| Faible (C0, C1) | Automatisation maximale |
| Moyen (C2) | Revue et tests |
| Élevé (C3) | Spécialistes, tests et approbation humaine |
| Critique (C4) | Exécution contrôlée par l'humain |

### 9.5 Non-débordement

Un agent ne transforme pas un ticket A en ticket A plus refactoring global, changement d'architecture, modification de base de données, changement d'UX ou de sécurité, sans autorisation. Il crée une proposition de changement ou un nouveau ticket.

### 9.6 Conditions d'arrêt

Un agent s'arrête et demande une décision humaine devant : ambiguïté métier, contradiction architecturale, permission insuffisante, données incohérentes, migration dangereuse hors environnement jetable, risque de perte de données, changement hors périmètre, budget épuisé, problème de sécurité, dépendance absente.

## 10. Sécurité

La sécurité couvre l'identité, l'authentification, l'autorisation, les secrets, l'infrastructure, l'application, la base de données, les agents, les MCP et les modèles. Chaque domaine a un propriétaire, un suppléant, un relecteur et un approbateur.

### 10.1 Modèle de menaces propre à l'IA

| Menace | Exemple | Parade principale |
| --- | --- | --- |
| Injection de prompt | Instruction cachée dans un ticket, un fichier ou une page web | P06 : les données ne sont jamais des instructions ; revue des sorties ; permissions minimales |
| Exfiltration | Un agent envoie du code ou des données vers l'extérieur | Réseau filtré (cible, voir §8.5), journalisation des accès, pas de secrets dans le contexte |
| Abus d'outil ou de MCP | Un MCP en écriture utilisé hors de son périmètre | MCP en lecture seule par défaut, liste d'agents autorisés |
| Chaîne d'approvisionnement | Paquet ou extension compromis, skill malveillante | Évaluation au Lab, verrouillage des versions, audit de dépendances, sources officielles |
| Code généré vulnérable ou non maîtrisé | Dépendance inventée, faille logique | SAST, audit des dépendances, revue obligatoire, tests |
| Débordement de périmètre | Un agent modifie ce qu'on ne lui a pas demandé | Règle de non-débordement, diff comparé au périmètre du ticket |
| Compromission de secrets | Secret écrit dans un journal ou un commit | Détection de secrets, coffre à durée courte, invalidation immédiate |

Ce modèle est revu à chaque évolution majeure du catalogue et après chaque incident de sécurité.

### 10.2 Provenance du code généré

Chaque commit produit par un agent porte les métadonnées de son exécution : agent, modèle, version des prompts, identifiant d'exécution, ticket. Un changement dont la provenance est inconnue n'est pas fusionné. La provenance inclut les empreintes des skills et des prompts utilisés. Les extraits copiés depuis des sources externes sont signalés et vérifiés au regard de la licence.

### 10.3 Capacités de sécurité attendues

Détection de secrets, analyse de dépendances, SAST, analyse de permissions, contrôle de configuration, défense contre l'injection de prompt, sécurité des MCP, sécurité de la chaîne d'approvisionnement, audit.

### 10.4 Autorisation personnalisée

Pour les ERP complexes, un système d'autorisation qui gère la visibilité et le masquage des champs, l'activation, la modification, les permissions et les exceptions par utilisateur est une **composante de sécurité critique** (C3 au minimum).

- **Modèle** : RBAC, ABAC, sécurité par enregistrement, par champ, par état et par workflow, masquage, dérogations.
- **Exigences** : modèle explicite, tests combinatoires, tests de régression, audit, revue spécialisée, protection contre le contournement par le frontend.
- **Propriétaires** : propriétaire humain, propriétaire sécurité, propriétaire backend, propriétaire des tests.

### 10.5 Séparation des rôles de sécurité

L'auteur d'un changement ne l'approuve jamais seul. Pour la sécurité critique, le relecteur sécurité est distinct de l'auteur et de l'approbateur de la release.

## 11. Spécification, design, tickets et workflows

Cette section décrit comment un besoin devient des unités de travail exécutables. Pour un changement simple, des étapes peuvent être fusionnées ; pour un changement critique, elles restent séparées.

### 11.1 Pipeline de spécification

Besoin, règle métier, spécification, architecture, conception technique, algorithme, contrat, tickets.

### 11.2 Technical Design Package

Structure standard : `docs/design/<feature>/` avec `overview.md`, `business-rules.md`, `architecture.md`, `database.md`, `api.md`, `algorithms.md`, `security.md`, `frontend.md`, `ux.md`, `tests.md`, `decisions.md`.

### 11.3 Analyse d'impact

Avant tout changement significatif, cinq questions reçoivent une réponse écrite, conservée avec le ticket :

1. Qu'est-ce qui change ?
2. De quoi cela dépend-il ?
3. Qu'est-ce qui peut casser ?
4. Qu'est-ce qui doit être testé ?
5. Qu'est-ce qui doit être approuvé ?

Surfaces à examiner : code, base de données, API, interface, mobile, permissions, rapports, intégrations, tests, déploiement, documentation.

### 11.4 Ticket complet

Identifiant, type, niveau, criticité, contexte, objectif, design, fichiers, contrat, règles métier, algorithme, base de données, transaction, permissions, erreurs, tests, acceptation, dépendances, risques, agent, relecteur, conditions d'arrêt.

### 11.5 Light Ticket

Pour les petites modifications : identifiant, objectif, contexte, changement, fichiers, tests, acceptation, agent, relecteur. La Factory ne transforme pas une correction de trois lignes en procédure bureaucratique.

### 11.6 États d'un ticket

Chemin nominal : `DRAFT`, `ANALYSIS`, `DESIGN`, `READY`, `ASSIGNED`, `IN_PROGRESS`, `IMPLEMENTED`, `CODE_REVIEW`, `DB_REVIEW`, `SECURITY_REVIEW`, `QA`, `ACCEPTED`, `READY_TO_MERGE`, `HUMAN_APPROVAL`, `MERGED`, `RELEASED`, `CLOSED`.

Boucle : `CHANGES_REQUESTED` renvoie vers `IN_PROGRESS`. États transverses : `BLOCKED`, `WAITING_HUMAN`, `WAITING_DEPENDENCY`, `CANCELLED`. Les revues conditionnelles s'activent selon la criticité.

### 11.7 Spike

Pour une inconnue technique importante : recherche, prototype, mesure, décision. Un spike n'est jamais une implémentation définitive.

### 11.8 Workflows standards

| Workflow | Usage |
| --- | --- |
| LIGHT\_CHANGE | Petite modification, ticket léger |
| BUG\_FIX | Correction d'anomalie |
| FEATURE | Nouvelle fonctionnalité |
| ARCHITECTURE | Changement d'architecture, ADR obligatoire |
| MIGRATION | Migration de données ou de schéma |
| SECURITY | Changement de sécurité ou d'autorisation |
| PERFORMANCE | Optimisation mesurée |
| RELEASE | Préparation et publication |
| INCIDENT | Gestion d'incident (section 14) |
| MODERNIZATION | Modernisation d'un système existant (section 13) |

Chaque workflow définit ses étapes, ses agents, sa criticité, ses Quality Gates, ses validations et ses Human Gates.

### 11.9 Prompt standard

Le prompt transmet : rôle, projet, ticket, objectif, contexte, entrées, outils et MCP autorisés, permissions, contraintes, livrable, tests, critères de fin, conditions d'arrêt. Les règles permanentes restent dans la Factory et dans le fichier de contexte (section 16), pas répétées à chaque prompt.

## 12. Qualité

La qualité repose sur des preuves : le résultat produit par un exécutant contrôlé par la Factory (la CI en est un) est la source de vérité, pas le rapport de l'agent. Cette section regroupe les Quality Gates, les revues, la QA, la régression, la performance et l'évaluation des agents.

### 12.1 Quality Gates

| Catégorie | Gates |
| --- | --- |
| Minimum pour tout projet | Format, lint, vérification de types, tests unitaires, tests d'intégration, build, sécurité, audit de dépendances, E2E |
| Selon le projet | Régression visuelle, accessibilité, performance, concurrence, validation de migration, mobile |

Un gate en échec bloque le passage à l'état suivant. Il ne peut être levé que par une dérogation humaine auditée.

### 12.2 Definition of Done

Un ticket n'est `ACCEPTED` que si, au minimum :

1. tous les Quality Gates requis sont verts en CI ;
2. les critères d'acceptation du ticket sont vérifiés par des tests ;
3. les revues requises par la criticité sont terminées ;
4. les règles métier touchées ont un test identifié ;
5. la documentation et les ADR concernés sont à jour ;
6. aucune alerte de sécurité ouverte n'est introduite.

### 12.3 Revue de code

Principe : **l'auteur n'est pas le relecteur**. Pour C3 et C4 : revue senior, revue spécialisée si nécessaire, QA, puis validation humaine. Un agent qui relit un autre agent doit utiliser, quand c'est possible, un modèle différent de celui de l'auteur, pour éviter les angles morts communs.

### 12.4 QA

La QA couvre : unitaires, intégration, API, E2E, interface, responsive, mobile, permissions, sécurité, régression, concurrence, performance. Elle ne se limite pas à vérifier que le code compile : elle vérifie le comportement métier attendu.

### 12.5 Régression ciblée

Code modifié, dépendances, modules affectés, tests affectés, régression ciblée. La suite complète n'est pas rejouée à chaque changement, mais elle l'est pour tout changement C3 ou C4 et avant chaque release.

### 12.6 Évaluation des agents

Un agent n'obtient un rôle et une criticité maximale qu'après avoir réussi un jeu d'évaluation propre à ce rôle. « Habilitation » désigne le droit d'agir hors d'un environnement jetable contrôlé. L'autonomie d'un agent sous bail dans un environnement explicitement jetable n'est pas une habilitation générale : elle reste bornée par l'environnement, la capacité, le bail, le périmètre, le budget, la politique et l'identité des ressources.

- **Contenu du jeu** : tâches de référence avec résultats attendus, pièges connus (injection de prompt, périmètre ambigu, permission manquante), cas de régression issus d'incidents passés.
- **Mesures** : taux de réussite, taux de rejet en revue, taux d'hallucination, respect du périmètre, respect des conditions d'arrêt, coût.
- **Seuils** : définis par rôle et par criticité ; un seuil non atteint plafonne la criticité autorisée pour cet agent.
- **Réévaluation** : à chaque changement de modèle, de prompt ou de skill, et au moins tous les trimestres.

### 12.7 Performance

Avant toute optimisation : mesure de référence (baseline). Après : mesure, comparaison, décision. Mesures possibles : processeur, mémoire, base de données, réseau, latence, débit, rendu frontend, concurrence. Une optimisation sans mesure avant/après n'est pas acceptée.

## 13. Données, base de données, migrations et modernisation

### 13.1 Base de données

La Factory distingue quatre choses : l'intégrité de la base, la logique métier, la logique applicative et l'implémentation en base. Les contraintes de la base protègent d'abord l'intégrité ; les règles métier se placent dans la couche appropriée et sont documentées (P08).

### 13.2 Migrations

Une migration sensible suit autant que possible le schéma en cinq temps :

1. **Expand** : ajouter la nouvelle structure sans casser l'ancienne.
2. **Migrate** : copier et transformer les données.
3. **Switch** : basculer l'application sur la nouvelle structure.
4. **Validate** : vérifier les résultats et la réconciliation.
5. **Contract** : retirer l'ancienne structure.

Une migration destructive de données réelles, hors environnement jetable (C4), exige une sauvegarde restaurée et testée, un plan de rollback et une décision humaine. Dans un environnement jetable sous bail, une migration peut être appliquée, cassée, annulée et rejouée sans décision humaine.

### 13.3 Migration importante de données

Prérequis : inventaire, correspondances (mapping), règles de transformation, conservation des identifiants, validation, comparaison avant/après, rollback, sauvegarde, tests de données.

### 13.4 Qualité des données à l'import

Source, validation, transformation, import, réconciliation, rapport. La réussite d'un import ne signifie pas « aucune erreur technique » : elle signifie que les données importées sont complètes, exactes et réconciliées avec la source.

### 13.5 Modernisation d'un système existant

1. **Caractériser** : décrire ce que fait le système aujourd'hui.
2. **Comprendre** : reconstituer les règles métier.
3. **Tester le comportement existant** : tests de caractérisation avant tout changement.
4. **Migrer.**
5. **Valider** par rapport au comportement d'origine.
6. **Refactorer.**
7. **Optimiser.**

La modernisation ne doit pas modifier les règles métier involontairement ; tout écart voulu est une décision tracée.

### 13.6 Data et BI

Pipeline : question métier, sources de données, indicateur, modèle de données, SQL, validation, KPI, tableau de bord ou rapport. Les indicateurs financiers et opérationnels ont une définition explicite, versionnée et validée par leur propriétaire métier.

## 14. Release, observabilité, audit, continuité et incidents

### 14.1 Gestion des releases

Avant une release, on contrôle : fonctionnalités, anomalies, base de données, migrations, sécurité, tests, sauvegarde, rollback, documentation, version. Puis : approbation humaine (Release Approver), release. Toute release majeure est C4.

### 14.2 Observabilité

On sépare les journaux applicatifs, l'audit de sécurité, l'audit métier, les journaux de base de données, les journaux système, les métriques, les traces et le suivi d'erreurs. L'audit métier n'est jamais confondu avec un simple journal technique.

### 14.3 Audit

Chaque exécution importante laisse une trace : horodatage, projet, ticket, agent, modèle, outil, MCP, permission, action, résultat, test, revue, approbation. La Factory doit pouvoir répondre : qui a fait quoi, quand, avec quoi, avec quelle autorisation et avec quel résultat. Les journaux d'audit sont en ajout seul, protégés contre la modification, et conservés selon la politique de rétention.

### 14.4 Sauvegarde et reprise des projets

Chaque projet définit : RPO, RTO, fréquence de sauvegarde, rétention, copie hors site, chiffrement, procédure de restauration, plan de reprise après sinistre.

> Une sauvegarde qui n'a jamais été restaurée n'est pas une preuve de récupérabilité.

Un test de restauration est exécuté à fréquence fixe et avant chaque migration destructive de données réelles.

### 14.5 Continuité de la Factory elle-même

La Factory est un système critique à part entière. Elle sauvegarde et sait restaurer :

- le graphe de connaissance et les registres ;
- les politiques, les workflows et les manifests ;
- les journaux d'audit ;
- les images de sandbox et les versions de prompts.

La dépendance à un fournisseur de modèles est traitée par le repli de modèle (5.4 et 8.7). Un mode dégradé est défini : si les agents sont indisponibles, les projets continuent en développement humain, et les tickets en cours restent dans un état cohérent.

### 14.6 Incidents

1. **Contenir** l'incident.
2. **Diagnostiquer.**
3. **Corriger.**
4. **Valider** la correction.
5. **Rétablir** le service.
6. **Identifier la cause racine.**
7. **Prévenir** la récidive.

La correction immédiate et la correction structurelle sont distinguées. Chaque incident alimente `knowledge/incidents` et, si pertinent, le jeu d'évaluation des agents (12.6).

## 15. Métriques, FinOps IA, versionnement et évolution

### 15.1 Métriques

| Famille | Mesures |
| --- | --- |
| Livraison | Tickets terminés, lead time, temps d'exécution, fréquence de release, taux de réussite des déploiements, MTTR |
| IA | Jetons, coût par modèle, nouvelles tentatives, itérations de revue, taux d'hallucination, taux de rejet en revue, taux de réussite des agents |
| Qualité | Taux de reprise, taux de défauts échappés, couverture, dette technique, échecs de CI, alertes de sécurité |
| Humain | Délai d'approbation humaine, tickets en `WAITING_HUMAN`, escalades |

Deux indicateurs sont définis sans ambiguïté :

- **Taux de reprise** = tickets nécessitant une reprise ÷ tickets terminés.
- **Taux de défauts échappés** = défauts détectés après merge ou release ÷ tickets livrés.

Chaque métrique a un propriétaire et une fréquence de revue ; une métrique que personne ne lit est supprimée.

### 15.2 FinOps IA

- **Budgets** par projet et par Factory, déclarés dans le manifest (section 7.5) et appliqués par la plateforme (8.6).
- **Suivi** du coût par ticket, par agent, par modèle et par type de workflow.
- **Arbitrage** : à qualité égale mesurée par l'évaluation (12.6), le modèle le moins coûteux est préféré ; les modèles les plus puissants sont réservés aux rôles et aux criticités qui le justifient.
- **Revue mensuelle** des coûts par le Factory Owner, avec alerte sur toute dérive supérieure à 20 % d'un mois sur l'autre.

### 15.3 Versionnement de la Factory

La Factory est versionnée (v3.1, v3.2, …). Chaque version fournit : numéro, changelog, guide de migration, matrice de compatibilité (outils, agents, modèles, projets), stratégie de rollback, politique de dépréciation.

Un projet peut rester temporairement sur une version antérieure ; la durée maximale de support d'une version est annoncée à sa publication.

### 15.4 Évolution du standard

Standard, observation, mesure, découverte, évaluation, Lab, test, adoption ou rejet, mise à jour du standard. La Factory ne doit jamais devenir figée. Toute évolution du standard est une décision du Factory Owner (section 3.2) avec un ADR.

### 15.5 Revue périodique

Chaque trimestre : revue des métriques, du catalogue, des risques, des seuils d'évaluation des agents et du modèle de menaces. Les résultats alimentent la prochaine version du Playbook.

## 16. Structure, documentation et contexte agent

### 16.1 Structure recommandée de la Factory

```text
software-factory/
├── core/
├── bootstrap/
├── orchestrator/
├── registry/
│   ├── tools/  agents/  skills/  mcp/
│   └── models/  workflows/  projects/
├── catalog/
├── knowledge/
├── adr/
├── risks/
├── compliance/
├── policies/
├── workflows/
├── quality/
├── security/
├── audit/
├── metrics/
├── discovery/
├── evaluation/
├── lab/
├── update/
├── docs/
└── projects/
```

### 16.2 Structure d'un projet

```text
project/
├── .factory/project.yaml   (profil du projet ; remplace factory.yaml, voir §7.5)
├── AGENT_CONTEXT.md        (contexte stable pour les agents)
├── docs/
│   ├── architecture/  design/  business/  security/
│   └── database/  api/  algorithms/  operations/
├── tickets/
└── tests/
```

### 16.3 Contexte agent

Le contexte stable destiné aux agents (présentation du projet, commandes, usages, renvois vers les règles) est tenu dans un fichier de contexte générique, `AGENT_CONTEXT.md`, que chaque runtime peut lire sous son propre nom ; ce fichier reste la source unique de ce contexte, pour préserver la neutralité vis-à-vis du fournisseur d'IA. Il ne contient aucune règle d'autorisation, de permission ou de sécurité : ces règles sont définies par le catalogue des règles et les politiques de la Factory, qui prévalent sur tout fichier de contexte en cas d'écart. Sur décision du Factory Owner, un dépôt peut tenir ce contexte dans le fichier propre à son runtime (par exemple `CLAUDE.md`) ; l'écart à la neutralité est alors déclaré dans ce fichier, et la règle d'absence d'autorité s'applique à l'identique.

Le fichier contient : conventions du projet, commandes de build et de test, règles métier permanentes, zones interdites, références aux ADR. Il ne contient jamais de secret.

### 16.4 Documentation vivante

La documentation est produite à partir du travail réel et évolue avec le code : architecture, ADR, modèle de données, API, règles métier, algorithmes, sécurité, déploiement, runbooks, releases. Une modification de code qui rend un document faux est incomplète tant que le document n'est pas corrigé (Definition of Done, 12.2).

### 16.5 Spécialisation des agents

Un agent peut être puissant sans avoir tous les pouvoirs. Par exemple, l'agent base de données reçoit les outils de base de données, de migration, de SQL et d'analyse de schéma ; l'agent frontend reçoit l'interface, le navigateur et Playwright. La spécialisation réduit les erreurs, le coût, le contexte inutile et la surface d'attaque.

### 16.6 Rôles et organisation des agents

| Famille | Rôles |
| --- | --- |
| Architecture | Solution Architect, Technical Planner (le Chief Architect est humain) |
| Analyse | Business Rule Engineer, Algorithm Engineer, Contract Engineer, Impact Analysis |
| Ingénierie | Backend, Frontend/UX, Database, DevOps, Migration, Refactoring |
| Qualité | QA, Security, Performance, Regression |
| Opérations | Release Manager, Observability Engineer, Backup/Recovery Engineer |
| Data | Data/BI Engineer |
| Documentation | Documentation Engineer |
| Coordination | Orchestrator |

## 17. Feuille de route : MVP et phasage

Le Playbook décrit la cible ; il ne se déploie pas d'un bloc. La mise en œuvre suit quatre phases, chacune fermée par un critère de passage vérifiable. Les durées sont indicatives et à ajuster selon les équipes.

La mise en œuvre suit désormais des phases de frontières ; chaque frontière n'est déclarée disponible que lorsque son application est démontrée au niveau qu'elle exige.

| Phase | Frontières visées |
| --- | --- |
| G1 Fondations | identité, stores, catalogue des règles, épinglage, baux authentifiés, journal d'autorité, racine de confiance |
| G2 Décision | Decision Center, exécution humaine, exceptions bornées |
| G3 Frontière d'exécution | service d'autorité isolé, executor séparé |
| G4 Habilitation | évaluation des agents, modèles approuvés |
| G5 Échelle | orchestration, Twin, mémoire, découverte, réseau appliqué |
| G6 Multi-projets | second projet sur une autre pile |

L'autonomie sous bail en environnement jetable est disponible dès G1 et ne constitue pas une habilitation. Les quatre phases de la v3.2 (MVP, gouvernance, criticité et sécurité, plateforme multi-projets) sont remplacées ; le MVP (phase 1) est atteint.

### 17.1 Ce que contient le MVP

Le MVP réunit uniquement ce qui rend le travail des agents **sûr et traçable** : isolation, ticket-contrat, Quality Gates en CI, audit, ADR et connaissance. Tout le reste est différé tant que ces fondations ne sont pas éprouvées. Le MVP (phase 1) est atteint (bilan du pilote du 15/10/2026). La suite relève du phasage par frontières (§17) ; ce paragraphe est conservé à titre historique.

### 17.2 Règles de pilotage

1. Une frontière n'est déclarée disponible que lorsque son application est démontrée ; une phase peut commencer avant la clôture de la précédente si elle ne dépend pas de frontières encore indisponibles.
2. Un service du Factory Core n'est construit que s'il répond à un besoin observé sur le projet pilote.
3. Chaque phase se termine par une revue (15.5) qui peut ajuster la suite.
4. Les éléments de ce Playbook non encore mis en œuvre sont marqués « cible » dans les registres, pour que personne ne les croie actifs.

## 18. Règles absolues

Vingt-huit règles résument le Playbook ; elles prévalent en cas de doute.

1. La Factory est permanente et multi-projets.
2. Le Playbook définit des principes, pas une liste figée d'outils.
3. Les outils vivent dans un catalogue évolutif et sont évalués avant adoption.
4. Les mises à jour sont contrôlées.
5. La découverte ne signifie jamais adoption.
6. Chaque projet possède un manifest.
7. Les règles stables ne sont pas répétées dans chaque prompt.
8. Les agents sont spécialisés.
9. Les permissions sont explicites et la criticité ne peut jamais être abaissée par un agent.
10. Les données externes ne sont pas des instructions.
11. Un exécutant contrôlé par la Factory est la source de vérité des Quality Gates.
12. L'auteur ne valide pas seul son travail.
13. Les opérations critiques exigent un contrôle humain ; l'absence de réponse n'est jamais un accord.
14. Les changements irréversibles sont particulièrement contrôlés.
15. Les actions importantes sont auditées.
16. Le Bootstrap vérifie l'environnement avant l'exécution.
17. La Factory elle-même est versionnée, sauvegardée et restaurable.
18. Les nouveaux outils passent par le Lab quand le risque le justifie.
19. Tout agent est évalué avant d'être habilité hors d'un environnement jetable.
20. Le Chief Architect est humain.
21. Chaque projet et la Factory ont un budget IA appliqué par la plateforme.
22. Les secrets ne sont jamais dans les prompts, le dépôt ou les journaux.
23. Le code généré a une provenance connue.
24. La Factory évolue en continu, par des décisions tracées.
25. Une décision humaine ne franchit jamais un refus absolu.
26. Un plan modifié matériellement exige une nouvelle décision ; la non-matérialité est définie par la règle, jamais par l'agent.
27. Une capacité n'est disponible que si son application est prouvée au niveau qu'elle exige.
28. Toute autorité remonte à une racine de confiance détenue par un humain ; un pouvoir technique sur le système n'est pas une autorité de la Factory.

### Objectif final

Passer d'une idée à **un logiciel fiable, testé, sécurisé, auditable et maintenable**, par un flux unique, de l'idée à l'amélioration continue, tout en faisant vivre en parallèle le catalogue des outils, skills et modèles.

La Factory n'est pas seulement une méthode de développement assisté par IA : c'est une infrastructure permanente de production logicielle, gouvernée, mesurable, sécurisée et évolutive.
