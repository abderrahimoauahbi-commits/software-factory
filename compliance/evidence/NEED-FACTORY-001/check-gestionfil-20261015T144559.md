# FACTORY BOOTSTRAP CHECK — gestionfil

2026-10-15T14:45:59+00:00 · Bootstrap 1.0.0 · mode CHECK · résultat **PARTIAL**

| Factory | Analyse du projet | Exécution d'agents | Manifest |
|---|---|---|---|
| **READY** | **READY** | **BLOCKED** | DRAFT |

## Constats

| Id | Élément | État | Preuve | Gravité | Détail |
|---|---|---|---|---|---|
| F-ROOT | FACTORY_ROOT | READY | VERIFIED | INFO | C:\Users\vboxuser\Desktop\software-factory |
| F-PLAYBOOK | Playbook normatif | READY | VERIFIED | INFO | v3.2, empreinte conforme |
| F-REGISTRY | Registre et schémas | READY | VERIFIED | INFO | 107 fiches valides |
| P-ROOT | PROJECT_ROOT | READY | VERIFIED | INFO | C:\Users\vboxuser\Desktop\gestionFil |
| P-MANIFEST | Manifest du projet | WARNING | DECLARED | MEDIUM | manifest absent du projet : brouillon de la Factory utilisé |
| S-DISK-C | Espace libre C:\ | WARNING | VERIFIED | MEDIUM | 14.1 Go libres (seuil 20 Go) |
| C-AGENT_RUNTIME | AGENT_RUNTIME | READY | VERIFIED | INFO | claude-code 2.1.300 (approuvé) |
| C-BROWSER_TEST | BROWSER_TEST | READY | VERIFIED | INFO | playwright 1.56.1 (approuvé) ; msedge (NON approuvé) |
| C-BUILD | BUILD | READY | VERIFIED | INFO | cargo 1.93.1 (approuvé) ; npm 11.6.2 (approuvé) |
| C-CONFIG_PARSING | CONFIG_PARSING | READY | VERIFIED | INFO | pyyaml 6.0.3 (approuvé) |
| C-DATABASE_INSPECTION | DATABASE_INSPECTION | READY | VERIFIED | INFO | postgresql-client 18.4 (approuvé) |
| C-DEPENDENCY_AUDIT | DEPENDENCY_AUDIT | DEGRADED | VERIFIED | MEDIUM | hors outils du projet : cargo-audit (CANDIDATE), cargo-deny (CANDIDATE), npm-audit (CANDIDATE) |
| C-FACTORY_RUNTIME | FACTORY_RUNTIME | READY | VERIFIED | INFO | python 3.14.2 (approuvé) |
| C-FORMAT | FORMAT | READY | VERIFIED | INFO | rustfmt (approuvé) |
| C-IDE | IDE | READY | VERIFIED | INFO | vscode 1.142.0 (approuvé) |
| C-ISOLATED_WORKSPACE | ISOLATED_WORKSPACE | READY | VERIFIED | INFO | git 2.55.0.windows.4 (approuvé) ; vérification : disponible ; 1 espace(s) de travail |
| C-LANGUAGE_TOOLCHAIN | LANGUAGE_TOOLCHAIN | READY | VERIFIED | INFO | hors outils du projet : python (APPROVED) ; rustc 1.93.1 (approuvé) ; node 24.13.0 (approuvé) |
| C-LINT | LINT | READY | VERIFIED | INFO | clippy (approuvé) |
| C-PACKAGE_MANAGEMENT | PACKAGE_MANAGEMENT | READY | VERIFIED | INFO | cargo 1.93.1 (approuvé) ; npm 11.6.2 (approuvé) ; rustup 1.28.2 (approuvé) |
| C-SECRET_SCAN | SECRET_SCAN | DEGRADED | VERIFIED | MEDIUM | hors outils du projet : gitleaks (CANDIDATE) |
| C-SECURITY_SCAN | SECURITY_SCAN | DEGRADED | VERIFIED | MEDIUM | hors outils du projet : semgrep (DISCOVERED) |
| C-SOURCE_CONTROL | SOURCE_CONTROL | READY | VERIFIED | INFO | git 2.55.0.windows.4 (approuvé) ; vérification : dépôt Git valide |
| C-TEST | TEST | READY | VERIFIED | INFO | cargo 1.93.1 (approuvé) ; node 24.13.0 (approuvé) ; playwright 1.56.1 (approuvé) |
| C-TYPECHECK | TYPECHECK | READY | VERIFIED | INFO | typescript 5.9.3 (approuvé) |
| T-git | outil exigé : git | READY | VERIFIED | INFO | 2.55.0.windows.4 — APPROVED |
| T-claude-code | outil exigé : claude-code | READY | VERIFIED | INFO | 2.1.300 — APPROVED |
| T-rustc | outil exigé : rustc | READY | VERIFIED | INFO | 1.93.1 — APPROVED |
| T-cargo | outil exigé : cargo | READY | VERIFIED | INFO | 1.93.1 — APPROVED |
| T-node | outil exigé : node | READY | VERIFIED | INFO | 24.13.0 — APPROVED |
| T-npm | outil exigé : npm | READY | VERIFIED | INFO | 11.6.2 — APPROVED |
| T-postgresql-client | outil exigé : postgresql-client | READY | VERIFIED | INFO | 18.4 — APPROVED |
| T-playwright | outil exigé : playwright | READY | VERIFIED | INFO | 1.56.1 — APPROVED |
| A-claude-code-DENY | claude-code : règles de refus | FAILED | VERIFIED | HIGH | 0 deny, 0 ask, 20 allow |
| A-claude-code-BYPASS | claude-code : contournement des permissions | WARNING | VERIFIED | MEDIUM | non interdit par la configuration |
| A-claude-code-RISK-1 | claude-code : règle risquée | WARNING | VERIFIED | MEDIUM | Read(//c/Users/vboxuser/Desktop/**) — lecture d'un dossier personnel entier |
| A-claude-code-RISK-2 | claude-code : règle risquée | WARNING | VERIFIED | MEDIUM | Bash(git checkout *) — commande Git pouvant détruire ou publier |
| A-claude-code-PROD | Protection de la production | FAILED | VERIFIED | HIGH | hôtes de production déclarés : 2 ; aucune règle ni hook ne les protège |
| A-claude-code-AGENTS | agents du projet non enregistrés | WARNING | VERIFIED | MEDIUM | ui-mobile-erp |
| A-claude-code-SKILLS | skills du projet non enregistrés | WARNING | VERIFIED | MEDIUM | axum-sqlx, erp-audit-logs, erp-finance, higgsfield-brandkit, higgsfield-generate, higgsfield-marketplace-cards, higgsfield-product-photoshoot, higgsfield-soul-id, higgsfield-video-explainer, higgsfield-websites, higgsfield-youtube-thumbnail, react-state-architecture, tauri-security |
| M-01 | MCP higgsfield | FAILED | VERIFIED | HIGH | UNAPPROVED — portée : projet, local (~/.claude.json) ; actif : oui ; fiche : higgsfield (DISCOVERED) |
| M-02 | MCP gestion-fil-sqlite | UNKNOWN | UNVERIFIABLE | HIGH | UNAPPROVED — portée : réglages utilisateur (clé non documentée) ; actif : inconnu ; fiche : mcp-server-sqlite (DISCOVERED) |
| M-03 | MCP postgres-local | UNKNOWN | UNVERIFIABLE | HIGH | UNAPPROVED — portée : réglages utilisateur (clé non documentée) ; actif : inconnu ; fiche : mcp-server-postgres (DISCOVERED) |
| M-04 | MCP postgres | UNKNOWN | UNVERIFIABLE | HIGH | UNAPPROVED — portée : projet (.mcp.json) ; actif : inconnu ; fiche : mcp-server-postgres (DISCOVERED) |
| M-05 | MCP fetch | UNKNOWN | UNVERIFIABLE | HIGH | UNAPPROVED — portée : projet (.mcp.json) ; actif : inconnu ; fiche : mcp-fetch (DISCOVERED) |
| M-06 | MCP sequentialthinking | UNKNOWN | UNVERIFIABLE | HIGH | UNAPPROVED — portée : projet (.mcp.json) ; actif : inconnu ; fiche : mcp-sequential-thinking (DISCOVERED) |
| M-07 | MCP semgrep | UNKNOWN | UNVERIFIABLE | HIGH | UNAPPROVED — portée : projet (.mcp.json) ; actif : inconnu ; fiche : semgrep-mcp (DISCOVERED) |
| M-08 | MCP context7 | FAILED | VERIFIED | HIGH | UNAPPROVED — portée : greffon utilisateur context7@claude-plugins-official (tous projets) ; actif : oui ; fiche : context7 (DISCOVERED) |
| M-09 | MCP playwright-mcp | FAILED | VERIFIED | HIGH | UNAPPROVED — portée : greffon utilisateur playwright@claude-plugins-official (tous projets) ; actif : oui ; fiche : playwright-mcp (DISCOVERED) |
| M-10 | MCP microsoft/playwright-mcp | FAILED | VERIFIED | HIGH | UNAPPROVED — portée : IDE (mcp.json) ; actif : oui ; fiche : playwright-mcp (DISCOVERED) |
| M-claude-docs-connector | MCP claude-docs-connector | UNKNOWN | UNVERIFIABLE | MEDIUM | activation invisible dans les fichiers locaux |
| X-TRACKED | Fichiers sensibles suivis par Git | FAILED | VERIFIED | HIGH | SENSITIVE_TRACKED — contenu non lu, noms seulement : db/pg/seed_100_referentiel_reel.sql, db/pg/seed_110_comptes_production.sql, db/pg/seed_120_entreprise.sql |
| X-IGNORED | Fichiers sensibles présents, exclus de Git | WARNING | VERIFIED | MEDIUM | contenu non lu : backend/.env, backend/.env.example, backend/sauvegardes/, deploiement/gestionfil-20261013-2007.tar.gz, deploiement/gestionfil-20261015-1055.tar.gz, deploiement/paquet/, frontend/rapport-e2e/, frontend/rapport-simulation/ |
| Q-format | gate format | READY | DECLARED | INFO | CONFIGURED : « cargo fmt --check » (dans backend) — déclarée, non exécutée |
| Q-lint | gate lint | READY | DECLARED | INFO | CONFIGURED : « npm run lint » (dans frontend) — déclarée, non exécutée |
| Q-typecheck | gate typecheck | READY | DECLARED | INFO | CONFIGURED : « npm run build » (dans frontend) — déclarée, non exécutée |
| Q-unit_tests | gate unit_tests | READY | DECLARED | INFO | CONFIGURED : « cargo test --bins » (dans backend) — déclarée, non exécutée |
| Q-integration_tests | gate integration_tests | READY | DECLARED | INFO | CONFIGURED : « python backend/tests/banc/banc.py » (dans .) — déclarée, non exécutée |
| Q-build | gate build | READY | DECLARED | INFO | CONFIGURED : « cargo build --bins » (dans backend) — déclarée, non exécutée |
| Q-security | gate security | FAILED | DECLARED | HIGH | aucun outil approuvé (SECRET_SCAN, SECURITY_SCAN) |
| Q-dependency_audit | gate dependency_audit | FAILED | DECLARED | HIGH | aucun outil approuvé (DEPENDENCY_AUDIT) |
| Q-e2e | gate e2e | READY | DECLARED | INFO | CONFIGURED : « python e2e/lancer.py » (dans frontend) — déclarée, non exécutée |
| Q-CI | Intégration continue | DEGRADED | VERIFIED | MEDIUM | aucune configuration de CI (la CI est la source de vérité, règle 11) |
| G-UNPUSHED | Commits non publiés | WARNING | VERIFIED | HIGH | 108 commit(s) sans copie distante sur lots-devise-import-machines (Playbook §14.4) |
| G-DIRTY | Modifications non commitées | WARNING | VERIFIED | LOW | 1 fichier(s) |
| G-HOOKS | Hooks Git | WARNING | VERIFIED | LOW | aucun hook actif |

## En attente d'une décision humaine

- P-MANIFEST : copier le manifest dans le projet (WAITING_HUMAN)
- A-claude-code-DENY : définir les refus (production, secrets, destructif)
- A-claude-code-RISK-1 : restreindre ou retirer (WAITING_HUMAN)
- A-claude-code-RISK-2 : restreindre ou retirer (WAITING_HUMAN)
- A-claude-code-PROD : garde de production (hook PreToolUse) : WAITING_HUMAN
- A-claude-code-AGENTS : inscrire au registre ou retirer (UNAPPROVED)
- A-claude-code-SKILLS : inscrire au registre ou retirer (UNAPPROVED)
- M-01 : désactiver ou faire évaluer (Security Owner)
- M-02 : désactiver ou faire évaluer (Security Owner)
- M-03 : désactiver ou faire évaluer (Security Owner)
- M-04 : désactiver ou faire évaluer (Security Owner)
- M-05 : désactiver ou faire évaluer (Security Owner)
- M-06 : désactiver ou faire évaluer (Security Owner)
- M-07 : désactiver ou faire évaluer (Security Owner)
- M-08 : désactiver ou faire évaluer (Security Owner)
- M-09 : désactiver ou faire évaluer (Security Owner)
- M-10 : désactiver ou faire évaluer (Security Owner)
- M-claude-docs-connector : vérifier dans le compte
- X-TRACKED : retirer de l'historique et invalider (WAITING_HUMAN)
- X-IGNORED : interdire leur lecture aux agents (règles de refus)
- Q-security : choisir et faire évaluer un outil
- Q-dependency_audit : choisir et faire évaluer un outil
- G-UNPUSHED : publier (action humaine)

## Preuves d'exécution

| Commande | Code | Résultat |
|---|---|---|
| `claude --version` | 0 | SUCCESS |
| `cargo --version` | 0 | SUCCESS |
| `npm --version` | 0 | SUCCESS |
| `psql --version` | 0 | SUCCESS |
| `code --version` | 0 | SUCCESS |
| `git --version` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil worktree list` | 0 | SUCCESS |
| `rustc --version` | 0 | SUCCESS |
| `node --version` | 0 | SUCCESS |
| `rustup --version` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil rev-parse --show-toplevel` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil status --short --branch` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil remote -v` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil worktree list` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil config --get core.hookspath` | 1 | FAILURE |
| `code --list-extensions` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil ls-files` | 0 | SUCCESS |
| `git -C C:\Users\vboxuser\Desktop\gestionFil ls-files --others --ignored --exclude-standard --directory` | 0 | SUCCESS |

## Lectures

- C:\Users\vboxuser\Desktop\software-factory\factory.yaml (identité)
- C:\Users\vboxuser\Desktop\gestionFil\backend\Cargo.toml (identité)
- C:\Users\vboxuser\Desktop\gestionFil\frontend\package.json (identité)
- C:\Users\vboxuser\Desktop\gestionFil/ (liste)
- C:\Users\vboxuser\Desktop\gestionFil\frontend\package.json
- C:\Users\vboxuser\Desktop\gestionFil\frontend\node_modules\@playwright\test\package.json
- C:\Users\vboxuser\Desktop\gestionFil\.git\hooks/ (liste)
- C:\Users\vboxuser\Desktop\gestionFil/ (liste)
- C:\Users\vboxuser\Desktop\gestionFil\frontend\package.json
- C:\Users\vboxuser\Desktop\gestionFil\frontend\node_modules\typescript\package.json
- C:\Users\vboxuser\.claude\settings.json
- C:\Users\vboxuser\.claude.json
- C:\Users\vboxuser\Desktop\gestionFil\.mcp.json
- C:\Users\vboxuser\Desktop\gestionFil\.claude\agents/ (liste)
- C:\Users\vboxuser\Desktop\gestionFil\.claude\skills/ (liste)
- C:\Users\vboxuser\AppData\Roaming\Code\User\settings.json
- C:\Users\vboxuser\AppData\Roaming\Code\User\mcp.json
- C:\Users\vboxuser\AppData\Roaming\Code\User\globalStorage\storage.json

## Accès refusés par le périmètre (non effectués)

- C:\Users\vboxuser\Desktop\gestionFil\.claude\settings.local.json : fichier ou répertoire sensible (DENY)

## Garanties

- aucune écriture hors bootstrap/reports
- aucune commande hors liste blanche
- aucun fichier sensible ouvert
- aucun serveur MCP démarré
- aucune connexion réseau ou base de données par le Bootstrap
