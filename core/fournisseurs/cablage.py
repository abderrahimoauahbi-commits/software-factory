"""Câblage de l'évolution E (Master Evolution Prompt v4) : assemble les composants génériques du cœur avec les
adaptateurs concrets, à partir des données du dépôt. Utilisé par la CLI (`factory env …`, `factory mission …`).

Racines : `workspaces_root` de policies/execution.yaml ; environnements et état sous cette racine
(orchestrator/environnements.yaml : roots). Rien n'est écrit dans le dépôt d'un projet.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import sys
from pathlib import Path

import yaml

CORE = Path(__file__).resolve().parents[1]
FACTORY = CORE.parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from fournisseurs.postgresql_jetable import PostgresJetable  # noqa: E402
from fournisseurs.runtime_claude_code import RuntimeClaudeCode  # noqa: E402
from noyau import contexte, epinglage  # noqa: E402
from noyau.audit import Journal  # noqa: E402
from noyau.baux import GestionnaireCapacites, RefusBail  # noqa: E402
from noyau.environnements import Gestionnaire  # noqa: E402
from noyau.mission import analyser  # noqa: E402
from noyau.modeles import choisir as choisir_modele  # noqa: E402
from noyau.orchestrateur import ALLOW, LECTURE, MetaOrchestrateur  # noqa: E402
from noyau.organisation import Organisation  # noqa: E402
from noyau.perimetre import Perimetre, Racine, canonique  # noqa: E402
from noyau.ressources import Registre  # noqa: E402
from noyau.runtime import RuntimeGates, Runtimes  # noqa: E402
from noyau.superviseur import Budget, Superviseur  # noqa: E402


def _y(rel: str) -> dict:
    return yaml.safe_load((FACTORY / rel).read_text(encoding="utf-8")) or {}


def racines() -> dict[str, Path]:
    base = Path(_y("policies/execution.yaml")["workspaces_root"])
    r = _y("orchestrator/environnements.yaml")["roots"]
    return {"base": base, "environnements": base / r["environments"], "etat": base / r["state"]}


def dans_une_session_d_agent() -> bool:
    """Marqueurs d'environnement d'un runtime d'agent (policies/human-approval.yaml) : présence = agent."""
    marqueurs = _y("policies/human-approval.yaml").get("agent_environment_markers") or []
    return any(os.environ.get(m) for m in marqueurs)


def fournisseurs() -> dict:
    pg = PostgresJetable()
    return {"par_genre": {pg.kind: pg}, "par_id": {pg.id: pg}}


def journal() -> Journal:
    return Journal(FACTORY / "audit" / "journal.jsonl")


def ressources() -> Registre:
    r = racines()
    return Registre(r["etat"] / "resources", fournisseurs()["par_id"], r["environnements"])


def environnements(avec_journal: bool = True) -> Gestionnaire:
    cycles = _y("core/schemas/lifecycles.yaml")
    return Gestionnaire(racines()["environnements"], _y("orchestrator/environnements.yaml")["profiles"],
                        cycles["environment"], ressources(), fournisseurs()["par_genre"],
                        journal() if avec_journal else None,
                        quotas=_y("orchestrator/environnements.yaml").get("quotas"))


def recette_base(projet: str) -> dict | None:
    """Socle de la base de test d'un projet (carte du registre : test_database). Chaque fichier est une LECTURE
    soumise au Policy Engine (acteur système) : un chemin sensible ou hors des chemins lisibles est refusé."""
    carte = _y(f"registry/projects/{projet}/project.yaml")
    recette = carte.get("test_database")
    if not recette:
        return None
    moteur, _ = contexte.moteur(FACTORY)
    racine = Path(carte["root"]["path"])
    fichiers = []
    for rel in recette.get("files") or []:
        d = moteur.decider({"actor": {"type": "system", "id": "environment-manager"}, "action": "read",
                            "project_id": projet, "resource": {"path": rel}})
        if d.decision != ALLOW:
            raise PermissionError(f"socle {rel} : {d.decision} {d.regle} — {'; '.join(d.motifs)}")
        fichiers.append(str(racine / rel))
    return {"roles": list(recette.get("roles") or []), "files": fichiers,
            "classification": recette.get("classification", "INTERNAL")}


def etat_epinglage() -> epinglage.Etat:
    pol = _y("policies/pinning.yaml")
    return epinglage.verifier(FACTORY, FACTORY / "audit" / "approvals" / "human", pol["roles"])


