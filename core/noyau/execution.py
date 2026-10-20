"""Plateforme d'exécution v1 (jalon J13, Playbook §8.1–§8.3, Executable Schemas §7 et §33).

Pipeline : Policy Engine (run_ticket) → AUTHORIZED (≤ 3 tentatives) → RESERVED → espace isolé + branche dédiée →
PREPARED → STARTED → RUNNING (l'agent travaille DANS l'espace, avec son enveloppe de contexte) → clôture :
diff réel comparé au périmètre (débordement = échec), gates du manifest exécutés avec preuves → COMPLETED ou
FAILED. Chaque transition passe par le moteur d'états (donc par l'audit). La plateforme ne supprime, ne pousse et
ne fusionne rien.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import preuves as _preuves
from . import revue as _revue
from .commandes import Executeur
from .approbation import empreinte
from .demandes import deposer
from .etats import APPLIED, Machine
from .perimetre import Perimetre, Racine, canonique
from .politique import Moteur
from .validation import chemin_relatif_sur

_CODE_PLANTAGE = 0xC0000000          # codes de sortie d'exception du système (Windows) : un plantage, pas un verdict


def _maintenant() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class Plateforme:
    racine_factory: Path
    moteur: Moteur
    machine: Machine
    config: dict                     # policies/execution.yaml
    racine_scope: dict               # policies/root-scope.yaml
    version_factory: str = "3.2"
    version_schemas: str = "1.0"
    version_prompt: str = "1.1"

    # ------------------------------------------------------------------ outillage
    def _perimetre(self, projet) -> Perimetre:
        racines = {"PROJECT_ROOT": Racine("PROJECT_ROOT", canonique(projet.racine)),
                   "WORKSPACES": Racine("WORKSPACES", canonique(self.config["workspaces_root"])),
                   "FACTORY_ROOT": Racine("FACTORY_ROOT", canonique(self.racine_factory))}
        return Perimetre(racines, self.racine_scope.get("sensitive_file_patterns", []),
                         self.racine_scope.get("sensitive_dir_names", []), self.racine_scope.get("never_traverse", []), [])

    def _vcs(self, projet) -> Executeur:
        """Exécuteur limité aux opérations déclarées par la politique (gabarits → argv autorisés)."""
        return Executeur(autorisees=list(self.config["operations"].values()), jokers=self.config["placeholders"],
                         perimetre=self._perimetre(projet), delai=120)

    def _op(self, vcs: Executeur, operation: str, cwd, **valeurs):
        argv = [a.format(**valeurs) if a.startswith("{") else a for a in self.config["operations"][operation]]
        return vcs.lancer(argv, cwd=cwd)

    def _transition(self, exe, vers, acteur, **k):
        r = self.machine.transitionner("execution", exe, vers, acteur, **k)
        exe.setdefault("history", []).append({"to": vers, "result": r.statut, "reasons": r.motifs, "event": r.evenement})
        return r

    def _echec(self, exe, acteur, vers, motif) -> dict:
        exe.setdefault("errors", []).append(motif)
        self._transition(exe, vers, acteur)
        return exe

    def _changements(self, vcs: Executeur, espace: Path, base: str) -> list[str]:
        """Fichiers suivis différents de la base + fichiers nouveaux non ignorés, triés."""
        suivis = self._op(vcs, "changed_tracked", espace, base=base)
        nouveaux = self._op(vcs, "changed_untracked", espace)
        return sorted({l.strip() for r in (suivis, nouveaux) if r.executee for l in r.sortie.splitlines() if l.strip()})

    def _ignores(self, vcs: Executeur, espace: Path) -> set[str]:
        """Entrées ignorées par git (répertoires regroupés) : ce que le contrôle du diff ne voit pas (NE3)."""
        if "ignored_entries" not in self.config.get("operations", {}):
            return set()
        r = self._op(vcs, "ignored_entries", espace)
        return {l.strip() for l in r.sortie.splitlines() if l.strip()} if r.executee else set()

    def _copier_dependances(self, projet, vcs, espace: Path) -> dict | str:
        """Copie dans l'espace isolé les dossiers déclarés par la carte du projet (workspace.copy_from_root), depuis
        la racine du projet. Une copie, jamais un lien : ce que les gates y écrivent reste dans l'espace, et retirer
        l'espace ne touche jamais le projet. Refus : chemin non relatif, sensible ou interdit, source absente,
        destination existante, ou dossier que l'outil de version ne dit pas ignoré (il deviendrait un changement)."""
        resultat = {}
        interdits = (projet.manifest.get("paths") or {}).get("forbidden", []) + projet.sensibles
        for chemin in (projet.espace or {}).get("copy_from_root") or []:
            if not chemin_relatif_sur(chemin) or self.moteur._sensible(chemin, interdits):
                return f"dépendance refusée (chemin non relatif, sensible ou interdit) : {chemin!r}"
            source, cible = projet.racine / chemin, espace / chemin
            if not source.is_dir():
                return f"dépendance absente du projet : {chemin}"
            if cible.exists():
                return f"dépendance déjà présente dans l'espace isolé : {chemin}"
            debut = _dt.datetime.now(_dt.timezone.utc)
            shutil.copytree(source, cible, symlinks=True)
            fichiers = sum(1 for p in cible.rglob("*") if p.is_file())
            visibles = [f for f in self._changements(vcs, espace, "HEAD") if f == chemin or f.startswith(chemin.rstrip("/") + "/")]
            if visibles:
                shutil.rmtree(cible)
                return f"dépendance non ignorée par l'outil de version (elle deviendrait un changement) : {chemin}"
            resultat[chemin] = {"files": fichiers,
                                "seconds": round((_dt.datetime.now(_dt.timezone.utc) - debut).total_seconds(), 1)}
        return resultat

    def _preuve_changements(self, exe, vcs, espace: Path, base: str, changes: list[str], neutres: list[str]) -> dict:
        """Preuve ARTIFACT des changements de l'agent, fichier par fichier (T-FACTORY-020) : le « diff --stat » brut
        ignore les fichiers nouveaux. Un fichier nouveau est décrit par sa taille, jamais par son contenu (il n'a pas
        encore passé le contrôle de périmètre : il pourrait être sensible)."""
        lignes = [f"Changements de l'agent — exécution {exe['execution_id']}, base {base}"]
        for f in changes:
            if (espace / f).is_file():
                stat = self._op(vcs, "diff_numstat", espace, base=base, fichier=f)
                champs = stat.sortie.split() if stat.executee and stat.code == 0 else []
                if len(champs) >= 2:
                    lignes.append(f"modifié  +{champs[0]} -{champs[1]}  {f}")
                else:
                    lignes.append(f"nouveau  {(espace / f).stat().st_size} octets  {f}")
            else:
                lignes.append(f"supprimé  {f}")
        lignes += [f"écarté (différence d'extraction inchangée, ADR-0013)  {f}" for f in neutres]
        nom = f"{exe['execution_id']}-changes.txt"
        racine = self.machine.racine_preuves
        racine.mkdir(parents=True, exist_ok=True)
        with open(racine / nom, "x", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lignes) + "\n")
        return {"id": f"{exe['execution_id']}-changes", "type": "ARTIFACT", "source": "plateforme : changements de l'agent",
                "timestamp": _maintenant(), "command": None, "exit_code": None, "result": "SUCCESS",
                "artifact_ref": nom, "hash": hashlib.sha256((racine / nom).read_bytes()).hexdigest(),
                "generated_by": f"plateforme:{exe['execution_id']}", "verified_by": None, "immutable": True}

    @staticmethod
    def _empreintes(espace: Path, fichiers: list[str]) -> dict[str, str]:
        """Empreinte SHA-256 du contenu de chaque fichier de l'espace (ABSENT s'il a été supprimé)."""
        return {f: (hashlib.sha256((espace / f).read_bytes()).hexdigest() if (espace / f).is_file() else "ABSENT")
                for f in fichiers}

    def _dossier(self, exe) -> Path:
        return self.racine_factory / "audit" / "executions" / exe["execution_id"]

    # ------------------------------------------------------------------ démarrage
    def demarrer(self, ticket: dict, projet_id: str, agent_id: str, modele: str, base: str = "HEAD",
                 approval_id: str | None = None, contrat: dict | None = None, prompt: str | None = None) -> dict:
        """`contrat` (ticket v2, ADR-0022 D8-D10) : résolution READY du ticket (`Resolution.en_dict()`), `ticket` étant
        alors sa vue d'exécution ; le profil, l'instantané et le prompt effectif sont figés dans l'enveloppe."""
        projet = self.moteur.projets.get(projet_id)
        acteur = {"type": "agent", "id": agent_id}
        anterieures = [p for p in (self.racine_factory / "audit" / "executions").glob("EX-*/context.json")
                       if json.loads(p.read_text(encoding="utf-8")).get("ticket", {}).get("id") == ticket.get("id")] \
            if (self.racine_factory / "audit" / "executions").is_dir() else []
        horodatage = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        eid = f"EX-{horodatage}-{hashlib.sha256((ticket.get('id', '') + horodatage).encode()).hexdigest()[:6]}"
        exe = {"execution_id": eid, "id": eid, "project_id": projet_id, "ticket_id": ticket.get("id"), "state": "REQUESTED",
               "agent": {"id": agent_id, "version": "registre"}, "model": {"id": modele, "version": modele},
               "budget": {"attempt": len(anterieures) + 1, "max_attempts": self.config.get("max_attempts", 3)},
               "timestamps": {"requested": _maintenant()}}
        if projet is None:
            return self._echec(exe, acteur, "BLOCKED", f"projet {projet_id!r} non enregistré")
        if "control_profile" in ticket:
            # ADR-0022 v2 : un ticket-contrat ne s'exécute que résolu READY, avec l'instantané de ce qu'il utilise.
            if not contrat or contrat.get("status") != "READY" or contrat.get("ticket_id") != ticket.get("id") \
                    or not prompt or hashlib.sha256(prompt.encode("utf-8")).hexdigest() != contrat.get("prompt_sha256"):
                return self._echec(exe, acteur, "BLOCKED", "ticket-contrat sans résolution READY ni prompt conforme "
                                   "(ADR-0022) : " + "; ".join((contrat or {}).get("reasons") or ["résolution absente"]))
            exe["budget"]["max_attempts"] = min(exe["budget"]["max_attempts"],
                                                (contrat["execution_profile"].get("budget") or {}).get("max_attempts")
                                                or exe["budget"]["max_attempts"])
        decision = self.moteur.decider({"actor": acteur, "project_id": projet_id, "action": "run_ticket",
                                        "ticket": {**ticket, "project_id": ticket.get("project_id", projet_id)},
                                        "resource": {"kind": "ticket", "id": ticket.get("id"), "environment": "LOCAL"},
                                        "approval_id": approval_id})
        exe["policy_decision"] = decision.en_dict()
        r = self._transition(exe, "AUTHORIZED", acteur, decision_politique=decision.en_dict())
        if r.statut != APPLIED:
            exe["errors"] = r.motifs + decision.motifs
            self._transition(exe, "BLOCKED", acteur)
            return exe
        exe["timestamps"]["authorized"] = _maintenant()
        self._transition(exe, "RESERVED", acteur)

        # Espace isolé + branche dédiée (Playbook §8.3) — jamais dans le dépôt, jamais un espace existant.
        racine_espaces = Path(self.config["workspaces_root"])
        espace = racine_espaces / f"{ticket['id']}-{eid}"
        branche = f"{self.config['branch_prefix']}{ticket['id']}/{eid}"
        if espace.exists():
            return self._echec(exe, acteur, "FAILED", "espace isolé déjà existant : jamais réutilisé")
        racine_espaces.mkdir(parents=True, exist_ok=True)
        vcs = self._vcs(projet)
        sha = self._op(vcs, "resolve_base", projet.racine, base=base)
        if not sha.executee or sha.code != 0:
            return self._echec(exe, acteur, "FAILED", f"base {base!r} introuvable")
        base_sha = sha.sortie.strip()
        cree = self._op(vcs, "create_workspace", projet.racine, branche=branche, espace=str(espace), base=base_sha)
        if not cree.executee or cree.code != 0:
            return self._echec(exe, acteur, "FAILED", f"création de l'espace isolé refusée ou en échec : {cree.motif_refus or cree.sortie[:200]}")
        erreur = self.moteur._espace_du_projet(espace, projet)
        if erreur:
            return self._echec(exe, acteur, "SECURITY_STOP", erreur)
        # Différences d'extraction (T-FACTORY-019, ADR-0013) : relevées AVANT tout travail de l'agent, avec l'empreinte
        # de chaque fichier (ex. fins de ligne d'un fichier jamais renormalisé).
        extraction = self._empreintes(espace, self._changements(vcs, espace, base_sha))
        exe["isolation"] = {"worktree": str(espace), "branch": branche, "base": base_sha, "sandbox": "aucun (v1 : espace isolé seul)",
                            "extraction_differences": extraction}
        # Dépendances copiées depuis le projet (T-FACTORY-020, ADR-0014) : rien n'est installé, aucun réseau.
        copies = self._copier_dependances(projet, vcs, espace)
        if isinstance(copies, str):
            return self._echec(exe, acteur, "FAILED", copies)
        exe["isolation"]["copied_dependencies"] = copies
        # NE3 : relevé des entrées ignorées par git APRÈS la copie des dépendances, AVANT tout travail de l'agent.
        exe["isolation"]["ignored_baseline"] = sorted(self._ignores(vcs, espace))
        self._transition(exe, "PREPARED", acteur)

        # Enveloppe de contexte (State Machines & Contracts §16) : l'agent ne reçoit que son périmètre.
        ecriture = {"project_write": (projet.manifest.get("paths") or {}).get("write", []),
                    "ticket_scope": (ticket.get("scope") or {}).get("paths", []),
                    "rule": "un chemin écrit doit appartenir aux deux listes ; forbidden et fichiers sensibles priment"}
        outils = (projet.manifest.get("tools") or {})
        enveloppe = {
            "factory": {"version": self.version_factory, "policies": "policies/"},
            "project": {"id": projet_id}, "ticket": {"id": ticket["id"], "criticality": ticket.get("criticality"),
                                                     "objective": ticket.get("objective"), "scope": ticket.get("scope")},
            "execution": {"id": eid, "worktree": str(espace), "branch": branche, "base": base_sha,
                          "extraction_differences": extraction, "copied_dependencies": copies,
                          "permissions": {"write": ecriture, "read": "paths.read du projet + périmètre du ticket"}},
            "tools": {"allowed": sorted(set(outils.get("required", [])) | set(outils.get("allowed", [])))},
            "mcp": {"allowed": []},
            "security": {"restrictions": ["toute action passe par le Policy Engine", "aucune action hors de l'espace isolé",
                                          "arrêt sur ambiguïté, permission manquante ou risque (Executable Schemas §24)"]},
            "budget": {"attempt": exe["budget"]["attempt"], "max_attempts": exe["budget"]["max_attempts"]},
        }
        if contrat:
            # ADR-0022 D8, D10 : profil d'exécution et instantané figés au démarrage ; le prompt effectif est déposé à
            # côté, son empreinte dans l'instantané. Une modification ultérieure d'un registre ne change rien ici.
            enveloppe["contract"] = {"execution_profile": contrat["execution_profile"], "snapshot": contrat["snapshot"],
                                     "prompt_file": "prompt.md", "prompt_sha256": contrat["prompt_sha256"]}
        self._dossier(exe).mkdir(parents=True, exist_ok=False)
        if contrat:
            with open(self._dossier(exe) / "prompt.md", "x", encoding="utf-8", newline="\n") as f:
                f.write(prompt)
        with open(self._dossier(exe) / "context.json", "x", encoding="utf-8") as f:
            json.dump(enveloppe, f, ensure_ascii=False, indent=1)
        exe["envelope"] = enveloppe
        self._transition(exe, "STARTED", acteur)
        exe["timestamps"]["started"] = _maintenant()
        self._transition(exe, "RUNNING", acteur)
        return exe

    # ------------------------------------------------------------------ clôture
    def cloturer(self, exe: dict, ticket: dict) -> dict:
        acteur = {"type": "agent", "id": exe["agent"]["id"]}
        if exe.get("state") != "RUNNING":
            exe.setdefault("errors", []).append(f"clôture impossible depuis {exe.get('state')}")
            return exe
        projet = self.moteur.projets[exe["project_id"]]
        espace, base = Path(exe["isolation"]["worktree"]), exe["isolation"]["base"]
        vcs = self._vcs(projet)
        tous = self._changements(vcs, espace, base)
        # Une différence d'extraction ne compte pas tant que son contenu est celui relevé à la création ; dès que
        # l'agent y touche, elle redevient un changement soumis au périmètre (T-FACTORY-019, ADR-0013).
        extraction = exe["isolation"].get("extraction_differences") or {}
        actuelles = self._empreintes(espace, [f for f in tous if f in extraction])
        neutres = sorted(f for f in actuelles if actuelles[f] == extraction[f])
        changes = [f for f in tous if f not in neutres]
        exe["changes"] = changes
        exe["extraction_unchanged"] = neutres
        racine_preuves = self.machine.racine_preuves
        diff = self._op(vcs, "diff_summary", espace, base=base)
        p_diff = _preuves.enregistrer_commande(diff, "ARTIFACT", f"{exe['execution_id']}-diff", racine_preuves,
                                               f"plateforme:{exe['execution_id']}")
        preuves = [p_diff, self._preuve_changements(exe, vcs, espace, base, changes, neutres)]
        if self._transition(exe, "ARTIFACTS_PRODUCED", acteur, preuves=preuves).statut != APPLIED:
            return self._finir(exe, ticket, "FAILED", preuves)

        # Non-débordement (Playbook §9.5, §10.1) : chaque fichier changé doit être permis au ticket ET au projet.
        hors = []
        ecriture = (projet.manifest.get("paths") or {}).get("write", [])
        portee = (ticket.get("scope") or {}).get("paths", [])
        for f in changes:
            if not (self.moteur._dans(f, portee) and self.moteur._dans(f, ecriture)) or \
                    self.moteur._sensible(f, (projet.manifest.get("paths") or {}).get("forbidden", []) + projet.sensibles):
                hors.append(f)
        # NE3 : un fichier ignoré par git échappe au diff ; un NOUVEAU fichier ignoré, sensible ou interdit (secret,
        # .env…), est un débordement. Les sorties ignorées ordinaires (build, caches) ne sont pas visées.
        interdits = (projet.manifest.get("paths") or {}).get("forbidden", []) + projet.sensibles
        avant = set(exe["isolation"].get("ignored_baseline") or [])
        hors += [f"{f} (ignoré par git)" for f in sorted(self._ignores(vcs, espace) - avant)
                 if self.moteur._sensible(f.rstrip("/"), interdits)]
        if hors:
            exe.setdefault("errors", []).append("SCOPE_VIOLATION : " + ", ".join(hors))
            return self._finir(exe, ticket, "FAILED", preuves)
        if not changes:
            exe.setdefault("errors", []).append("aucune modification produite")
            return self._finir(exe, ticket, "FAILED", preuves)

        self._transition(exe, "TESTING", acteur)
        gates = (projet.manifest.get("quality") or {}).get("gates") or {}
        # Régression ciblée (Playbook §12.5) : les gates exigés par le TICKET s'ils sont déclarés, sinon ceux du projet.
        demandes = (ticket.get("quality") or {}).get("required_gates") or (projet.manifest.get("quality") or {}).get("required", [])
        inconnus = [g for g in demandes if not (gates.get(g) or {}).get("command")]
        if (ticket.get("quality") or {}).get("required_gates") and inconnus:
            exe.setdefault("errors", []).append("gates du ticket non déclarés par le manifest : " + ", ".join(inconnus))
            return self._finir(exe, ticket, "FAILED", preuves)
        requis = [g for g in demandes if (gates.get(g) or {}).get("command")]
        if not requis:
            exe.setdefault("errors", []).append("aucun gate exécutable déclaré : aucune preuve possible")
            return self._finir(exe, ticket, "FAILED", preuves)
        executeur = Executeur(autorisees=[gates[g]["command"].split() for g in requis], jokers={},
                              perimetre=self._perimetre(projet), delai=900)
        for g in requis:
            argv = gates[g]["command"].split()
            refus = self.moteur._outil(argv, projet, ticket)
            if refus:
                exe.setdefault("errors", []).append(f"gate {g} : {refus[1]}")
                return self._finir(exe, ticket, "FAILED", preuves)
            sous_dossier = gates[g].get("cwd") or "."
            if sous_dossier != "." and not chemin_relatif_sur(sous_dossier):
                exe.setdefault("errors", []).append(f"gate {g} : répertoire hors de l'espace isolé ({sous_dossier!r})")
                return self._finir(exe, ticket, "FAILED", preuves)
            dossier = espace if sous_dossier == "." else espace / sous_dossier
            res = executeur.lancer(argv, cwd=dossier)
            if res.executee and res.code is not None and res.code >= _CODE_PLANTAGE:
                # Plantage du processus (code d'exception du système, ex. 0xC0000005), pas un verdict de la gate :
                # une seule relance, tracée. Un échec ordinaire (code de l'outil) n'est jamais relancé.
                exe.setdefault("gate_retries", []).append({"gate": g, "crash_code": res.code})
                preuves.append(_preuves.enregistrer_commande(res, "TEST", f"{exe['execution_id']}-{g}-plantage",
                                                             racine_preuves, f"plateforme:{exe['execution_id']}"))
                res = executeur.lancer(argv, cwd=dossier)
            if not res.executee:
                exe.setdefault("errors", []).append(f"gate {g} non exécuté : {res.motif_refus}")
                return self._finir(exe, ticket, "FAILED", preuves)
            preuve = _preuves.enregistrer_commande(res, "TEST", f"{exe['execution_id']}-{g}", racine_preuves,
                                                   f"plateforme:{exe['execution_id']}")
            preuves.append(preuve)
            if res.code != 0:
                exe.setdefault("errors", []).append(f"gate {g} en échec (code {res.code})")
                return self._finir(exe, ticket, "FAILED", preuves)
        # État exact de l'espace après les gates (ADR-0013) : la revue exigera qu'il n'ait pas bougé. Les fichiers
        # produits par les gates (caches, rapports) y figurent, distingués des changements de l'agent.
        apres = self._empreintes(espace, self._changements(vcs, espace, base))
        exe["post_gates"] = apres
        exe["gate_outputs"] = sorted(f for f in apres if f not in changes and f not in neutres)
        return self._finir(exe, ticket, "COMPLETED", preuves)

    def _finir(self, exe, ticket, vers, preuves) -> dict:
        acteur = {"type": "agent", "id": exe["agent"]["id"]}
        r = self._transition(exe, vers, acteur, preuves=preuves)
        if r.statut != APPLIED and vers == "COMPLETED":
            self._transition(exe, "FAILED", acteur)
        exe["timestamps"]["completed"] = _maintenant()
        env = exe.get("envelope", {})
        instantane = (env.get("contract") or {}).get("snapshot") or {}
        exe["provenance"] = {
            "project": exe["project_id"], "ticket": exe["ticket_id"], "execution": exe["execution_id"],
            "agent": exe["agent"]["id"], "model": exe["model"]["id"], "model_version": exe["model"]["version"],
            "factory_version": self.version_factory, "schema_version": self.version_schemas,
            "prompt_version": (instantane.get("prompt_profile") or {}).get("ref") or self.version_prompt,
            "tools": (env.get("tools") or {}).get("allowed", []),
            "skills": [e.get("ref") for e in instantane.get("skills") or []],
            "mcp": (env.get("mcp") or {}).get("allowed", []), "permissions": (env.get("execution") or {}).get("permissions", {}),
            "branch": exe["isolation"]["branch"], "worktree": exe["isolation"]["worktree"],
            "sandbox": exe["isolation"]["sandbox"], "artifacts": [p["id"] for p in preuves if p["type"] == "ARTIFACT"],
            "tests": [p["id"] for p in preuves if p["type"] == "TEST"], "reviews": [], "approvals": []}
        if instantane:
            # ADR-0022 v2, F-8 : versions RÉELLEMENT résolues au démarrage.
            exe["provenance"].update({
                "ticket_version": (instantane.get("ticket") or {}).get("version"),
                "role_version": (instantane.get("role") or {}).get("ref"),
                "skill_versions": [e.get("ref") for e in instantane.get("skills") or []],
                "tool_versions": {e["ref"].split("@")[0]: e.get("observed") for e in instantane.get("tools") or []},
                "prompt_profile": (instantane.get("prompt_profile") or {}).get("ref"),
                "control_profile": (instantane.get("control_profile") or {}).get("ref"),
                "policy_fingerprint": instantane.get("policy_fingerprint"),
                "context": instantane.get("context") or [], "decisions": instantane.get("decisions") or [],
                "snapshot": instantane})
        exe["evidence"] = preuves
        with open(self._dossier(exe) / "execution.json", "x", encoding="utf-8") as f:
            json.dump(exe, f, ensure_ascii=False, indent=1, default=str)
        return exe

    # ------------------------------------------------------------------ revue humaine (T-FACTORY-018, ADR-0012)
    def diff_complet(self, exe: dict) -> str:
        """Diff complet relu par l'humain : les fichiers de l'agent, et eux seuls — fichiers suivis (opération
        diff_file) + contenu des fichiers nouveaux. L'espace est recomparé à son état après les gates (fichiers et
        empreintes) : s'il a bougé depuis la clôture, quel que soit le fichier, la revue est impossible."""
        projet = self.moteur.projets[exe["project_id"]]
        espace, base = Path(exe["isolation"]["worktree"]), exe["isolation"]["base"]
        vcs = self._vcs(projet)
        if "post_gates" not in exe:
            raise ValueError("exécution sans état relevé après les gates : revue impossible")
        if self._empreintes(espace, self._changements(vcs, espace, base)) != exe["post_gates"]:
            raise ValueError("l'espace isolé a changé depuis la clôture : nouvelle exécution requise")
        nouveaux = self._op(vcs, "changed_untracked", espace)
        nouveaux = {l.strip() for l in nouveaux.sortie.splitlines() if l.strip()}
        morceaux = []
        for f in exe.get("changes") or []:
            if f in nouveaux:
                contenu = (espace / f).read_text(encoding="utf-8", errors="replace")
                morceaux.append(f"=== nouveau fichier : {f}\n" + "".join(f"+{l}\n" for l in contenu.splitlines()))
                continue
            suivi = self._op(vcs, "diff_file", espace, base=base, fichier=f)
            if not suivi.executee or suivi.code != 0:
                raise ValueError(f"diff de {f} impossible : {suivi.motif_refus or suivi.sortie[:200]}")
            morceaux.append(suivi.sortie)
        return "".join(morceaux)

    def _contexte_revue(self, exe: dict, ticket: dict) -> tuple[dict, str]:
        if exe.get("state") != "COMPLETED":
            raise ValueError(f"revue impossible : exécution {exe.get('state')} (COMPLETED exigé)")
        diff = self.diff_complet(exe)
        h = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        ctx = _revue.contexte(ticket, exe, diff, f"{exe['execution_id']}-review-{h[:12]}.diff")
        return ctx, diff

    def demander_revue(self, exe: dict, ticket: dict) -> Path:
        """Prépare la demande de revue (l'agent DEMANDE ; seule la commande humaine décide). Le diff relu est
        déposé dans les preuves, la demande dans audit/approvals/requests/."""
        if ticket.get("state") != "CODE_REVIEW":
            raise ValueError(f"revue impossible : ticket {ticket.get('state')} (CODE_REVIEW exigé)")
        ctx, diff = self._contexte_revue(exe, ticket)
        racine = self.machine.racine_preuves
        racine.mkdir(parents=True, exist_ok=True)
        fichier = racine / ctx["diff_file"]
        if not fichier.exists():
            with open(fichier, "x", encoding="utf-8", newline="\n") as f:
                f.write(diff)
        elif hashlib.sha256(fichier.read_bytes()).hexdigest() != ctx["diff_sha256"]:
            raise ValueError("artefact de diff existant différent : jamais écrasé")
        demande = {"context": ctx, "context_sha256": empreinte(ctx), "roles": list(self.machine.roles_revue),
                   "purpose": f"REVUE DE CODE du ticket {ticket['id']} ({ticket.get('criticality')}) — exécution "
                              f"{exe['execution_id']}, branche {ctx['branch']}. APPROUVE = revue favorable ; "
                              "REFUSE = modifications demandées."}
        dossier = self.racine_factory / "audit" / "approvals" / "requests"
        pol = self.racine_factory / "policies" / "human-approval.yaml"
        quota = (yaml.safe_load(pol.read_text(encoding="utf-8")) or {}).get("max_open_requests") if pol.is_file() else None
        chemin, _ = deposer(dossier, f"AR-REV-{ticket['id']}-{demande['context_sha256'][:8]}.json", demande,
                            self.machine.approbations.repertoire, quota)          # dédoublonnée, sous quota (I8)
        return chemin

    def preuve_revue(self, exe: dict, ticket: dict, ident: str) -> dict:
        """Preuve REVIEW tirée de l'enregistrement humain — seulement si le diff n'a pas changé depuis la revue."""
        verif, e = _revue.verifier(self.machine.approbations, ident, ticket, self.machine.roles_revue)
        if not verif.valide:
            raise ValueError(verif.motif)
        ctx, _ = self._contexte_revue(exe, ticket)
        if empreinte(ctx) != e["context_sha256"]:
            raise ValueError("le code a changé depuis la revue : la revue ne vaut plus (nouvelle revue requise)")
        octets = _revue.octets_enregistrement(e)
        racine = self.machine.racine_preuves
        nom = f"{ident}-review.json"
        if not (racine / nom).exists():
            with open(racine / nom, "xb") as f:
                f.write(octets)
        elif (racine / nom).read_bytes() != octets:
            raise ValueError("artefact de revue existant différent : jamais écrasé")
        return {"id": f"{exe['execution_id']}-review-{ident}", "type": "REVIEW", "source": ident,
                "timestamp": e["created_at"], "command": None, "exit_code": None, "result": "SUCCESS",
                "review_decision": _revue.DECISIONS[e["decision"]], "approval_ref": ident,
                "context_sha256": e["context_sha256"], "artifact_ref": nom,
                "hash": hashlib.sha256(octets).hexdigest(), "generated_by": "humain:commande-d-approbation",
                "verified_by": f"human:{e['approver_role']}", "immutable": True}
