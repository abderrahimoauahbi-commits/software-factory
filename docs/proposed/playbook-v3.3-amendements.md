# Playbook v3.3 — amendements proposés au Playbook v3.2

| Champ | Valeur |
|---|---|
| Statut | **Adoptés le 17/10/2026** : texte consolidé déposé par le Factory Owner dans `docs/playbook/playbook-v3.3.md` (identique à `docs/proposed/playbook-v3.3.md`, sha256 `bb3ab348…`) ; ce document reste la trace des amendements |
| Rédaction | agent de construction, à la demande du Factory Owner (16/10/2026) |
| Base | `docs/playbook/playbook-v3.2.md` (sha256 `a98ab8c1…`), **non modifié** |
| Liée à | ADR-0016 (actif) ; ADR-0017 v5 (`adr/accepted/ADR-0017-gouvernance-autonomie.md`, gelé le 17/10/2026) |
| Adoption | revue humaine, puis dépôt par le Factory Owner d'un texte consolidé `docs/playbook/playbook-v3.3.md` dont la nouvelle empreinte est vérifiée par le Bootstrap. L'agent ne dépose ni ne modifie aucun texte normatif. |

**Texte consolidé** : `docs/proposed/playbook-v3.3.md` (39 amendements appliqués par remplacement exact sur le v3.2,
sha256 `bb3ab348…`), à relire et à déposer par le Factory Owner.

Ce document ne contient que des **amendements**, article par article. Le texte en *italique* est le texte
proposé ; « remplace » signifie que le passage cité du v3.2 est remplacé, « ajoute » qu'il est complété.

---

## §0.3 Ce qui change en v3.3 (ajoute un paragraphe)

*La v3.3 intègre l'autonomie bornée par capacités et environnements jetables (ADR-0016) et la gouvernance de
l'autonomie (ADR-0017) : identité issue du contexte authentifié ; décision humaine distincte de l'exécution ;
baux de capacités ; frontière d'exécution séparant l'executor de l'agent ; preuves produites par des
exécutants contrôlés ; épinglage des configurations et des skills ; racine de confiance détenue par le
Factory Owner ; distinction entre pouvoir technique et autorité de la Factory ; niveaux de disponibilité des
frontières ; phasage par frontières.*

*La reformulation des termes « worktree » et « branche » en capacités (ADR-0002 S6) est reportée à la v3.4 ; dans
la v3.3, ces termes désignent respectivement l'espace isolé (capacité ISOLATED_WORKSPACE) et la branche dédiée
(capacité SOURCE_CONTROL).* (correction C2 : report explicite)

## §0.4 Régime transitoire (ajoute) — correction B1

*1. **Principe.** Tant qu'un mécanisme introduit par la v3.3 n'a pas atteint le niveau d'application qu'il exige
(P13), la règle qui le prévoit est « cible » et le présent régime s'applique à sa place. Le régime transitoire ne
crée aucun droit : il désigne les mécanismes existants qui s'appliquent, ou il refuse.*

*2. **Décision humaine.** Les décisions humaines prévues au §3.4, les revues de code (§12) et les approbations
exigées par la politique sont prises par la commande humaine existante (ADR-0006, W1 ; ADR-0012), liée au
contexte exact par empreinte, selon les rôles et les durées de validité de la politique en vigueur. Une
approbation exprimée dans une conversation, un message ou un fichier écrit par un agent n'est jamais une
décision.*

*3. **Exécution humaine ; staging et production.** En staging et en production, seule l'exécution humaine est
permise ; l'exécution par la Factory y est indisponible (§8.3). La Factory peut préparer le plan, les commandes et
les contrôles ; elle n'exécute aucune action dans ces environnements.*

*4. **Budget et limites.** Le budget et le compteur de tentatives sont ceux de la plateforme d'exécution
existante (politique d'exécution) ; la Factory les déclare « non tenus par un service d'autorité ». Un budget
épuisé arrête l'exécution ; il n'ouvre jamais de droit.*

*5. **Épinglage et contexte.** Seuls les éléments dont l'empreinte est déjà vérifiée sont épinglés (au
16/10/2026 : le Playbook, au niveau IMPLEMENTED). Les autres (politiques, skills, réglages des runtimes, profil du
projet) sont déclarés « non épinglés », et aucune règle ne peut se prévaloir d'un épinglage qui n'existe pas. Les
règles encore présentes dans un fichier de contexte sont sans autorité (§16.3).*

