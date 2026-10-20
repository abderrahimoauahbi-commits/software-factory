# ADR-0017 — Gouvernance de l'autonomie : identité, décision, bail, frontière, preuve, racine de confiance

| Champ | Valeur |
|---|---|
| Identifiant / version | ADR-0017, **v5 révisé le 16/10/2026** (version alignée finale proposée ; révision : corrections B4, B5, B6, C5 et NE2 à NE5 du plan de correction validé par le Factory Owner) |
| Statut | **Accepté — gelé le 17/10/2026** par le Factory Owner (instruction explicite en conversation), après adoption du Playbook v3.3 déposé par lui dans `docs/playbook/` ; gel non attesté par la commande humaine W1 (journal d'audit) |
| Chemin vers le gel | revue humaine → adoption du Playbook v3.3 (17/10/2026, `docs/playbook/playbook-v3.3.md`) → **gel normatif** (17/10/2026) : exécuté |
| Date | 2026-10-16 |
| Propriétaire | Factory Owner (humain) |
| Rédaction | agent de construction, à la demande du Factory Owner ; aucun code, aucun fichier normatif, aucun réglage modifié |
| Sources | Vision fondamentale (version de référence) ; Master Evolution Prompt v4 ; AUDIT-0002 ; ADR-0016 ; revues v1 à v4 du 16/10/2026 |
| Modifie (à l'adoption) | ADR-0001 §1 (D29) · ADR-0002 K6 (D37) · ADR-0006 J4 point 1 (qualifications, D11), J4 point 4 (D38 et réseau D33), W1 (D31), D2 (D37) · ADR-0012 (canal, D31 ; la revue humaine est maintenue, voir D31) · ADR-0016 (réseau, `PACKAGE_INSTALL`, caractère jetable des profils ; R09 complétée pour l'executor) |
| Hiérarchie | Subordonné au Playbook v3.3 ; les règles dont la frontière n'est pas encore construite restent « cible » (Playbook §17.2 règle 4) et leur niveau réel est celui de l'annexe D |

## 1. Contexte

L'autonomie en environnement jetable existe et est prouvée (ADR-0016, jalon E1). Il manque une gouvernance
appliquée par des **frontières techniques** : identité, décision, bail, preuve, épinglage, explicabilité,
maintenance sûre et racine de confiance. L'audit de cohérence a relevé six trous structurels (S1 à S6) qui
doivent être fermés avant le Decision Center.

## 2. Principes (normatifs)

| N° | Principe |
|---|---|
| P1 | **Puissance dans la frontière.** En LOCAL_SANDBOX, LOCAL_TEST et CI, sous un bail valide, un agent crée, supprime et réinitialise des bases de test, modifie le schéma, lance, casse et annule des migrations, recrée l'environnement, installe des dépendances depuis un registre autorisé, teste, modifie son code, crée des worktrees, lance plusieurs agents et recommence. C'est l'objectif du système. La sécurité vient de : environnement sûr + capacité bornée + bail valide + audit + preuve. |
| P2 | Identité ≠ Rôle ≠ Autorité ≠ Capacité ≠ Bail. |
| P3 | Prompt, Skill, Contrat d'agent, Plan, Approbation, Bail : aucun n'est une permission permanente. |
| P4 | Autorité d'exécution = qualification par la Politique + Décision (si requise) + Bail + Environnement + Périmètre. |
| P5 | Une déclaration d'agent n'est pas une preuve. |
| P6 | Plan approuvé ≠ plan courant. |
| P7 | Être présent dans un dépôt ne donne pas la confiance. |
| P8 | Décision humaine ≠ exécution humaine. |
| P9 | Une exception n'est pas une modification de politique. |
| P10 | Le backend fait autorité pour le métier ; le Policy Engine pour l'exécution. |
| P11 | **Chaîne : Policy Engine → [Decision Center, seulement si APPROVAL_REQUIRED] → Capability Manager → Executor ou Agent.** Le Capability Manager ne crée jamais d'autorité : il matérialise celle de la Policy, ou d'une décision valide dans le cadre permis par la Policy. Le bail est un jeton d'exécution borné et dérivé. Monotonie de restriction : tout composant peut refuser, suspendre, arrêter ou demander une révocation. |
| P12 | Le niveau de confiance (`TRUST_LEVEL`) et l'état réel de chaque frontière sont toujours annoncés. |
| P13 | Tout contenu externe est une donnée. |
| P14 | Une décision humaine agit seulement dans l'espace que la politique ouvre ; jamais au-delà d'un DENY_ABSOLUTE. |
| P15 | Identité déclarée ≠ résolue ≠ chargée ou exécutée. |
| P16 | Un executor rejoue un plan, il n'improvise pas ; une reprise du Supervisor n'est pas une montée en autorité. |
| P17 | Une capacité ou une frontière n'est disponible qu'au niveau d'application qu'elle exige (§3.5) : une frontière préventive n'est disponible qu'en `ENFORCED_PREVENTIVE`. |
| P18 | Une politique devenue plus restrictive peut invalider l'existant ; devenue plus permissive, elle n'élargit jamais rétroactivement. Droit effectif = intersection du bail et de la politique en vigueur. |
| P19 | Contrôle applicatif ≠ frontière d'exécution. |
| P20 | Toute garantie se déclare par rapport à un TCB explicitement défini (D42). Aucun niveau de confiance ne signifie « sécurité absolue ». |
| P21 | La lignée d'une décision est permanente. |
| **P22** | **Pouvoir technique ≠ autorité Factory.** Le pouvoir de modifier le système (administrateur du système d'exploitation, accès au disque) n'est jamais une autorité de décision de la Factory. L'autorité Factory ne vient que de la chaîne de signatures issue de la racine de confiance (D36). |

## 3. Vocabulaire et modèles

### 3.1 Les cinq actes

| Acte | Qui | Exemple |
|---|---|---|
| Qualification de politique | Policy Engine | ALLOW, APPROVAL_REQUIRED, DENY_BY_POLICY, DENY_ABSOLUTE |
| Décision d'autorité humaine | Humain détenteur d'une identité certifiée (D36), par le Decision Center, seulement si la politique l'exige | FACTORY_EXECUTE, HUMAN_EXECUTE, REJECT |
| Matérialisation | Capability Manager | émission d'un bail |
| Décision technique d'exécution | Agent dans son bail ; executor seulement entre les opérations prévues par le plan | choix d'implémentation |
| Exécution | Agent ou executor dans le bail ; humain s'il exécute lui-même | commande, migration |

### 3.2 Acteurs, qualifications, cycles

- **Acteurs** : `human`, `agent`, `executor`, `system`. L'identité vient du contexte authentifié.
- **Qualifications** : `ALLOW` · `APPROVAL_REQUIRED` · `DENY_BY_POLICY` (exception possible seulement si la règle le prévoit) · `DENY_ABSOLUTE`.
- **Demande de décision** : `OPEN → DECIDED | WITHDRAWN | EXPIRED` ; puis `DECIDED → REVOKED | SUPERSEDED | INVALIDATED | EXPIRED`.
- **Bail** : `PENDING → ACTIVE ⇄ SUSPENDED → EXPIRED | REVOKED | INVALIDATED | CONSUMED`. Une demande de bail refusée est un refus audité, pas un état.
- **Exécution par executor** : `PREPARED → VERIFYING_PRECONDITIONS → EXECUTING → VERIFYING → COMPLETED | ROLLED_BACK | EXECUTION_BLOCKED | FAILED`.

| État de fin | Sens |
|---|---|
| EXPIRED | le temps est écoulé |
| REVOKED | un acte explicite d'un acteur habilité, ou une restriction (P11) |
| INVALIDATED | une condition obligatoire est perdue (artefact, ressource, règle, empreinte de politique, précondition) |
| SUPERSEDED | remplacé par une décision qui le remplace explicitement (D10) |
| CONSUMED | usage unique utilisé, ou exécution terminée normalement |
| WITHDRAWN | demande retirée avant décision |

### 3.3 Versions et canonicalisation

- **Versions de schéma** : `scope_schema_version`, `decision_schema_version`, `lease_schema_version`,
  `evidence_envelope_version`, `audit_event_version`, `rule_catalog_version`, `profile_schema_version`,
  `trust_root_manifest_version`.
- **Canonicalisation** : RFC 8785 (JCS), UTF-8 (O3).
  - Un ensemble est trié par sa forme canonique ; une séquence garde son ordre, chaque étape étant numérotée.
  - Ressource : `{kind, id, identity_sha256}`. Artefact : `{root_id, path POSIX normalisé, sha256, size}`.
  - Commande : tableau argv exact ; chaque script figure comme artefact.
  - Variable d'environnement : son nom, et l'empreinte de sa valeur si elle n'est pas secrète ; un secret
    n'apparaît que par sa référence.
  - Les horodatages sont hors du périmètre, dans l'enveloppe signée.

### 3.4 Confiance des faits

- Deux axes : **stade d'identité** (`DECLARED → DETECTED → RESOLVED → EXECUTED`) et **niveau de confiance**
  (`DECLARED_HUMAN · DECLARED_FILE · DETECTED · INFERRED · CONFIRMED · UNKNOWN · CONFLICT`).
- `DECLARED_HUMAN` = déclaré par une identité humaine authentifiée ; ce n'est pas « fiable ».
- `CONFIRMED` = vérifié opérationnellement par un mécanisme contrôlé, selon une méthode, à un instant :
  `{method, evidence_ref, at, environment, version, fingerprint, valid_until}`. Jamais par concordance entre
  `DECLARED_FILE` et `DETECTED`.
- `SECURITY_ELIGIBLE` est défini **par la règle** pour chaque attribut ; la déclaration humaine n'est
  obligatoire que là où la politique l'exige.
- Tout fait porte `provenance, confidence, valid_from, valid_until, status`.

### 3.5 Niveaux de confiance, contrôles, disponibilité

- **`TRUST_LEVEL`** : L1 (même compte : une altération est détectée) ou L2 (frontière technique contre un agent
  ou un runtime non fiable, dans les limites du TCB, D42).
- **Contrôle applicatif** (`runtime enforcement`) ≠ **frontière d'exécution** (`execution boundary`).
- **Disponibilité** (remplace la notion « ENFORCED en détection ») :

| Niveau | Sens |
|---|---|
| `ARCHITECTURE_ONLY` | décrit, non implémenté |
| `IMPLEMENTED` | implémenté et testé avec des appelants coopératifs ; aucune application démontrée contre un acteur non coopératif |
| `ENFORCED_DETECTIVE` | toute violation est **détectée** de façon démontrée (essais négatifs, preuves scellées), mais n'est pas empêchée |
| `ENFORCED_PREVENTIVE` | toute violation est **empêchée** de façon démontrée, contre un acteur non coopératif, au `TRUST_LEVEL` annoncé |

- Chaque capacité ou frontière déclare le **niveau exigé** pour être disponible. Une capacité qui exige une
  frontière préventive n'est disponible qu'en `ENFORCED_PREVENTIVE` ; un `ENFORCED_DETECTIVE` ne suffit pas.
- Chaque niveau s'énonce avec sa **portée** (runtime concerné, `TRUST_LEVEL`).
- Les preuves exigées sont en Annexe E.

## 4. Décisions

### A. Identité, confiance, stores, racine de confiance

**D42. TCB technique, TCB d'affichage, autorité Factory.**

- **TCB d'autorisation (technique)** : les composants dont la compromission rompt les garanties. Le système
  d'exploitation et ses comptes administrateurs ; le service d'autorité (Trust Store, Decision Center
  côté service, Capability Manager, Exception Manager, compteur de budget) ; le service d'exécution
  (executor) et le lanceur de runtimes ; le code épinglé du Policy Engine et le catalogue ; les bibliothèques
  cryptographiques ; l'authentificateur matériel et le TPM s'il est utilisé ; la racine de confiance (D36).
- **TCB d'affichage** : ce qui présente une décision à l'humain (navigateur, interface Web, CLI, intégration
  VS Code). Sa compromission peut **tromper l'humain** (R6) ; elle ne donne **jamais** d'autorité. Le
  navigateur et l'interface ne sont jamais une autorité Factory, **ni en L1 ni en L2** : la décision, sa
  vérification et son enregistrement restent côté service d'autorité.
- **Autorité Factory** : seuls les détenteurs d'une identité inscrite dans le manifeste d'identité signé par
  la racine (D36), avec leurs rôles. **Un administrateur du système n'est pas automatiquement Factory
  Owner** et ne possède aucune autorité de décision Factory du fait de ses droits système (P22).
- **Modèle de menace** : un administrateur qui agit hors de D36, ou un compte administrateur compromis, est
  traité comme une **compromission potentielle du TCB**, jamais comme une autorité légitime. Ses actions ne
  produisent ni décision, ni bail, ni épinglage valides ; leur détection passe par l'ancrage externe, les
  enregistrements hors bande et les vérifications d'empreintes.
- **Hors du TCB (non fiable)** : agents, runtimes, dépôts de projets, skills non chargées par le lanceur,
  contenu du State Store, Twin, mémoire, récit des agents, contenu venu du réseau.
- Les garanties L2 protègent le TCB d'autorisation contre ce qui est hors du TCB, et rien d'autre.

**D4. Identité humaine.** Contrat abstrait (fournisseur d'identité → identité → authentification →
décision liée) ; première mise en œuvre par passkey WebAuthn avec vérification de l'utilisateur. Les passkeys
valides sont celles du manifeste d'identité signé par la racine. Origine et RP ID exacts vérifiés, ce qui ne
suffit pas en L1 (R6). En L2, la garantie vient de l'identité du service et d'un canal protégé. L'interface
reste un client sans autorité (D42).

**D24. Identité par le contexte.** Humain : session du service. Agent : identité attribuée par la Factory.
Executor : décision et empreinte du plan, rien d'autre. System : périmètre fixe.

**D23. Trois stores.**
- **Trust Store** (autorité) : identités, manifeste d'identité, certificats de clés, décisions, baux,
  exceptions, épinglages, identités des ressources, journal d'autorité et ses ancres, compteur de budget qui
  fait foi.
- **State Store** : l'état, sans jamais créer d'autorisation.
- **Evidence Store** : un artefact y fait foi par son rattachement et sa provenance.

**D14. Intégrité épinglée** de la politique, du catalogue, du moteur, des exécutants contrôlés et de la
configuration des runtimes. Une empreinte différente met la Factory en BLOCKED (DENY_ABSOLUTE). Toute mise à
jour passe par D36.

**D36. Racine de confiance, amorçage, maintenance, rotation, récupération, compromission.**

1. **La racine** est la **clé racine du Factory Owner** (Owner Root Key, ORK), une paire asymétrique, sur un
   support hors ligne (O4). Sa partie privée n'est jamais présente sur le poste en fonctionnement normal. Son
   empreinte publique est l'ancre de confiance.

2. **Hiérarchie des clés :**

| Clé | Où | Signée ou désignée par | Seuls usages permis | Fréquence |
|---|---|---|---|---|
| ORK (racine) | hors ligne | elle-même à la genèse ; une nouvelle ORK par certificat croisé ou par l'autorité de récupération | manifeste d'identité, certificat de la clé de service, liste de révocation, désignation de l'autorité de récupération, certificat croisé de rotation | rare (cérémonie) |
| Passkeys du Factory Owner | authentificateur matériel | inscrites dans le manifeste d'identité signé par l'ORK | décisions humaines, artefacts de maintenance ordinaire | courant |
| Clé de service | Trust Store (L1 : lisible par le compte ; L2 : service, TPM si disponible) | certificat à validité limitée signé par l'ORK | signer les baux, sceller les preuves, chaîner le journal | continu |
| Clé de l'autorité de récupération | hors ligne, séparée de l'ORK | désignée par l'ORK (désignation signée) | **un seul acte** : signer un certificat de remplacement de racine lors d'une cérémonie de récupération | exceptionnel, à usage unique |

3. **La clé de récupération n'est pas une seconde ORK.** Elle ne peut signer **ni** manifeste d'identité,
   **ni** certificat de clé de service, **ni** artefact de maintenance, **ni** décision, **ni** bail. Son seul
   pouvoir est de désigner une nouvelle ORK lors d'une cérémonie de récupération ; elle est ensuite retirée.
   Chaîne :

   ```text
   ORK₁ ──(désignation signée, à la genèse)──► autorité de récupération R₁
   [ORK₁ perdue ou compromise]
   R₁ ──(cérémonie : certificat de remplacement {nouvelle racine ORK₂, révocation de ORK₁, motif, date})──► ORK₂
   ORK₂ ──► nouveau manifeste d'identité, nouveau certificat de clé de service, réépinglage vérifié, révocations
   ORK₂ ──► désignation d'une NOUVELLE autorité de récupération R₂ ; R₁ est retirée (usage unique)
   Chaque étape : journal d'autorité + ancre externe + enregistrement hors bande de l'empreinte de ORK₂ et de la révocation de ORK₁
   ```

   La rotation **ordinaire** de la racine (ORK disponible et saine) se fait par certificat croisé de l'ORK
   sortante et n'utilise pas la clé de récupération.

4. **Amorçage : le moment précis où la confiance s'établit.** Cérémonie physique du Factory Owner, hors du
   chemin normal :
   1. générer l'ORK hors ligne ;
   2. noter l'empreinte racine hors bande (papier, et un second support) ;
   3. enrôler les passkeys ;
   4. signer avec l'ORK le manifeste d'identité (clés publiques des passkeys, rôles) ;
   5. signer le certificat de la clé de service ;
   6. générer la clé de l'autorité de récupération, hors ligne, et signer sa désignation ;
   7. signer l'épinglage initial, calculé à partir d'un commit relu et identifié ;
   8. écrire l'événement « genèse » du journal d'autorité (empreinte racine, empreinte de l'autorité de
      récupération, empreintes initiales) ;
   9. faire un premier ancrage externe.

   Rien de ce qui précède la genèse n'est fiable. La confiance initiale repose explicitement sur cette
   cérémonie : c'est un premier usage de confiance assumé, pas une présomption.

5. **Protection.** ORK et clé de récupération hors ligne, sur des supports distincts et en des lieux
   distincts, protégés par phrase de passe ou code PIN matériel. L'empreinte racine est épinglée à trois
   endroits : Trust Store, enregistrement hors bande, ancre externe. Un changement de racine sans certificat
   croisé de l'ancienne ORK ni certificat de remplacement de l'autorité de récupération désignée donne
   DENY_ABSOLUTE et BLOCKED.

6. **Maintenance ordinaire.** Le Factory Owner, authentifié par passkey, ouvre le mode maintenance (aucun
   runtime d'agent, aucun bail) et présente un artefact signé par passkey (fichiers, empreintes et versions
   attendues, motif, référence). Le service vérifie la signature, l'inscription de la passkey dans le
   manifeste signé par l'ORK, et les empreintes réelles ; il réépingle, journalise, ancre, ferme le mode et
   revérifie. Cette voie ne passe pas par le Policy Engine. **Maintenance de confiance** (manifeste d'identité,
   clés, liste de révocation, désignation de récupération) : ORK exigée.

7. **Rotation.** Clé de service : périodique, nouveau certificat signé par l'ORK, l'ancien révoqué. Passkeys :
   nouveau manifeste signé par l'ORK. ORK : certificat croisé, nouvelle empreinte hors bande, événement au
   journal, nouvelle désignation de récupération.

8. **Récupération.** Clé de service perdue : l'ORK certifie une nouvelle clé ; les épinglages sont revérifiés
   à partir d'un commit relu ; le Trust Store est restauré depuis la dernière sauvegarde vérifiée contre les
   ancres. Passkey perdue : manifeste réémis par l'ORK. ORK perdue : cérémonie de récupération (point 3).
   ORK et autorité de récupération perdues : nouvel amorçage complet ; les anciennes décisions restent
   vérifiables historiquement mais n'ouvrent aucune autorité nouvelle.

9. **Compromission.** Clé de service : révoquée par l'ORK ; tous les baux qu'elle a signés passent à
   INVALIDATED et sont réémis ; les preuves scellées pendant la fenêtre sont marquées « à revoir ». Passkey :
   retirée du manifeste. ORK : cérémonie de récupération (point 3), révocation hors bande de l'ancienne
   empreinte ; décisions de la fenêtre soumises à revue. Autorité de récupération : l'ORK révoque la
   désignation et en désigne une nouvelle.

10. **Ce que l'agent ne peut pas faire.** ORK et clé de récupération sont hors ligne : un agent ne peut
    jamais produire de signature racine, de manifeste d'identité valide, de certificat de remplacement ni
    d'artefact de maintenance de confiance. Réserve L1 : il peut modifier le code qui vérifie ces signatures
    (R1, R7, R15) ; c'est détecté par l'ancre et l'épinglage, pas empêché. En L2, le vérificateur appartient au
    TCB d'autorisation. Un administrateur du système agissant hors de cette chaîne relève du modèle de menace
    de D42.

**D27. Épinglage et identité réelle.** Vérification en quatre temps (déclaré → résolu → chargé → empreinte
réelle comparée au Trust Store), faite par le lanceur hors du processus agent ; une différence donne
DENY_ABSOLUTE. Même logique, selon les possibilités techniques, pour les outils, les MCP, les modèles et la
configuration des runtimes. Le projet est lisible comme contexte ; il ne fait autorité qu'après épinglage.

### B. Règles, politique, exceptions

- **D30. Catalogue → Policy Engine → décision.** Le catalogue est normatif ; le Policy Engine est décisionnel.
  Chaque règle porte : `rule_id`, `rule_version`, définition, criticité, qualification, nature, frontière
  humaine et explication, conditions d'éligibilité de sécurité, capacité d'exception
  (`exceptable, max_scope, max_duration, max_uses, allowed_roles, compensating_controls`), transformations non
  matérielles déclarées (D9), preuves exigées. Test bloquant de correspondance entre code et catalogue.
- **D11. DENY_ABSOLUTE** : falsifier une approbation, une preuve ou une identité ; se faire passer pour un
  humain ; auto-approbation d'un agent ; contourner le Policy Engine, l'audit ou un contrôle de sécurité ;
  altérer l'audit ou une preuve scellée ; accès à un secret interdit ou à un autre projet ; modifier l'identité
  ou l'authentification ; transformer artificiellement un DENY en ALLOW ; modifier ce qui est épinglé hors
  D36 ; changer la racine de confiance hors D36 ; erreur interne du moteur ; demande malformée.
- **D12.** L'Exception Manager gère, le Policy Engine décide ; I5 : contrôle structurel de l'exception
  contre la capacité d'exception de sa règle avant tout usage.
- **D13.** Chaque décision et chaque bail portent `policy_id, policy_version, policy_fingerprint, rule_id,
  rule_version` ; P18 s'applique quand la politique évolue.
- **D31.** Une seule chaîne d'approbation (R12, R38 et portes du moteur d'états intégrés ou supprimés). La revue
  de code humaine avant fusion (ADR-0012) est maintenue à tous les niveaux de criticité ; les revues d'agents
  (critiques, optimiseurs) sont complémentaires et ne la remplacent jamais. Un assouplissement exigerait un nouvel
  ADR (ADR-0012, Conséquences).
- **K8.** Les explications sont masquées selon le rôle du lecteur.

### C. Décision humaine

- **D1, D2, D3.** Trois objets (demande, décision, exécution) ; cycles de §3.2 ; interfaces sans autorité.
  Une restriction faite par l'humain au moment de décider produit un nouveau périmètre signé par lui.
- **D28.** Faits de la Factory séparés du récit de l'agent ; changements d'autorité mis en évidence.
- **I8.** Demandes créées par le Core seulement, dédoublonnées par l'empreinte du périmètre, sous quota (O6).
- **D5.** Périmètre canonique : sections Action, Préconditions, Postconditions, Vérification, Rollback ;
  capacités, ressources, environnement, artefacts, limites, exécutant, politique et règle. Signature sur
  `{request_id, scope_sha256, scope_schema_version, choix, restrictions, expires_at, nonce, decided_at}`.
- **D6.** Valeurs par défaut réductibles : C3 = 24 h ; C4 = 4 h, usage unique. Expiration ≠ révocation.
- **D8.** En exécution humaine, la Factory ne lance que les contrôles de la section Vérification approuvée.
- **D9. Changement matériel.**
  1. Le Core calcule mécaniquement la différence canonique entre périmètre approuvé et périmètre courant.
  2. Une modification n'est non matérielle que si la règle concernée déclare explicitement que cette
     transformation est monotone pour la sécurité et pour la sémantique (`non_material_transformations` :
     type, champs, conditions, justification), dans le catalogue épinglé.
  3. `subset`, `subsequence`, `≤ durée`, `≤ limite` sont des mécanismes de comparaison, jamais une preuve de
     monotonie.
  4. Toute transformation touchant Préconditions, Postconditions, Vérification ou Rollback est matérielle.
  5. Absence de définition ou incertitude : `MATERIAL_CHANGE`, bail SUSPENDED, nouvelle décision.
  6. L'agent n'apprécie jamais la matérialité.
- **D10. Lignée.** Toute demande et toute décision portent, quand c'est pertinent : `derived_from`,
  `related_requests[]`, `previous_decision`, `previous_scope_sha256`, `supersedes`, `change_reason`,
  `canonical_diff_ref`.

| Cas | Effet sur les décisions antérieures |
|---|---|
| Réapprobation (même objectif, périmètre modifié) | remplace la précédente (`supersedes`), qui passe à SUPERSEDED |
| Décision qui remplace (autre plan, déclarée remplaçante) | la précédente passe à SUPERSEDED |
| Nouvelle décision liée | aucun effet ; liée par `derived_from` ou `related_requests` |

  Ne pas être une réapprobation ne veut jamais dire ne pas avoir de lignée ; la lignée est en ajout seul.

### D. Bail, exécution, frontière, preuve

- **D7.** Bail authentifié par la clé de service, avec `authority`, politique et règle, `lease_schema_version`.
- **D25.** Contrôle applicatif par un hook ; cascade F12 ; la révocation passe avant l'expiration. Ce n'est
  pas la frontière ultime (P19).
- **D38. Frontière d'exécution (C3, C4, STAGING, PRODUCTION).**
  - L'executor est séparé de l'agent : autre contexte de sécurité, autre processus.
  - **Entrée unique de l'executor** : `{approved_plan_ref, plan_sha256, execution_context}`, où
    `execution_context` ne contient que l'identifiant d'environnement, la référence du bail et l'identifiant
    d'exécution. **L'executor ne reçoit jamais de commande arbitraire ni de shell libre provenant de l'agent**,
    ni de paramètre qui modifierait une étape.
  - Les artefacts exécutables sont récupérés depuis le store protégé **par leur empreinte**, jamais depuis
    l'espace de l'agent.
  - L'executor ne choisit qu'entre les opérations et branches **explicitement prévues** par le plan approuvé.
    Toute entrée qui ne correspond pas exactement au plan approuvé est refusée.
  - L'agent ne possède jamais les identifiants ni le chemin réseau vers STAGING ou PRODUCTION.
  - L'empreinte du plan est vérifiée à chaque étape ; le contrôle reste effectif même si le runtime ou
    l'agent est compromis.
  - En L1, cette frontière n'existe pas : `FACTORY_EXECUTE` en STAGING et PRODUCTION est ARCHITECTURE_ONLY ;
    seul `HUMAN_EXECUTE` est disponible.
- **Executor (normatif).** Il vérifie, exécute, arrête, prouve et applique le retour arrière prévu ; il
  n'invente rien. Étape impossible : `EXECUTION_BLOCKED` → preuve → Supervisor et circuit de décision.
  **R09 révisée** : production refusée à un agent ; APPROVAL_REQUIRED pour un executor, seulement quand D38
  est `ENFORCED_PREVENTIVE`.
- **D26.** Une preuve vient d'un exécutant contrôlé ; enveloppe versionnée, empreinte au journal,
  rattachement à l'exécution, intégrité vérifiable.

### E. Environnements, réseau, ressources

- Caractère jetable d'un profil : dans la politique ; `orchestrator/environnements.yaml` ne garde que la
  rétention et le nettoyage.
- **D32.** Budget unique tenu par le service ; stratégies selon l'environnement (LOCAL/TEST : nouvelle
  tentative, réparation, reset, recréation ; STAGING : nouvelle tentative contrôlée, retour arrière, rejeu ;
  PRODUCTION : reprise et retour arrière approuvés seulement) ; le Supervisor ne crée jamais d'autorisation.
