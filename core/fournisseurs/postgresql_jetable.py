"""Fournisseur de bases jetables PostgreSQL (ADR-0016 proposé, décision 7 ; Master Evolution Prompt v4 §8–§11, §38).

La Factory CRÉE la base, elle n'en choisit pas une : chaque ressource est un cluster privé (initdb) dans le
répertoire de son environnement, qui n'écoute que 127.0.0.1 sur un port libre, avec un rôle local sans mot de
passe (authentification « trust » limitée à ce cluster). L'empreinte d'identité relevée à la création :
`system_identifier` (pg_control), `data_directory`, `port`. Toute commande passe -h/-p explicitement et retire
de l'environnement PGPASSWORD, PGSERVICE, PGHOST, PGPORT… hérités : une erreur ne peut pas viser l'instance
du poste (5432).
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

HOTE = "127.0.0.1"
ROLE = "factory"
_HERITES = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGHOST", "PGHOSTADDR", "PGPORT", "PGUSER",
            "PGDATABASE", "PGOPTIONS", "PGSSLMODE")
_CONF = """
# --- Factory : cluster jetable (ne jamais réutiliser pour des données réelles)
listen_addresses = '127.0.0.1'
port = {port}
fsync = off
synchronous_commit = off
full_page_writes = off
max_connections = 30
logging_collector = off
"""


class ErreurPostgres(Exception):
    pass


class PostgresJetable:
    id = "postgresql-disposable"
    kind = "database"

    def __init__(self, bin_dir: str | None = None, delai: int = 300):
        self.bin_dir = bin_dir
        self.delai = delai

    # ------------------------------------------------------------------ outillage
    def _bin(self, nom: str) -> str:
        if self.bin_dir:
            for c in (Path(self.bin_dir) / nom, Path(self.bin_dir) / f"{nom}.exe"):
                if c.is_file():
                    return str(c)
        trouve = shutil.which(nom)
        if not trouve:
            raise ErreurPostgres(f"{nom} introuvable")
        return trouve

    def disponible(self) -> tuple[bool, str]:
        try:
            for n in ("initdb", "pg_ctl", "psql"):
                self._bin(n)
            return True, "binaires présents"
        except ErreurPostgres as e:
            return False, str(e)

    @staticmethod
    def _env() -> dict:
        env = {k: v for k, v in os.environ.items() if k.upper() not in _HERITES}
        env["PGCLIENTENCODING"] = "UTF8"
        return env

    def _run(self, argv: list[str], entree: str | None = None, delai: int | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              input=entree, timeout=delai or self.delai, env=self._env(), shell=False,
                              stdin=None if entree is not None else subprocess.DEVNULL)

    @staticmethod
    def _port_libre() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOTE, 0))
            return s.getsockname()[1]

    def _psql(self, port: int, base: str, *args: str) -> list[str]:
        return [self._bin("psql"), "-h", HOTE, "-p", str(port), "-U", ROLE, "-d", base, "-v", "ON_ERROR_STOP=1",
                "-X", *args]

    # ------------------------------------------------------------------ cycle de la ressource
    def creer(self, dossier: Path, spec: dict, environnement) -> dict:
        donnees = Path(dossier) / "pgdata"
        journal = Path(dossier) / "postgres.log"
        r = self._run([self._bin("initdb"), "-D", str(donnees), "-U", ROLE, "-A", "trust", "-E", "UTF8",
                       "--locale=C"])
        if r.returncode:
            raise ErreurPostgres(f"initdb : {r.stderr.strip()[-400:]}")
        port = self._port_libre()
        with open(donnees / "postgresql.auto.conf", "a", encoding="utf-8") as f:
            f.write(_CONF.format(port=port))
        self._demarrer(donnees, journal)
        base = spec.get("database") or "factory_test"
        r = self._run(self._psql(port, "postgres", "-c", f'CREATE DATABASE "{base}"'))
        if r.returncode:
            raise ErreurPostgres(f"création de la base : {r.stderr.strip()[-400:]}")
        connexion = {"host": HOTE, "port": port, "user": ROLE, "database": base, "data_dir": str(donnees),
                     "log": str(journal)}
        if spec.get("baseline"):
            connexion["reference"] = self._reference(port, base, spec["baseline"], Path(dossier))
        empreinte = self._interroger(port)
        return {"connection": connexion, "identity": empreinte}

    def _reference(self, port: int, base: str, socle: dict, dossier: Path) -> str:
        """Base de référence : rôles (sans connexion), fichiers SQL dans l'ordre, puis gabarit figé pour les resets."""
        for role in socle.get("roles") or []:
            if not role.replace("_", "").isalnum():
                raise ErreurPostgres(f"nom de rôle refusé : {role!r}")
            r = self._run(self._psql(port, "postgres", "-c", f'CREATE ROLE "{role}" NOLOGIN'))
            if r.returncode:
                raise ErreurPostgres(f"rôle {role} : {r.stderr.strip()[-300:]}")
        trace = dossier / "reference.log"
        for f in socle.get("files") or []:
            r = self._run(self._psql(port, base, "-q", "-f", str(f)), delai=max(self.delai, 900))
            with open(trace, "a", encoding="utf-8") as t:
                t.write(f"== {f} : code {r.returncode}\n{r.stderr[-4000:]}\n")
            if r.returncode:
                raise ErreurPostgres(f"référence {Path(f).name} : {r.stderr.strip()[-400:]}")
        for sql in socle.get("statements") or []:
            r = self._run(self._psql(port, base, "-q"), entree=sql)
            if r.returncode:
                raise ErreurPostgres(f"référence (instruction) : {r.stderr.strip()[-300:]}")
        gabarit = f"{base}_reference"
        r = self._run(self._psql(port, "postgres", "-c", f'CREATE DATABASE "{gabarit}" TEMPLATE "{base}"'))
        if r.returncode:
            raise ErreurPostgres(f"gabarit : {r.stderr.strip()[-300:]}")
        return gabarit

    def _demarrer(self, donnees: Path, journal: Path):
        # Le serveur lancé par pg_ctl hérite des descripteurs : jamais de tube capturé ici (sinon l'attente ne
        # finit qu'à l'arrêt du serveur). La sortie du serveur va dans son journal (-l).
        r = subprocess.run([self._bin("pg_ctl"), "-D", str(donnees), "-l", str(journal), "-w", "-t", "60", "start"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=self.delai, env=self._env(), shell=False)
        if r.returncode:
            fin = journal.read_text(encoding="utf-8", errors="replace")[-400:] if journal.is_file() else ""
            raise ErreurPostgres(f"démarrage (code {r.returncode}) : {fin.strip()}")

    def _interroger(self, port: int) -> dict:
        r = self._run(self._psql(port, "postgres", "-tA", "-F", "|", "-c",
                                 "select system_identifier, current_setting('data_directory'), "
                                 "current_setting('port') from pg_control_system()"), delai=30)
        if r.returncode:
            raise ErreurPostgres(f"interrogation : {r.stderr.strip()[-300:]}")
        sysid, dossier, port_lu = r.stdout.strip().split("|")
        return {"system_identifier": sysid, "data_directory": os.path.normcase(os.path.realpath(dossier)),
                "port": str(port_lu)}

    def identite(self, ressource) -> dict:
        return self._interroger(int(ressource.connection["port"]))

    def variables(self, ressource) -> dict:
        c = ressource.connection
        return {"PGHOST": c["host"], "PGPORT": str(c["port"]), "PGUSER": c["user"], "PGDATABASE": c["database"]}

    def executer_sql(self, ressource, sql: str | None = None, fichier: str | None = None,
                     base: str | None = None) -> subprocess.CompletedProcess:
        c = ressource.connection
        args = ["-q"] + (["-f", fichier] if fichier else ["-c", sql or ""])
        return self._run(self._psql(int(c["port"]), base or c["database"], *args))

    def valeur(self, ressource, sql: str) -> tuple[int, str]:
        """(code, valeur brute sans en-tête ni alignement) : contrôles d'évaluation à résultat attendu."""
        c = ressource.connection
        r = self._run(self._psql(int(c["port"]), c["database"], "-q", "-t", "-A", "-c", sql))
        return r.returncode, (r.stdout or "").strip() if r.returncode == 0 else (r.stderr or "").strip()[-300:]

    def reinitialiser(self, ressource):
        c = ressource.connection
        r = self._run(self._psql(int(c["port"]), "postgres", "-c", f'DROP DATABASE IF EXISTS "{c["database"]}" WITH (FORCE)'))
        if r.returncode:
            raise ErreurPostgres(f"reset : {r.stderr.strip()[-300:]}")
        gabarit = f' TEMPLATE "{c["reference"]}"' if c.get("reference") else ""
        r = self._run(self._psql(int(c["port"]), "postgres", "-c", f'CREATE DATABASE "{c["database"]}"{gabarit}'))
        if r.returncode:
            raise ErreurPostgres(f"reset : {r.stderr.strip()[-300:]}")

    def arreter(self, ressource):
        r = self._run([self._bin("pg_ctl"), "-D", ressource.connection["data_dir"], "-m", "fast", "-w", "stop"])
        if r.returncode and "PID" not in (r.stdout + r.stderr):
            raise ErreurPostgres(f"arrêt : {(r.stdout + r.stderr).strip()[-300:]}")

    def demarrer(self, ressource):
        c = ressource.connection
        self._demarrer(Path(c["data_dir"]), Path(c["log"]))

    def detruire(self, ressource):
        self.arreter(ressource)
