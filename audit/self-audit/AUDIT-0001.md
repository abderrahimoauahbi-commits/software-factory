# AUDIT-0001 — Auto-audit indépendant de la Factory v1 (jalon J12, guide §26)

| Champ | Valeur |
|---|---|
| Date | 2026-10-15 |
| Méthode | mesures relevées par script en lecture seule + exécution des suites de tests ; aucune modification |
| Réserve d'indépendance | auditeur = agent de construction (même modèle) : **ce n'est pas une revue indépendante** au sens du Playbook §12.3 ; une revue humaine ou par un modèle différent reste requise |

## Mesures

| Mesure | Valeur | Preuve |
|---|---|---|
| Tests | **212** (cœur 210, Bootstrap 2), tous verts | `python -P -m unittest discover -s core/tests -t core` ; idem `bootstrap/tests` |
| Registre | 114 objets VALID, 0 erreur ; aucun agent, MCP, modèle ni skill actif | `factory validate` |
| Contrôles du modèle de menaces | 27 VERIFIED (chacun cite un test existant), 4 DECLARED, 4 PLANNED, 11 ABSENT | `security/threats.yaml`, `test_modeles_securite.py` |
| Journal d'audit | chaîne intacte, ancrée dans chaque sauvegarde | `factory state check`, F-AUDIT |
| Reprise | exercice réel réussi : RTO 37,2 s (copie restaurée : `factory check` READY + suite du cœur verte) | `compliance/evidence/D2/drill-1.json` |
| Modules du cœur | 14 modules, aucun nom de projet / pile / fournisseur / IDE / MCP | `test_registre.py::CoeurGenerique` |

## Contrôles demandés par le guide §26

| Point | Verdict | Fondement |
|---|---|---|
| Caractère générique (projet) | **OK** | deux piles fictives, même cœur (`test_multiprojet.py`) ; test de généricité du cœur |
| Cohérence des schémas | **OK** | 29 schémas + cycles en tables ; validateur ; registre entièrement VALID |
| Cohérence des politiques | **OK, avec réserve** | politiques en données ; les extensions de schéma (ADR-0002, 0004, 0005) ne sont pas ratifiées en v1.1 |
| Sécurité par défaut | **OK au niveau du moteur** | refus par défaut testé ; **non imposé à l'agent réel** (pas de garde globale) |
| Transitions d'état | **OK** | contrat §22 testé, refus audités |
| Auditabilité | **OK, détection seulement** | chaîne d'empreintes + ancre externe ; pas d'immuabilité au niveau du système de fichiers |
| Preuves | **OK** | déclaration rejetée ; preuve = exécution réelle + artefact haché |
| Portes humaines | **ATTÉNUÉ** | liaison au contexte, pas d'héritage ; W1 fermée seulement dans les sessions de la Factory |
| Isolation | **OK au niveau du moteur** | projets, espaces isolés, liens et jonctions testés |
| Tests négatifs | **OK** | majorité des tests du Policy Engine et des FAT sont adversariaux |
| Documentation | **OK** | README, ADR-0001 à 0008, procédures, manuel d'exploitation testé |

## Ce qui est déclaré mais pas exécuté

1. **Le Policy Engine ne gouverne pas l'agent réel** : il décide quand on l'interroge ; aucun outil de l'agent
   ne passe par lui (seule la garde W1 est branchée, et seulement dans les sessions de la Factory).
2. **Aucune CI** : les Quality Gates sont déclarés, la « CI source de vérité » (règle 11) n'existe pas.
3. **Approbation humaine** : authentifiée par procédure (console interactive), pas cryptographiquement.
4. **Agents** : 15 rôles définis, aucun évalué ni habilité ; la phase 2 (évaluation) n'a pas commencé.
5. **Les 11 contrôles ABSENT** (règles de refus de l'agent, 7 MCP non approuvés actifs, scanner de secrets,
   CI, garde de déploiement, copie hors poste, données sensibles vers l'IA) dépendent de décisions humaines
   ou de configuration hors Factory.

## Hypothèses non testées

- Le format des réglages et des hooks de l'agent a été vérifié dans sa documentation, pas en session réelle
  ouverte dans FACTORY_ROOT (cette session est ouverte sur un autre dossier).
- La commande d'approbation n'a jamais été exécutée par un humain (seul son refus hors console est testé).
- Le Bootstrap n'a été exercé que sur un projet réel (GestionFil) ; aucun second projet réel de pile différente.
- La version 1.1 des Executable Schemas n'existe pas : les extensions de la Factory peuvent diverger.

## Verdict

**Factory v1 : construite et cohérente — NON opérationnelle pour exécuter des agents.**
Prête pour la revue humaine. Préalables à l'activation : décisions humaines listées dans
`docs/prompts/construction-factory-v1.md` §10, puis phase 2 (évaluation des agents, Lab, CI).
