# ADR-0012 — Revue de code humaine : une preuve REVIEW vient de la commande humaine

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0012 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | « valide » du Factory Owner, 15/10/2026, sur la proposition T-FACTORY-018 |
| Rédaction | agent de construction — ticket T-FACTORY-018 |
| Remplacé en partie par | à son gel, ADR-0017 (D31 : canal de décision par le Decision Center) ; l'exigence de revue de code humaine avant fusion est maintenue — traçabilité ajoutée le 16/10/2026 |

## Contexte

Le premier ticket pilote T-GF-001 est arrivé à IMPLEMENTED. Pour passer CODE_REVIEW, le moteur d'états exigeait
une preuve REVIEW « réussie » dont le relecteur (`verified_by`) diffère de l'auteur. Rien ne liait ce relecteur à un
humain : un agent pouvait écrire `verified_by: "humain:revue"` et passer (test `test_relecteur_distinct`, qui
validait ce comportement). C'est l'imitation d'un acte humain que la décision W1 interdit.

## Décision

1. **Demande de revue** (`Plateforme.demander_revue`) : l'agent prépare le contexte exact relu — ticket, exécution,
   auteur, branche, base, fichiers, empreinte SHA-256 du **diff complet** (fichiers suivis et nouveaux), preuves des
   gates — dépose le diff dans `compliance/evidence/artifacts/` et la demande dans `audit/approvals/requests/`.
2. **Décision humaine** : la même commande `scripts/factory_approve.py`, lancée par l'humain dans sa console. Pour
   une demande `CODE_REVIEW`, elle vérifie l'empreinte du diff puis l'affiche. `APPROUVE` = revue favorable,
   `REFUSE` = modifications demandées. Rôles admis : `review_roles` de `policies/human-approval.yaml`.
3. **Preuve REVIEW** (`Plateforme.preuve_revue`) : recalcule le contexte sur le code actuel ; si le diff a changé
   depuis la revue, la revue ne vaut plus. La preuve est la copie à l'octet près de l'enregistrement humain et le
   cite (`approval_ref`).
4. **Moteur d'états** : nouvelle exigence `human_review: APPROVED | CHANGES_REQUESTED`
   (`policies/transitions.yaml`). CODE_REVIEW → QA / SPECIALIST_REVIEW / DB_REVIEW / SECURITY_REVIEW exige une revue
   humaine APPROVED ; CODE_REVIEW → IN_PROGRESS exige CHANGES_REQUESTED. Le moteur relit l'enregistrement : canal de
   la commande humaine, empreinte intacte, type CODE_REVIEW, même ticket et même projet, rôle admis, preuve identique à
   l'enregistrement, relecteur identique.

## Conséquences

- Une revue déclarée par l'agent est refusée (`test_revue_declaree_par_l_agent_refusee`).
- Pas d'héritage : la revue d'un autre ticket, ou une approbation qui n'est pas une revue, ne compte pas.
- Une revue ne périme pas avec le temps : c'est l'empreinte du diff qui la lie au code relu.
- Toute revue de code est humaine, quel que soit le niveau (C0–C4). Assouplir pour C0/C1 (relecteur agent évalué)
  exigera un nouvel ADR.
- Limite inchangée (ADR-0006) : hors des sessions de la Factory, rien n'empêche techniquement un agent compromis
  d'écrire dans `audit/approvals/human/` ; W1 reste atténuée, pas fermée.
