# CLAUDE.md — contexte du dépôt de la Factory

> **Ce fichier est du contexte. Il ne fait autorité sur rien.** En cas d'écart, le Policy Engine, le catalogue des
> règles, les politiques (`policies/`), les décisions humaines, les baux et les ADR prévalent (Playbook v3.3 proposé,
> §16.3 ; ADR-0017 D41). Aucun secret ici.
>
> **Choix du Factory Owner (16/10/2026)** : pour faciliter le travail, le contexte de ce dépôt est tenu ici, dans
> `CLAUDE.md`, et non dans le fichier neutre `AGENT_CONTEXT.md`. C'est un écart déclaré à la neutralité vis-à-vis du
> fournisseur (Playbook §16.3) ; `AGENT_CONTEXT.md` ne contient plus qu'un renvoi vers ce fichier.

## 1. Contexte

Ce dépôt est le plan de contrôle générique de la Factory : schémas (`core/schemas/`), cœur générique
(`core/noyau/`), fournisseurs propres à un outil (`core/fournisseurs/`), Bootstrap (`bootstrap/`), registre
(`registry/`), politiques (`policies/`), données d'orchestration (`orchestrator/`), audit (`audit/`), preuves
(`compliance/`), ADR (`adr/`), propositions en cours (`adr/proposed/`, `docs/proposed/`).

Hiérarchie des sources : norme > politique > implémentation > test > preuve (`docs/normative/README.md`).

État au 17/10/2026 :
- normes en vigueur : Playbook v3.3 (`docs/playbook/playbook-v3.3.md`, adopté le 17/10/2026 ; la v3.2 est
  conservée telle quelle) ; ADR acceptés (`adr/accepted/`, dont ADR-0016 actif et ADR-0017 v5 gelé le 17/10/2026) ;
- `factory.yaml` n'est plus maintenu (décision du Factory Owner, 17/10/2026) : ne pas s'y fier pour la version
  du Playbook ;
- EXC-0003 a pris fin à sa première échéance (gel de l'ADR-0017) ; la construction se poursuit sur instruction
  explicite du Factory Owner, tracée au journal ;
- épinglage de la gouvernance : référence approuvée par l'humain (W1) ; toute modification d'un fichier couvert
  (`policies/pinning.yaml`) exige une nouvelle demande (`factory pin request`) et son approbation ;
- GestionFil est développé EN PARALLÈLE par une autre session : la Factory n'y fait QUE des évaluations (copies
  isolées au commit fixe des suites, rien n'est fusionné) ; quand les agents seront habilités, tout développement
  passera par la Factory (un seul chemin) — décision du Factory Owner du 19/10/2026 ;
- tickets des projets (ADR-0022 v2, alignée sur le modèle canonique GMAO v1.0) : le ticket vit dans le dépôt du projet
  (`tickets.path` du manifest) ; un ticket qui porte `control_profile` est un contrat d'exécution qui référence rôle,
  skills, profil de prompt (`registry/prompts/`) et profil de contrôle (`policies/control-profiles.yaml`) avec leurs
  versions ; aucune copie dans la Factory ; `factory ticket check` dit READY ou BLOCKED ; prérequis humains :
  `factory decide request` ;
- approbations : `python -P scripts/factory_approve.py --ouvertes` (toutes les demandes, expliquées en clair) ;
- niveau réel des frontières : ADR-0017, annexe D (aucune n'est ENFORCED à ce jour) ;
- audits : `audit/self-audit/` ; point de reprise historique : `docs/prompts/construction-factory-v1.md`.

## 2. Instructions opérationnelles

Commandes sûres :

```bash
python -P factory.py check | validate | registry list | state check | policy check DEMANDE.json
python -P factory.py env list | mission plan FICHIER
python -P factory.py pin status | key status | decide list | decide show NOM | exception list
python -P factory.py ticket check PROJET [TICKET] [--prompt]     # ADR-0022 : READY/BLOCKED, lecture seule
python -P bootstrap/bootstrap.py check --projet <id> --sans-rapport
python -P -m unittest discover -s core/tests -t core -p "test_*.py"
python -P -m unittest discover -s bootstrap/tests -t bootstrap -p "test_*.py"
python -P scripts/factory_backup.py backup | verify <archive> | restore-test <archive>
```

Toujours `python -P` (PyYAML est dans le site utilisateur ; `-I` le masquerait).

## 3. Où sont les règles (renvois, sans recopie)

| Sujet | Source qui fait autorité |
|---|---|
| Qualification des actions (ALLOW, APPROVAL_REQUIRED, refus) | `policies/policy-engine.yaml`, `policies/autonomy.yaml`, `core/noyau/politique.py` |
| Sécurité par défaut, exceptions | `policies/security-defaults.yaml`, `policies/exceptions/` |
| Racines, chemins sensibles | `policies/root-scope.yaml`, manifest de chaque projet |
| Approbations et revues humaines | ADR-0006 (W1), ADR-0012 ; `policies/human-approval.yaml` |
| Autonomie en environnement jetable | ADR-0016 |
| Généricité du cœur | ADR-0003 ; test `CoeurGenerique` |
| Preuves, audit, transitions | ADR-0007 ; `policies/transitions.yaml` |
| Gouvernance cible (identité, décision, bail, frontières) | ADR-0017 v5 (proposé, non normatif) |
| Toute décision structurante | un ADR (`adr/`) |

## 4. Règles retirées du contexte (16/10/2026)

Ces lignes figuraient dans l'ancien `AGENT_CONTEXT.md` comme « règles » ; elles sont retirées parce qu'un fichier de
contexte ne fait pas autorité. Leur sujet est désormais traité par la source indiquée :

| Ancienne ligne | Où le sujet est traité |
|---|---|
| « Refus par défaut ; trois décisions : ALLOW, DENY, APPROVAL_REQUIRED » | politiques et Policy Engine ; évolution proposée par l'ADR-0017 (D11) |
| « Un jalon à la fois ; ADR pour toute décision structurante ; aucun commit par l'agent » | exception de construction EXC-0003 (commit exclu) ; ADR-0016 (commit local sous bail en environnement jetable) ; mode construction proposé (ADR-0017 D37) |
| « Zones interdites à l'agent » (approbations humaines, commande d'approbation, réécriture du journal, textes normatifs, chemins hors racine) | ADR-0006 (W1) et garde de l'agent ; journal en ajout seul (ADR-0007) ; `docs/normative/README.md` ; `policies/root-scope.yaml` ; EXC-0002, EXC-0003 |
| « Décisions de référence : ADR-0001 à ADR-0010 » | `adr/accepted/` (ADR-0001 à ADR-0016) et `adr/proposed/` |
