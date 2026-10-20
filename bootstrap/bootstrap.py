"""Factory Bootstrap v1 — point d'entrée.

    python -P bootstrap/bootstrap.py check [--projet <id>] [--sans-rapport]

CHECK ne modifie rien : sa seule écriture est le rapport dans bootstrap/reports/ (supprimée par
--sans-rapport). SETUP et REPAIR sont « cible » (Playbook §7.2) et refusent de s'exécuter.
Code de sortie : 0 READY, 1 DEGRADED, 2 BLOCKED, 3 mode non implémenté ou erreur d'usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
# « python -P » n'ajoute pas le dossier du script au chemin d'import : on ajoute explicitement deux chemins
# connus, le cœur partagé (core/) et le Bootstrap lui-même.
for _chemin in (ICI.parent / "core", ICI):
    sys.path.insert(0, str(_chemin))

from check import controles, rapport  # noqa: E402

VERSION = "1.0.0"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bootstrap", description="Factory Bootstrap v1")
    p.add_argument("mode", choices=["check", "setup", "repair"])
    p.add_argument("--projet", help="identifiant d'un projet enregistré (registry/projects/<id>)")
    p.add_argument("--sans-rapport", action="store_true", help="n'écrit aucun fichier (affichage seul)")
    a = p.parse_args(argv)
    if a.mode != "check":
        print(f"Mode {a.mode.upper()} : cible, non implémenté (Playbook §7.2). Rien n'a été fait.")
        return 3
    racine = ICI.parent
    ctx, col = controles.executer(racine, a.projet)
    r = rapport.construire(ctx, col, a.projet, VERSION)
    b = r["bootstrap"]
    print(f"Factory : {b['factory_state']} | analyse : {b['phase_readiness']['PROJECT_ANALYSIS']} | "
          f"exécution : {b['phase_readiness']['EXECUTION']} | constats : {len(b['constats'])} | "
          f"commandes : {len(b['preuves_commandes'])} | lectures : {len(b['lectures'])} | refus : {len(b['refus'])}")
    if not a.sans_rapport:
        for f in rapport.ecrire(r, racine / "bootstrap" / "reports"):
            print(f"rapport : {f.relative_to(racine).as_posix()}")
    pire = "BLOCKED" if b["factory_state"] == "BLOCKED" else max(
        b["phase_readiness"].values(), key=["READY", "DEGRADED", "BLOCKED"].index)
    return {"READY": 0, "DEGRADED": 1, "BLOCKED": 2}[pire]


if __name__ == "__main__":
    sys.exit(main())