- **D33.** Classes réseau nommées ; `PACKAGE_INSTALL` sous `NETWORK_PACKAGE_REGISTRY` ; registre inconnu =
  DENY ; ARCHITECTURE_ONLY sans mécanisme d'application.
- **D34.** Resource Broker : quota disque, quota d'environnements, budget d'API et de modèle.

### F. Orchestration

- **D20.** Le Meta-Orchestrator coordonne ; la plateforme J13 gère l'espace d'une tâche ; la frontière
  humaine vient du catalogue ; une seule identité d'exécution.
- **D39.** Services abstraits d'optimisation (brief, développement) ; `developer-prompt-reformulator` et
  `agent-code-optimizer` n'en sont que des implémentations ; repli déterministe.
- **K14.** Agent vers agent : neuf contrôles formels ; besoin hors périmètre = SCOPE EXPANSION.

### G. Projet, Twin, mémoire

- **D29.** Profil unique `.factory/project.yaml` ; sections d'autorité épinglées.
- **D18.** Frontière Core / Project Factory ; matrice de compatibilité.
- **D16.** Twin à deux axes ; seuls les faits SECURITY_ELIGIBLE alimentent la sécurité ; une détection ne fait
  que relever une criticité.
- **D15.** Sept portées ; promotion selon le type ; jamais de règle créée silencieusement.

