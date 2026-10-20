# Registry v1

Source unique des fiches (ADR-0001) ; `catalog/` en sera l'index engendré des fiches approuvées.
Chaque fiche suit son schéma de `core/schemas/objects/` et son cycle de vie de `core/schemas/lifecycles.yaml`.

| Registre | Fiches | État au 15/10/2026 |
|---|---|---|
| `capabilities/` | 34 | vocabulaire des politiques (Executable Schemas §27) ; une capacité désigne ses outils |
| `tools/` | 27 | outils de base `APPROVED` par adoption humaine initiale (évaluation formelle due) ; sécurité `CANDIDATE` ; autres `DISCOVERED` |
| `mcp/` | 14 | tous `DISCOVERED` : 4 fentes génériques candidates + 10 MCP observés, **aucun approuvé** |
| `models/` | 4 | `DISCOVERED` ; caractéristiques non renseignées (benchmark à faire) |
| `agents/` | 15 | rôles `DISCOVERED`, non habilités (évaluation requise, Playbook §12.6) |
| `skills/` | 0 | aucune skill enregistrée (ADR-0002, extension 5) |
| `workflows/` | 11 | `DRAFT` |
| `projects/` | 2 | `gestionfil` (pilote, `REGISTERED`, manifest en brouillon) ; `software-factory` (la Factory elle-même) |

**Aucune version n'est écrite dans les fiches** : le Bootstrap les détecte et les cite comme preuves.
Toute fiche est validée à chaque CHECK ; une fiche invalide (`VALIDATION_FAILED`) bloque la Factory.