*6. **Mécanismes non disponibles.** Une capacité dont la frontière préventive n'est pas appliquée reste refusée ;
en particulier, l'installation de paquets et l'accès réseau restent refusés aux agents tant que la frontière
réseau n'est pas appliquée de façon préventive. Exception : l'autonomie sous bail en environnement jetable déjà en
vigueur (ADR-0016), dans les seules limites de sa politique.*

*7. **Transparence.** La Factory publie, pour chaque mécanisme, son niveau (ARCHITECTURE_ONLY, IMPLEMENTED,
ENFORCED_DETECTIVE, ENFORCED_PREVENTIVE) et le niveau de confiance (TRUST_LEVEL) en vigueur. Elle n'annonce
aucune garantie non appliquée.*

*8. **Interdits.** Le régime transitoire ne peut ni justifier une action que la politique refuse, ni lever un
refus absolu, ni étendre l'ADR-0016 au-delà des environnements jetables.*

*9. **Fin.** Le régime prend fin mécanisme par mécanisme, lorsque le Factory Owner constate, preuves à l'appui
(annexe E de l'ADR-0017), que le niveau exigé est atteint ; la constatation est enregistrée. Le régime transitoire
dure au plus **30 jours** à compter de l'adoption humaine de la v3.3. À cette échéance, rien ne s'active
automatiquement : pour chaque mécanisme encore transitoire, le Factory Owner décide explicitement de le prouver et
de le promouvoir, de le maintenir indisponible, ou de prendre une nouvelle décision. Chaque revue périodique
(§15.5) réexamine les mécanismes encore transitoires.*

## §1 Principes fondamentaux

**P02** (remplace la deuxième phrase)

*Elle ne peut pas, seule : modifier l'architecture globale, changer une politique de sécurité critique,
supprimer ou modifier des données réelles, exécuter une migration destructive hors d'un environnement
jetable, publier en production, modifier des permissions critiques, ni valider son propre travail. Dans un
environnement jetable créé par la Factory et sous un bail valide, créer, modifier, casser, réinitialiser et
détruire des ressources de test est une activité normale de l'agent.*

**P09** (ajoute)

*La permission d'exécution résulte de la combinaison agent + rôle + projet + ticket + criticité +
environnement + ressource + outils + MCP, qualifiée par le Policy Engine, complétée d'une décision humaine
lorsque la politique l'exige, et matérialisée par un bail de capacités borné dans le temps et le périmètre.*

**P10** (ajoute)

*Fait foi le résultat produit par un exécutant contrôlé par la Factory (CI, exécutant de quality gates,
executor), rattaché à l'exécution par une empreinte inscrite au journal d'autorité.*

**Nouveaux principes P11 à P15** (ajoute) ; l’introduction du §1 « Dix principes » devient « Quinze principes » (correction NE15 : numérotation sans trou)

- ***P11 — La puissance est donnée dans la frontière.** La Factory maximise l'autonomie de l'IA à
  l'intérieur d'un environnement jetable et d'un bail, et minimise sa capacité à franchir ces frontières.*
- ***P12 — Décider n'est pas exécuter.** Une décision humaine peut confier l'exécution à la Factory ou la
  garder ; dans les deux cas, le résultat est vérifié par les contrôles du plan approuvé.*
- ***P13 — Une frontière n'existe que si elle est appliquée.** Une capacité n'est disponible que lorsque son
  application est démontrée au niveau qu'elle exige : détectif (`ENFORCED_DETECTIVE`) ou préventif
  (`ENFORCED_PREVENTIVE`). Une capacité qui exige une frontière préventive n'est jamais disponible sur la
  seule base d'une détection.*
- ***P14 — Toute autorité remonte à une racine de confiance détenue par un humain.** Le pouvoir technique sur
  le système, y compris celui d'un administrateur, n'est jamais une autorité de la Factory ; exercé hors de
  la procédure de maintenance de confiance, il est traité comme une compromission potentielle.*
- ***P15 — L’affichage n'est pas l'autorisation.** Une interface (navigateur, CLI, intégration d'IDE)
  présente une décision ; la décision, sa vérification et son enregistrement appartiennent au service
  d'autorité.*

## §2.5 Architecture multi-projets (ajoute) — correction C8

*… Chaque projet conserve ses configurations, permissions, secrets, environnements et son manifest ; les éléments
de sécurité de cette configuration ne font autorité qu'après relecture et épinglage (§7.5).*

## §3.2 Décisions et circuit d'approbation, tableau RACI (intitulés de lignes, remplace) — correction NE16

*« Migration destructive » devient « Migration destructive de données réelles » ; « Suppression de données » devient
« Suppression de données réelles ».*

## §3.3 Délais et escalade (point 1, remplace) — correction C3

*1. **Délai de réponse** à une demande de décision, par criticité : C3 sous 2 jours ouvrés, C4 sous 1 jour ouvré
(valeurs par défaut à ajuster par projet). Il est distinct de la **validité d'une décision**, fixée par la
politique.*

## §3.4 Moments où l'humain intervient obligatoirement (remplace la liste)

*L'humain intervient obligatoirement, par le Decision Center, lorsque la politique qualifie l'action
d'APPROVAL_REQUIRED, ou lorsqu'une exception est demandée sur une règle qui la permet : écriture ou
suppression de données réelles ; migration destructive hors environnement jetable ; mise en production ;
sécurité critique ou politique d'autorisation ; changement architectural majeur ; données sensibles ; action
métier irréversible ; ambiguïté métier importante. Un échec de build, de test, de migration ou de seeder dans
un environnement jetable n'est jamais une raison d'intervention humaine : il se reprend dans le budget. Une
décision humaine n'agit que dans l'espace que la politique lui ouvre et ne franchit jamais un refus absolu.*

## §6.7 Agents et §12.6 Évaluation des agents (ajoute)

*« Habilitation » désigne le droit d'agir hors d'un environnement jetable contrôlé. L'autonomie d'un agent
sous bail dans un environnement explicitement jetable n'est pas une habilitation générale : elle reste
bornée par l'environnement, la capacité, le bail, le périmètre, le budget, la politique et l'identité des
ressources.*

## §6.8 Skills, §6.9 MCP, §10.2 Provenance (ajoute)

*Une skill, un MCP, un outil ou un modèle n'est chargé dans un runtime gouverné que si son empreinte
réellement chargée correspond à celle épinglée dans le Trust Store ; la vérification est faite hors du
processus agent. La provenance d'un changement inclut les empreintes des skills et des prompts utilisés.*

## §7.5 Project Manifest (ajoute en tête) — correction A6

*Le manifest du projet est le profil canonique `.factory/project.yaml`, dans le dépôt du projet. Ses sections qui
peuvent augmenter l'autorité (environnements, agents, outils, sécurité, autonomie, bases de données, ressources) ne
prennent effet qu'après relecture et épinglage ; une modification du dépôt n'augmente jamais à elle seule les
droits du projet. Pendant le régime transitoire (§0.4), le manifest `factory.yaml` à la racine du projet reste
lu.*

## §8.1 Pipeline d'exécution d'un ticket (étape 5, remplace) — correction C1

*5. **Création du sandbox** : espace isolé, branche dédiée, secrets limités, réseau selon §8.5.*

## §8.3 Isolation (remplace la dernière phrase)

*Pour C3 et C4, et pour toute action en staging ou en production, l'exécution passe par un executor séparé
de l'agent, dans un autre contexte de sécurité. L'executor ne reçoit qu'une référence de plan approuvé, son
empreinte et un contexte d'exécution ; il ne reçoit jamais de commande ni de shell fournis par l'agent ; il
récupère les artefacts depuis un store protégé par leur empreinte et ne choisit qu'entre les opérations
prévues par le plan. L'agent ne détient jamais les identifiants de ces environnements. Tant que cette
frontière n'est pas appliquée de façon préventive, l'exécution par la Factory y est indisponible et
l'exécution reste humaine.*

## §8.5 Réseau (remplace)

*Le sandbox n'a pas d'accès sortant par défaut. L'accès sortant est une capacité nommée (documentation,
registre de paquets, fournisseur Git, registre de modèles, registre MCP), limitée en destination, protocole,
port, durée, volume et mission. Un registre inconnu est refusé. Tant qu'aucun mécanisme technique n'applique
ces limites, la politique réseau est déclarée déclarative.*

## §8.6 Budgets et limites (remplace la ligne « Nombre de tentatives »)

*| Tentatives | Exécution et mission | Budget unique tenu par le service d'autorité ; un échec récupérable se
reprend sans intervention humaine ; budget épuisé : arrêt (BUDGET_STOP), puis escalade dans la hiérarchie
d'agents, puis décision humaine seulement si une frontière est en jeu |*

## §9.1 Profils et §9.2 Matrice de pouvoirs (remplace la définition de C4 et le sens de « Humain »)

*C4 : l'agent prépare ; un humain décide ; l'exécution est humaine, ou confiée à un executor déterministe
qui rejoue exactement le plan approuvé. Dans la matrice, « Humain » signifie : décision humaine signée par
une identité certifiée.*

## §9.1 Profils (ligne C4, colonne « Exemples », remplace) — correction A1

*Production, migration destructive de données réelles, suppression ou changement massif de données réelles,
déploiement majeur. Les ressources d'un environnement jetable créé par la Factory, utilisées sous un bail valide,
ne relèvent pas de C4 du seul fait d'une opération destructive.*

## §9.2 Matrice de pouvoirs (lignes) — corrections A2 et C7

- *(remplace l'intitulé de ligne)* « Suppression de données » devient *« Suppression de données réelles »*.
- *(ajoute une ligne)* *| Ressources d'un environnement jetable sous bail (créer, modifier, casser, réinitialiser,
  supprimer) | Non | Oui (bail) | Oui (bail) | Oui (bail) | — |*
- *(remplace l'intitulé de ligne)* « Écriture base de données de développement » devient *« Écriture base de
  données de développement jetable ou désignée par le projet »*, avec la note : *« Une politique de projet peut
  restreindre davantage (par exemple une base locale contenant des données réelles). »*

## §9.6 Conditions d'arrêt (remplace « échec répété, migration dangereuse »)

*… budget épuisé, migration dangereuse hors environnement jetable, …*

## §10.1 Modèle de menaces (ligne Exfiltration, remplace) — correction NE16

*« Réseau filtré » devient « Réseau filtré (cible, voir §8.5) ».*

## §12 Qualité (introduction, remplace la première phrase) — correction B2

*La qualité repose sur des preuves : le résultat produit par un exécutant contrôlé par la Factory (la CI en est un)
est la source de vérité, pas le rapport de l'agent.*

## §13.1 Base de données (dernière phrase, remplace) — correction A3

*Une migration destructive de données réelles, hors environnement jetable (C4), exige une sauvegarde restaurée et
testée, un plan de rollback et une décision humaine. Dans un environnement jetable sous bail, une migration peut
être appliquée, cassée, annulée et rejouée sans décision humaine.*

## §14.4 Sauvegarde et reprise des projets (remplace) — correction NE16

*Un test de restauration est exécuté à fréquence fixe et avant chaque migration destructive de données réelles.*

## §16.2 Structure d'un projet (ligne de l'arborescence, remplace) — correction A6

*`├── .factory/project.yaml   (profil du projet ; remplace factory.yaml, voir §7.5)`* — la ligne
`AGENT_CONTEXT.md` reste inchangée.

## §16.3 Contexte agent (remplace) — correction A5

*Le contexte stable destiné aux agents (présentation du projet, commandes, usages, renvois vers les règles) est
tenu dans un fichier de contexte générique, `AGENT_CONTEXT.md`, que chaque runtime peut lire sous son propre nom ;
ce fichier reste la source unique de ce contexte, pour préserver la neutralité vis-à-vis du fournisseur d'IA. Il ne
contient aucune règle d'autorisation, de permission ou de sécurité : ces règles sont définies par le catalogue des
règles et les politiques de la Factory, qui prévalent sur tout fichier de contexte en cas d'écart. Sur décision du
Factory Owner, un dépôt peut tenir ce contexte dans le fichier propre à son runtime (par exemple `CLAUDE.md`) ;
l'écart à la neutralité est alors déclaré dans ce fichier, et la règle d'absence d'autorité s'applique à
l'identique.* (Le dépôt de la Factory utilise cette option depuis le 16/10/2026.)

## §17 Feuille de route (remplace le tableau des phases)

*La mise en œuvre suit des phases de frontières ; chaque frontière n'est déclarée disponible que lorsque son
application est démontrée au niveau qu'elle exige.*

| Phase | Frontières visées |
|---|---|
| *G1 Fondations* | *identité, stores, catalogue des règles, épinglage, baux authentifiés, journal d'autorité, racine de confiance* |
| *G2 Décision* | *Decision Center, exécution humaine, exceptions bornées* |
| *G3 Frontière d'exécution* | *service d'autorité isolé, executor séparé* |
| *G4 Habilitation* | *évaluation des agents, modèles approuvés* |
| *G5 Échelle* | *orchestration, Twin, mémoire, découverte, réseau appliqué* |
| *G6 Multi-projets* | *second projet sur une autre pile* |

*L'autonomie sous bail en environnement jetable est disponible dès G1 et ne constitue pas une habilitation.*

**§17.1** (ajoute) — correction C6

*Le MVP (phase 1) est atteint (bilan du pilote du 15/10/2026). La suite relève du phasage par frontières (§17) ; ce
paragraphe est conservé à titre historique.*

**§17.2 règle 1** (remplace)

*Une frontière n'est déclarée disponible que lorsque son application est démontrée ; une phase peut
commencer avant la clôture de la précédente si elle ne dépend pas de frontières encore indisponibles.*

## §18 Règles absolues

**Règle 11** (remplace) : *Un exécutant contrôlé par la Factory est la source de vérité des Quality Gates.*

**Règle 19** (remplace) : *Tout agent est évalué avant d'être habilité hors d'un environnement jetable.*

**Nouvelles règles** (ajoute) :

25. *Une décision humaine ne franchit jamais un refus absolu.*
26. *Un plan modifié matériellement exige une nouvelle décision ; la non-matérialité est définie par la règle,
    jamais par l'agent.*
27. *Une capacité n'est disponible que si son application est prouvée au niveau qu'elle exige.*
28. *Toute autorité remonte à une racine de confiance détenue par un humain ; un pouvoir technique sur le
    système n'est pas une autorité de la Factory.*

---

## Executable Schemas v1.1 (à produire séparément)

Le texte source des Executable Schemas v1.0 n'est pas déposé dans le dépôt ; seule sa forme exécutable
(`core/schemas/`) existe. Deltas à intégrer dans une v1.1, après dépôt du texte source par le Factory Owner :

- §24 : arrêt après 3 échecs remplacé par le budget unique ;
- §34 : production refusée à un agent ; APPROVAL_REQUIRED pour un executor quand la frontière d'exécution est
  appliquée de façon préventive ;
- énumération DECISION : ALLOW, APPROVAL_REQUIRED, DENY_BY_POLICY, DENY_ABSOLUTE (avec correspondance) ;
- énumération ENVIRONMENT : ajout de LOCAL_SANDBOX, LOCAL_TEST, CI, DEV_SHARED ;
- `execution.schema` : `budget.max_attempts` remplacé par le budget global ;
- cycles de vie : décision, bail, exécution par executor, exception ;
- enveloppe de preuve versionnée et référence de l'exécutant ;
- `trust.yaml` : type d'acteur `executor`, sans verbe de pouvoir ;
- versions de schéma de l'ADR-0017 §3.3 ;
- niveaux de disponibilité ARCHITECTURE_ONLY, IMPLEMENTED, ENFORCED_DETECTIVE, ENFORCED_PREVENTIVE.

**Report explicite de la v1.1 (NE7, NE8 ; recommandation appliquée à la demande du Factory Owner, 16/10/2026).**
*La v3.3 peut être adoptée avant les Executable Schemas v1.1. Jusqu'à la v1.1, la forme exécutable v1.0
(`core/schemas/`) reste en vigueur ; en cas d'écart avec la v3.3, la v3.3 prévaut (rang supérieur). Écarts connus,
annotés dans `core/schemas/` sans modification de leur texte : NE1 (borne `max_attempts` à 3, à lire dans la
politique d'exécution) ; NE8 (règles « DELETE = autorisation humaine C4 », « pas de DELETE sans politique C4
explicite », « opération destructive = C4 », à lire « hors environnement jetable »).* La v1.1 sera rédigée après le
dépôt du texte source v1.0 par le Factory Owner.

**Correction B9 : bloquée par NE7.** Le texte source des Executable Schemas v1.0 n'est pas présent dans le dépôt
(`docs/normative/` ne contient que son README ; ADR-0005 M4). La liste ci-dessus ne peut donc pas être complétée
comme amendement d'un texte absent, et aucun texte v1.0 n'est reconstruit. Restent à intégrer après le dépôt par le
Factory Owner : les extensions en attente de l'ADR-0002 (`EVIDENCE_KIND`, `SEVERITY`, schémas `capability` et
`adapter`, champs de `tool`, `quality.gates`, état d'entrée des skills externes), de l'ADR-0004 (verdicts et clés
`references`, `mandatory`, `limits`, `version_fields`) et de l'ADR-0005 (M1, M2) ; la correspondance
`EVIDENCE_KIND` → ADR-0017 §3.4 ; la limite `budget.max_attempts` (NE1).
