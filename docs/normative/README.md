# docs/normative — textes normatifs et hiérarchie des sources (décision M4)

Une implémentation ne devient **jamais** normative parce qu'elle existe dans le dépôt. L'autorité descend :

| Niveau | Rôle | Où | Peut contredire le niveau supérieur ? |
|---|---|---|---|
| 1. **Norme** | Règles durables | ce dossier + `docs/playbook/` | — |
| 2. **Politique** | Application des normes, en données | `policies/`, `core/schemas/` | non : écart = ADR + approbation |
| 3. **Implémentation** | Code et configuration | `core/`, `bootstrap/`, `scripts/`, `registry/` | non : l'implémentation suit la politique |
| 4. **Test** | Spécification exécutable du comportement attendu | `core/tests/`, `bootstrap/tests/` | non : un test ne redéfinit pas une politique |
| 5. **Preuve** | Résultat observé d'une exécution | `compliance/evidence/`, `audit/` | ne prescrit rien : elle constate |

Les ADR (`adr/accepted/`) tranchent les contradictions entre normes et fixent les extensions ; ils n'ont pas
autorité pour modifier un texte normatif (Playbook §15.4 : nouvelle version du standard).

## Textes normatifs

| Texte | Statut dans le dépôt | Empreinte |
|---|---|---|
| AI Software Factory — Playbook v3.2 | ✔ `docs/playbook/playbook-v3.2.md` (copie de l'original du Factory Owner) | sha256 `a98ab8c1…` (vérifiée par le Bootstrap) |
| Master Package v3.2 | **à déposer** : `docs/normative/master-package-v3.2.md` | — |
| Executable Schemas v1.0 | **à déposer** : `docs/normative/executable-schemas-v1.0.txt` ; forme exécutable : `core/schemas/` | — |
| State Machines & Contracts v1.0 | **à déposer** : `docs/normative/state-machines-contracts-v1.0.md` | — |
| Cycle opérationnel complet | **à déposer** : `docs/normative/cycle-operationnel.md` | — |
| Guide d'utilisation v1.0 | **à déposer** : `docs/normative/guide-utilisation-v1.0.md` | — |

Dépôt par le **Factory Owner** à partir des originaux : l'agent ne les recopie pas (une des copies reçues en
session était tronquée). Une fois déposés, leur empreinte sera vérifiée par le Bootstrap comme celle du Playbook.