### H. Registre, skills, optimiseurs

- Registre : Tool, Skill, Agent, Model, MCP, Runtime, Capability, Workflow distincts ; une entrée par version,
  avec son niveau de disponibilité.
- **D19 à D22.** Rôles logiques ; skills intactes ; sortie « proposition d'optimisation » ; optimiseurs en
  lecture et en proposition. `agent_prompt_optimiser` → `developer-prompt-reformulator` ;
  `agent_devloppe_optimiser` → `agent-code-optimizer`.
- **D35.** `code-agent-prompt-optimizer` : DEPRECATED.

### I. Phasage, construction, contexte

- **D37. Mode construction.** Au gel, le mode construction remplace l'exception de construction ; EXC-0002 →
  `BACKUP_WRITE` exécuté par un composant system. **État au 16/10/2026** (décision B7, option 2) : EXC-0001 est
  `EXHAUSTED`, remplacée par **EXC-0003** (construction bornée : corrections A1–C8, NE1–NE7 et étape G1 ; échéance
  la première de : gel de l'ADR-0017, adoption du Playbook v3.3 + 30 jours, 2026-11-15 ; aucune prolongation
  automatique) ; la dérive passée sous EXC-0001 est tracée au journal (AE-000238), non régularisée. La migration
  d'EXC-0002 n'est **pas exécutée**.
