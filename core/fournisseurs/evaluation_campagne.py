"""Campagne d'évaluation d'un agent (Playbook v3.3 §12.6 ; étape G4) : assemble la plateforme d'exécution des
tickets, le runtime d'agent et le moteur d'évaluation du cœur.

Pour chaque tâche de la suite : ticket d'évaluation (périmètre = celui de la tâche) → `Plateforme.demarrer` (Policy
Engine `run_ticket`, espace isolé) → agent réel dans l'espace → `Plateforme.cloturer` (diff, contrôle du périmètre
J13, gates du projet avec leur répertoire) → contrôles de la suite (fichiers cachés copiés APRÈS le passage de
l'agent, puis commandes de vérification). Le résultat est constaté, jamais déclaré par l'agent.

Lancer de vrais agents est un acte humain : `factory eval run` est refusé dans une session d'agent.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

from fournisseurs import cablage
from fournisseurs.runtime_claude_code import RuntimeClaudeCode
from noyau import contexte, evaluation
from noyau.approbation import canonique, empreinte
from noyau.execution import Plateforme
from noyau.graphe import Tache
from noyau.masquage import masquer
from noyau.organisation import Membre
from noyau.runtime import Contexte, ResultatTache

FACTORY = cablage.FACTORY
EVIDENCE = FACTORY / "compliance" / "evidence" / "evaluations"
CAPACITES = ["FILESYSTEM_READ", "FILESYSTEM_WRITE", "TEST", "BUILD"]


def charger_suite(chemin: Path) -> dict:
    s = yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
    erreurs = evaluation.valider_suite(s or {})
    # Une tâche sans gate retomberait sur TOUTES les gates obligatoires du manifest, dont certaines peuvent viser une
    # base réelle (pilote : integration_tests sur le port 5432) : chaque tâche déclare explicitement les siennes.
    erreurs += [f"{t.get('id')} : aucune gate déclarée (suite ou tâche)" for t in (s or {}).get("tasks") or []
                if not (t.get("gates") or s.get("gates"))]
    # Une campagne part d'un commit FIXE où la suite a été vérifiée : jamais d'une tête qui bouge (auto-test du
    # 17/10/2026 : un commit du projet pendant la campagne a cassé un test sans rapport avec les tâches).
    if s and not re.fullmatch(r"[0-9a-f]{7,40}", str(s.get("base_commit") or "")):
        erreurs.append("base_commit absent ou invalide (empreinte de commit attendue)")
    if erreurs:
        raise ValueError("suite invalide : " + " ; ".join(erreurs))
    return s


def plateforme(moteur=None) -> Plateforme:
    moteur = moteur or contexte.moteur(FACTORY)[0]
    return Plateforme(FACTORY, moteur, contexte.machine(FACTORY), cablage._y("policies/execution.yaml"),
                      cablage._y("policies/root-scope.yaml"))


def ticket_de(suite: dict, tache: dict, campagne: str) -> dict:
    return {"id": f"{campagne}-{tache['id']}", "project_id": suite["project_id"],
            "criticality": tache.get("criticality", "C1"), "scope": {"paths": list(tache["scope"])},
            "objective": tache["instructions"], "state": "READY",
            "quality": {"required_gates": list(tache.get("gates") or suite.get("gates") or [])}}


def avant_lancement(suite: dict, agent: str, moteur=None) -> list[str]:
    """Refus prévisibles AVANT de lancer quoi que ce soit (lecture seule) : décision du Policy Engine par tâche."""
    moteur = moteur or contexte.moteur(FACTORY)[0]
    refus = []
    for t in suite["tasks"]:
        tk = ticket_de(suite, t, "PLAN")
        d = moteur.decider({"actor": {"type": "agent", "id": agent}, "project_id": suite["project_id"],
                            "action": "run_ticket", "ticket": tk,
                            "resource": {"kind": "ticket", "id": tk["id"], "environment": "LOCAL"}})
        if d.decision != "ALLOW":
            refus.append(f"{t['id']} : {d.decision} {d.regle} — {'; '.join(d.motifs)}")
    return refus


class EnvironnementBase:
    """Base de données jetable d'une tâche d'évaluation (rôle database) : créée avec le socle du projet (recette du
    registre), bail limité aux capacités déclarées par la suite (jamais plus), contrôles SQL de l'évaluateur,
    destruction en fin de tâche. L'agent n'y accède que par `factory env sql … --bail`, qui revérifie le bail et la
    politique à chaque opération et classe chaque fichier selon son contenu."""

    def __init__(self, spec: dict, projet: str, agent: str):
        self.spec, self.projet, self.agent = spec, projet, agent
        self.g, self.gc = cablage.environnements(), cablage.capacites()
        self.pg = cablage.fournisseurs()["par_genre"]["database"]
        self.env = self.res = self.bail = self.execution = None

    def preparer(self, tk: dict, exe: dict) -> tuple[str | None, dict | None, list[str], str | None]:
        """→ (bail, environnement pour la consigne, notes pour l'agent, erreur)."""
        ident = re.sub(r"[^a-z0-9-]", "-", ("ev-" + exe["execution_id"]).lower())[:60]
        socle = cablage.recette_base(self.projet)
        if socle:
            # Le socle est lu dans l'espace isolé (commit fixe de la suite), jamais dans le dossier de travail du
            # projet, où une autre session peut avoir des modifications non commitées.
            espace = Path(exe["isolation"]["worktree"])
            racine = Path(cablage._y(f"registry/projects/{self.projet}/project.yaml")["root"]["path"])
            socle = dict(socle, files=[str(espace / Path(f).relative_to(racine)) for f in socle["files"]])
            absents = [f for f in socle["files"] if not Path(f).is_file()]
            if absents:
                return None, None, [], f"socle absent au commit de base : {', '.join(absents)}"
        spec = {"kind": "database", "name": "db", "database": f"{self.projet}_test".replace("-", "_")}
        if socle:
            spec.update(baseline=socle, classification=socle["classification"])
        self.execution = exe["execution_id"]
        self.env = self.g.creer(ident, self.projet, self.execution, self.spec.get("profile", "LOCAL_TEST"), [spec])
        self.res = self.g.ressource(self.env.id, "database")
        caps = list(self.spec["lease_capabilities"])
        _, s = self.gc.demander({"type": "agent", "id": self.agent}, self.projet,
                                {"id": tk["id"], "project_id": self.projet, "criticality": "C1"},
                                {"id": self.execution, "worktree": exe["isolation"]["worktree"]}, self.env.id, caps,
                                [self.res.id])
        if s["decision"] != "ALLOW":
            return None, None, [], f"bail refusé : {s['decision']} — {'; '.join(s['reasons'])}"
        self.bail = s["lease"]
        cmd = (f"python -P {(FACTORY / 'factory.py').as_posix()} env sql {self.env.id} --bail {self.bail} "
               f"--agent {self.agent} --projet {self.projet} --ticket {tk['id']} --execution {self.execution}")
        return self.bail, {"id": self.env.id}, [
            f"Base de test jetable {self.env.id} (socle du projet) : requête → {cmd} --sql \"SELECT …\" ; appliquer une "
            f"migration → {cmd} --fichier <chemin du fichier>. Ton bail couvre : {', '.join(caps)} (rien d'autre)."], None

    def valeur(self, sql: str) -> tuple[int, str]:
        return self.pg.valeur(self.res, sql)

    def appliquer(self, fichier: Path) -> tuple[int, str]:
        r = self.pg.executer_sql(self.res, fichier=str(fichier))
        return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-500:]

    def fermer(self) -> None:
        if self.bail:
            self.gc.liberer(self.execution, "fin de la tâche d'évaluation")
        if self.env:
            self.g.detruire(self.env.id, "fin de la tâche d'évaluation")


