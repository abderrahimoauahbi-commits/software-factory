# ADR-0015 — Habilitation provisoire : plafond relevé de C1 à C2

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0015 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | choix « Relever à C2 (Recommandé) » du Factory Owner, 15/10/2026 |
| Rédaction | agent de construction — ticket T-FACTORY-021 (l'agent ne relève pas son propre plafond : décision humaine) |
| Remplace | le plafond C1 de l'ADR-0010 (le reste de l'ADR-0010 demeure) |

## Contexte

Pilote GestionFil : 9 tickets C1 fusionnés après revue humaine, sans débordement de périmètre. Le parcours des
écrans a trouvé des défauts qui touchent des **données enregistrées** — dont un avoir fournisseur enregistré à 0 DH
pour un prix saisi « 1.234,56 » (T-GF-011) — donc C2, hors de l'habilitation provisoire plafonnée à C1.

## Décision

1. `policies/policy-engine.yaml` : `provisional_habilitation.criticality_cap: C2`. C3 et C4 restent interdits à toute
   habilitation provisoire.
2. Fiche `registry/agents/qa.yaml` : `permissions.max_criticality: C2` (phase 1 plafonnée à C2, Playbook §17) et
   `provisional_habilitation.max_criticality: C2`, mêmes projet (gestionfil) et dates (30 jours au plus).
3. Le contexte d'habilitation change : l'approbation C1 (HA-20261015T173953-d9412803) **ne vaut plus**. Une nouvelle
   demande (`audit/approvals/requests/AR-HAB-qa-C2-*.json`) doit être approuvée par la commande humaine ; d'ici là,
   `qa` n'a plus aucune habilitation (VÉRIFIÉ).

## Conséquences

- Les tickets C2 restent soumis à la revue humaine par la commande (ADR-0012) et à la fusion décidée par l'humain.
- Tests : C2 approuvée permet C2 ; C3/C4 refusés ; une fiche relevée à C2 sans nouvelle approbation est refusée
  (`test_c1_approuvee_ne_vaut_pas_c2`).