FICHIER_CLE = "service-key.l1"


def chemin_cle() -> Path:
    return racines()["etat"] / FICHIER_CLE


def cle_de_service() -> bytes | None:
    """Clé d'authentification des baux. Clé PROVISOIRE L1, hors cérémonie D36 (ADR-0017) : fichier hors du dépôt,
    à côté des baux, lisible par le compte (R2 : l'altération d'un bail est détectée ; un processus qui lit la clé
    peut en forger un). Absente ou illisible = aucun bail émis."""
    p = chemin_cle()
    try:
        cle = bytes.fromhex(p.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None
    return cle if len(cle) >= 32 else None


def identifiant_cle(cle: bytes) -> str:
    """Identifiant public d'une clé (rotation, journal) : jamais la clé elle-même."""
    return "L1-" + hashlib.sha256(b"factory-service-key-id\0" + cle).hexdigest()[:12]


def cmd_key(a, sortir) -> int:
    """`status` : présence et identifiant de la clé ; `init` : création unique (écriture exclusive), journalisée."""
    p = chemin_cle()
    if a.action == "status":
        cle = cle_de_service()
        sortir({"cle": identifiant_cle(cle) if cle else None, "chemin": str(p)},
               f"clé de service : {identifiant_cle(cle) + ' (provisoire L1, hors D36)' if cle else 'ABSENTE — aucun bail émis'}")
        return 0 if cle else 1
    if p.exists():
        sortir({"refus": "clé déjà présente"}, f"refus : une clé existe déjà ({p}) ; une rotation est un acte à part")
        return 2
    cle = secrets.token_bytes(32)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "x", encoding="ascii") as f:                          # jamais d'écrasement
        f.write(cle.hex())
    journal().ajouter(actor={"type": "system", "id": "factory-cli"}, project_id="software-factory",
                      action="création de la clé de service provisoire L1 (hors cérémonie D36)", result="CREATED",
                      from_state=None, to_state="ACTIVE", key_id=identifiant_cle(cle),
                      reasons=["fichier hors du dépôt, lisible par le compte (ADR-0017 R2)",
                               "la cérémonie D36 reste à tenir pour une clé détenue par le service (L2)"])
    sortir({"cle": identifiant_cle(cle), "chemin": str(p)}, f"clé créée : {identifiant_cle(cle)} ({p})")
    return 0


def capacites() -> GestionnaireCapacites:
    moteur, _ = contexte.moteur(FACTORY, ressources=ressources())       # identité : registre des ressources
    cycles = _y("core/schemas/lifecycles.yaml")
    return GestionnaireCapacites(racines()["etat"] / "leases", moteur, cycles["capability_lease"],
                                 _y("orchestrator/supervision.yaml")["budgets"]["lease"], journal(),
                                 cle=cle_de_service(), empreinte_politique=contexte.empreinte_politique(FACTORY))