- **D40. Phasage par frontières G1 à G6** (amendement §17 du Playbook v3.3).
- **D41. Contexte du dépôt réécrit** en quatre parties, sans autorité. (**Exécuté** le 16/10/2026, correction NE6.)
  Sur décision du Factory Owner du même jour, ce contexte est tenu dans `CLAUDE.md` ; `AGENT_CONTEXT.md` ne
  contient plus qu'un renvoi (écart déclaré à la neutralité, Playbook v3.3 proposé §16.3).

## 5. Invariants

- **I1.** Aucun composant ne cumule, pour une même action, la qualification, l'octroi d'autorité et
  l'exécution hors de P11 ; personne ne s'accorde une autorité qu'il n'a pas.
- **I2.** Seule la chaîne de P11 accorde.
- **I3.** Le relecteur n'est pas l'auteur.
- **I4.** Aucune autorité ne vient de ce qui est hors du TCB, ni d'un fait non SECURITY_ELIGIBLE.
- **I5.** Une exception ne dépasse jamais la capacité d'exception de sa règle.
- **I6.** Aucune décision humaine ne franchit un DENY_ABSOLUTE.
- **I7.** Un executor n'exécute que les étapes du plan approuvé, à l'empreinte près, à partir d'une référence
  de plan et jamais d'une commande fournie par l'agent.
