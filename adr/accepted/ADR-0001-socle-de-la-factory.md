# ADR-0001 — Socle de la Factory : emplacement, structure, langage, dépôt

| Champ | Valeur |
|---|---|
| Identifiant | ADR-0001 |
| Statut | accepté |
| Date | 2026-10-15 |
| Propriétaire | Factory Owner (humain) |
| Approbation | Factory Owner, le 2026-10-15 (choix explicites en session, options recommandées retenues) |
| Rédaction | agent Claude Code (Claude Opus 5.5) — rédige, ne décide pas (Playbook P02, §3.1) |
| Remplacé en partie par | [ADR-0002](ADR-0002-cycle-schemas-et-corrections.md) (F-03 : emplacement des brouillons de projet) ; [ADR-0016](ADR-0016-autonomie-bornee-par-capacites.md) (conciliation « aucun agent n'est actif », pour les seuls environnements jetables sous bail) ; à son gel, ADR-0017 (§1 : emplacement du manifest, profil `.factory/project.yaml`) — traçabilité ajoutée le 16/10/2026 |

## Contexte

La construction de la Factory démarre (Playbook v3.2, phase 1 — MVP). L'instruction de construction
du 15/10/2026 et le Playbook divergent sur quatre points ; l'instruction demande de signaler toute
contradiction au lieu de trancher. Le Factory Owner a tranché.

## Problèmes et décisions

### 1. Où vivent le manifest et le contexte d'un projet (contradiction X1)

- Instruction : `software-factory/projects/gestionfil/{factory.yaml, AGENT_CONTEXT.md, CLAUDE.md}`.
- Playbook : dans le projet (§16.2 structure d'un projet, §2.5 « chaque projet conserve son manifest »).
- Fait technique (documentation Claude Code, vérifiée le 15/10/2026) : `CLAUDE.md` n'est chargé que
  depuis le dossier de travail et ses parents ; un fichier rangé dans la Factory n'est pas lu quand
  l'agent travaille dans le dépôt du projet.

**Décision** : le manifest `factory.yaml` et `AGENT_CONTEXT.md` vivent **dans le dépôt du projet**.
La Factory prépare des **brouillons** dans `projects/<id>/` ; leur copie dans le projet est une
action `WAITING_HUMAN`. La Factory tient une fiche `registry/projects/<id>.yaml` qui pointe vers le
dépôt et le manifest.

### 2. Noms et rangement (contradictions X2, X3)

**Décision** : noms du Playbook. `policies/` (et non `policy/`). Les fiches vivent dans `registry/`,
**source unique** avec leur statut de cycle de vie ; `catalog/` est un **index engendré** des fiches
`approved | available | active`, jamais écrit à la main (aucune fiche en double).

### 3. Manifest incomplet (contradiction X4)

Le manifest de l'instruction omet des champs du §7.5 (`criticality_default`, `data_classification`,
`compliance`, `budget` — règle absolue 21). **Décision** : les champs sont présents, valeur
`WAITING_HUMAN` tant que l'humain ne les fixe pas ; aucun chiffre n'est inventé.

### 4. Langage de l'outillage de la Factory

Options : Python + PyYAML, PowerShell 7, Rust. **Décision** : Python ≥ 3.12 + PyYAML — présent sur le
poste (3.14.2 / 6.0.3, vérifié), portable Windows/Linux, lit le YAML sans conversion, aucune
compilation. Une seule dépendance tierce.

### 5. Dépôt

**Décision** : `C:\Users\vboxuser\Desktop\software-factory`, Git local, branche `main`, **rien n'est
poussé**. La publication (GitHub privé) est une décision ultérieure.

## Conciliations sans décision (consignées)

- L'instruction demande les politiques C0–C4 et 15 agents ; le Playbook limite le MVP à C0–C2 (§17)
  et interdit un agent actif sans évaluation (règle 19). Les éléments sont **écrits** mais marqués
  « cible » ou `candidate` (§17.2 règle 4) ; aucun n'est actif.
- Le Bootstrap CHECK ne **lance aucun serveur MCP** (`claude mcp list` démarre les serveurs, donc
  exécute du code non évalué) : il lit les configurations. La santé d'un MCP reste `UNKNOWN` tant que
  le MCP n'est pas évalué au Lab.

## Conséquences

- Intégrer un projet demande une action humaine dans son dépôt (copie du manifest et du contexte).
- Le Bootstrap doit chercher le manifest dans le projet, puis le brouillon, en le signalant.
- PyYAML devient une dépendance de la Factory (fiche `registry/tools/pyyaml.yaml`).

## Risques

- Divergence entre brouillon et manifest copié : le Bootstrap compare les deux et le signale.
- Dépendance PyYAML : surface faible, remplaçable par un autre lecteur YAML.
