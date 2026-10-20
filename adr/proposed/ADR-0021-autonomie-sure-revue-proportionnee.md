# ADR-0021 — Autonomie sûre : intervention humaine proportionnée au risque

| Champ | Valeur |
|---|---|
| Identifiant / version | ADR-0021, v1 du 19/10/2026 |
| Statut | **proposé** — à accepter par le Factory Owner |
| Décision d'origine | correction de gouvernance demandée par le Factory Owner le 19/10/2026, à la validation du découpage en tickets du projet GMAO |
| Propriétaire | Factory Owner (humain) |
| Rédaction | session de conception du projet GMAO, à la demande du Factory Owner |
| Modifie (à l'acceptation) | **ADR-0012** : la revue humaine n'est plus exigée pour chaque ticket, mais selon le profil de contrôle du § 3 |
| Prolonge | ADR-0016 (K-4 : l'attente d'un humain est réservée à une décision requise) ; ADR-0017 (P1 : la puissance dans la frontière est l'objectif du système ; P8 : décision humaine ≠ exécution humaine) |

## 1. Principe (normatif)

> **« L'objectif de la Factory n'est pas de maximiser le nombre de validations humaines, mais de maximiser le travail
> autonome sûr. L'humain intervient lorsque sa décision, sa responsabilité ou son jugement apporte une valeur
> réelle. »**
> — Factory Owner, 19/10/2026

## 2. Contexte

L'ADR-0012 impose une revue humaine, par la commande, à chaque ticket. Appliquée à tous les tickets d'un projet, elle
fait de l'humain un goulot : des tâches simples, déterministes, réversibles et entièrement couvertes par les gates
attendent une validation qui n'apporte pas de valeur.

## 3. Décision : quatre profils de contrôle

Chaque ticket déclare son **profil de contrôle**, qui distingue explicitement : l'exécution autonome autorisée, la revue
automatique, la revue spécialisée et la décision humaine obligatoire.

| Profil | Pour | Exécution | Revue automatique | Revue spécialisée | Décision humaine |
|---|---|---|---|---|---|
| **AUTONOME** | tâches simples, déterministes, réversibles, couvertes par les gates : documentation (C0), code local et tests (C1) | autonome, dès que l'agent est habilité pour le rôle et la criticité | Quality Gates + relecture par un agent **distinct de l'auteur** | non | aucune par ticket ; contrôle par échantillonnage et bilan de lot |
| **AUTONOME RELU** | changement applicatif réversible en environnement de développement (C2) | autonome, agent habilité | Quality Gates + relecture par un agent distinct | automatique, si le ticket touche la base ou la sécurité | aucune par ticket ; **démonstration humaine en fin de lot** |
| **C3** | changement sensible (Playbook § 9.1) | agent habilité à C3 pour son rôle, Factory autorisée à C3 | Quality Gates | **obligatoire** | **aux points du chemin C3 seulement** : confirmation de la criticité au démarrage (Playbook § 9.3), revue et fusion à la fin ; pas de validation de chaque sous-étape |
| **DÉCISION HUMAINE** | acte de décision, de responsabilité ou d'irréversibilité : habilitation, acceptation d'ADR, approbation du manifest, mise en service, production, données au-delà d'INTERNAL, suppression, C4 | — | — | — | **obligatoire** |

Règles :
1. Une **revue automatique** n'est jamais faite par l'agent auteur (Playbook P02 : pas de validation de son propre
   travail) ; elle produit une preuve enregistrée comme les autres.
2. Un gate en échec ou une relecture défavorable renvoie le ticket à l'agent ; trois échecs : arrêt et décision
   humaine (Playbook § 8.6).
3. Toute **frontière** de la Factory reste inchangée : production, données sensibles, destruction hors ressource
   jetable, politique de sécurité et habilitations restent des décisions humaines (ADR-0016, ADR-0017).
4. Le **profil ne s'abaisse jamais** pour faire passer un ticket ; en cas de doute, le profil le plus contrôlé
   s'applique (Playbook § 9.3).
5. **Mesure** : la Factory mesure le nombre d'interventions humaines, leur durée et leur valeur (rejets obtenus),
   pour ajuster les profils.

## 4. Conséquences

- La commande de revue de l'ADR-0012 reste l'outil des profils C3 et DÉCISION HUMAINE.
- Les politiques d'états (`policies/transitions.yaml`) et le moteur devront accepter une revue automatique pour les
  profils AUTONOME et AUTONOME RELU : travaux de la Factory à planifier.
- **Tant que cet ADR n'est pas accepté et mis en œuvre, l'ADR-0012 s'applique sans changement.**

## 5. Risques

| Risque | Parade |
|---|---|
| Erreur non vue sans revue humaine | gates obligatoires, relecture par un agent distinct, échantillonnage, démonstration de fin de lot, profil plus contrôlé en cas de doute |
| Dérive vers moins de contrôle | profil déclaré dans le ticket, jamais abaissé ; changement de profil = décision humaine |
