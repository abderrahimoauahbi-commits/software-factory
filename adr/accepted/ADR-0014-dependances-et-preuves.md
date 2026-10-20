# ADR-0014 — Dépendances copiées dans l'espace isolé ; tickets validés ; preuve des changements

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0014 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | choix « T-FACTORY-020 d'abord (Recommandé) » puis « Copie par espace (Recommandé) », 15/10/2026 |
| Rédaction | agent de construction — ticket T-FACTORY-020 |

## Contexte

Trois défauts relevés pendant les tickets pilotes T-GF-002 à T-GF-007 :

1. **Tickets jamais validés par le registre** (VÉRIFIÉ) : `factory.py validate` ne chargeait pas
   `registry/projects/*/tickets/`, et le schéma des tickets ne déclarait aucune référence. `workflow_id: bugfix`
   (au lieu de `bug-fix`) passait VALID.
2. **Preuve de diff vide** pour un fichier nouveau : `git diff --stat` ignore les fichiers non suivis.
3. **Aucune dépendance dans l'espace isolé** : une extraction ne contient pas `node_modules` ; seul le code sans
   dépendance pouvait être testé ; build, lint et écrans étaient impossibles.

## Décision

1. Le registre charge et valide les tickets de chaque projet (identité = nom de fichier, `project_id` = dossier).
   Le schéma des tickets déclare `workflow_id → workflows`, `project_id → projects`,
   `dependencies.tickets[] → tickets`.
2. À la clôture, la plateforme ajoute une preuve ARTIFACT `<exécution>-changes` : chaque fichier de l'agent,
   « modifié +a -b » (opération `diff_numstat`), « nouveau N octets » ou « supprimé », et les différences d'extraction
   écartées. Un fichier nouveau est décrit par sa taille, jamais par son contenu : il n'a pas encore passé le contrôle
   de périmètre et pourrait être sensible.
3. **Copie par espace**, choisie par le Factory Owner contre la jonction (risque d'écriture à travers le lien et de
   suppression du dossier du projet) et contre `npm ci` hors ligne (installation). La carte du projet déclare
   `workspace.copy_from_root` ; à la création de l'espace, la plateforme copie chaque dossier depuis la racine du
   projet. Refus : chemin non relatif, sensible ou interdit ; source absente ; destination existante ; dossier que
   l'outil de version ne dit pas ignoré (il deviendrait un changement — la copie est alors retirée).

## Conséquences

- Rien n'est installé, aucun réseau. Ce que les gates écrivent dans la copie (caches, build) reste dans l'espace ;
  retirer l'espace ne touche jamais le projet.
- Coût : disque (~271 Mo pour GestionFil) et temps de copie à chaque ticket.
- Les dépendances sont celles du dépôt du projet au moment de la copie, pas celles du `package-lock.json` de la base :
  si le propriétaire met à jour ses dépendances sans commit, l'espace les reçoit telles quelles (NON VÉRIFIABLE par la
  plateforme ; à surveiller).
- Les gates `lint` et `typecheck` du manifest deviennent exécutables dans l'espace : un ticket peut les exiger
  (`quality.required_gates`).
