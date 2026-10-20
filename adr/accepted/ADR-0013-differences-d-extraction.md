# ADR-0013 — Différences d'extraction et sorties des gates : relevées, montrées, figées

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0013 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | choix « Corriger la Factory (Recommandé) » du Factory Owner, 15/10/2026 |
| Rédaction | agent de construction — ticket T-FACTORY-019, distinct du ticket pilote |

## Contexte

Ticket pilote T-GF-002 : clôture refusée, `SCOPE_VIOLATION : db/pg/socle/schema.sql`, fichier que l'agent n'a pas
touché. Cause (VÉRIFIÉ) : `schema.sql` a été commité en CRLF (`70b2f7f`, 09/10) puis `.gitattributes` lui a imposé
`eol=lf` (`4602355`, 10/10) sans renormalisation ; selon les horodatages de l'extraction, git relit le fichier et le
voit modifié. L'espace de T-GF-001 était propre, celui de T-GF-002 non : le symptôme n'est pas déterministe.

En corrigeant, un second cas est apparu dans les tests : les gates produisent eux-mêmes des fichiers (`__pycache__`).
Ils apparaissaient comme « nouveaux fichiers » dans le diff relu par l'humain (T-FACTORY-018).

La plateforme ne pouvait pas distinguer ces faux changements d'un débordement réel : elle a refusé, à raison. Corriger
ce contrôle au profit du ticket qu'il bloquait était un conflit d'intérêts : décision humaine.

## Décision

1. **Différences d'extraction** : à la création de l'espace isolé, avant tout travail de l'agent, la plateforme relève
   les fichiers déjà différents de la base, avec l'empreinte SHA-256 de leur contenu
   (`isolation.extraction_differences`, aussi dans `context.json`).
2. À la clôture, un tel fichier **dont l'empreinte est inchangée** n'est pas un changement de l'agent
   (`extraction_unchanged`). **Dès que son contenu bouge**, il redevient un changement soumis au périmètre.
3. **Sorties des gates** : après les gates, la plateforme relève l'état exact de l'espace (fichiers et empreintes,
   `post_gates`). Les fichiers apparus pendant les gates sont listés à part (`gate_outputs`).
4. **Revue** : le diff relu ne contient que les fichiers de l'agent (opération `diff_file`, un fichier à la fois). La
   demande liste, avec leurs empreintes, les différences d'extraction écartées et les sorties des gates : rien n'est
   caché. Si l'espace a bougé depuis la clôture — n'importe quel fichier — la revue est impossible.

## Conséquences

- Le contrôle de périmètre n'est pas affaibli : seul un contenu identique à celui relevé avant le travail de l'agent
  est écarté (`test_difference_retouchee_par_l_agent`).
- La revue est plus stricte qu'avant : un fichier ajouté ou une sortie de gate modifiée après la clôture l'empêche.
- La commande humaine affiche les fichiers écartés et les sorties des gates (« à ne pas commiter »).
- Hygiène de GestionFil (hors Factory, décision du propriétaire) : `git add --renormalize db/pg/socle/schema.sql`
  ferait disparaître la cause.