# ------------------------------------------------------------------------------------------- mission
def orchestrateur(mission: dict, espace: str | None = None, a_blanc: bool = True, journal_mission: Path | None = None):
    """Méta-orchestrateur d'une mission réelle : runtime de gates du manifest + runtime d'agent de code."""
    moteur, _ = contexte.moteur(FACTORY)
    projet = moteur.projets.get(mission.get("project_id"))
    if projet is None:
        raise ValueError(f"projet {mission.get('project_id')!r} non enregistré")
    gates = ((projet.manifest.get("quality") or {}).get("gates") or {})
    plan = analyser(mission, _y("orchestrator/domaines.yaml"), _y("orchestrator/organisation.yaml"), gates)
    sup_donnees = _y("orchestrator/supervision.yaml")
    reg = __import__("noyau.registre", fromlist=["charger"]).charger(FACTORY)
    m_agents = projet.manifest.get("agents") or {}
    autorises = set(m_agents.get("required", [])) | set(m_agents.get("allowed", []))
    budget = Budget.depuis(mission.get("budget"), Budget.depuis(sup_donnees["budgets"]["mission"]))
    sup = Superviseur(budget, sup_donnees["recovery"], sup_donnees["recoverable_failures"],
                      seuil_boucle=int(sup_donnees.get("loop_threshold", 3)))
    orga = Organisation(_y("orchestrator/organisation.yaml"), reg.objets["agents"], autorises, budget.max_agents)
    perim = Perimetre({"WORKSPACE": Racine("WORKSPACE", canonique(espace or projet.racine))}, [], [], [], [])
    commandes = [str(g["command"]) for g in gates.values() if (g or {}).get("command")]
    runtimes = Runtimes([RuntimeGates(gates, perim, FACTORY / "compliance" / "evidence" / "artifacts"),
                         RuntimeClaudeCode(commandes_permises=commandes, a_blanc=a_blanc,
                                           baux=racines()["etat"] / "leases")])
    gc = capacites()

    def autoriser(tache, membre):
        if set(tache.capacites) <= LECTURE or (tache.entree or {}).get("gate"):
            return {"decision": ALLOW, "motif": "lecture ou gate de la Factory"}
        try:
            b, s = gc.demander({"type": "agent", "id": tache.role}, plan.projet_id,
                               {"id": f"{plan.mission_id}/{tache.id}", "project_id": plan.projet_id,
                                "criticality": "C1"},
                               {"id": f"{plan.mission_id}/{tache.id}", "worktree": espace}, None, tache.capacites,
                               list(tache.ressources) or ["workspace"])
        except RefusBail as e:                                           # refus par défaut : aucun bail
            return {"decision": "DENY", "motif": str(e), "bail": None}
        return {"decision": s["decision"], "motif": "; ".join(s["reasons"]) or "bail accordé", "bail": s["lease"]}

    cycles = _y("core/schemas/lifecycles.yaml")
    j = Journal(journal_mission) if journal_mission else None
    return MetaOrchestrateur(plan, cycles, sup_donnees["human_boundaries"], orga, sup, runtimes, autoriser=autoriser,
                             choisir_modele=lambda t, ex: choisir_modele(reg.objets["models"], t, ex),
                             liberer=lambda t: gc.liberer(f"{plan.mission_id}/{t.id}"), journal=j, espace=espace)


# ------------------------------------------------------------------------------------------- commandes CLI
_COMMENTAIRES_SQL = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_SQL_DESTRUCTIF = re.compile(r"\b(TRUNCATE|DROP\s+(TABLE|SCHEMA|DATABASE|OWNED))\b", re.I)


def _classer_sql(sql: str | None, fichier: str | None) -> str:
    """Capacité exigée par une opération SQL (§5). Un fichier est une migration, SAUF s'il contient, hors
    commentaires, une destruction de données (TRUNCATE, DROP TABLE|SCHEMA|DATABASE|OWNED) : il exige alors
    DATABASE_DROP. Un fichier illisible exige la capacité la plus haute (refus par défaut)."""
    if fichier:
        try:
            texte = Path(fichier).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "DATABASE_DROP"
        return "DATABASE_DROP" if _SQL_DESTRUCTIF.search(_COMMENTAIRES_SQL.sub(" ", texte)) else "DATABASE_MIGRATION"
    s = (sql or "").upper()
    if any(m in s for m in ("DROP ", "TRUNCATE ")):
        return "DATABASE_DROP"
    if any(m in s for m in ("CREATE ", "ALTER ")):
        return "DATABASE_SCHEMA_CHANGE"
    if any(m in s for m in ("INSERT ", "UPDATE ", "DELETE ", "COPY ")):
        return "DATABASE_WRITE"
    return "DATABASE_READ"


def _sous_bail(a, capacite: str, ressource: str) -> tuple[bool, str]:
    if not a.bail:
        return False, "session d'agent : opération permise seulement sous bail (--bail), via le Policy Engine"
    d = capacites().autoriser_operation(a.bail, {"type": "agent", "id": a.agent}, a.projet,
                                        {"id": a.ticket, "project_id": a.projet, "criticality": "C1"},
                                        {"id": a.execution}, capacite, ressource)
    return d["decision"] == "ALLOW", "; ".join(d.get("reasons") or [])


