# security

| Élément | Statut |
|---|---|
| `threats.yaml` — modèle de menaces : chaîne contenu externe → agent → MCP → fichiers → Git → base → CI → production ; 16 menaces, contrôles avec statut VERIFIED / DECLARED / PLANNED / ABSENT | **implémenté** (J3b) ; cohérence et preuves contrôlées par `core/tests/test_modeles_securite.py` |
| Modèle d'identité et de confiance | `core/schemas/trust.yaml` (J3c) |
| Capacités de sécurité (Playbook §10.3) : détection de secrets, audit de dépendances, SAST | cible — outils au registre en `CANDIDATE` / `DISCOVERED` |

Règle : un contrôle n'est VERIFIED que s'il cite un test qui existe ; sinon il est DECLARED, PLANNED ou ABSENT.
Les contrôles ABSENT sont la liste de travail de la sécurité.
