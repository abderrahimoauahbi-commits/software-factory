# Procédure — sauvegarde et restauration de la Factory

Politique : `policies/backup.yaml` (décision D2). Outil : `scripts/factory_backup.py`. Exécutable par
l'humain ou par l'agent : la sauvegarde ne modifie pas la Factory ; la restauration réelle est un acte humain.

## Sauvegarder

```powershell
python -P scripts/factory_backup.py backup
```

Produit dans la destination (`F:/software-factory-backups`) :

- `factory-backup-<horodatage>-<empreinte>.zip` — toutes les portées exigées (D2) et le reste de la Factory,
  sans `.git/`, caches ni rapports régénérables ; un manifeste interne `BACKUP-MANIFEST.json` donne le chemin,
  la taille et le SHA-256 de chaque fichier ;
- `<archive>.zip.sha256` — empreinte de l'archive entière.

L'outil refuse : une portée exigée absente ou vide, une destination dans la source, l'écrasement d'une archive.

## Vérifier — à faire après chaque sauvegarde

```powershell
python -P scripts/factory_backup.py verify F:/software-factory-backups/<archive>.zip
python -P scripts/factory_backup.py restore-test F:/software-factory-backups/<archive>.zip
```

`restore-test` restaure dans un répertoire temporaire neuf (jamais par-dessus la Factory), refuse tout chemin
d'archive qui sortirait de ce répertoire, compare chaque fichier à son empreinte, recharge le registre (aucune
erreur de validation admise) et contrôle l'empreinte du Playbook. Sa durée mesure le **RTO**.

Une sauvegarde sans `restore-test` réussi n'est pas une preuve de récupérabilité (Playbook §14.4).

## Restaurer (acte humain)

1. Choisir l'archive la plus récente dont `verify` et `restore-test` sont OK.
2. Contrôler l'empreinte : `Get-FileHash <archive>.zip -Algorithm SHA256` doit égaler le fichier `.sha256`.
3. Extraire dans un **répertoire neuf** (jamais par-dessus une Factory existante).
4. Dans ce répertoire :
   `python -P -m unittest discover -s core/tests -t core -p "test_*.py"`, puis
   `python -P bootstrap/bootstrap.py check` — la Factory doit être `READY`.
5. Basculer : renommer l'ancienne Factory (conservée), placer la restaurée à `FACTORY_ROOT`, relancer le CHECK.
6. Consigner la restauration (événement d'audit, raison, archive utilisée).

## Limites connues (v1)

- Copie **sur le même poste** (autre lecteur) : ne protège pas d'une perte du poste. Copie hors poste :
  `offsite_copy: WAITING_HUMAN`.
- Pas d'historique Git tant qu'aucun commit n'existe ; ensuite, ajouter un `git bundle` à la sauvegarde.
- RPO non fixé (`rpo_target: WAITING_HUMAN`) ; la sauvegarde n'est pas planifiée automatiquement.