def _controle_base(c: dict, env, espace: Path, changes: list[str]) -> tuple[bool, dict]:
    """Contrôles sur la base jetable : `apply` (migrations de l'agent appliquées N fois : rejouables) ou `sql`
    (résultat attendu exact, ou seulement un code de sortie nul)."""
    if env is None:
        return False, {"check": c, "held": False, "output": "aucune base jetable pour ce contrôle"}
    if "apply" in c:
        fichiers = sorted(f for f in changes if f.startswith(c["apply"]) and f.endswith(".sql"))
        if not fichiers:
            return False, {"apply": c["apply"], "held": False, "output": "aucune migration produite"}
        for _ in range(int(c.get("times", 1))):
            for f in fichiers:
                code, sortie = env.appliquer(espace / f)
                if code != 0:
                    return False, {"apply": f, "held": False, "code": code, "output": masquer(sortie)}
        return True, {"apply": fichiers, "times": int(c.get("times", 1)), "held": True}
    code, valeur = env.valeur(c["sql"])
    tenu = code == 0 and ("equals" not in c or valeur == str(c["equals"]))
    return tenu, {"sql": c["sql"][:200], "code": code, "value": masquer(valeur)[-300:], "expected": c.get("equals"),
                  "held": tenu}


def _controles(tache: dict, dossier_suite: Path, espace: Path, delai: int, env=None,
               changes: list[str] | None = None) -> tuple[bool | None, list[dict]]:
    """Fichiers cachés (copiés après l'agent) puis contrôles de la tâche : commandes (argv, mutations) et contrôles
    de base jetable (apply, sql). None = aucun contrôle."""
    controles = tache.get("checks") or []
    if not controles:
        return None, []
    for rel in tache.get("hidden_files") or []:
        src, dst = dossier_suite / rel["from"], espace / rel["to"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    sorties, ok = [], True
    for c in controles:
        if "apply" in c or "sql" in c:
            tenu, sortie = _controle_base(c, env, espace, changes or [])
            sorties.append(sortie)
            ok = ok and tenu
            continue
        cwd = espace / (c.get("cwd") or ".")
        attendu = c.get("expect", "pass")                  # « fail » : contrôle de mutation (les tests doivent échouer)
        mutation, cible, original = c.get("mutation"), None, None
        if mutation:
            cible = espace / mutation["file"]
            original = cible.read_bytes() if cible.is_file() else None          # octets : fins de ligne intactes
            avant, apres = mutation["original"].encode("utf-8"), mutation["mutated"].encode("utf-8")
            if original is None or original.count(avant) != 1:
                sorties.append({"argv": c["argv"], "code": None, "output": "mutation inapplicable"})
                ok = False
                continue
            temps = cible.stat()
            cible.write_bytes(original.replace(avant, apres))
            # Date décalée : un cache compilé (bytecode, build incrémental) ne doit jamais masquer la mutation.
            os.utime(cible, ns=(temps.st_atime_ns, temps.st_mtime_ns + 2_000_000_000))
        try:
            r = subprocess.run(list(c["argv"]), cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=delai, shell=False, stdin=subprocess.DEVNULL)
            code, sortie = r.returncode, masquer((r.stdout or "") + (r.stderr or ""))[-2000:]
        except (OSError, subprocess.TimeoutExpired) as e:
            code, sortie = None, type(e).__name__
        finally:
            if mutation:
                cible.write_bytes(original)                   # toujours rétabli, à l'octet près
                os.utime(cible, ns=(temps.st_atime_ns, temps.st_mtime_ns + 4_000_000_000))   # caches invalidés
        tenu = (code == 0) if attendu == "pass" else (code not in (0, None))
        sorties.append({"argv": c["argv"], "code": code, "expect": attendu, "held": tenu, "output": sortie})
        ok = ok and tenu
    return ok, sorties


def retirer_espace(racine_projet: Path, exe: dict) -> None:
    """Retire l'espace isolé d'une tâche d'évaluation et sa branche, une fois ses preuves capturées : une évaluation
    ne se fusionne jamais, et chaque espace porte une copie des dépendances (centaines de Mo)."""
    iso = exe.get("isolation") or {}
    for argv in (["git", "-C", str(racine_projet), "worktree", "remove", "--force", str(iso.get("worktree"))],
                 ["git", "-C", str(racine_projet), "branch", "-D", str(iso.get("branch"))]):
        if iso.get("worktree") and iso.get("branch"):
            subprocess.run(argv, capture_output=True, text=True, timeout=600, shell=False, stdin=subprocess.DEVNULL)


def executer_tache(pf: Plateforme, runtime, suite: dict, dossier_suite: Path, tache: dict, agent: str, modele: str,
                   campagne: str, delai: int = 900, nettoyer: bool = False, fabrique_env=None) -> dict:
    tk = ticket_de(suite, tache, campagne)
    exe = pf.demarrer(tk, suite["project_id"], agent, modele, base=str(suite["base_commit"]))   # cible fixe
    base = {"task": tache["id"], "execution_id": exe.get("execution_id"), "review": None, "tokens": 0, "changed": []}
    if exe.get("state") != "RUNNING":
        return {**base, "executed": False, "agent_status": None, "gates_ok": None, "scope_ok": True,
                "errors": exe.get("errors") or [f"démarrage : {exe.get('state')}"]}
    env = None
    try:
        if suite.get("environment"):
            fabrique = fabrique_env or (lambda spec: EnvironnementBase(spec, suite["project_id"], agent))
            env = fabrique(suite["environment"])
        return _executer_dans(pf, runtime, suite, dossier_suite, tache, agent, modele, campagne, delai, tk, exe, base,
                              env)
    finally:
        if env is not None:
            env.fermer()                                   # base détruite, bail libéré, même en échec
        if nettoyer:
            retirer_espace(pf.moteur.projets[suite["project_id"]].racine, exe)


def _executer_dans(pf, runtime, suite, dossier_suite, tache, agent, modele, campagne, delai, tk, exe, base,
                   env=None) -> dict:
    espace = Path(exe["isolation"]["worktree"])
    bail, contexte_env, notes_env, capacites = None, None, [], list(CAPACITES)
    if env is not None:
        bail, contexte_env, notes_env, erreur = env.preparer(tk, exe)
        if erreur:
            pf.cloturer(exe, tk)
            return {**base, "executed": False, "agent_status": None, "gates_ok": None, "scope_ok": True,
                    "errors": [erreur]}
        capacites += list(suite["environment"]["lease_capabilities"])
    t = Tache(tache["id"], tache.get("title") or tache["id"], agent, capacites=capacites,
              entree={"instructions": tache["instructions"], "ticket": tk["id"]}, ecrit=list(tache["scope"]))
    ctx = Contexte(campagne, suite["project_id"], t, Membre(f"{agent}-eval", agent, "SPECIALIST"), modele=modele,
                   espace=str(espace), consignes=[f"Rôle : {agent}. Évaluation {suite['id']}, tâche {tache['id']}."]
                   + [str(n) for n in suite.get("agent_notes") or []] + notes_env,
                   environnement=contexte_env, bail=bail,
                   autorite={"kind": "TICKET_EXECUTION", "execution_id": exe["execution_id"], "worktree": str(espace),
                             "scope": list(tache["scope"]),
                             "executions_dir": (FACTORY / "audit" / "executions").as_posix()})
    r = runtime.executer(ctx)
    refus = list(getattr(runtime, "refus", lambda _c: [])(ctx))           # tentatives bloquées par la garde
    fin = pf.cloturer(exe, tk)
    erreurs = list(fin.get("errors") or [])
    hors = any(e.startswith("SCOPE_VIOLATION") for e in erreurs)
    changes = list(fin.get("changes") or [])
    gates_ok = True if fin.get("state") == "COMPLETED" else (None if not changes and not hors else False)
    controle_ok, sorties = (_controles(tache, dossier_suite, espace, delai, env, changes) if changes and not hors
                            else (None, []))
    if controle_ok is False:
        gates_ok = False
    return {**base, "executed": True, "agent_status": "success" if r.succes else "failure",
            "gates_ok": gates_ok, "scope_ok": not hors, "changed": changes, "tokens": int(r.jetons or 0),
            "errors": erreurs, "checks": sorties, "agent_summary": (r.motif or "")[:500],
            "denied_attempts": refus}


class RuntimeReference:
    """Auto-test de la suite (SELFTEST) : à la place d'un agent, pose la solution de référence de chaque tâche.
    Prouve que chaque tâche est faisable et que ses contrôles distinguent un bon travail d'un mauvais, sur le vrai
    projet. Un résultat d'auto-test n'est JAMAIS une preuve d'habilitation."""

    def __init__(self, suite: dict, dossier_suite: Path):
        self.taches = {t["id"]: t for t in suite["tasks"]}
        self.dossier = Path(dossier_suite)

    def executer(self, ctx: Contexte) -> ResultatTache:
        ref = self.taches[ctx.tache.id].get("reference") or {}
        for f in ref.get("files") or []:
            cible = Path(ctx.espace) / f["to"]
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.dossier / f["from"], cible)
        for e in ref.get("edits") or []:                    # modification exacte d'un fichier existant (octets)
            cible = Path(ctx.espace) / e["file"]
            texte = cible.read_bytes()
            avant, apres = e["original"].encode("utf-8"), e["replacement"].encode("utf-8")
            if texte.count(avant) != 1:
                return ResultatTache(False, "PLAN_INVALID", "reference:edit", f"référence inapplicable : {e['file']}")
            cible.write_bytes(texte.replace(avant, apres))
        ok = ref.get("status") == "success"
        return ResultatTache(ok, None if ok else "AGENT_STUCK", "reference", "solution de référence", jetons=0)


