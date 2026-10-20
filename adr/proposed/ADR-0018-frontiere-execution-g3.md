# ADR-0018 — Frontière d'exécution G3 : service d'autorité sous un compte séparé (L2 minimal, poste unique)

| Champ | Valeur |
|---|---|
| Identifiant / version | ADR-0018, v1 du 17/10/2026 |
| Statut | **proposé** — rédigé par l'agent de construction sur délégation du Factory Owner ; à accepter par lui |
| Applique | ADR-0017 : D23 (Trust Store), D36 (racine de confiance), D38 (executor), D42 (TCB), garanties L2 G1, G2, G3 ; Playbook v3.3 §17 (G3) |
| Propriétaire | Factory Owner (humain) |

## 1. Contexte

Tout ce que G1, G2 et G4 ont livré est **L1** : la clé des baux, le journal, les références d'épinglage et les
approbations sont lisibles et modifiables par le compte qui exécute aussi les agents. Une altération est détectée,
pas empêchée (ADR-0017 R2). G3 crée la première frontière **technique** : ce qui fait autorité vit sous un compte
que l'agent ne peut pas utiliser.

## 2. Décision

1. **Compte de service** `factory-svc` : compte local standard (non administrateur), sans session interactive,
   mot de passe long tenu par l'humain seul.
2. **Arborescence protégée** `C:\ProgramData\SoftwareFactory\` :
   - `service\` : copie figée du code du service d'autorité et du cœur qu'il exécute ; Administrateurs : contrôle
     total ; `factory-svc` : lecture et exécution ; compte de l'agent : lecture ;
   - `trust\` : clé de service, journal d'autorité, références d'épinglage ; `factory-svc` : modification ;
     compte de l'agent : **aucun accès** à `trust\keys\`, lecture seule du journal.
3. **Service d'autorité** : processus lancé au démarrage par le Planificateur de tâches sous `factory-svc`,
   joint par un canal local nommé (`\\.\pipe\factory-authority`) dont la liste d'accès admet le compte de l'agent en
   connexion seulement. Opérations v1 : `issue_lease` (le service rejoue lui-même le Policy Engine depuis sa copie
   figée, puis signe), `verify_lease`, `append_authority_event`, `pin_status`. Le client de la Factory n'envoie que
   des demandes ; il ne reçoit jamais la clé.
4. **Clé de service** : engendrée par le service à son premier démarrage, dans `trust\keys\`, jamais lisible par
   le compte de l'agent. Sa certification par l'ORK (D36) suit lors de la cérémonie ; jusque-là la clé est
   `L2-UNCERTIFIED` et le dit.
5. **La clé provisoire L1** (`factory key init`) est retirée dès que le service répond : un bail émis par la clé L1
   n'est plus reconnu.

## 3. Répartition

| Qui | Quoi |
|---|---|
| Humain (administrateur, session à part) | relire puis exécuter le script fourni : création du compte, des dossiers, des listes d'accès, de la tâche planifiée ; choisir le mot de passe ; accepter cet ADR |
| Agent de construction | code du service et du client, protocole, tests en processus, script d'installation **à relire**, essais négatifs de l'annexe E rédigés |

L'agent n'exécute ni le script d'installation ni aucune commande d'administration : créer un compte et poser des
listes d'accès est un acte d'administrateur humain (P22).

## 4. Ce que G3 garantit, et ce qu'il ne garantit pas

- **Garanti contre un agent ou un runtime compromis sous le compte de l'utilisateur** (L2, dans le TCB) : il ne lit
  pas la clé, donc ne forge pas de bail ; il n'écrit pas le journal d'autorité ; il ne déplace pas une référence
  d'épinglage.
- **Non garanti** : un administrateur, ou une élévation de privilèges accordée à l'invite UAC par l'humain, est
  dans le TCB (D42) ; le compte de l'utilisateur étant administrateur du poste, **l'invite UAC fait partie de la
  frontière** et ne doit jamais être acceptée pour une demande venue d'un agent ; un poste unique n'offre pas de
  séparation des pouvoirs entre humains.

## 5. Preuves exigées (ADR-0017 annexe E) avant `ENFORCED_PREVENTIVE`

Depuis une vraie session d'agent lancée par la Factory : lecture de `trust\keys\` refusée par le système ;
écriture du journal d'autorité refusée ; bail forgé ou rejoué refusé par `verify_lease` ; service arrêté →
aucun bail émis (refus par défaut). Preuves scellées, revues par le Factory Owner.

## 6. Conséquences

- Les baux, l'épinglage et le journal d'autorité passent de L1 à L2 **pour ce qui est protégé par le compte de
  service** ; le reste de `audit/` reste L1 jusqu'à la migration D23.
- Coût : un processus résident, une tâche planifiée, un compte à garder.
