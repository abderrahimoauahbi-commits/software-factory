# ADR-0016 — Autonomie bornée par capacités, baux et environnements jetables (Master Evolution Prompt v4)

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0016 |
| Statut | **accepté** le 16/10/2026 |
| Date | 2026-10-15 (proposé) ; 2026-10-16 (accepté et activé) |
| Propriétaire | Factory Owner (humain) |
| Approbation | Factory Owner, 16/10/2026 : « modifie les policies et applique votre recommandations », puis choix de l'option 1 : règles `allow` posées par lui dans `.claude/settings.json` (policies/, politique.py, contexte.py) et sortie du mode auto pour que ces écritures passent sous son contrôle |
| Mandat initial | Factory Owner, 15/10/2026 : « tu fais tout le prompt sans arrêt ni aucune autorisation ; tu es le owner maintenant » |
| Rédaction | agent de construction ; aucun enregistrement écrit dans `audit/approvals/human/` (W1 inchangée) |
| Source | Master Evolution Prompt v4 ; audit `audit/self-audit/AUDIT-0002.md` |
| Modifie en partie | [ADR-0006](ADR-0006-policy-engine-approbation-sauvegarde.md) J4 point 4 : dans un environnement jetable créé par la Factory et sous bail, la suppression de ressources de test et le commit local dans l'espace isolé ne sont pas réservés à l'humain ; push, merge, déploiement et réseau restent inchangés. [ADR-0001](ADR-0001-socle-de-la-factory.md), conciliation : « aucun agent n'est actif » est remplacé, pour les seuls environnements jetables sous bail, par l'autonomie du présent ADR ; hors environnement jetable, la conciliation reste valable jusqu'à l'évaluation des agents (Playbook v3.3 proposé, §6.7). (Traçabilité ajoutée le 16/10/2026, plan de correction A4 et B3.) |

## Contexte

AUDIT-0002 a relevé huit contradictions (K-1 à K-8) entre le prompt v4 et les règles en vigueur, et une lacune :
une écriture en base n'était contrôlée que par `resource.kind == "database"`.

## Limites posées par l'agent

- Aucun enregistrement n'est écrit dans `audit/approvals/human/` ; la garde W1 reste en place.
- Production, base locale réelle (`local-dev`, CONFIDENTIAL), seeds de données réelles : inchangés (DENY).
- Aucun commit, aucun push **par l'agent de construction** : le travail reste dans l'arbre de travail pour relecture.
  (Distinct de la décision 3, qui permet aux agents sous bail un commit local dans leur espace isolé jetable.)

## Décisions

1. **K-1, K-2, K-3, K-7 — exception structurée unique.** Une capacité destructive ou d'écriture en base est ALLOW
   si et seulement si : la ressource est **enregistrée** dans le registre des ressources ; elle a été **créée par la
   Factory** (`owner: factory`) ; elle est `disposable: true` ; son **identité est vérifiée à l'appel** (empreinte
   relevée à la création, jamais le nom) ; son profil d'environnement est jetable ; un **bail actif** de l'exécution
   courante la couvre. Hors de ce cas, les refus antérieurs s'appliquent sans changement.
2. **K-4 — reprise.** Un échec dans le budget (tentatives, durée) déclenche diagnostic, reset, nouvelle tentative ;
   jamais WAITING_HUMAN. Budget épuisé : `BUDGET_STOP` (état existant), puis escalade. WAITING_HUMAN est réservé à
   une décision APPROVAL_REQUIRED du Policy Engine (frontières du §49).
3. **K-5, K-6 — niveau A2.** Dans un environnement jetable sous bail : base de test, processus locaux de
   l'environnement, commits **locaux** dans l'espace isolé. Installation de paquets et réseau public restent refusés
   tant qu'une politique de projet ne les accorde pas (profil, destination, durée).
4. **K-8 — numérotation.** Les jalons d'évolution sont nommés **E0, E1…** ; l'historique J1–J13 est conservé.
5. **Agents non évalués.** Dans un profil jetable, un agent du registre agit sous bail si le projet l'autorise et
   si sa fiche déclare la capacité. Hors profil jetable, l'évaluation (ou l'habilitation provisoire) reste exigée.
6. **Une capacité n'existe que dans un bail** : acteur × projet × exécution × ticket × environnement × ressources ×
   capacités × durée × budget ; révoqué à la fin de l'exécution ; émission, refus et révocation audités.
7. **La Factory crée la base, elle n'en choisit pas une.** Le premier fournisseur crée un cluster privé par
   environnement (répertoire sous `workspaces_root`, écoute 127.0.0.1, port libre, rôle éphémère).

## Mise en œuvre (16/10/2026)

| Élément | Où | Preuve |
|---|---|---|
| Politique active : niveaux A0–A3, capacités, matrice par profil, classification, profils ↔ environnements du manifest, capacités du catalogue → capacités opérationnelles | `policies/autonomy.yaml` (`status: active`) | `test_politique_capacites.py` |
| Action `use_capability` (version 1.1) | `policies/policy-engine.yaml` | idem |
| Règles R30–R39 : R30 politique non active ; R31 capacité inconnue ou mauvais genre de ressource ; R32 ressource non enregistrée, d'un autre projet ou inactive ; R09 production toujours refusée à un agent ; R33 profil inconnu ou non déclaré par le manifest ; R08 criticité au-delà de l'agent ; R39 capacité non déclarée par la fiche de l'agent ; R34 niveau d'autonomie ; R35 matrice du profil ; R36 destructif hors ressource jetable créée par la Factory ; R37 identité non vérifiée à l'appel ; R38 approbation humaine (données au-delà d'INTERNAL, niveau A1, capacités `approval`) | `core/noyau/politique.py : _capacite` | idem (17 essais, dont 15 négatifs) |
| Agent non évalué admis seulement sur ressource jetable du registre (décision 5) | `politique.py : _ressource_jetable` | idem |
| Moteur branché sur le registre des ressources (seule source de l'identité) | `core/noyau/contexte.py`, `core/fournisseurs/cablage.py` | `test_baux.py`, E1 |
| `security-defaults.yaml` 1.1 : exception unique documentée | `policies/security-defaults.yaml` | — |
| Fiche `database` : capacité de catalogue DATABASE_MIGRATION (son rôle : « migrations hors production ») | `registry/agents/database.yaml` | E1 |
| E1 sur le pilote avec le VRAI moteur : 6 baux accordés par R35, tous libérés ; refus R04 sans registre, R39 pour `qa`/DATABASE_DROP | `core/tests/test_pilote_e1.py` | `compliance/evidence/E1/` |

Révocation : `status: suspended` dans `policies/autonomy.yaml` suffit à refuser toute capacité (R30, testé).
