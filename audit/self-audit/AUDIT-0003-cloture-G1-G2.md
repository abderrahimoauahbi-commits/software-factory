# AUDIT-0003 — Revue de clôture des phases G1 (Fondations) et G2 (Décision)

| Champ | Valeur |
|---|---|
| Date | 2026-10-17 |
| Demande | Playbook v3.3 §17.2 règle 3 : chaque phase se termine par une revue qui peut ajuster la suite |
| Méthode | relecture du code et de l'annexe D de l'ADR-0017 ; suites de tests ; `factory check`, `pin status`, `decide list` |
| Réserve d'indépendance | auditeur = agent de construction (même modèle que l'auteur) : pas une revue indépendante (Playbook §12.3) ; à relire par le Factory Owner |
| Statut | **G1 et G2 IMPLEMENTED en L1** ; aucune frontière `ENFORCED` ; G4 ouverte (règle 17.2-1) |

## 1. Mesures relevées

| Mesure | Valeur | Preuve |
|---|---|---|
| Tests du cœur | 414, dont 413 verts ; seul échec attendu : `factory check` BLOCKED par l'épinglage tant que la nouvelle référence n'est pas approuvée | `python -P -m unittest discover -s core/tests -t core -p "test_*.py"` |
| Tests du Bootstrap | 2, verts | `python -P -m unittest discover -s bootstrap/tests -t bootstrap -p "test_*.py"` |
| Journal d'audit | chaîne intacte (AE-000261 au 17/10/2026) | `python -P factory.py state check` |
| Normes | Playbook v3.3 adopté (17/10/2026) ; ADR-0017 v5 gelé (17/10/2026) | `docs/playbook/`, `adr/accepted/` |
| Exécution d'agents | BLOCKED : 15 agents `DISCOVERED`/`NOT_EVALUATED`, 0 modèle approuvé | `python -P factory.py check` |

## 2. G1 — Fondations

| Frontière (Playbook §17) | Livré | Niveau réel | Limite principale |
|---|---|---|---|
| Identité | refus d'une identité humaine déclarée par la requête (R01) ; rôle pris du contexte d'appel | IMPLEMENTED | aucun service n'authentifie un humain : toute action humaine par la CLI est refusée |
| Catalogue des règles | `policies/rule-catalog.yaml`, nature des refus, explication | IMPLEMENTED | — |
| Exceptions bornées (I5) | `PEX-…` = approbation W1 d'une portée exacte ; lève sa seule règle | IMPLEMENTED | aucun exécutant ne consomme encore d'usage |
| Épinglage | 26 fichiers de gouvernance, référence approuvée par l'humain, BLOCKED au lancement | IMPLEMENTED | détectif ; qui forge une approbation forge la référence (NE2) |
| Baux authentifiés | HMAC, empreinte de politique, `INVALIDATED` ; clé provisoire L1 `L1-b430e9949aff` | IMPLEMENTED | clé lisible par le compte (R2) ; cérémonie D36 non tenue |
| Hook du bail | garde PreToolUse par session lancée par la Factory | IMPLEMENTED | aucune vraie session ; pas d'arrêt du runtime à l'expiration |
| Demandes (I8) | dédoublonnées, quota de 20 ouvertes | IMPLEMENTED | écriture directe dans le dossier des demandes non empêchée |
| Resource Broker | quotas d'environnements et de disque | IMPLEMENTED | dépassement en cours constaté, pas empêché |
| Stores, journal d'autorité, racine de confiance | — | ARCHITECTURE_ONLY | sans service L2 (G3), une migration n'apporterait aucune protection |

## 3. G2 — Décision

| Frontière | Livré | Niveau réel | Limite principale |
|---|---|---|---|
| Decision Center | `factory decide list\|show\|prune` : demandes et états, sans jamais décider | IMPLEMENTED (L1, CLI) | pas de service identifié ni de canal protégé (G3) |
| Exécution humaine | `factory plan request\|execute` : étapes exactes approuvées, usage unique, journalisées (I7) | IMPLEMENTED | refus en session d'agent : garde procédurale ; executor non séparé (G3) |
| Exceptions bornées | voir G1 | IMPLEMENTED | — |

## 4. Écarts et incidents de la période

1. **Garde W1 et construction dynamique de chemin** : une commande de l'agent construisait le chemin des approbations
   par concaténation (motif NE2) ; neutralisée avant exécution, tracée (AE-000254). Le défaut NE2 reste ouvert.
2. **Classifieur du mode auto** : plusieurs actes de gouvernance (adoption, statuts) refusés ; non contournés ;
   réalisés ensuite hors mode auto, chaque modification validée par le Factory Owner (AE-000255 à AE-000260).
3. **Adoption et gel sans attestation W1** : décidés par le Factory Owner en conversation, tracés au journal.
4. **EXC-0003** a pris fin à sa première échéance (gel de l'ADR-0017) ; la construction se poursuit sur instruction
   explicite, tracée.

## 5. Ajustements de la suite (décision de l'agent sur délégation du Factory Owner, 17/10/2026)

- **G4 ouverte avant G3** (règle 17.2-1) : l'évaluation se fait sous bail en environnement jetable, disponible depuis
  G1 ; elle débloque l'exécution d'agents sur le pilote (règle 17.2-2).
- **Registre des agents et des modèles à épingler** : l'état `APPROVED` d'un agent est lu dans `registry/agents/`,
  modifiable par le même compte ; l'habilitation devient une décision humaine W1 liée aux preuves d'évaluation, et
  ces fichiers entrent dans l'épinglage.
- **G3 avant tout accès STAGING ou PRODUCTION** : condition maintenue.
