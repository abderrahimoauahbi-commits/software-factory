# Bootstrap v1

Service permanent de contrôle (Playbook §7). **Mode CHECK seulement** ; SETUP et REPAIR sont « cible » et
refusent de s'exécuter.

```bash
python -P bootstrap/bootstrap.py check                       # la Factory seule
python -P bootstrap/bootstrap.py check --projet <id>         # la Factory et un projet enregistré
python -P bootstrap/bootstrap.py check --projet <id> --sans-rapport
python -P -m unittest discover -s core/tests -t core -p "test_*.py"
python -P -m unittest discover -s bootstrap/tests -t bootstrap -p "test_*.py"
```

`-P` et non `-I` : `-P` empêche le chargement de code depuis le dossier courant, mais garde le site
utilisateur de Python, où PyYAML est installé sur le poste actuel (fiche `registry/tools/pyyaml.yaml`).

Code de sortie : 0 READY, 1 DEGRADED, 2 BLOCKED, 3 mode non implémenté.

## Ce que garantit CHECK

| Garantie | Comment | Preuve |
|---|---|---|
| Aucune écriture hors `bootstrap/reports/` | seul `rapport.ecrire` écrit | `test_check_sans_ecriture_ni_secret` |
| Aucune commande hors liste blanche | `core/noyau/commandes.py` refuse **avant** exécution, sans shell | `test_commande_absente_refusee_sans_execution` |
| Aucun fichier sensible ouvert | `core/noyau/perimetre.py` refuse avant ouverture ; existence seule permise | `test_fichier_sensible_jamais_ouvert`, test de bout en bout |
| Aucun secret dans le rapport | masquage de toute sortie | `test_aucune_valeur_ne_survit` |
| Aucun serveur MCP démarré | inventaire par lecture des configurations seulement | liste blanche (`claude mcp list` interdite) |
| Aucune connexion réseau ni base | aucune commande de ce type dans la liste blanche | idem |
| Jamais READY si un critique n'est pas prouvé | `etat_phase` : critique UNKNOWN = BLOCKED | `test_critique_inconnu_bloque` |
| Cœur générique (Executable Schemas §36) | aucun nom de projet, d'outil ni de fournisseur dans `core/noyau/` et `check/` | `test_noyau_sans_nom_specifique` |

## Organisation

```text
bootstrap.py             point d'entrée
bootstrap.yaml           seuils, phases bloquées par domaine, motifs de règles risquées
check/                   mode CHECK
  controles.py           Factory → racines → capacités → inventaires → MCP → secrets → qualité → dépôt
  rapport.py             contrat de sortie universel, JSON et Markdown
adaptateurs/             seul endroit où un outil précis est connu ; choisi par la fiche du registre
tests/                   tests de bout en bout du CHECK

Cœur partagé (ADR-0003) : core/noyau/ — perimetre, commandes, registre, modele, masquage.
```

## Lecture du verdict

Le verdict est donné **par phase** (décision K5, ADR-0002) :

- `PROJECT_ANALYSIS` : lecture et analyse ; exige la Factory, ROOT_SCOPE et les capacités critiques.
- `EXECUTION` : agents qui écrivent ; exige en plus MCP approuvés, règles de refus, protection de la
  production, secrets hors de portée, gates de qualité.

Chaque constat porte sa nature de preuve : `VERIFIED` (observé), `DECLARED` (configuration seulement),
`UNVERIFIABLE` (hors de portée du CHECK), `HUMAN_REQUIRED`.