def lancer(chemin_suite: Path, agent: str, modele: str, executable: str = "claude", auto_test: bool = False) -> Path:
    """Campagne réelle (acte humain), ou auto-test de la suite avec les solutions de référence. → résultats."""
    suite = charger_suite(chemin_suite)
    pf = plateforme()
    gates = ((pf.moteur.projets[suite["project_id"]].manifest.get("quality") or {}).get("gates") or {})
    # Commandes permises à l'agent : celles des gates du projet, plus celles que la suite déclare (lancer un seul
    # test, par exemple). Elles exécutent le code de l'agent comme les gates : aucune classe de risque nouvelle.
    commandes = [str(g["command"]) for g in gates.values() if (g or {}).get("command")]
    commandes += [str(c) for c in suite.get("agent_commands") or []]
    if auto_test:
        sans_ref = [t["id"] for t in suite["tasks"] if not t.get("reference")]
        if sans_ref:
            raise ValueError("auto-test impossible : tâches sans solution de référence : " + ", ".join(sans_ref))
        runtime = RuntimeReference(suite, Path(chemin_suite).parent)
    else:
        runtime = RuntimeClaudeCode(commandes_permises=commandes, executable=executable, a_blanc=False,
                                    baux=cablage.racines()["etat"] / "leases")
    campagne = f"{'SELFTEST' if auto_test else 'EVAL'}-{agent}-{_dt.datetime.now(_dt.timezone.utc):%Y%m%dT%H%M%S}"
    plancher = int((cablage._y("orchestrator/environnements.yaml").get("quotas") or {}).get("min_free_disk_mb", 0))
    racine_espaces = Path(cablage._y("policies/execution.yaml")["workspaces_root"])
    dossier = EVIDENCE / campagne
    dossier.mkdir(parents=True, exist_ok=False)
    camp = {"campaign": campagne, "agent": agent, "model": modele, "mode": "SELFTEST" if auto_test else "REAL",
            "suite_file": Path(chemin_suite).as_posix(), "suite_sha256": empreinte(suite), "complete": False}
    (dossier / "campaign.json").write_text(canonique(camp), encoding="utf-8")
    resultats = []
    for tache in suite["tasks"]:
        libre = shutil.disk_usage(racine_espaces).free // (1024 * 1024)
        if libre < plancher:                      # Resource Broker : jamais un disque plein en cours de campagne
            camp["stopped"] = f"espace libre {libre} Mo < {plancher} Mo avant {tache['id']}"
            break
        resultats.append(executer_tache(pf, runtime, suite, Path(chemin_suite).parent, tache, agent, modele, campagne,
                                        nettoyer=True))
        (dossier / "results.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        camp["complete"] = True
    (dossier / "campaign.json").write_text(canonique(camp), encoding="utf-8")
    if not camp["complete"]:
        raise RuntimeError(f"campagne interrompue : {camp['stopped']} (aucun rapport valable)")
    return dossier / "results.json"


def rapport(dossier: Path) -> dict:
    camp = json.loads((dossier / "campaign.json").read_text(encoding="utf-8"))
    suite = charger_suite(FACTORY / camp["suite_file"]) if not Path(camp["suite_file"]).is_absolute() \
        else charger_suite(Path(camp["suite_file"]))
    if empreinte(suite) != camp["suite_sha256"]:
        raise ValueError("la suite a changé depuis la campagne : rapport impossible")
    if not camp.get("complete"):
        raise ValueError(f"campagne incomplète ({camp.get('stopped', 'interrompue')}) : rapport impossible")
    resultats = json.loads((dossier / "results.json").read_text(encoding="utf-8"))
    agent = contexte.moteur(FACTORY)[0].registre.get("agents", camp["agent"]) or {"id": camp["agent"]}
    r = evaluation.rapport(suite, agent, camp["model"], resultats, camp["campaign"],
                           _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"))
    r["mode"] = camp.get("mode", "REAL")
    r["report_sha256"] = empreinte({k: v for k, v in r.items() if k != "report_sha256"})
    (dossier / "report.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


def bloc_habilitation(r: dict, jours: int, aujourd_hui: _dt.date | None = None) -> dict:
    """Bloc `habilitation` proposé par un rapport (à approuver par l'humain, W1)."""
    if r.get("mode") != "REAL":
        raise ValueError("un auto-test de la suite (solutions de référence) n'est jamais une preuve d'habilitation")
    if not r["verdict"]["max_criticality"]:
        raise ValueError("aucun niveau tenu : aucune habilitation à demander")
    jour = aujourd_hui or _dt.date.today()
    return {"max_criticality": r["verdict"]["max_criticality"], "projects": [r["project_id"]], "model": r["model"],
            "evaluation": {"suite_sha256": r["suite"]["sha256"], "report_sha256": r["report_sha256"]},
            "granted_at": jour.isoformat(), "expires_at": (jour + _dt.timedelta(days=jours)).isoformat()}


# ------------------------------------------------------------------------------------------- registre
def ecrire_habilitation(fiche: Path, bloc: dict) -> None:
    """Écrit l'habilitation approuvée dans la fiche de l'agent en conservant le reste du texte (commentaires
    compris) : état `APPROVED` et bloc `habilitation` (remplacé s'il existe)."""
    out, saute = [], False
    for ligne in fiche.read_text(encoding="utf-8").splitlines():
        if saute:
            if ligne and not ligne[0].isspace() and not ligne.startswith("#"):
                saute = False
            else:
                continue
        if ligne.startswith("habilitation:"):
            saute = True
            continue
        out.append("lifecycle: APPROVED" if ligne.startswith("lifecycle:") else ligne)
    texte = "\n".join(out).rstrip("\n") + "\n" + yaml.safe_dump({"habilitation": bloc}, allow_unicode=True,
                                                                sort_keys=False)
    fiche.write_text(texte, encoding="utf-8")


# ------------------------------------------------------------------------------------------- CLI
def cmd_eval(a, sortir) -> int:
    from noyau.approbation import Magasin
    from noyau.audit import Journal
    from noyau.demandes import RefusDemande, deposer
    from noyau.politique import contexte_habilitation_definitive
    pol_h = cablage._y("policies/human-approval.yaml")
    regle = cablage._y("policies/policy-engine.yaml")["habilitation"]
    if a.action == "plan":
        suite = charger_suite(Path(a.cible))
        refus = avant_lancement(suite, a.agent)
        lignes = [f"suite {suite['id']} v{suite['version']} — rôle {suite['role']}, projet {suite['project_id']}"]
        lignes += [f"  {t['id']:10} {t['kind']:10} {t.get('title', '')}" for t in suite["tasks"]]
        lignes += [f"REFUS : {x}" for x in refus] or ["Policy Engine : toutes les tâches peuvent démarrer"]
        sortir({"suite": suite["id"], "tasks": [t["id"] for t in suite["tasks"]], "refus": refus}, "\n".join(lignes))
        return 2 if refus else 0
    if a.action == "selftest":
        # Aucun agent n'est lancé : les solutions de référence prouvent la suite et la chaîne sur le vrai projet.
        try:
            chemin = lancer(Path(a.cible), a.agent, "reference", auto_test=True)
        except (RuntimeError, ValueError) as e:
            sortir({"refus": str(e)}, f"refus : {e}")
            return 2
        rel = chemin.parent.relative_to(FACTORY).as_posix()
        sortir({"resultats": str(chemin)}, f"auto-test terminé : {chemin}\nrapport : python -P factory.py eval report "
                                            f"{rel}")
        return 0
    if a.action == "run":
        if cablage.dans_une_session_d_agent():
            sortir({"refus": "session d'agent"}, "refus : lancer de vrais agents est réservé à l'humain")
            return 2
        e = cablage.etat_epinglage()
        if e.statut == "BLOCKED":
            sortir({"refus": e.motif}, f"refus : épinglage BLOCKED — {e.motif}")
            return 2
        if not a.modele:
            sortir({"refus": "--modele exigé"}, "refus : précisez le modèle évalué (--modele)")
            return 3
        try:
            chemin = lancer(Path(a.cible), a.agent, a.modele)
        except (RuntimeError, ValueError) as e:
            sortir({"refus": str(e)}, f"refus : {e}")
            return 2
        sortir({"resultats": str(chemin)}, f"campagne terminée : {chemin}\nrapport : python -P factory.py eval report "
                                            f"{chemin.parent.relative_to(FACTORY).as_posix()}")
        return 0
    dossier = FACTORY / a.cible
    if a.action == "report":
        r = rapport(dossier)
        m, v = r["measures"], r["verdict"]
        sortir(r, "\n".join([f"{r['campaign']} — agent {r['agent']}, modèle {r['model']}, suite {r['suite']['id']}",
                             f"réussite {m['success_rate']:.0%} · affirmations fausses {m['false_success']} · "
                             f"sorties de périmètre {m['scope_violations']} · pièges ratés {m['trap_failures']} · "
                             f"jetons {m['tokens']}",
                             f"tâches en échec : {', '.join(m['failed_tasks']) or 'aucune'}",
                             f"criticité maximale prouvée : {v['max_criticality'] or 'AUCUNE'}"]
                            + [f"  {k} : {'; '.join(x)}" for k, x in v["detail"].items()]))
        return 0
    r = json.loads((dossier / "report.json").read_text(encoding="utf-8"))
    if r.get("report_sha256") != empreinte({k: v for k, v in r.items() if k != "report_sha256"}):
        sortir({"refus": "rapport modifié"}, "refus : rapport modifié depuis sa production")
        return 2
    if a.action == "request":
        try:
            bloc = bloc_habilitation(r, int(regle["max_days"]))
        except ValueError as e:
            sortir({"refus": str(e)}, f"refus : {e}")
            return 2
        ctx = contexte_habilitation_definitive(r["agent"], bloc)
        demande = {"context": ctx, "context_sha256": empreinte(ctx), "roles": list(regle["approver_roles"]),
                   "purpose": f"HABILITATION de l'agent {r['agent']} jusqu'à {bloc['max_criticality']} sur "
                              f"{', '.join(bloc['projects'])}, modèle {bloc['model']}, jusqu'au {bloc['expires_at']}. "
                              f"Preuves : rapport {r['report_sha256'][:12]} ({r['campaign']}), réussite "
                              f"{r['measures']['success_rate']:.0%}, pièges ratés {r['measures']['trap_failures']}."}
        (dossier / "habilitation.json").write_text(canonique(bloc), encoding="utf-8")
        try:
            chemin, _ = deposer(FACTORY / pol_h["requests"], f"AR-HABDEF-{r['agent']}-{demande['context_sha256'][:8]}"
                                ".json", demande, FACTORY / pol_h["records"], pol_h.get("max_open_requests"))
        except RefusDemande as e:
            sortir({"refus": str(e)}, f"refus : {e}")
            return 2
        rel = chemin.relative_to(FACTORY).as_posix()
        sortir({"demande": rel}, f"demande préparée : {rel}\n{demande['purpose']}\n"
                                 f"acte humain : python -P scripts/factory_approve.py {rel}")
        return 0
    bloc = json.loads((dossier / "habilitation.json").read_text(encoding="utf-8"))
    verif = Magasin(FACTORY / pol_h["records"]).trouver(contexte_habilitation_definitive(r["agent"], bloc),
                                                        regle["approver_roles"], int(regle["max_days"]) * 24)
    if not verif.valide:
        sortir({"refus": verif.motif}, f"refus : {verif.motif}")
        return 2
    ecrire_habilitation(FACTORY / "registry" / "agents" / f"{r['agent']}.yaml", bloc)
    j = Journal(FACTORY / "audit" / "journal.jsonl")
    for depart, vers in (("DISCOVERED", "EVALUATING"), ("EVALUATING", "TESTED"), ("TESTED", "APPROVED")):
        j.ajouter(actor={"type": "system", "id": "factory-cli"}, project_id=r["project_id"],
                  action="transition agent (habilitation, Playbook §12.6)", from_state=depart, to_state=vers,
                  result=vers, agent_id=r["agent"], evidence_refs=[f"{a.cible}/report.json"],
                  reasons=[verif.motif, f"rapport {r['report_sha256'][:12]}, plafond {bloc['max_criticality']}"])
    sortir({"agent": r["agent"], "habilitation": bloc},
           f"{r['agent']} APPROVED jusqu'à {bloc['max_criticality']} ({verif.motif})\n"
           f"la fiche est épinglée : nouvelle référence à approuver (python -P factory.py pin request)")
    return 0
