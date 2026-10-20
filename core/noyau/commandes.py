"""Exécuteur de commandes sous liste blanche (politique command-whitelist).

Une commande absente de la liste est refusée SANS être lancée (COMMAND_NOT_ALLOWED). Aucun shell : l'argv
est passé tel quel. Toute sortie est masquée avant d'être conservée comme preuve.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .masquage import masquer
from .modele import Preuve

_META = re.compile(r"[;&|<>`$\n\r]")


@dataclass
class Resultat:
    autorisee: bool
    executee: bool
    code: int | None
    sortie: str                      # masquée
    motif_refus: str | None = None
    preuve: Preuve | None = None


@dataclass
class Executeur:
    autorisees: list[list[str]]
    jokers: dict[str, str]
    perimetre: object                # Perimetre : le répertoire passé par option n'est admis que dans ROOT_SCOPE
    delai: int = 30
    environnement: dict[str, str] = field(default_factory=dict)
    journal: list[Preuve] = field(default_factory=list)
    options_repertoire: dict[str, str] = field(default_factory=dict)   # exécutable → option « répertoire » (politique)

    def _correspond(self, argv: list[str]) -> bool:
        for modele in self.autorisees:
            if len(modele) != len(argv):
                continue
            ok = True
            for attendu, recu in zip(modele, argv):
                if attendu in self.jokers:
                    if not re.fullmatch(self.jokers[attendu], recu):
                        ok = False
                        break
                elif attendu != recu:
                    ok = False
                    break
            if ok:
                return True
        return False

    def autorisee(self, argv: list[str]) -> tuple[bool, str | None, list[str], str | None]:
        """(autorisée, motif de refus, argv normalisé, répertoire -C)."""
        if any(_META.search(a) for a in argv):
            return False, "caractère de shell interdit", argv, None
        repertoire = None
        normal = list(argv)
        option = self.options_repertoire.get(argv[0]) if argv else None
        if option and len(argv) >= 3 and argv[1] == option:
            repertoire = argv[2]
            if not self.perimetre.dans_perimetre(Path(repertoire)):
                return False, "répertoire d'exécution hors ROOT_SCOPE", argv, repertoire
            normal = [argv[0]] + argv[3:]
        if not self._correspond(normal):
            return False, "COMMAND_NOT_ALLOWED", argv, repertoire
        return True, None, normal, repertoire

    def lancer(self, argv: list[str], cwd: str | Path | None = None) -> Resultat:
        ok, motif, _, _ = self.autorisee(argv)
        if ok and cwd is not None and not self.perimetre.dans_perimetre(Path(cwd)):
            ok, motif = False, "répertoire d'exécution hors ROOT_SCOPE"
        affichee = masquer(" ".join(argv))
        if not ok:
            p = Preuve(type="COMMAND", source=affichee, result="FAILURE", extrait=f"refusée : {motif}")
            self.journal.append(p)
            return Resultat(False, False, None, "", motif, p)
        executable = shutil.which(argv[0])
        if executable is None:
            p = Preuve(type="COMMAND", source=affichee, result="FAILURE", extrait="exécutable introuvable dans le PATH")
            self.journal.append(p)
            return Resultat(True, False, None, "", "absent", p)
        env = dict(os.environ)
        env.update(self.environnement)
        debut = time.monotonic()
        try:
            r = subprocess.run([executable] + argv[1:], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=self.delai, stdin=subprocess.DEVNULL, env=env, shell=False,
                               cwd=str(cwd) if cwd is not None else None)
            sortie = masquer((r.stdout or "") + (("\n" + r.stderr) if r.stderr and r.returncode else ""))
            code = r.returncode
        except subprocess.TimeoutExpired:
            sortie, code = "délai dépassé", None
        extrait = "\n".join(sortie.strip().splitlines()[:5])[:500]
        p = Preuve(type="COMMAND", source=affichee, result="SUCCESS" if code == 0 else "FAILURE", exit_code=code,
                   extrait=f"{extrait} ({time.monotonic() - debut:.1f} s)")
        self.journal.append(p)
        return Resultat(True, True, code, sortie, None, p)
