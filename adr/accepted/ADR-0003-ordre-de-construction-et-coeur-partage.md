# ADR-0003 — Ordre de construction du guide et cœur partagé

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0003 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | Factory Owner, réponses écrites du 2026-10-15 : « suis le guide », « votre recommandation », « reconstruis les prompts jusqu'où le projet est exactement arrivé » (APR-0002) |
| Rédaction | agent de construction (Claude Opus 5.5) |

## Contexte

Le « Guide d'utilisation — AI Software Factory v1 » (v1.0) fixe un ordre de construction (§9) qui diffère
de celui de l'instruction de construction initiale, propose une arborescence différente de l'existant (§2),
et cite un prompt de construction et une spécification d'architecture qui n'ont jamais été transmis.

## Décisions

### G1 — Ordre de construction : celui du guide

Schémas → validateur → registre → **Policy Engine** → **State Engine** → Bootstrap CHECK → audit →
preuves → portes humaines → modèle de capacités → CLI → tests → documentation.
Le Bootstrap, construit avant le Policy Engine, est conservé ; il sera branché sur le Policy Engine dès
que celui-ci sera prêt (aujourd'hui il applique lui-même sa liste blanche).

### G2 — Arborescence : celle de l'existant, avec un cœur partagé

Les noms validés par l'ADR-0001 (`core/schemas/`, `policies/`, adaptateurs sous `bootstrap/`) sont gardés :
le guide demande de ne pas recréer une structure existante. Le code commun est extrait dans
`core/noyau/` pour servir le Bootstrap, le Policy Engine, le State Engine et la CLI :

| Avant | Après |
|---|---|
| `bootstrap/noyau/{modele, masquage, perimetre, commandes, registre}.py` | `core/noyau/` |
| `bootstrap/noyau/{controles, rapport}.py` | `bootstrap/check/` |
| `bootstrap/tests/{test_noyau, test_registre}.py` | `core/tests/` |

Correspondance avec les noms du guide : `schemas/` = `core/schemas/` ; `validation/` = `core/noyau/registre.py`
(validateur autonome au jalon J2) ; `policy/` = `policies/` ; `adapters/` = `bootstrap/adaptateurs/` ;
`tests/` = `core/tests/` et `bootstrap/tests/`.

### G3 — Premier commit

Reste un geste humain (guide §12). Tant qu'il n'a pas eu lieu, chaque rapport de jalon liste lui-même les
fichiers touchés, faute de `git diff`.

### G4 — Documents manquants

Le prompt de construction est **reconstruit** à partir de toutes les instructions reçues et de l'état réel
du projet : `docs/prompts/construction-factory-v1.md` (version 1.1). La spécification d'architecture n'est
pas reconstruite : ADR-0001 à ADR-0003 et les READMEs en tiennent lieu. Le texte source des Executable
Schemas reste à déposer par le Factory Owner dans `docs/schemas/` (une des copies reçues était tronquée).

## Conséquences

- Les tests se lancent par composant, en ne découvrant que les dossiers de tests :
  `python -P -m unittest discover -s core/tests -t core` et `-s bootstrap/tests -t bootstrap`.
- Le test de généricité couvre `core/noyau/` et `bootstrap/check/`.

## Preuve que J1 ne change aucun résultat

Empreinte du CHECK sur le projet pilote (identifiant, état, nature, gravité, criticité, phases bloquées de
chacun des 65 constats) capturée avant et après le déplacement : fichiers identiques octet pour octet.
28 tests verts (26 cœur, 2 bout en bout).
