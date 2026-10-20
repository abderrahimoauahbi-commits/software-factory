# ADR-0019 — Installation assistée d'un projet (« équiper » un projet rattaché)

| Champ | Valeur |
|---|---|
| Identifiant / version | ADR-0019, v1 du 19/10/2026 |
| Statut | **proposé** — conception sur le papier, demandée par le Factory Owner ; **construction après la validation de l'architecture technique de GMAO**, premier cas réel |
| Complète | ADR-0001 (le manifest vit dans le projet) ; `factory project init` (rattachement) ; ADR-0017 (frontières, décisions humaines) ; décision B8 (installation de paquets et réseau refusés aux agents) |
| Propriétaire | Factory Owner (humain) |

## 1. Contexte

`factory project init` rattache un projet : un manifest minimal, un contexte de travail, des gardes, une carte au
registre. Il manque l'étape qui **équipe** le projet une fois sa pile choisie : les outils, les skills, les MCP, les
agents et les règles propres au projet. Aujourd'hui :

- le **catalogue** de la Factory (`registry/`) définit agents, outils, capacités, MCP, modèles, workflows ; le
  manifest du projet n'en fait qu'une **sélection** ; un élément inconnu du catalogue est refusé ;
- le catalogue des **skills** est vide ; les skills de l'utilisateur ne sont pas connues de la Factory ;
- le Bootstrap **détecte** les outils présents (version, module, paquet, extension, MCP configurés) mais n'installe
  rien ; l'installation est **interdite aux agents** (B8) ;
- il n'existe aucune **recherche** de plugins ou de MCP (« découverte », phase G5).

## 2. Décision proposée

Une commande **`factory project equip <id>`**, menée **étape par étape**, chaque étape s'arrêtant sur une décision du
Factory Owner, avec ce que fait chaque commande expliqué en clair (même générateur que les approbations,
`noyau/explication`). Point de départ : l'**architecture technique validée** du projet (la pile choisie).

| Étape | Ce que fait la Factory | Décision humaine |
|---|---|---|
| **E1. Besoins** | traduit l'architecture validée en **capacités** nécessaires (langage, build, test, lint, migration de base, mobile, QR, notifications…), chacune justifiée par un passage de l'architecture | valider la liste |
| **E2. Catalogue** | pour chaque capacité, cherche l'outil dans le catalogue (lien capacité → outils existant) ; s'il manque, **propose une fiche d'outil** au statut `DISCOVERED` (rien n'est actif) | approuver ou refuser chaque fiche nouvelle ; un outil approuvé passe `APPROVED` |
| **E3. Poste** | le Bootstrap vérifie la présence et la version de chaque outil requis ; pour ce qui manque, prépare un **plan d'installation** (`factory plan`) : commandes exactes, source, version, effet, retour arrière | approuver le plan, puis **l'exécuter soi-même** (`factory plan execute`) ; l'agent n'installe jamais |
| **E4. Skills et MCP** | propose les skills et MCP utiles à la pile, depuis ce qui est **déjà présent** sur le poste (inventaire du Bootstrap) ; tout candidat entre au catalogue `DRAFT`/`DISCOVERED`, **refusé par défaut** aux agents ; épinglage de ceux qui seront approuvés | approuver chacun, et son périmètre (projets, agents) |
| **E5. Agents** | propose les rôles nécessaires au projet (parmi les 15) et prépare leurs **suites d'examen** pour cette pile (G4) | choisir les rôles ; approuver les habilitations provisoires ; lancer les campagnes |
| **E6. Manifest** | complète `factory.yaml` : pile, chemins de lecture et d'écriture (statut `PROPOSED` → validé), gates de qualité (commandes et répertoires), agents, outils, skills, MCP ; le **vérifie** par le registre ; présente l'écart avec la version précédente | approuver le manifest : c'est l'acte qui **donne des droits** aux agents sur le projet |

Chaque étape est **rejouable** et **traçable** au journal ; elle n'écrase jamais une décision précédente sans la
montrer.

## 3. Recherche de plugins et de MCP

Le réseau est refusé aux agents (B8). En V1 de cette commande :
- la recherche porte sur ce qui est **déjà installé** sur le poste (inventaire du Bootstrap) ;
- l'agent peut **suggérer** des candidats connus, marqués **« non vérifié »** (source, éditeur, licence, permissions
  demandées), sans rien télécharger ;
- toute recherche ou installation en ligne est un acte humain (plan d'exécution humaine), jusqu'à ce qu'une frontière
  réseau existe (G5).

## 4. Mise à jour d'un projet rattaché (`factory project sync`)

Les fichiers posés par `init` (contexte, gardes) ne suivent pas seuls l'évolution de la Factory. Proposition :
`factory project sync <id>` régénère **seulement les parties gérées par la Factory** (balisées dans les fichiers),
montre la différence, et ne touche jamais au contenu propre du projet ; acte humain.

## 5. Ce que cette décision ne fait pas

- Aucune installation par un agent ; aucun téléchargement automatique.
- Aucun outil, skill, MCP ou agent actif sans approbation explicite.
- Aucun droit d'écriture accordé sur le projet sans approbation du manifest (E6).

## 6. Décisions demandées au Factory Owner

1. Accepter le principe des six étapes E1 à E6 et l'ordre.
2. Recherche de plugins limitée au poste et aux suggestions « non vérifiées » tant que G5 n'existe pas : d'accord ?
3. `factory project sync` : à construire en même temps ?
4. Construction : après la validation de l'architecture technique de GMAO, et essai direct sur GMAO.
