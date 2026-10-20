# ADR-0006 — Policy Engine v1, approbation humaine (W1) et sauvegarde (D2)

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0006 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | décisions 1 à 7 du Factory Owner du 15/10/2026 (APR-0005) |
| Rédaction | agent de construction (Claude Opus 5.5) |
| Remplacé en partie par | [ADR-0016](ADR-0016-autonomie-bornee-par-capacites.md) (J4 point 4, ressources jetables sous bail) ; à son gel, ADR-0017 (J4 point 1, J4 point 4, W1, D2) — traçabilité ajoutée le 16/10/2026 |

## D2 — Sauvegarde, préalable à J4 opérationnel

- Outil générique `core/noyau/sauvegarde.py` + `scripts/factory_backup.py` ; politique `policies/backup.yaml` ;
  procédure `docs/operations/restauration-factory.md`.
- Destination **`F:/software-factory-backups`**, autre lecteur que la Factory (exception EXC-0002 : écriture
  limitée à ce répertoire). Jamais d'écrasement (création exclusive), jamais de restauration par-dessus.
- Preuve exigée au-delà de la copie : empreinte de l'archive, manifeste interne par fichier, restauration
  d'essai dans un répertoire temporaire avec revalidation du registre et du Playbook. Archive piégée refusée.
- Limites : copie sur le même poste ; pas d'historique Git (aucun commit) ; RPO et copie hors poste :
  `WAITING_HUMAN`.

## J4 — Policy Engine v1

1. **Trois décisions** seulement, comme exigé : `ALLOW`, `DENY`, `APPROVAL_REQUIRED`. Écart avec
   l'énumération `DECISION` des Executable Schemas (5 valeurs), tranché par le Factory Owner :
   `APPROVAL_REQUIRED` ≡ `WAITING_HUMAN` ; `WAITING_DEPENDENCY` et `ESCALATE` relèvent du moteur d'états (J5).
2. **Refus par défaut** : action inconnue, acteur inconnu, demande malformée, erreur d'évaluation → `DENY`.
3. Modèle évalué : QUI + QUOI + PROJET + TICKET + CRITICITÉ + ENVIRONNEMENT + RESSOURCE + ACTION + CHEMIN +
   OUTIL + MCP + APPROBATION + CONFIANCE. **Aucune règle dans le code** : `policies/policy-engine.yaml`,
   `policies/command-classes.yaml`, `core/schemas/trust.yaml`, registre, manifest du projet.
4. Règles notables : agent non habilité (registre) refusé ; criticité jamais abaissée ; ticket C0 = lecture
   seule ; production refusée à un agent même en lecture ; écriture seulement dans un espace isolé du même
   projet, dans les `paths.write` du projet **et** le périmètre du ticket ; `forbidden` et fichiers sensibles
   prioritaires ; liens et jonctions résolus avant contrôle ; commande non reconnue refusée (Master §12) ;
   commit contrôlé (approbation) ; push, merge, déploiement, suppression, réseau réservés à l'humain ;
   lecture permise à tout niveau (Playbook §9.2).
   *Note (16/10/2026) : « réservés à l'humain » signifie « soumis à une décision humaine » ; l'exécution peut être
   humaine ou confiée selon la politique en vigueur. Pour les ressources d'un environnement jetable sous bail, voir
   ADR-0016.*
5. Le moteur **n'est pas encore branché** sur l'agent d'exécution : il décide, rien ne l'impose encore.
   Le branchement (garde de l'agent) est une étape ultérieure, qui touche la configuration de l'agent
   (décision humaine).

## W1 — Approbation humaine par un acte que l'agent ne peut pas imiter

- Canal primaire : **commande lancée par l'humain** `scripts/factory_approve.py` sur une demande
  (`audit/approvals/requests/`) ; enregistrement en création exclusive dans `audit/approvals/human/`.
- Liaison au **contexte exact** (projet, ticket, criticité, acteur, action, ressource, commande, outil, MCP,
  périmètre) par empreinte SHA-256 ; tout changement de contexte invalide ; tout enregistrement modifié
  (empreinte propre) invalide ; rôle habilité par niveau ; durée de validité bornée.
- Les fiches `APR-*` écrites par l'agent ne sont **jamais** acceptées par le moteur.
- Gardes de la commande : console interactive en entrée **et** en sortie (constat : dans l'environnement de
  l'agent, l'entrée est interactive mais pas la sortie) ; refus en présence de variables d'environnement d'un
  runtime d'agent.
- **Risque résiduel** : ces gardes sont procédurales. Un agent compromis pourrait écrire un enregistrement
  complet. Fermeture : règles de refus côté agent (écriture dans `audit/approvals/human/`, exécution de la
  commande), à poser par l'humain ; statut `MITIGATED_PARTIAL` jusqu'à leur vérification par le Bootstrap.

## Autres décisions consignées

- **M3** : l'archive `/mnt/data/AI_Software_Factory_Implementation_v1.0.zip` est introuvable sur ce poste
  (chemin d'un autre environnement) : `PATH_NOT_FOUND`, aucune recherche ailleurs.
- **M2** : les `paths` proposés pour GestionFil restent `PROPOSED`, non normatifs.
- **M4** : `docs/normative/README.md` fixe la hiérarchie norme > politique > implémentation > test > preuve ;
  les textes restent à déposer par le Factory Owner.
- La liste des tests J4 reçue était tronquée (« sortie de PROJECT_ROOT ; ») : complétée par l'agent avec les
  cas du guide §15–§21 et des tests d'acceptation proposés ; à relire.
