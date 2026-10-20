# Bilan du pilote GestionFil — phase 1 (15/10/2026)

Critère de la phase 1 (guide d'utilisation) : **10 tickets C1/C2 menés de bout en bout** sur le projet pilote.
**Atteint** (VÉRIFIÉ : fiches `registry/projects/gestionfil/tickets/`, journal `audit/journal.jsonl`, 237 événements
chaînés valides).

## Tickets

| Ticket | Niv. | Nature | Commit fusionné |
|---|---|---|---|
| T-GF-001 | C1 | tests `nombreOuZero`, `lireNombre` | f06df9d |
| T-GF-002 | C1 | tests `versCsv` (2 exécutions : la 1re bloquée par une différence d'extraction) | 8002c15 |
| T-GF-003 | C1 | **correction** export CSV : NaN/∞ → cellule vide | 1552e47 |
| T-GF-004 | C1 | tests des conversions du conditionnement | f0b8e11 |
| T-GF-005 | C1 | tests de la règle de suppression, écran ↔ serveur | 50015da |
| T-GF-006 | C1 | **correction** saisie d'espaces lue 0 | ebaa0fb |
| T-GF-007 | C1 | **correction** `pourChamp(NaN)` | 5f8d2d0 |
| T-GF-009 | C1 | **correction** `fmt` : NaN/∞ → « — » dans toute l'application | 3dc9f17 |
| T-GF-010 | C1 | **correction** clôture de réception « soit NaN MAD » | a28c3d2 |
| T-GF-011 | C2 | **correction** retour fournisseur : avoir enregistré à 0 DH | e427e9a |

En attente (C2, consignés) : T-GF-008 (palettes selon `arrondi_palette`), T-GF-012 (coefficient de saison vidé
enregistré à 0), T-GF-013 (factures : valeurs illisibles envoyées).

## Ce que le pilote a prouvé (VÉRIFIÉ)

- Chaque ticket : autorisation du Policy Engine, espace isolé et branche dédiée, écriture limitée au périmètre
  (R25 refuse le reste), contrôle du diff, gates du manifest avec preuves, **revue par la commande humaine**,
  fusion constatée (contenu fusionné = contenu relu, aux fins de ligne près).
- Aucun débordement de périmètre ; aucune fusion sans revue humaine enregistrée ; les « approuvé » écrits dans le
  chat n'ont jamais été pris pour des revues.

## Défauts de la Factory révélés et corrigés

| Ticket | Défaut | ADR |
|---|---|---|
| T-FACTORY-017 | R09 bloquait l'écriture de sources dans l'espace isolé | ADR-0011 |
| T-FACTORY-018 | une revue « humaine » pouvait être déclarée par l'agent | ADR-0012 |
| T-FACTORY-019 | différences d'extraction (fins de ligne) et sorties des gates prises pour des changements | ADR-0013 |
| T-FACTORY-020 | tickets jamais validés ; preuve de diff vide ; espace sans dépendances | ADR-0014 |
| T-FACTORY-021 | plafond des habilitations provisoires (décision : C1 → C2) | ADR-0015 |

## Écarts de l'agent (consignés au journal)

- Un lancement direct de `node --test` hors plateforme (T-GF-002, refusé a posteriori par R13).
- Un dossier d'exécution non conservé par le script de l'opérateur, reconstruit et marqué comme tel.

## Limites et suites

- Commit et fusion faits par l'agent **sur autorisation explicite du propriétaire, ticket par ticket** : tracé
  comme tel dans les commits et le journal, jamais présenté comme un acte humain.
- Aucun essai d'écran réel (base et serveur interdits à l'agent) : T-GF-011 est à essayer par le propriétaire.
- Restent ouverts : les 11 protections ABSENT de `security/threats.yaml`, la sauvegarde hors site, le premier commit
  du dépôt de la Factory, la revue des tickets T-FACTORY-015 à 021, l'évaluation formelle de l'agent `qa`.
