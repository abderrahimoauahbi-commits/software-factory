# ADR-0020 — Exception d'amorçage : construction du banc d'évaluation des agents

| Champ | Valeur |
|---|---|
| Identifiant / version | ADR-0020, v1 du 19/10/2026 |
| Statut | **proposé** — à accepter par le Factory Owner |
| Décision d'origine | choix « B » du Factory Owner pour le point ORC-7 du projet GMAO, le 19/10/2026 (`GMAO/docs/04-decoupage-en-tickets.md` § 4) |
| Propriétaire | Factory Owner (humain) |
| Rédaction | session de conception du projet GMAO (rôles architect et planner), à la demande du Factory Owner |
| Complète | Playbook § 6.7 et § 12.6 (évaluation préalable des agents) ; ADR-0015 (plafond C2) ; ADR-0016 (agents non évalués en environnement jetable) ; ADR-0017 P9 (une exception n'est pas une modification de politique) |

## 1. Contexte

Un agent n'obtient un rôle et une criticité qu'après avoir réussi un jeu d'évaluation (Playbook § 12.6). Pour
évaluer les agents qui travailleront sur un nouveau projet, il faut un **banc** : un petit projet de référence à la
pile du projet, et les tests qui prouvent le résultat attendu de chaque tâche. Or aucun agent n'est encore habilité à
construire ce banc : c'est un **paradoxe d'amorçage**. Le projet GMAO, sans code existant, y est confronté le premier.

## 2. Décision

1. Le banc d'évaluation d'un projet peut être construit par la **session de conception de ce projet**, sous la
   **supervision directe du Factory Owner**, par exception aux règles d'évaluation préalable.
2. Règles obligatoires de l'exception :
   - banc **totalement isolé du produit** : dossier propre (pour la GMAO, `evaluation/`), aucune dépendance du
     produit vers le banc, aucune modification du produit ;
   - **aucune donnée réelle** ;
   - **aucune habilitation** accordée par l'exception, à aucune criticité ; en particulier, **aucune habilitation C3** ;
   - artefacts du banc **vérifiables et traçables** : versionnés dans Git, empreinte de chaque version, gates du banc
     exécutables et rejouables ;
   - le banc est **validé une fois, comme infrastructure d'évaluation**, par le Factory Owner ; il n'exige pas de
     validation humaine de chaque opération technique élémentaire.
3. L'exception ne vaut que pour le banc et ses suites d'évaluation ; elle ne s'étend ni au produit ni à d'autres
   tickets.

## 3. Conséquences

- Les campagnes d'évaluation peuvent commencer dès que le banc est validé.
- Toute modification ultérieure du banc suit la même exception et crée une nouvelle version, référencée par les
  rapports de campagne.

## 4. Risques

| Risque | Parade |
|---|---|
| Banc biaisé en faveur d'une solution | tâches de référence avec résultats prouvés par les tests ; pièges des trois types (Playbook § 12.6) ; revue du banc par le Factory Owner |
| Glissement de l'exception vers le produit | isolation obligatoire, vérifiée par le contrôle des chemins ; aucune dépendance du produit vers le banc |
