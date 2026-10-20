# ADR-0022 — Le ticket, contrat d'exécution qui référence des composants versionnés

| Champ | Valeur |
|---|---|
| Identifiant / version | ADR-0022, **v2 du 19/10/2026** (la v1 du même jour est remplacée, voir § 7) |
| Statut | **Accepté le 19/10/2026** par le Factory Owner (« j accept ») ; **v2** : alignement sur le modèle canonique validé dans le projet GMAO, choix du Factory Owner (« Aligner sur GMAO », 19/10/2026) ; acceptation non attestée par la commande humaine W1 |
| Décision d'origine | audit en lecture seule des 63 tickets du premier projet rattaché (GMAO) ; portée : **tous les projets** |
| Référence de conception | GMAO/docs/tickets/modele-canonique.md **v1.0**, validé par le Factory Owner avec les corrections de son § 9, qui priment ; changements de la Factory F-1 à F-10 (§ 5.1) |
| Complète | ADR-0001 ; ADR-0003 ; ADR-0004 ; ADR-0007 ; ADR-0016, ADR-0017 (baux, intersection des droits) ; ADR-0019 ; ADR-0020, ADR-0021 (proposés) |
| Modifie | Executable Schemas v1.0 : ticket 1.1 (extensions facultatives), agent, skill, provenance (champs facultatifs), prompt_profile (nouveau) ; Policy Engine : R40, R41 |
| Propriétaire | Factory Owner (humain) |

## 1. Contexte

L'audit des tickets du premier projet rattaché montre des tickets **bien gouvernés mais non exécutables** :