- **I8.** Demandes de décision : créées par le Core, dédoublonnées, sous quota.
- **I9.** Une évolution permissive n'est jamais rétroactive.
- **I10.** Disponible = niveau d'application exigé atteint (§3.5).
- **I11.** Le non matériel est défini par la règle, jamais par une comparaison seule ni par l'agent.
- **I12.** La lignée d'une décision est permanente.
- **I13.** Toute autorité remonte, par une chaîne de signatures vérifiable, à la racine de confiance.
- **I14 (nouveau).** Un pouvoir technique sur le système (administrateur, accès disque) n'est jamais une
  autorité Factory ; exercé hors de D36, il est une compromission potentielle du TCB.
- **I15 (nouveau).** L'affichage n'est jamais l'autorisation : l'interface présente, le service décide,
  vérifie et enregistre.

## 6. Flux

```text
F1  Évaluation : demande (contexte authentifié) → Policy (catalogue et politique épinglés, identités du Trust Store)
    → ALLOW → Capability Manager → bail → exécution
    → APPROVAL_REQUIRED → Decision Center (F2)
    → DENY_BY_POLICY → exception conforme ? (I5) → oui : ALLOW (EXC-…) ; non : demande d'exception → F2
    → DENY_ABSOLUTE (ou erreur) → arrêt

F2  Decision Center : demande (faits de la Factory | récit de l'agent, séparés) → humain certifié (passkey) signe
    → FACTORY_EXECUTE → bail (authority = décision) → executor (D38 : référence de plan + empreinte) ou agent → preuves
    → HUMAN_EXECUTE → kit → action humaine → contrôles de la section Vérification → preuves
    → REJECT → close

F3  Chaque appel d'outil → hook → service : bail authentifié, non révoqué, non expiré → Policy (intersection P18)
    → ALLOW | DENY ; révocation ou expiration → Supervisor : plus d'action → arrêt propre → arrêt forcé

F4  Plan courant → empreinte → comparaison canonique (Core) → identique : exécution
    → différence couverte par une transformation non matérielle déclarée par la règle : exécution + journal
    → sinon : MATERIAL_CHANGE → bail SUSPENDED → nouvelle décision (lignée D10)

F5  Boucle autonome en environnement jetable : mission → plan → Policy (ALLOW) → bail → environnement (quotas)
    → runtime → gates (exécutant contrôlé) → preuves → échec → Supervisor (budget unique) → reset / réparation
    → succès → revues d'agents (I3) → revue de code humaine avant fusion (ADR-0012) → libération → destruction
    → archives

F6  Scellement : exécutant contrôlé → artefact → Evidence Store → empreinte → journal d'autorité → ancre

F7  Épinglage : ressource détectée → évaluation → proposition → revue → maintenance (F13) → épinglage
    → lancement de runtime : empreinte chargée = empreinte épinglée, sinon DENY_ABSOLUTE

F8  Exception : DENY_BY_POLICY → demande (périmètre haché) → contrôle I5 → Decision Center → exception bornée
    → Policy : exception exacte ? → ALLOW (EXC-…) ; usages, expiration, révocation ; usage répété → ADR

F9  Brief agent → agent : mission validée → service d'optimisation de brief (D39) → neuf contrôles (K14)
    → brief haché → runtime ; hors périmètre → SCOPE EXPANSION → décision

F10 Promotion de mémoire : exécution → candidate → classification → relecteur selon le type → promotion + historique

F11 Twin : sources → faits (deux axes) → réconciliation (CONFIRMED par mécanisme contrôlé | CONFLICT)
    → instantanés → What Changed → Policy : seulement SECURITY_ELIGIBLE

F12 Cascade : révocation | identité de ressource changée | empreinte de politique, de règle ou d'artefact changée
    → bail REVOKED | INVALIDATED → exécution SUSPENDED → runtime arrêté → appels en attente refusés → journal

F13 Maintenance : passkey certifiée → mode maintenance (aucun runtime, aucun bail) → artefact signé
    → vérification (signature, manifeste signé par l'ORK, empreintes réelles) → réépinglage → journal + ancre
    → fermeture → revérification. Maintenance de confiance : ORK. Récupération : autorité de récupération (D36.3).
```

## 7. Options pour L2 (décision O2)

| Critère | 1. Compte Windows dédié | 2. Service Windows + ACL / SID de service | 3. Service + TPM |
|---|---|---|---|
| Trust Store, audit | ACL au compte | ACL au SID du service virtuel, sans mot de passe | comme 2 |
| Clés | DPAPI du compte, exportables par lui | DPAPI ou CNG du compte de service | non exportables (fournisseur TPM) |
| Service d'autorité | processus lancé sous ce compte | service géré par le système | comme 2 |
| Authentification des clients | localhost seul (R6) | canal protégé (tube nommé avec ACL et identification du client) | comme 2 |
| Rotation, récupération | manuelle | procédure de service + D36 | + scellement matériel ; restauration par rotation |
| Complexité | faible | moyenne | élevée |
| Limite (D42) | administrateur dans le TCB | idem | idem |
| Sur ce poste | oui | oui (Windows 11 Pro) | UNKNOWN (machine virtuelle probable, TPM virtuel à vérifier) |

Recommandation : option 2, enrichie par l'option 3 si un TPM est confirmé.

## 8. Garanties

**Risques en L1** (annoncés comme tels) :

| N° | Risque |
|---|---|
| R1 | Stores modifiables par un processus du même compte ; détecté seulement par l'ancre |
| R2 | Clé de service lisible : baux et sceaux falsifiables |
| R3 | Runtimes non gouvernés et sessions interactives hors Factory |
| R4 | Le hook dépend du runtime |
| R5 | Réseau ARCHITECTURE_ONLY |
| R6 | WebAuthn sur `localhost` : RP ID partagé par tous les ports, transaction non affichée par l'authentificateur ; un faux affichage peut obtenir une signature. Le navigateur reste hors de l'autorité (D42), mais le TCB d'affichage peut tromper l'humain |
| R7 | Exécutants contrôlés sous le même compte |
| R8 | Un seul humain tient tous les rôles |
| R9 | Pas de quota disque avant D34 |
| R10 | Agent de construction et règles `allow` de `settings.json` toujours présents |
| R11 | Pas d'ancre hors poste |
| R12 | Le récit d'un agent influence l'humain |
| R13 | Pas de frontière d'exécution : `FACTORY_EXECUTE` STAGING et PRODUCTION indisponible |
| R14 | Fenêtre entre vérification et chargement d'une skill |
| R15 | Le code qui vérifie les signatures racine et passkeys est modifiable ; la racine reste hors de portée |

**Garanties en L2**, contre un agent ou un runtime compromis, **dans les limites du TCB** (D42) :
G1 Trust Store non modifiable par un agent · G2 clés détenues par le service · G3 journal écrit par le
service seulement, ancré · G4 Decision Center = service identifié joint par canal protégé · G5 épinglages
vérifiés par le lanceur du service à partir de copies protégées · G6 révocation immédiate · G7 identifiants
de STAGING et PRODUCTION détenus par le service seul.

