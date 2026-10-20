# Manuel d'exploitation de la Factory (jalon J11)

Comment administrer la Factory comme un système critique. **Chaque commande citée existe** : le test
`core/tests/test_runbook.py` la confronte à la CLI et aux scripts. Une opération sans commande se fait par
édition contrôlée d'une fiche (registre, politique) **dans un ticket**, revue, puis `factory validate`.

Légende des acteurs : **H** humain (rôle indiqué) · **A** agent (dans un ticket, sous Policy Engine).

## Démarrer / arrêter

La Factory n'est pas un service : elle n'a ni démon ni processus permanent. « Démarrer » = contrôler.

```bash
factory check
factory state check
```

« Arrêter » = ne plus lancer d'agent : poser les règles de refus de l'agent, ou retirer son approbation (voir
« Bloquer un agent »). Aucune commande ne « tue » une Factory.

## Contrôle de santé

```bash
factory check
factory bootstrap check --projet gestionfil
factory validate
```

Lire : `FACTORY READY|DEGRADED|BLOCKED — exécution d'agents : …` ; constats F-* (Factory), P-* (projet).

## Ajouter un outil (Master §57) — H : Factory Owner

1. Fiche `registry/tools/<id>.yaml` en `DISCOVERED` ou `CANDIDATE` (jamais plus haut sans preuve).
2. Évaluation, Lab si risque (Playbook §6.5) ; installation **par l'humain** ; détection déclarée (`detection`).
3. Passage `APPROVED` + `approval.status: APPROVED` (sinon `ACTIVE_WITHOUT_APPROVAL`) ; ADR si structurant.
4. Vérifier :

```bash
factory validate
factory registry list tools
factory bootstrap check --projet gestionfil
```

## Retirer un outil

Passer la fiche à `DEPRECATED` puis `REMOVED` (jamais supprimer la fiche : l'historique reste) ; retirer l'outil des
manifests qui l'autorisent ; `factory validate`.

## Ajouter un agent / bloquer un agent — H : Factory Owner, Security Owner

- Ajouter : fiche `registry/agents/<id>.yaml`, évaluation (Playbook §12.6), `governance.approved_by` renseigné
  avant tout état `APPROVED` ; l'agent doit figurer dans `agents.allowed` du projet.
- Bloquer : repasser la fiche en `DEPRECATED` ; le Policy Engine refuse aussitôt (R04).

```bash
factory registry list agents --etat APPROVED
```

## Habiliter provisoirement un agent (décision C-17) — H : Factory Owner

Pour le pilote de la phase 1 seulement : un agent non évalué, plafonné à **C1**, pour un projet, 30 jours au plus.
La fiche de l'agent déclare `provisional_habilitation` (demande) ; l'agent prépare la demande d'approbation ;
**l'humain** l'approuve dans sa console :

```bash
python -P scripts/factory_approve.py audit/approvals/requests/AR-HAB-qa.json
```

Toute modification de la demande (plafond, projets, dates) invalide l'approbation. Vérifier :

```bash
factory policy check demande.json
```

## Mettre à jour un modèle (Master §58)

Nouvelle version = réévaluation avant reprise des tâches C2+ (Playbook §5.4) : fiche `registry/models/` en
`REEVALUATION`, benchmark, approbation, puis retour en `MONITORED`.

## Ajouter un MCP / révoquer un accès — H : Security Owner

- Ajouter : fiche `registry/mcp/<id>.yaml` (`DISCOVERED`), évaluation de sécurité, Lab, `APPROVED` +
  approbation ; l'autoriser dans `mcp.allowed` du **projet** concerné seulement.
- Révoquer : retirer de `mcp.allowed`, fiche en `REVOKED` ; désactiver dans la configuration de l'agent (humain).

```bash
factory registry list mcp
```

## Créer un projet — H : Project Owner

1. Carte `registry/projects/<id>/project.yaml` (racine, marqueurs d'identité, chemins sensibles).
2. Manifest `factory.yaml` **dans le dépôt du projet** (brouillon possible dans la carte) ; `AGENT_CONTEXT.md`.
3. Vérifier :

```bash
factory validate registry/projects/gestionfil/factory.draft.yaml
factory bootstrap check --projet gestionfil
```

## Approuver (C3, C4, actions contrôlées) — H seulement

L'agent prépare la demande (`audit/approvals/requests/`) ; l'humain, **dans sa propre console** :

```bash
python -P scripts/factory_approve.py audit/approvals/requests/AR-HG-xxxx.json
```

Vérifier une décision avant d'agir :

```bash
factory policy check demande.json
```

## Sauvegarder, restaurer, exercer la reprise

```bash
python -P scripts/factory_backup.py backup
python -P scripts/factory_backup.py verify ARCHIVE.zip
python -P scripts/factory_backup.py restore-test ARCHIVE.zip
python -P scripts/factory_backup.py drill ARCHIVE.zip
```

Procédures : `restauration-factory.md`, `reprise-apres-sinistre.md`.

## Rollback d'une modification de la Factory

Tant qu'il n'y a pas de commit : restaurer le fichier depuis la dernière archive vérifiée (extraction ciblée,
dans un répertoire neuf, puis copie par l'humain). Après le premier commit : `git` par l'humain.

## Incident / incident de sécurité (Playbook §14.6)

1. **Contenir** : bloquer l'agent ou révoquer le MCP (ci-dessus) ; ne rien effacer.
2. **Diagnostiquer** avec les preuves :

```bash
factory state check
factory check
```

3. Secret exposé : le considérer compromis, l'invalider (humain), consigner l'incident.
4. Journal d'audit rompu (`F-AUDIT` BLOCKED) : ne plus écrire ; comparer la tête à l'ancre de la dernière
   sauvegarde ; restaurer le journal ; incident.
5. Cause racine, prévention, leçon dans `knowledge/incidents/`.

## Mettre à jour la Factory — H : Factory Owner

Évolution du standard = ADR + nouvelle version (Playbook §15.4) ; modification de politique = ADR + approbation
(`change_policy` réservé au Factory Owner) ; après toute mise à jour :

```bash
factory validate
factory check
python -P scripts/factory_backup.py backup
```
