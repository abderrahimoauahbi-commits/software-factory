"""Sauvegarde de la Factory (décision D2) — politique : policies/backup.yaml ; procédure :
docs/operations/restauration-factory.md.

    python -P scripts/factory_backup.py backup                 # archive + empreinte, jamais d'écrasement
    python -P scripts/factory_backup.py verify <archive.zip>   # intégrité de l'archive et de chaque fichier
    python -P scripts/factory_backup.py restore-test <archive> # restauration dans un répertoire temporaire + revalidation
    python -P scripts/factory_backup.py drill <archive>        # exercice de reprise : la copie restaurée FONCTIONNE (RTO)

Code de sortie : 0 OK, 1 FAIL, 2 sauvegarde refusée (rien n'a été écrit).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY / "core"))          # « python -P » : chemin explicite et connu

import yaml  # noqa: E402

from noyau import sauvegarde  # noqa: E402
from noyau.audit import Journal  # noqa: E402
from noyau.registre import charger  # noqa: E402


def _yaml(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def revalider(racine: Path) -> list[str]:
    """Une Factory restaurée doit être utilisable : registre valide et Playbook intègre."""
    problemes = []
    reg = charger(racine)
    problemes += [f"registre restauré invalide : {e.fichier} : {e.message}" for e in reg.erreurs]
    factory = _yaml(racine / "factory.yaml")
    pb = racine / factory["playbook"]["path"]
    if not pb.is_file() or hashlib.sha256(pb.read_bytes()).hexdigest() != factory["playbook"]["sha256"]:
        problemes.append("Playbook restauré absent ou altéré")
    journal = Journal(racine / "audit" / "journal.jsonl").verifier()
    if not journal.valide:
        problemes.append(f"journal d'audit restauré rompu à la ligne {journal.rupture + 1}")
    return problemes


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="factory_backup")
    p.add_argument("operation", choices=["backup", "verify", "restore-test", "drill"])
    p.add_argument("archive", nargs="?")
    a = p.parse_args(argv)
    politique = _yaml(FACTORY / "policies" / "backup.yaml")
    try:
        if a.operation == "backup":
            factory = _yaml(FACTORY / "factory.yaml")["factory"]
            journal = Journal(FACTORY / "audit" / "journal.jsonl").verifier()
            if not journal.valide:
                raise sauvegarde.SauvegardeRefusee(f"journal d'audit rompu à la ligne {journal.rupture + 1} : "
                                                   "on ne sauvegarde pas un journal compromis")
            # Ancre : la tête du journal est consignée hors du journal (une réécriture complète la changerait).
            r = sauvegarde.sauvegarder(FACTORY, Path(politique["destination"]), politique["required_scopes"],
                                       politique["excluded"], {"factory": factory, "audit_head": journal.tete,
                                                               "audit_events": journal.evenements})
        elif a.operation == "verify":
            r = sauvegarde.verifier(Path(a.archive))
        elif a.operation == "drill":
            # La copie restaurée doit FONCTIONNER : CLI et suite de tests du cœur, lancées depuis elle-même.
            py = [sys.executable, "-P"]
            r = sauvegarde.exercice_reprise(Path(a.archive), [
                py + ["{racine}/factory.py", "check"],
                py + ["-m", "unittest", "discover", "-s", "{racine}/core/tests", "-t", "{racine}/core", "-p", "test_*.py"],
            ], revalider)
        else:
            r = sauvegarde.tester_restauration(Path(a.archive), revalider)
    except sauvegarde.SauvegardeRefusee as e:
        print(json.dumps({"operation": a.operation, "statut": "REFUSED", "raison": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(r.en_dict(), ensure_ascii=False, indent=1))
    return 0 if r.statut == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