**Non fournies, même en L2** : compromission du TCB (système, administrateur compromis ou agissant hors de
D36, service d'autorité, executor, Policy Engine, lanceur) ; défaut de l'executor ou du Policy Engine ; ORK ou
autorité de récupération compromises ; erreur de conception d'une règle ; décision humaine obtenue par
tromperie, y compris par un TCB d'affichage compromis ; runtimes non gouvernés ; réseau sans mécanisme
d'application ; séparation des pouvoirs avec un seul humain ; confidentialité des données envoyées au modèle.

## 9. Migrations décidées

| Migration | État au 16/10/2026 |
|---|---|
| EXC-0001 (D37, B7) | **exécutée** : `EXHAUSTED`, remplacée par EXC-0003 ; dérive tracée (AE-000238) |
| EXC-0002 → `BACKUP_WRITE` (D37) | non exécutée |
| Contexte du dépôt (D41, NE6) | **exécutée** : réécrit en quatre parties, sans autorité ; tenu dans `CLAUDE.md` (décision du Factory Owner), `AGENT_CONTEXT.md` réduit à un renvoi |
| Profil `.factory/project.yaml` (D29) | non exécutée (au gel) |
| Approbations vers le Decision Center (D31) | non exécutée (G2) |
| `audit/` vers les stores (D23) | non exécutée (G1) |

Les migrations exécutées sont tracées au journal d'audit ; les autres le seront à leur exécution.

## 10. Relation avec le Playbook

Normative depuis le 17/10/2026 : le Playbook v3.3 (`docs/playbook/playbook-v3.3.md`, amendements dans
`docs/proposed/playbook-v3.3-amendements.md`) a été adopté par le Factory Owner, puis cette baseline gelée sur son
instruction. Une décision normative n'est pas une frontière : le niveau réel de chaque frontière reste celui de
l'annexe D, et aucune n'est `ENFORCED` tant que ses preuves de l'annexe E n'ont pas été produites et revues.

---

## Annexe A — Matrice d'autorité

Colonnes : **Q** qualifie · **DA** décision d'autorité · **M** matérialise · **DT** décision technique ·
**X** exécute · **W** écrit.

| Composant | Q | DA | M | DT | X | W |
|---|---|---|---|---|---|---|
| Humain (identité certifiée, D36) | non | **oui**, si la politique l'exige (P14) | non | — | oui (exécution humaine) | politique et Core via D36 seulement |
| Administrateur du système | non | **non** (P22, I14) | non | — | — | hors D36 : compromission potentielle du TCB |
| Policy Engine | **oui** | non | non | non | non | rien |
| Catalogue | non (normatif) | non | non | non | non | lui-même via D36 |
| Decision Center (service) | non | recueille et vérifie | non | non | non | demandes, décisions (via le service) |
| Interfaces (navigateur, CLI, VS Code) | non | **non** (I15) | non | non | non | rien |
| Exception Manager | non | non | non | non | non | exceptions conformes à I5 |
| Service d'autorité (Trust Store) | non | non | non | non | non | seul écrivain du Trust Store, sous la racine (D36) |
| Capability Manager | non | non | **oui** (sans créer d'autorité) | non | non | baux authentifiés |
| Bail | — | — | jeton dérivé | — | — | — |
| Executor | non | non | non | seulement entre opérations prévues | rejoue le plan (entrée D38) | ressources du bail |
| Agent | non | non | non | **oui**, dans son bail | oui, dans son bail | ce que couvre le bail |
| Runtime, lanceur | non | non | non | non | héberge ; vérifie les épinglages | rien hors bail |
| Mission Manager | non | non | non | structure la mission | non | State Store |
| Meta-Orchestrator | non | non | non | coordination | coordonne | State Store |
| Supervisor | non | non | non | stratégie autorisée d'avance | arrête | State Store ; demande une révocation |
| Environment Manager | non | non | non | non | environnements jetables | environnements ; identités via le service |
| Resource Broker | non | non | non | allocation dans les quotas | non | allocations |
| Gates et contrôles | non | non | non | non | commandes épinglées, ou section Vérification | Evidence Store |
| Evidence Store, Audit | non | non | non | non | non | ajout seul, par le service |
| Twin, Mémoire | non | non | non | non | non | leur état (I4) |
| Registre, Skills, Profil | non | non | non | non | non | via cycle de vie, épinglage, D36 |
| Services d'optimisation (D39) | non | non | non | propositions | brief ou méthode, dans le bail | propositions |

## Annexe B — Les sept chemins anti-auto-autorisation

Seule une frontière techniquement imposée compte comme rupture.

| Chemin | ALLOW sans humain ? | Rupture | Autorité requise | Preuve | Risque L1 | Risque L2 | Aujourd'hui (avant G1) |
|---|---|---|---|---|---|---|---|
| 1. Agent → State → Twin → Policy → Décision → Bail | non | Policy n'accepte que des faits SECURITY_ELIGIBLE (déclaration signée ou confirmation scellée), vérifiés par le service | signature humaine certifiée ou sceau d'exécutant contrôlé | déclaration signée, preuve scellée | sceau falsifiable (R2), store réécrit (R1) : détecté | empêché, dans le TCB | la Policy lit `factory.yaml` à la racine du projet : un DECLARED_FILE utilisé comme autorité |
| 2. Agent → Evidence → Humain → Décision → Bail | non | signature WebAuthn avec vérification de l'utilisateur ; faits calculés par le service ; dédoublonnage et quota côté service | décision humaine certifiée | décision signée, preuves scellées | faux affichage (R6), preuves falsifiées (R1, R2), récit (R12) | empêché pour la signature et les faits ; reste l'humain trompé | approbation en console (W1) |
| 3. Agent → Profil → Épinglage → Policy | non | profil chargé seulement si son empreinte correspond à l'épinglage ; épinglage modifié seulement par D36 | maintenance signée | épinglage, journal | réécriture cohérente profil + épinglage (R1) | empêché, dans le TCB | pas d'épinglage (voir chemin 1) |
| 4. Agent → Skill → Runtime → Capacité | non (une skill ne donne aucune capacité) | droits du runtime issus du bail ; lanceur hors agent vérifie l'empreinte chargée | bail | empreinte chargée au journal | fenêtre de vérification (R14), épinglage falsifiable (R1) ; mauvais usage d'un bail existant | empêché (copies protégées) ; le mauvais usage dans le bail demeure | skills chargées sans contrôle ; `--setting-sources` non utilisé |
| 5. Agent → Exception → Policy → Bail | non | exception créée par le service sur décision certifiée ; contrôle I5 par le service | décision d'un rôle habilité, dans la capacité d'exception | exception, journal | fausse exception (R1, R2) | empêché, dans le TCB | G1 : exception = approbation W1 contrôlée I5 par le moteur, sans service ni Decision Center (L1) |
| 6. Agent → Supervisor → Reprise → Bail | oui, seulement pour une stratégie autorisée d'avance ; aucune autorité nouvelle | Supervisor sans pouvoir d'émission ; budget tenu par le service | qualification de la politique | journal des stratégies | évasion de budget par le State Store | empêché | compteurs dans le processus de l'orchestrateur |
| 7. Agent → Executor → Production | jamais | D38 : l'executor ne reçoit qu'une référence de plan et son empreinte ; artefacts depuis le store ; aucun identifiant ni chemin réseau pour l'agent | décision certifiée + plan haché | preuves scellées par étape | aucune frontière (R13) : fermé par indisponibilité | empêché, dans le TCB ; reste le mauvais plan approuvé ou un défaut d'executor | pas d'executor ; R09 (applicatif) ; scripts de déploiement lisibles (C10c) |

**Conclusion.** En L2, les sept chemins sont techniquement empêchés pour un agent ou un runtime compromis,
**dans les limites du TCB défini par D42**. L2 ne protège pas contre : compromission du TCB (système,
administrateur compromis ou agissant hors de D36, service d'autorité, executor, Policy Engine, lanceur) ;
défaut de l'executor ou du Policy Engine ; racine ou autorité de récupération compromises ; erreur de
conception d'une règle ; décision humaine obtenue par tromperie. En L1, les chemins 1 à 5 ne sont que
détectés, le chemin 7 est fermé par indisponibilité, le chemin 6 permet une évasion de budget. Aujourd'hui,
les chemins 1 et 3 reposent sur un DECLARED_FILE utilisé comme autorité : premier écart à fermer.

## Annexe C — Cohérence ADR-0016 / ADR-0017 / Playbook

| Sujet | Playbook v3.2 | ADR-0016 (actif) | ADR-0017 v5 | Playbook v3.3 proposé | État |
|---|---|---|---|---|---|
| Autonomie en environnement jetable | non prévue (§9.6, règle 19) | active (R30–R39) | conservée (P1), pas une habilitation | P02, P11, §6.7 | écart actuel, résolu par la v3.3 |
| Destruction de ressources de test | P02 : interdit à l'IA seule | ALLOW sur ressource jetable | conservé | P02 précisé | idem |
| Échecs répétés | 3 échecs : arrêt et humain (§8.6) | reprise dans le budget | budget unique tenu par le service (D32) | §8.6 | idem |
| Habilitation | évaluation obligatoire (règle 19) | agent non évalué admis en jetable | habilitation = hors jetable | §6.7, règle 19 | idem |
| Production | humain (§9.2), DENY agent (§34) | R09 : production toujours refusée à un agent | agent DENY ; executor si D38 ENFORCED_PREVENTIVE | §8.3, §9.1, §9.2 | cohérent après la v3.3 ; R09 complétée pour l'executor par l'ADR-0017 (l'ADR-0016 n'est pas à amender sur ce point) |
| Réseau | liste blanche par projet | NETWORK_READ et WRITE génériques | classes nommées, ARCHITECTURE_ONLY | §8.5 | ADR-0016 à amender |
| Installation de paquets | non traitée | sur approbation en sandbox | autonome sous NETWORK_PACKAGE_REGISTRY | §8.5 | ADR-0016 à amender |
| Caractère jetable d'un profil | — | fichier d'orchestration | dans la politique | — | à amender en implémentation |
| Canal d'approbation | RACI (§3.2) | — | Decision Center, identité certifiée | P12, §3.4 | remplace ADR-0006 et 0012 (transition) |
| Autorité d'un administrateur | non traitée | — | aucune (P22, I14) | P14, règle 28 | nouveau |
| Preuve | la CI fait foi | — | exécutant contrôlé | P10, règle 11 | résolu par la v3.3 |
| Exceptions | Security Owner (§3.1) | — | objets bornés (I5) ; EXC-0001 `EXHAUSTED`, remplacée par EXC-0003 (exécuté, B7) | — | cohérent |
| Profil projet | manifest (§7.5) | — | `.factory/project.yaml` | §7.5 | remplace ADR-0001 |
| Phasage | 4 phases séquentielles | — | G1 à G6 | §17, §17.2 | résolu par la v3.3 |
| Racine de confiance | — | — | D36 | P14, règle 28 | nouveau |
| Disponibilité | « cible » (§17.2 règle 4) | — | quatre niveaux (§3.5) | P13, règle 27 | nouveau |
| Contexte agent | §16.3 (« source unique » des règles stables) | — | D41 (exécuté : contexte sans autorité) | §16.3 amendé | cohérent après adoption de la v3.3 |

Sans adoption de la v3.3, l'ADR-0016 reste en écart normatif déclaré, comme depuis le 15/10/2026.

## Annexe D — Disponibilité au 16/10/2026

Niveau exigé : **P** = préventif exigé (`ENFORCED_PREVENTIVE`), **D** = détectif suffisant (`ENFORCED_DETECTIVE`).

| Capacité ou frontière | Exigé | Niveau réel | Portée et remarque |
|---|---|---|---|
| Garde W1 (écriture des approbations, commande d'approbation) | P | IMPLEMENTED | préventive contre les tentatives directes (outils d'édition, commandes citant le chemin protégé), dans les sessions Claude Code avec les réglages de la Factory ; **contournable** par une commande qui construit le chemin dynamiquement (NE2) ; aucune preuve de l'annexe E (acteur non coopératif, preuve scellée, revue humaine) ; cohérent avec ADR-0006 et ADR-0012 (« atténuée, pas fermée ») |
| Contrôle du diff contre le périmètre (J13) | D | IMPLEMENTED | constate un débordement **dans le worktree** après coup ; G4 (NE3 en partie) : un nouveau fichier ignoré par git, sensible ou interdit (`.env`…), est désormais un débordement ; les écritures par les outils d'édition sont refusées à l'avance hors du périmètre (garde du bail, autorité d'exécution de ticket) ; **reste ouvert** : une écriture hors du worktree par une commande, et la modification d'un fichier ignoré déjà présent ; aucune preuve de l'annexe E |
| Empreinte du Playbook (Bootstrap) | D | IMPLEMENTED | l'empreinte attendue est dans `factory.yaml`, modifiable par le même compte : une modification cohérente des deux fichiers n'est pas détectée par le Bootstrap (NE4) ; G1 : les deux fichiers sont couverts par l'épinglage, qui la détecte une fois une référence approuvée ; aucune preuve de l'annexe E |
| Journal d'audit chaîné | D (L1) / P (L2) | IMPLEMENTED | ancre locale seulement (F:) ; essais de rechaînage non menés contre un acteur non coopératif |
| Qualification `use_capability` (R30–R39) | P | IMPLEMENTED | n'agit que si l'appelant coopère |
| Environnements jetables, identité des ressources | P | IMPLEMENTED | identité vérifiée dans le chemin `factory env` |
| Baux | P | IMPLEMENTED | G1 : authentifiés en L1 (HMAC-SHA256 avec la clé de service, autorité et empreinte de politique portées par le bail ; bail altéré ou forgé refusé ; changement de politique → `INVALIDATED`) ; clé de service **provisoire L1** `L1-b430e9949aff` créée le 17/10/2026 sur instruction du Factory Owner (`factory key init`, fichier hors du dépôt sous workspaces_root) : les baux sont émis ; la clé est lisible par le compte, donc un processus qui la lit peut forger un bail (R2) ; la cérémonie D36 (clé détenue par le service, L2) reste à tenir |
| Hook de projection du bail | P | IMPLEMENTED | G1 : garde PreToolUse engendrée dans les réglages de chaque session lancée par la Factory ; bail relu à chaque appel d'écriture ou de commande (révocation, expiration, changement de politique refusent l'appel suivant) ; outil non projeté refusé ; G4 : seconde autorité, l'exécution de ticket autorisée (`run_ticket`) — écriture admise seulement dans l'espace isolé ET le périmètre du ticket, tant que l'exécution est en cours (J13 devient préventif) ; chaque refus est tracé et compté par l'évaluation ; **vraie session observée le 17/10/2026** (campagne EVAL-qa-20261017T164745) : la garde a bien refusé toute écriture sans autorité — c'est ce qui a révélé l'autorité manquante ; aucune vraie session encore avec la seconde autorité ; le fichier de projection est modifiable par le même compte (L1) ; l'arrêt du runtime à l'expiration n'est pas fait |
| Identité par le contexte | P | IMPLEMENTED | G1 : le Policy Engine refuse une identité humaine déclarée par la requête (R01) et prend le rôle du contexte d'appel ; **aucun service n'authentifie encore un appel humain** : la CLI n'en fournit aucun, donc toute action humaine par la CLI est refusée (S1 fermé par refus, pas par authentification) |
| Trust, State, Evidence Stores | P | ARCHITECTURE_ONLY | `audit/` et approbations dans le dépôt |
| Catalogue, deux types de DENY | P | IMPLEMENTED | G1 : `policies/rule-catalog.yaml` (34 règles, nature, explication, capacité d'exception) ; correspondance code ↔ catalogue testée ; règle non cataloguée → `DENY_ABSOLUTE` ; exceptions lues par le moteur (ligne « Exceptions ») |
| Épinglage (politique, skills, réglages, identité réelle) | P | IMPLEMENTED (politique, schémas, réglages, hooks, Playbook) | G1 : la référence est une approbation humaine W1 (`factory pin request`, puis la commande d'approbation) ; vérifiée par `factory check` et au lancement d'une mission (BLOCKED → refus) ; **aucune référence approuvée** à ce jour (UNPINNED) ; skills et identité réelle non couvertes ; L1 : qui forge une approbation forge la référence (NE2) |
| Racine de confiance, D36 | P | ARCHITECTURE_ONLY | — |
| Budget unique tenu par le service | P | ARCHITECTURE_ONLY | compteur dans le processus de l'orchestrateur |
| Decision Center, exécution humaine | P | IMPLEMENTED (L1, ligne de commande) | G2 : `factory decide list\|show\|prune` rassemble les demandes et leur état (ouverte, approuvée, refusée, obsolète, exécutée) sans jamais décider ; la décision reste la commande humaine W1 ; `factory plan request\|execute` : l'agent prépare un plan d'étapes exactes, l'humain l'approuve puis l'exécute, l'exécuteur ne lance que les étapes approuvées à l'empreinte près (I7), une seule fois, chaque étape journalisée ; refus en session d'agent et hors console : gardes **procédurales** ; pas de service identifié ni de canal protégé (L2, G3) |
| Exceptions (I5) | P | IMPLEMENTED | G1 : exception de politique `PEX-…` = approbation humaine W1 d'une portée exacte (`factory exception request`) ; I5 contrôlé à la demande (rejet avant le moteur) et à chaque usage (catalogue courant, rôle de l'approbateur, durée, usages) ; l'exception lève **sa seule règle** et l'évaluation reprend : toutes les autres règles restent appliquées ; usages et révocations au journal ; seules R03 et R24 sont exceptables ; **aucune exception approuvée** ; aucun exécutant ne consomme encore d'usage (la qualification seule ne consomme rien) ; L1 : qui forge une approbation forge une exception (NE2) ; les exceptions de construction `EXC-…` restent hors du moteur |
| Dédoublonnage et quota des demandes | P | IMPLEMENTED | G1 : `core/noyau/demandes.py` — demande dédoublonnée par empreinte de contexte, refusée au-delà de 20 demandes sans décision humaine (`policies/human-approval.yaml`) ; branché sur les demandes d'épinglage, d'exception et de revue de code ; les demandes des portes de transition restent dédoublonnées par leur porte, hors quota ; un agent qui écrit directement dans le dossier des demandes n'est pas empêché (L1) |
| Service d'autorité L2 | P | ARCHITECTURE_ONLY | TPM UNKNOWN |
| Executor, frontière d'exécution (D38) | P | ARCHITECTURE_ONLY | `FACTORY_EXECUTE` STAGING et PRODUCTION indisponible |
| Évaluation des agents, modèles approuvés | P | IMPLEMENTED (outillage) | G4 : habilitation définitive = état du registre ET approbation humaine W1 du bloc `habilitation` (plafond, projets, modèle, empreintes de la suite et du rapport, 92 jours au plus), vérifiée par le Policy Engine ; moteur d'évaluation (§12.6 : réussite, affirmations fausses, sorties de périmètre, pièges, rejets en revue, coût ; seuils par criticité) ; `factory eval plan\|run\|report\|request\|apply` (campagne réelle par l'humain seul ; contrôles cachés et mutations) ; registres des agents et des modèles épinglés ; suites qa et frontend auto-testées sur le pilote (commit fixe, 100 %), suite database prête (base jetable par tâche, bail sans DROP) ; campagnes réelles qa : v1 non probante (défaut de la Factory), v2 sans habilitation (un piège raté), relance après ajout de la condition d'arrêt à la consigne ; 15 agents NOT_EVALUATED, 0 modèle approuvé |
| Méta-orchestrateur, Supervisor, graphe, organisation | D | IMPLEMENTED | testés avec un runtime scripté |
| Runtime Claude Code | P | IMPLEMENTED (sans lancement réel) | MCP refusés seulement dans les runs de la Factory |
| Réseau (classes nommées, mécanisme d'application) | P | ARCHITECTURE_ONLY | déclaratif |
| Twin, What Changed | D | ARCHITECTURE_ONLY | Bootstrap existant comme source |
| Portées de mémoire, promotion | D | ARCHITECTURE_ONLY | filtre de transfert : IMPLEMENTED |
| Resource Broker (quotas) | P | IMPLEMENTED (environnements jetables) | G1 : nombre d'environnements vivants et disque occupé vérifiés à la création (refus) ; dépassement en cours d'exécution constaté par `factory env list`, pas empêché (aucun quota du système de fichiers) |
| Second projet réel | — | ARCHITECTURE_ONLY | — |

**Aucune frontière n'est aujourd'hui `ENFORCED_DETECTIVE` ni `ENFORCED_PREVENTIVE` au sens de l'annexe E.**
Les mécanismes qui fonctionnent dans le cas nominal (garde W1, contrôle du diff J13, empreinte du Playbook)
restent `IMPLEMENTED` tant que leurs preuves de l'annexe E n'ont pas été produites et revues ; leurs défauts
connus (NE2, NE3, NE4) seront traités en G1.

## Annexe E — Preuves nécessaires au passage de chaque frontière

**Règle générale.** Passer à `ENFORCED_DETECTIVE` ou `ENFORCED_PREVENTIVE` exige : (1) des essais négatifs avec
un acteur non coopératif (un vrai runtime d'agent qui tente de franchir la frontière) ; (2) exécutés par un
exécutant contrôlé, preuves scellées ; (3) au `TRUST_LEVEL` annoncé ; (4) une revue humaine des preuves ;
(5) une nouvelle preuve à chaque changement de version d'un composant épinglé. `IMPLEMENTED` exige seulement
des tests verts avec des appelants coopératifs.

| Frontière | → ENFORCED_DETECTIVE | → ENFORCED_PREVENTIVE |
|---|---|---|
| Identité par le contexte | — | requête d'agent se déclarant `human` ou `executor` : DENY ; appel au service sans session : DENY (L1 et L2) |
| Bail authentifié | bail modifié ou rejoué : détecté et refusé (L1) | falsification impossible : clé détenue par le service (L2 seulement) |
| Hook du bail | — | vraie session Claude Code : appel hors bail refusé ; révocation en cours, appel suivant refusé dans un délai mesuré ; expiration, runtime arrêté (L1 applicatif, portée runtime) |
| Épinglage | politique ou skill modifiée : BLOCKED, détecté au lancement (L1) | empreinte chargée ≠ épinglée : chargement refusé, copies protégées (L2) |
| Racine de confiance (D36) | changement de racine hors chaîne : BLOCKED et alerte (L1) | artefact signé par une clé non enrôlée, passkey hors manifeste, certificat de remplacement non désigné : refusés par le service ; cérémonie de récupération exécutée à blanc (L2) |
| Autorité de récupération | — | tentative de signer un manifeste ou une maintenance avec la clé de récupération : refusée ; second usage : refusé |
| Mode maintenance | — | lancement d'un runtime ou émission d'un bail pendant la maintenance : refusé |
| Journal d'autorité | rechaînage complet détecté par l'ancre (L1) | écriture par le compte agent refusée par les ACL (L2) |
| Stores | modification détectée par empreinte et ancre (L1) | écriture depuis le compte agent refusée par le système (L2) |
| Decision Center | faux affichage détecté par comparaison de l'empreinte affichée et signée (L1, partiel, R6) | origine, nonce, périmètre, expiration vérifiés ; faux service refusé par le canal protégé ; dédoublonnage et quota observés (L2) |
| TCB d'affichage | — | décision transmise par une interface compromise : rejetée si la signature ne porte pas sur le périmètre exact calculé par le service |
| Administrateur hors D36 | modification par un administrateur détectée par l'ancre externe et l'enregistrement hors bande | — (hors portée de L2, D42) |
| Exceptions | — | exception plus large que la capacité de sa règle : rejetée avant le moteur |
| Changement matériel (D9) | — | transformation non déclarée par la règle : MATERIAL_CHANGE ; retrait d'une étape de Vérification : toujours matériel |
| Évolution de politique (P18) | — | règle assouplie : bail existant non élargi ; règle durcie : invalidation en cascade observée |
| Executor (D38) | — | entrée autre qu'une référence de plan approuvé : refusée ; commande ou shell fourni par l'agent : refusé ; artefact d'empreinte différente : `EXECUTION_BLOCKED` ; accès du processus agent aux identifiants de STAGING : impossible (L2 seulement) |
| Autonomie en jetable | — | E1 rejoué avec un vrai runtime Claude Code ; tentatives vers la base réelle (5432), une ressource non enregistrée, une capacité non déclarée : refusées (L1, portée runtime gouverné) |
| Réseau | accès hors classe journalisé et détecté | registre inconnu refusé ; connexion directe hors mécanisme d'application bloquée (pare-feu ou bac à sable) |
| Budget unique | modification du compteur détectée (L1) | modification du compteur dans le State Store sans effet (L2) |
| Twin (sécurité) | — | concordance DECLARED_FILE + DETECTED refusée comme SECURITY_ELIGIBLE |
| Resource Broker | dépassement journalisé | quota atteint : création d'environnement refusée |
