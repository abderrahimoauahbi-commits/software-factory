# ADR-0011 — R09 : le drapeau d'écriture d'un environnement ne gouverne pas les fichiers source

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0011 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | choix « Corriger le moteur (Recommandé) » du Factory Owner, 15/10/2026 |
| Rédaction | agent de construction — ticket T-FACTORY-017, distinct du ticket pilote |

## Contexte

Premier ticket pilote T-GF-001 : la première écriture réelle (un fichier de test dans l'espace isolé) a été
refusée par R09, « écriture interdite dans l'environnement LOCAL ». L'environnement LOCAL de GestionFil a
`write_allowed: false` pour protéger la base locale `gestionfil` (données possiblement réelles). Le moteur
appliquait ce drapeau à toute écriture, y compris aux fichiers source d'un espace isolé.

L'agent qui exécutait le ticket ne pouvait pas corriger lui-même la politique qui le bloquait (Executable Schemas
§8) : arrêt et décision humaine.

## Décision

`write_allowed` d'un environnement ne gouverne que les actions sur les **données et l'exécution**
(`environment_write_actions: [db_write, execute]` dans `policies/policy-engine.yaml`). Les fichiers source
(`write`, `commit`) sont gouvernés par `paths.write` ∩ périmètre du ticket ∩ espace isolé du même projet ∩
interdits et fichiers sensibles — règles inchangées et toujours testées.

## Conséquences

- La base locale reste protégée : `db_write` et `execute` en LOCAL non inscriptible → DENY (test
  `test_r09_la_base_locale_reste_protegee`).
- Un fichier hors chemins, hors ticket, hors espace isolé ou sensible reste refusé
  (`test_r09_fichier_de_l_espace_isole_gouverne_par_les_chemins`).
- Le pilote a rempli son rôle : il a révélé un défaut de sémantique que 234 tests n'avaient pas couvert.