def cmd_env(a, sortir) -> int:
    agent = dans_une_session_d_agent()
    g = environnements()
    if a.action == "list":
        lignes, donnees = [], []
        for p in sorted(g.racine.glob("*/environment.json")) if g.racine.is_dir() else []:
            e = g.obtenir(p.parent.name)
            mo = round(g.occupation_mo(e.id), 1)
            donnees.append({"id": e.id, "projet": e.project_id, "profil": e.profile, "etat": e.state, "mo": mo})
            lignes.append(f"{e.id:28} {e.project_id:16} {e.profile:12} {e.state:12} {mo:>8} Mo")
        depasse = g.depassements()
        sortir({"environnements": donnees, "depassements": depasse},
               "\n".join(lignes + [f"DÉPASSEMENT : {x}" for x in depasse]) + f"\n{len(donnees)} environnement(s)")
        return 0
    if a.action == "create":
        ident = a.id or f"{a.projet}-{(a.execution or 'manuel').lower()}".replace("_", "-")[:60]
        socle = recette_base(a.projet)
        spec = {"kind": "database", "name": "db", "database": a.base or f"{a.projet}_test".replace("-", "_")}
        if socle:
            spec.update(baseline=socle, classification=socle["classification"])
        e = g.creer(ident, a.projet, a.execution or "MANUEL", a.profil, [spec])
        sortir({"id": e.id, "etat": e.state, "ressources": e.resources, "variables": g.variables(e.id)},
               f"{e.id} {e.state} — " + ", ".join(e.resources))
        return 0
    if a.action == "vars":
        sortir(g.variables(a.env), "\n".join(f"{k}={v}" for k, v in g.variables(a.env).items()))
        return 0
    r = g.ressource(a.env, "database")
    if a.action == "sql":
        capacite = _classer_sql(a.sql, a.fichier)
    else:
        capacite = {"reset": "DATABASE_RESET", "destroy": "DATABASE_DROP"}[a.action]
    if agent:
        ok, motif = _sous_bail(a, capacite, r.id)
        if not ok:
            sortir({"decision": "DENY", "capacite": capacite, "motif": motif}, f"DENY {capacite} : {motif}")
            return 2
    if a.action == "reset":
        g.reinitialiser(a.env, "database")
        sortir({"id": a.env, "reset": True}, f"{a.env} réinitialisé")
        return 0
    if a.action == "destroy":
        b = g.detruire(a.env, "commande destroy")
        sortir(b, f"{a.env} : {'détruit' if b['destroyed'] else 'NON détruit ' + str(b.get('refused'))}")
        return 0 if b["destroyed"] else 2
    ok, motif = g.ressources.verifier_identite(r.id)
    if not ok:
        sortir({"decision": "DENY", "motif": motif}, f"DENY : {motif}")
        return 2
    x = fournisseurs()["par_genre"]["database"].executer_sql(r, a.sql, a.fichier)
    sortir({"code": x.returncode, "sortie": x.stdout[-4000:], "erreur": x.stderr[-2000:], "capacite": capacite},
           (x.stdout + x.stderr)[-4000:])
    return 0 if x.returncode == 0 else 1


def cmd_mission(a, sortir) -> int:
    mission = yaml.safe_load(Path(a.fichier).read_text(encoding="utf-8"))
    o = orchestrateur(mission, a.espace, a_blanc=not a.reel)
    if a.action == "plan":
        p = o.plan
        sortir({"domaines": p.domaines, "metier": p.domaines_metier, "qualite": p.plan_qualite,
                "securite": p.plan_securite, "taches": [{"id": t.id, "role": t.role, "deps": t.dependances,
                                                         "capacites": t.capacites} for t in p.taches]},
               "\n".join([f"domaines : {', '.join(p.domaines)} ; métier : {', '.join(p.domaines_metier) or '—'}",
                          f"qualité : {', '.join(map(str, p.plan_qualite)) or '—'} ; critiques : {', '.join(p.plan_securite)}"]
                         + [f"  {t.id:32} {t.role:14} ← {', '.join(t.dependances) or '—'}" for t in p.taches]))
        return 0
    if a.reel and dans_une_session_d_agent():
        sortir({"refus": "un agent ne lance pas d'agents réels"}, "refus : lancement réel réservé à l'opérateur humain")
        return 2
    e = etat_epinglage()
    if e.statut == epinglage.BLOCKED:                    # artefact de gouvernance modifié sans nouvelle référence
        sortir({"refus": e.motif, "ecarts": e.ecarts}, f"refus : épinglage BLOCKED — {e.motif}\n  "
                                                        + "\n  ".join(e.ecarts))
        return 2
    b = o.executer()
    sortir(b.__dict__, f"mission {b.mission_id} : {b.etat}\n  tâches : {b.taches}\n  bloquées : {b.bloquees}\n"
                       f"  en attente humaine : {b.en_attente_humaine}\n  métriques : {b.metriques}")
    return {"SUCCEEDED": 0, "WAITING_HUMAN": 1}.get(b.etat, 2)