- **ce qui manque** : sur 63 tickets, aucun ne déclare de version du ticket, de résultat attendu, d'entrées ou de sorties, d'instructions ou d'interdictions propres, de skills, d'outils, de MCP, de profil de prompt ni de tests ; aucun ne cite de gate qui existe ; aucun rôle n'est versionné ;
- **ce qui est recopié** : une vingtaine de champs ont la même valeur dans presque tous les tickets (budget, conditions d'arrêt, rollback, revue, évidence exigée, décisions humaines, références du projet). Corriger une règle oblige à éditer chaque ticket ;
- **ce qui est incohérent sans être détecté** : des tickets C3 confiés à des rôles plafonnés à C2 ; des gates citées qui n'existent pas ; une habilitation écrite deux fois en texte libre.

La cause est dans la Factory, pas dans le projet : la Factory ne fournit pas aujourd'hui les éléments versionnés qu'un
ticket devrait **référencer**, ni le calcul qui dit si un ticket peut être exécuté. Le catalogue des skills est vide ;
les outils sont en version `*` ; les profils de prompt et les profils de contrôle n'existent pas comme registres ; le
profil d'exécution est dispersé (Policy Engine, baux, garde, manifest) ; aucun contrôle ne répond READY ou BLOCKED.

## 2. Principe

> Chaque information est écrite **à un seul endroit**, versionnée, et **référencée** ailleurs. Le ticket ne contient que
> ce qui lui est propre. La Factory calcule le reste, le fige au démarrage et le prouve.
>
> L'objectif est de maximiser le travail autonome sûr, non le nombre de validations humaines (ADR-0021, § 1) : ce
> mécanisme **n'ajoute aucune validation humaine** ; il remplace des vérifications humaines implicites par un contrôle
> automatique qui bloque.

## 3. Décision (v2)

La Factory met en œuvre le **modèle canonique GMAO v1.0** (avec son § 9), de façon générique, pour tous les projets.
Les responsabilités restent séparées : ticket (ce qui est demandé), rôle (qui), skill (savoir-faire), outil et MCP
(avec quoi), politique (permis ou interdit), contexte (ce qu'il faut connaître), profil de prompt (comment le prompt
est assemblé), profil d'exécution (objet `execution` préparé + bail), provenance et preuves.

| N° | Décision | Mise en œuvre |
|---|---|---|
| D1 | Les tickets vivent dans le dépôt du projet, à l'emplacement déclaré par son manifest (`tickets.path`) ; la Factory les lit **sur place**, seulement si cet emplacement est lisible au sens du manifest (correction 2 du § 9) ; aucune copie | `noyau/resolution.tickets_du_projet` |
| D2 | **Le schéma de ticket existant reste la base** (champs exigés et champs lus par le moteur à leur place : `scope.paths`, `quality.required_gates`, `tools`, `mcp`, `execution.agent_id`) ; les blocs du modèle canonique § 3 sont des **extensions facultatives** ; un ticket qui porte `control_profile` est un **contrat d'exécution** | `ticket.schema.yaml` 1.1 |
| D3 | **Versions à trois niveaux** (correction 1) : le ticket exige ou référence (`agent.role.version`, `skills[].version`, `prompt.profile.version`, `control_profile.version`, `tool_versions` facultatif) ; le registre est la source de vérité ; la provenance enregistre la version réellement utilisée | résolution, provenance |
| D4 | **F-1 rôles** : fiches complétées (`domains` par projet, `workflows`, `skills`, `prompt` = consigne du rôle, `suspension`, `revocation` ; relecteur = `review.preferred_reviewer`, champ existant) ; version 0.2.0 | `registry/agents/` |
| D5 | **F-2 skills** : champ `instructions` (partie C du prompt) ; **10 skills au plus**, aucune sans besoin réel ; le premier lot attend la validation de la correspondance du projet (DC-6) | schéma `skill` ; registre encore vide |
| D6 | **F-3 outils** : versions figées dans les fiches (relevé du Bootstrap, majeure.mineure), `project` quand le projet la fixe, `*` = non épinglée (BLOCKED si exigée) ; disponibilité réelle vérifiée par l'inventaire du Bootstrap | `registry/tools/`, `factory ticket check` |
| D7 | **F-4 profil de prompt** : `registry/prompts/`, **un seul profil** `execution-standard` ; parties A à H (§ 4.2) ; ne donne aucun droit ; la consigne de sécurité du runtime vient après et prévaut | `registry/prompts/` |
| D8 | **F-5 profils de contrôle** : `policies/control-profiles.yaml` (AUTONOME, AUTONOME_RELU, C3, DECISION_HUMAINE, EXCEPTION_AMORCAGE) nomme et versionne ce que décident l'ADR-0021 et l'ADR-0020 ; un profil ne s'abaisse jamais | `policies/control-profiles.yaml` |
| D9 | **F-6 Policy Engine** : R40 (domaine du ticket parmi les domaines du rôle pour le projet), R41 (skill autorisée au rôle et approuvée) ; R08, R14, R15, R39 et le non-débordement inchangés ; droits = **intersection** | `noyau/politique.py`, `rule-catalog.yaml` |
| D10 | **F-7 contexte par sections** : `chemin#ancre`, `RG-xx` ou `CA-xx` dans la spécification déclarée par le manifest (`context.specification`), document entier ; lecture gouvernée ; empreinte de chaque section | `noyau/sections.py` |
| D11 | **F-8 provenance** : `ticket_version`, `role_version`, `skill_versions`, `tool_versions`, `prompt_profile`, `control_profile`, `policy_fingerprint`, `context`, `decisions`, instantané complet | `noyau/execution.py` |
| D12 | **Décisions humaines** (§ 2.11) : un prérequis humain devient une demande `factory decide request` ; le ticket la cite dans `dependencies.decisions` ; ouverte ou refusée = BLOCKED pour ce ticket seulement | `factory decide request` |
| D13 | **READY ou BLOCKED** : `factory ticket check PROJET [TICKET]`, lecture seule ; tout manque est BLOCKED avec sa cause ; `TO_COMPLETE` = inconnu, jamais inventé ; une approbation demandée par le Policy Engine (C3) est un **point humain au démarrage**, pas un blocage ; un ticket-contrat ne démarre que résolu READY, avec un prompt conforme à l'empreinte | `noyau/resolution.py`, `Plateforme.demarrer` |
| D14 | **F-10** (revue automatique des profils autonomes, correction 3) : **non mise en œuvre** tant que l'ADR-0021 n'est pas accepté ; d'ici là, la règle transitoire de chaque profil s'applique (revue humaine de l'ADR-0012) | après l'ADR-0021 |

Un profil de prompt, ses gabarits, les consignes des rôles, les skills et la politique des profils de contrôle ne
valent que s'ils figurent, à leur empreinte exacte, dans la **référence d'épinglage approuvée** par l'humain (W1).

## 4. Ce que cette décision ne fait pas

- Elle ne change aucune frontière (production, données sensibles, destruction hors ressource jetable, politique de
  sécurité, habilitations) et n'accorde aucun droit nouveau à un agent.
- Elle n'ajoute aucune validation humaine par ticket : l'humain n'intervient qu'aux points du profil de contrôle.
- Elle n'invente aucun contenu : ce qui n'est pas connu est `TO_COMPLETE`, donc bloquant.
- Elle ne fixe ni les domaines des rôles pour un projet, ni ses skills : ils suivent la validation de la
  correspondance des tickets du projet.

## 5. Normalisation des tickets d'un projet

Faite par la session qui possède les tickets (pour GMAO : la session GMAO, choix du Factory Owner), selon la
correspondance validée (étape C), puis vérifiée par `factory ticket check`. La Factory ne réécrit pas les tickets.

## 6. Risques

| Risque | Parade |
|---|---|
| Deux modèles qui divergent (Factory et projet) | un seul modèle de référence (§ 3) ; tout écart tranché par le Factory Owner |
| Références de sections cassées | ancre vérifiée à chaque `ticket check` ; section figée par son empreinte au démarrage |
| Prompt utilisé pour élargir des droits | aucun droit dans le prompt ; consigne de sécurité en dernier ; fichiers épinglés |
| Ticket qui élargit ses droits | intersection seulement ; budget seulement plus bas ; Policy Engine consulté tel quel |

## 7. Historique

- **v1 (19/10/2026)** : ticket « v2 » distinct, registres `registry/control-profiles/` et `registry/prompt-profiles/`
  (un profil par rôle), prérequis externes en texte. Construite sans connaître le modèle canonique validé le même
  jour dans le projet GMAO.
- **v2 (19/10/2026)** : alignement sur le modèle GMAO v1.0 (choix du Factory Owner) : schéma existant étendu,
  politique des profils de contrôle, un seul profil de prompt et une consigne par rôle, règles R40 et R41, contexte
  par sections, décisions `factory decide`. Le moteur de la v1 (verdict, instantané, épinglage, garde de
  l'exécution, versions des outils) est conservé.
