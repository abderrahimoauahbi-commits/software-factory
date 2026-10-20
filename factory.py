"""CLI de la Factory (jalon J6, guide d'utilisation §32). À lancer avec « python -P factory.py … » ou « factory … ».

    factory check                              Factory seule : validation, journal, Bootstrap        0 READY · 1 DEGRADED · 2 BLOCKED
    factory validate [FICHIER --type T]        registre + tickets, ou un fichier (T = schéma)         0 VALID · 1 INVALID · 2 REJECTED
    factory bootstrap check [--projet ID] [--sans-rapport]                                         0 READY · 1 DEGRADED · 2 BLOCKED
    factory registry list [TYPE] [--etat E]    fiches du registre                                    0
    factory policy check DEMANDE.json          décision du Policy Engine (lecture seule)             0 ALLOW · 1 APPROVAL_REQUIRED · 2 DENY
    factory state check                        journal chaîné, cycles, états des tickets, portes     0 OK · 2 problème
    factory env list|create|vars|reset|destroy|sql [ENV] …   environnements jetables (évolution E)  0 OK · 1 échec SQL · 2 refus
    factory mission plan|run FICHIER [--espace D] [--reel]   Mission Manager + Meta-Orchestrateur   0 SUCCEEDED · 1 WAITING_HUMAN · 2 autre
    factory pin status|request                 épinglage des artefacts de gouvernance (G1, L1)       0 PINNED · 1 UNPINNED · 2 BLOCKED
    factory key status|init                    clé de service des baux, provisoire L1 (hors D36)     0 présente · 1 absente · 2 refus
    factory project init DOSSIER --id ID --nom NOM   rattacher un projet à la Factory (humain seul)   0 · 2 refus · 3 usage
    factory decide list|show NOM|prune         centre de décision L1 (G2) : demandes et leur état     0 · 3 inconnue
    factory decide request --projet P --id D --question Q [--reponse R]   décision humaine d'un projet (ADR-0022)  0 · 2 refus
    factory eval plan|selftest|run SUITE --agent A [--modele M] | report|request|apply DOSSIER
                                               évaluation des agents (G4, §12.6) ; `run` : humain seul  0 · 2 refus
    factory plan request PLAN.yaml | execute AR-PLAN-….json   exécution humaine d'un plan approuvé (I7)  0 · 1 échec · 2 refus
    factory exception request DEMANDE.json --heures H --usages N --motif M | list | revoke PEX-… --motif M
                                               exceptions de politique (I5) : demande, état, révocation  0 OK · 2 refus
    factory ticket check PROJET [TICKET] [--prompt]   tickets v2 du projet, lus sur place (ADR-0022)  0 READY · 1 BLOCKED · 3 inconnu
    (« --json » : sortie JSON.  3 : erreur d'usage.)

La CLI ne modifie rien, sauf `bootstrap check` sans `--sans-rapport` (rapport dans bootstrap/reports/),
`env` (environnements jetables sous workspaces_root, jamais dans un dépôt de projet), `pin request` et
`exception request` (une DEMANDE d'approbation dans audit/approvals/requests/ : rien n'existe avant l'approbation
humaine), `key init` (clé provisoire L1 créée une fois hors du dépôt, sous workspaces_root), `plan request` (une demande),
`plan execute` (les étapes approuvées, par l'humain seul), `decide prune` (retrait de demandes obsolètes, journalisé),
`project init` (rattachement d'un projet par l'humain seul : manifest, contexte et gardes posés dans le projet, carte
au registre ; jamais d'écrasement),
`eval run|report|request|apply` (campagne réelle par l'humain seul, rapport et demande sous compliance/evidence/,
habilitation écrite au registre seulement après approbation humaine)
et `exception revoke` (un événement de révocation au journal, qui ne fait que restreindre). Dans une session d'agent,
`env reset|destroy|sql` exige un bail (--bail) accordé par le Policy Engine ; `mission run --reel` est refusé.
Elle n'offre aucune commande d'approbation : l'approbation est un acte humain (scripts/factory_approve.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

FACTORY = Path(__file__).resolve().parent
for _p in (FACTORY / "core", FACTORY / "bootstrap"):          # « python -P » : chemins explicites et connus
    sys.path.insert(0, str(_p))

import yaml  # noqa: E402

from noyau import contexte  # noqa: E402
from noyau.audit import Journal  # noqa: E402
from noyau.masquage import masquer  # noqa: E402
from noyau.registre import charger, valider_manifest  # noqa: E402
from noyau.validation import INVALID, REJECTED, VALID  # noqa: E402

CODES_VERDICT = {VALID: 0, INVALID: 1, REJECTED: 2}


def _sortir(donnees, en_json: bool, texte: str) -> None:
    print(masquer(json.dumps(donnees, ensure_ascii=False, indent=1, default=str)) if en_json else masquer(texte))


def _tickets(reg):
    for carte in sorted((FACTORY / "registry" / "projects").glob("*/tickets/*.yaml")):
        yield carte, yaml.safe_load(carte.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------- validate
def cmd_validate(a) -> int:
    reg = charger(FACTORY)
    if a.fichier:
        doc = yaml.safe_load(Path(a.fichier).read_text(encoding="utf-8"))
        if a.type == "project" or (a.type is None and isinstance(doc, dict) and "project" in doc):
            v = valider_manifest(reg, doc, a.fichier)
        else:
            if not a.type:
                print("préciser --type (schéma de l'objet)", file=sys.stderr)
                return 3
            v = reg.validateur.valider(a.type, doc, a.fichier)
        _sortir({"statut": v.statut, "defauts": [d.__dict__ for d in v.defauts], "attentes": v.attentes},
                a.json, f"{v.statut} — {a.fichier}" + "".join(f"\n  {d.code} {d.chemin} : {d.message}" for d in v.defauts))
        return CODES_VERDICT[v.statut]
    verdicts = list(reg.verdicts)
    for chemin, t in _tickets(reg):
        verdicts.append(reg.validateur.valider("ticket", t, chemin.relative_to(FACTORY).as_posix()))
    pire = max((v.statut for v in verdicts), key=lambda s: CODES_VERDICT[s], default=VALID)
    if reg.erreurs:
        pire = max(pire, INVALID, key=lambda s: CODES_VERDICT[s])
    lignes = [f"{len(verdicts)} objets validés : " + ", ".join(
        f"{s} {sum(1 for v in verdicts if v.statut == s)}" for s in (VALID, INVALID, REJECTED))]
    lignes += [f"  {v.statut} {v.source} : {d.code} {d.chemin} {d.message}" for v in verdicts if v.statut != VALID
               for d in v.defauts]
    lignes += [f"  ERREUR {e.fichier} : {e.message}" for e in reg.erreurs if not e.message.startswith(("INVALID", "REJECTED"))]
    _sortir({"statut": pire, "objets": len(verdicts), "erreurs": [e.__dict__ for e in reg.erreurs]}, a.json,
            "\n".join(lignes))
    return CODES_VERDICT[pire]


# ------------------------------------------------------------------------------------------- registry
def cmd_registry(a) -> int:
    reg = charger(FACTORY)
    types = [a.type] if a.type else [t for t in reg.objets]
    if a.type and a.type not in reg.objets:
        print(f"type inconnu : {a.type} (types : {', '.join(reg.objets)})", file=sys.stderr)
        return 3
    lignes, donnees = [], []
    for t in types:
        for ident, o in sorted(reg.objets[t].items()):
            etat = o.get("lifecycle") if isinstance(o.get("lifecycle"), str) else (o.get("lifecycle") or {}).get("state", o.get("status"))
            if a.etat and etat != a.etat:
                continue
            donnees.append({"type": t, "id": ident, "etat": etat, "nom": o.get("name")})
            lignes.append(f"{t:13} {ident:28} {str(etat):14} {o.get('name') or ''}")
    _sortir(donnees, a.json, "\n".join(lignes) + f"\n{len(donnees)} fiche(s)")
    return 0


# ------------------------------------------------------------------------------------------- policy
def cmd_policy(a) -> int:
    demande = json.loads(Path(a.demande).read_text(encoding="utf-8"))
    m, remarques = contexte.moteur(FACTORY)
    d = m.decider(demande)
    explication = d.explication or {}
    _sortir({**d.en_dict(), "remarques_projets": remarques}, a.json,
            f"{d.decision}{' / ' + d.nature if d.nature else ''} ({d.regle}) — " + " ; ".join(d.motifs)
            + (f"\n  règle : {explication.get('nom')} — pourquoi : {explication.get('pourquoi')}" if explication else "")
            + (f"\n  approbation requise : {', '.join(d.approbation_requise['roles'])} — contexte {d.empreinte_contexte[:16]}…"
               if d.approbation_requise else ""))
    return {"ALLOW": 0, "APPROVAL_REQUIRED": 1, "DENY": 2}[d.decision]


# ------------------------------------------------------------------------------------------- state
def cmd_state(a) -> int:
    reg = charger(FACTORY)
    problemes, constats = [], []
    j = Journal(FACTORY / "audit" / "journal.jsonl").verifier()
    constats.append(f"journal : {j.evenements} événements, " + ("chaîne intacte" if j.valide else f"ROMPU ligne {j.rupture + 1}"))
    if not j.valide:
        problemes.append("journal d'audit rompu")
    problemes += [f"{e.fichier} : {e.message}" for e in reg.erreurs if "lifecycles" in e.fichier]
    for chemin, t in _tickets(reg):
        if t.get("state") not in reg.cycles["ticket"]["states"]:
            problemes.append(f"{chemin.name} : état {t.get('state')!r} hors du cycle ticket")
        constats.append(f"ticket {t.get('id')} : {t.get('state')}")
    portes = sorted((FACTORY / "audit" / "gates").glob("HG-*.json")) if (FACTORY / "audit" / "gates").is_dir() else []
    attente = [p.stem for p in portes if not p.stem.endswith(".resolution")
               and not (p.parent / f"{p.stem}.resolution.json").exists()]
    constats.append(f"portes humaines en attente : {len(attente)}")
    from noyau.demandes import ouvertes
    pol = yaml.safe_load((FACTORY / "policies" / "human-approval.yaml").read_text(encoding="utf-8"))
    nb = len(ouvertes(FACTORY / pol["requests"], FACTORY / pol["records"]))
    constats.append(f"demandes de décision ouvertes : {nb} / {pol.get('max_open_requests')} (I8)")
    _sortir({"ok": not problemes, "problemes": problemes, "constats": constats, "portes_en_attente": attente}, a.json,
            "\n".join(constats + [f"PROBLÈME : {p}" for p in problemes]) + ("\nOK" if not problemes else ""))
    return 0 if not problemes else 2


# ------------------------------------------------------------------------------------------- bootstrap / check
def _bootstrap(argv: list[str]) -> int:
    import bootstrap as amorce                              # bootstrap/bootstrap.py
    return amorce.main(argv)


def cmd_bootstrap(a) -> int:
    return _bootstrap(["check"] + (["--projet", a.projet] if a.projet else []) + (["--sans-rapport"] if a.sans_rapport else []))


def cmd_check(a) -> int:
    """État de la FACTORY (pas des projets) : l'aptitude à exécuter des agents est rapportée à part (K5)."""
    from check import controles, rapport
    codes = []
    print("== validate"); codes.append(cmd_validate(argparse.Namespace(fichier=None, type=None, json=False)))
    print("== state check"); codes.append(cmd_state(argparse.Namespace(json=False)))
    print("== bootstrap check (Factory seule)")
    ctx, col = controles.executer(FACTORY, None)
    b = rapport.construire(ctx, col, None, "cli")["bootstrap"]
    codes.append({"READY": 0, "DEGRADED": 1}.get(b["factory_state"], 2))
    for c in col.constats:
        if c.domaine == "factory" and c.statut != "READY":
            print(f"  {c.id} {c.statut} : {c.element} — {c.detail}")
    print("== épinglage (G1, L1)")
    e = etat_epinglage()
    print(f"  {e.statut} : {e.motif}" + "".join(f"\n    {x}" for x in e.ecarts[:20]))
    codes.append(2 if e.statut == "BLOCKED" else 0)          # UNPINNED : attente humaine, signalée sans dégrader
    pire = min(max(codes), 2)
    print(f"FACTORY {['READY', 'DEGRADED', 'BLOCKED'][pire]} — exécution d'agents : {b['phase_readiness']['EXECUTION']}")
    return pire


def _deposer(nom: str, demande: dict) -> tuple[str, bool]:
    """Dépôt d'une demande de décision humaine : dédoublonnée et sous quota (ADR-0017 I8)."""
    from noyau.demandes import deposer
    pol = yaml.safe_load((FACTORY / "policies" / "human-approval.yaml").read_text(encoding="utf-8"))
    chemin, creee = deposer(FACTORY / pol["requests"], nom, demande, FACTORY / pol["records"],
                            pol.get("max_open_requests"))
    return chemin.relative_to(FACTORY).as_posix(), creee


def _epinglage() -> tuple[dict, Path]:
    pol = yaml.safe_load((FACTORY / "policies" / "pinning.yaml").read_text(encoding="utf-8"))
    return pol, FACTORY / "audit" / "approvals" / "human"


def etat_epinglage():
    from noyau import epinglage
    pol, approbations = _epinglage()
    return epinglage.verifier(FACTORY, approbations, pol["roles"])


def cmd_pin(a) -> int:
    """Référence d'épinglage (ADR-0017 G1) : `status` lit ; `request` prépare la demande que l'humain approuvera."""
    from noyau import epinglage
    from noyau.demandes import RefusDemande
    if a.action == "status":
        e = etat_epinglage()
        _sortir(e.__dict__, a.json, "\n".join([f"épinglage : {e.statut} — {e.motif}"] + [f"  {x}" for x in e.ecarts]))
        return {epinglage.PINNED: 0, epinglage.UNPINNED: 1}.get(e.statut, 2)
    pol, _ = _epinglage()
    d = epinglage.demande(FACTORY, pol["patterns"], pol["roles"])
    from noyau import centre_decision as C
    ph = _politique_humaine()
    for e in C.etats(FACTORY / ph["requests"], FACTORY / ph["records"]):     # même état des fichiers : même demande
        if e.type == epinglage.KIND and e.statut == C.OPEN:
            ctx = json.loads((FACTORY / ph["requests"] / e.nom).read_text(encoding="utf-8"))["context"]
            if ctx.get("files") == d["context"]["files"] and ctx.get("patterns") == d["context"]["patterns"]:
                rel = f"{ph['requests'].rstrip('/')}/{e.nom}"
                _sortir({"demande": rel, "existante": True}, a.json,
                        f"demande déjà ouverte pour cet état exact : {rel}\n"
                        f"acte humain, dans votre terminal : python -P scripts/factory_approve.py {rel}")
                return 0
    try:
        rel, _ = _deposer(f"AR-PIN-{d['context_sha256'][:8]}.json", d)
    except RefusDemande as e:
        _sortir({"refus": str(e)}, a.json, f"refus : {e}")
        return 2
    _sortir({"demande": rel, "fichiers": len(d["context"]["files"]), "manifeste": d["context"]["manifest_sha256"]},
            a.json, f"demande préparée : {rel} ({len(d['context']['files'])} fichiers)\n"
                    f"acte humain, dans votre terminal : python -P scripts/factory_approve.py {rel}")
    return 0


# ------------------------------------------------------------------------------------- ticket (ADR-0022)
class InventaireBootstrap:
    """Version observée d'un outil par les adaptateurs du Bootstrap, à la demande (lecture seule, mise en cache) :
    None = absent ; "" = présent, version illisible. Outils du poste ou dépendances déclarées par le projet."""

    def __init__(self, projet_id: str):
        from check.controles import Collecte, preparer
        self.ctx, self.cache = preparer(FACTORY, projet_id, Collecte()), {}

    def get(self, ident: str):
        from check.controles import detecter_outil
        if self.ctx is None:
            return None
        o = detecter_outil(self.ctx, ident, self.cache)
        return (o.get("version") or "") if o.get("present") else None


def sources_tickets(projet_id: str, reg=None, inventaire=None):
    """(Sources, projet) pour résoudre les tickets d'un projet ; lecture seule."""
    from noyau import epinglage, resolution
    reg = reg or charger(FACTORY)
    m, _ = contexte.moteur(FACTORY, reg)
    projet = m.projets.get(projet_id)
    carte = reg.get("projects", projet_id) or {}
    chemin_manifest = Path((carte.get("root") or {}).get("path", "")) / (carte.get("manifest") or {}).get("path", "factory.yaml")
    pol, approbations = _epinglage()
    src = resolution.Sources(
        racine_factory=FACTORY, registre=reg, moteur=m, projet_id=projet_id,
        reference_epinglage=epinglage.derniere_reference(approbations, pol["roles"]),
        statut_epinglage=epinglage.verifier(FACTORY, approbations, pol["roles"]).statut,
        empreinte_politique=contexte.empreinte_politique(FACTORY),
        profils_controle=yaml.safe_load((FACTORY / "policies" / "control-profiles.yaml").read_text(encoding="utf-8")) or {},
        profils_environnement=set((yaml.safe_load((FACTORY / "policies" / "autonomy.yaml").read_text(encoding="utf-8"))
                                   or {}).get("profiles") or {}),
        decisions=etats_des_decisions(projet_id), adr_acceptes=adr_acceptes(), inventaire=inventaire,
        manifest_sha256=resolution._sha(chemin_manifest) if carte else None)
    return src, projet


def adr_acceptes() -> set[str]:
    return {p.name[:8] for p in (FACTORY / "adr" / "accepted").glob("ADR-*.md")}


def etats_des_decisions(projet_id: str) -> dict[str, str]:
    """Décision humaine (HUMAN_DECISION) d'un projet → état de sa demande ; clé : identifiant de la décision et nom
    de la demande. Lecture seule."""
    from noyau import centre_decision as C
    ph = _politique_humaine()
    out = {}
    for e in C.etats(FACTORY / ph["requests"], FACTORY / ph["records"]):
        if e.type != "HUMAN_DECISION":
            continue
        ctx = json.loads((FACTORY / ph["requests"] / e.nom).read_text(encoding="utf-8"))["context"]
        if ctx.get("project_id") == projet_id:
            out[str(ctx.get("decision_id"))] = e.statut
            out[e.nom.removesuffix(".json")] = e.statut
    return out


def cmd_decide_request(a) -> int:
    """Demande de décision humaine d'un projet (ADR-0022 v2, § 2.11) : l'agent DEMANDE ; l'humain décide avec la
    commande d'approbation. Un ticket qui la cite dans dependencies.decisions reste BLOCKED tant qu'elle n'est pas
    approuvée."""
    from noyau.demandes import RefusDemande
    from noyau.approbation import empreinte
    if not (a.projet and a.id and a.question):
        _sortir({"erreur": "--projet, --id et --question sont exigés"}, a.json, "--projet, --id et --question sont exigés")
        return 3
    ph = _politique_humaine()
    ctx = {"kind": "HUMAN_DECISION", "project_id": a.projet, "decision_id": a.id, "question": a.question,
           "proposed_answer": a.reponse}
    d = {"context": ctx, "context_sha256": empreinte(ctx), "roles": list(ph.get("decision_roles") or ["factory_owner"]),
         "purpose": f"DÉCISION {a.id} du projet {a.projet} : {a.question}"
                    + (f" — réponse proposée : {a.reponse}" if a.reponse else "")}
    try:
        rel, creee = _deposer(f"AR-DEC-{a.projet}-{a.id}-{d['context_sha256'][:8]}.json", d)
    except RefusDemande as e:
        _sortir({"refus": str(e)}, a.json, f"refus : {e}")
        return 2
    _sortir({"demande": rel, "creee": creee}, a.json,
            f"demande {'préparée' if creee else 'déjà ouverte'} : {rel}\n"
            f"acte humain, dans votre terminal : python -P scripts/factory_approve.py --ouvertes")
    return 0


def cmd_ticket(a) -> int:
    """`check` : chaque ticket du projet est READY ou BLOCKED, avec ses motifs (ADR-0022 D9). Lecture seule."""
    from collections import Counter
    from noyau import resolution
    src, projet = sources_tickets(a.projet, inventaire=InventaireBootstrap(a.projet))
    if projet is None:
        _sortir({"erreur": f"projet {a.projet!r} inconnu ou sans manifest"}, a.json, f"projet {a.projet!r} inconnu ou sans manifest")
        return 3
    tickets, erreurs = resolution.tickets_du_projet(projet.racine, projet.manifest, resolution._lisible(src, projet))
    if a.ticket and a.ticket not in tickets:
        _sortir({"erreur": f"ticket {a.ticket!r} introuvable", "lecture": erreurs}, a.json,
                "\n".join([f"ticket {a.ticket!r} introuvable"] + erreurs))
        return 3
    choisis = [a.ticket] if a.ticket else sorted(tickets)
    res = [resolution.resoudre(tickets[i][1], tickets[i][0], tickets, src) for i in choisis]
    pret = sum(r.statut == resolution.READY for r in res)
    if a.json:
        _sortir({"project": a.projet, "read_errors": erreurs, "ready": pret, "blocked": len(res) - pret,
                 "tickets": [r.en_dict() | ({"prompt": r.prompt} if a.prompt else {}) for r in res]}, True, "")
    else:
        lignes = [f"projet {a.projet} : {len(res)} ticket(s) — {pret} READY, {len(res) - pret} BLOCKED"] + \
                 [f"  lecture : {e}" for e in erreurs]
        for r in res:
            lignes.append(f"{r.ticket_id}  {r.statut}" + (f"  ({len(r.motifs)} motif(s))" if r.motifs else "")
                          + (f"  — point humain au démarrage : {r.point_humain}" if r.point_humain else ""))
            lignes += [f"    - {m}" for m in r.motifs]
        if len(res) > 1:
            familles = Counter(m[:110] for r in res for m in r.motifs)
            lignes += ["", "motifs les plus fréquents :"] + [f"  {n:3d}  {k}" for k, n in familles.most_common(12)]
        if a.prompt and len(res) == 1:
            lignes += ["", "=== prompt effectif (la consigne de sécurité du runtime est ajoutée après) ===", res[0].prompt,
                       "=== profil d'exécution ===", json.dumps(res[0].profil, ensure_ascii=False, indent=1)]
        _sortir(None, False, "\n".join(lignes))
    return 0 if pret == len(res) and not erreurs else 1


def cmd_exception(a) -> int:
    """Exceptions de politique (ADR-0017 F8, I5) : `request` prépare une DEMANDE que l'humain approuvera ; `list` lit ;
    `revoke` trace une révocation au journal (ne fait que restreindre)."""
    from noyau.demandes import RefusDemande
    from noyau.derogations import RefusException
    m, _ = contexte.moteur(FACTORY)
    gex = m.exceptions
    if a.action == "list":
        actives = gex.actives(m.catalogue)
        _sortir([x.__dict__ for x in actives], a.json,
                "\n".join(f"{x.id} {x.rule} usages {x.uses}/{x.max_uses} jusqu'au {x.expires_at:%Y-%m-%d %H:%M} "
                          f"({x.approval})" for x in actives) + f"\n{len(actives)} exception(s) active(s)")
        return 0
    if a.action == "revoke":
        if not a.cible or not a.motif:
            print("usage : factory exception revoke PEX-… --motif « … »")
            return 3
        gex.revoquer(a.cible, a.motif, {"type": "system", "id": "factory-cli"})
        _sortir({"revoquee": a.cible}, a.json, f"{a.cible} révoquée (journal)")
        return 0
    if not a.cible or not a.motif or a.heures is None or a.usages is None:
        print("usage : factory exception request DEMANDE.json --heures H --usages N --motif « … »")
        return 3
    d = json.loads(Path(a.cible).read_text(encoding="utf-8"))
    dec = m.decider(d)
    if dec.decision != "DENY" or dec.nature != "DENY_BY_POLICY":
        _sortir(dec.en_dict(), a.json, f"aucune exception à demander : {dec.decision} {dec.nature or ''} ({dec.regle})")
        return 2
    try:
        demande = gex.demande(dec.regle, d, a.heures, a.usages, a.motif, m.catalogue)
    except RefusException as e:
        _sortir({"refus": str(e)}, a.json, f"refus : {e}")
        return 2
    try:
        rel, _ = _deposer(f"AR-{demande['context']['exception_id']}.json", demande)
    except RefusDemande as e:
        _sortir({"refus": str(e)}, a.json, f"refus : {e}")
        return 2
    _sortir({"demande": rel, "exception": demande["context"]["exception_id"], "regle": dec.regle}, a.json,
            f"demande préparée : {rel} (lever {dec.regle} pour cette portée exacte)\n"
            f"acte humain, dans votre terminal : python -P scripts/factory_approve.py {rel}")
    return 0


def _politique_humaine() -> dict:
    return yaml.safe_load((FACTORY / "policies" / "human-approval.yaml").read_text(encoding="utf-8"))


def _obsolete(m):
    """Constat d'obsolescence par type de demande (le centre de décision ne décide pas : il montre)."""
    from noyau import epinglage
    from noyau.derogations import controle_i5

    def constat(ctx: dict) -> str | None:
        if ctx.get("kind") == epinglage.KIND:
            if epinglage.releve(FACTORY, ctx.get("patterns") or []) != ctx.get("files"):
                return "les fichiers couverts ont changé depuis la demande"
        if ctx.get("kind") == "POLICY_EXCEPTION":
            ecarts = controle_i5(ctx, m.catalogue)
            if ecarts:
                return "capacité d'exception dépassée au catalogue courant : " + "; ".join(ecarts)
        return None
    return constat


def explication_de(ctx: dict) -> str:
    """Explication en clair engendrée par le code (noyau.explication) ; épinglage comparé à la dernière référence."""
    from noyau import epinglage
    from noyau.explication import expliquer
    reference = None
    if ctx.get("kind") == epinglage.KIND:
        pol, approbations = _epinglage()
        ref = epinglage.derniere_reference(approbations, pol["roles"])
        reference = ref["context"] if ref else None
    pol, _ = _epinglage()
    return expliquer(ctx, reference, pol.get("file_roles"))


def cmd_decide(a) -> int:
    """Centre de décision L1 (G2) : `list` et `show` lisent ; `prune` retire les demandes ouvertes devenues
    obsolètes. Aucune décision n'est prise ici : l'humain décide avec la commande d'approbation."""
    if a.action == "request":
        return cmd_decide_request(a)
    from noyau import centre_decision as C
    from noyau.execution_humaine import executes
    pol = _politique_humaine()
    m, _ = contexte.moteur(FACTORY)
    journal = Journal(FACTORY / "audit" / "journal.jsonl")
    etats = C.etats(FACTORY / pol["requests"], FACTORY / pol["records"], _obsolete(m), executes(journal))
    cmd = "python -P scripts/factory_approve.py " + pol["requests"].rstrip("/")
    if a.action == "list":
        _sortir([e.__dict__ for e in etats], a.json, "\n".join(
            f"{e.statut:9} {e.type:22} {e.nom}" + (f" — {e.motif}" if e.motif else "")
            + (f"\n          décider : {cmd}/{e.nom}" if e.statut == C.OPEN else "") for e in etats)
            + f"\n{sum(e.statut == C.OPEN for e in etats)} ouverte(s), {len(etats)} demande(s)")
        return 0
    if a.action == "show":
        e = next((x for x in etats if x.nom == a.nom), None)
        if e is None:
            print(f"demande inconnue : {a.nom!r}")
            return 3
        d = json.loads((FACTORY / pol["requests"] / e.nom).read_text(encoding="utf-8"))
        texte = explication_de(d.get("context") or {})
        _sortir({"etat": e.__dict__, "explication": texte, "demande": d}, a.json,
                f"{e.nom} — {e.statut} ({e.type})" + (f" — {e.motif}" if e.motif else "")
                + f"\nrôles admis : {', '.join(e.roles)}\n\n{texte}\n\n"
                + f"Texte de l'agent (non vérifié) : {d.get('purpose', '—')}\n"
                + f"Contexte exact (ce que couvre l'empreinte) :\n"
                + json.dumps(d.get("context"), ensure_ascii=False, indent=1)
                + (f"\ndécider : {cmd}/{e.nom}" if e.statut == C.OPEN else f"\ndécision : {e.decision}"))
        return 0
    retirees = [e for e in etats if e.statut == C.OBSOLETE]
    for e in retirees:
        (FACTORY / pol["requests"] / e.nom).unlink()
    if retirees:
        journal.ajouter(actor={"type": "system", "id": "factory-cli"}, project_id="software-factory",
                        action="retrait des demandes de décision obsolètes", result="PRUNED", from_state="OPEN",
                        to_state="OBSOLETE", reasons=[f"{e.nom} : {e.motif}" for e in retirees])
    _sortir([e.nom for e in retirees], a.json, f"{len(retirees)} demande(s) obsolète(s) retirée(s)"
            + "".join(f"\n  {e.nom} — {e.motif}" for e in retirees))
    return 0


def cmd_plan(a) -> int:
    """Exécution humaine (G2, I7) : `request` prépare un plan (l'agent peut) ; `execute` l'exécute (humain seul)."""
    from noyau import execution_humaine as X
    from noyau.demandes import RefusDemande
    pol = _politique_humaine()
    if a.action == "request":
        plan = yaml.safe_load(Path(a.fichier).read_text(encoding="utf-8"))
        try:
            d = X.demande(plan, pol["execution_roles"])
            rel, _ = _deposer(f"AR-{d['context']['plan_id']}.json", d)
        except (X.RefusPlan, RefusDemande) as e:
            _sortir({"refus": str(e)}, a.json, f"refus : {e}")
            return 2
        _sortir({"demande": rel, "plan": d["context"]["plan_id"]}, a.json,
                f"plan préparé : {rel}\n{d['purpose']}\n1) décider : python -P scripts/factory_approve.py {rel}"
                f"\n2) exécuter (humain) : python -P factory.py plan execute {rel}")
        return 0
    if any(os.environ.get(v) for v in pol.get("agent_environment_markers") or []):
        _sortir({"refus": "session d'agent"}, a.json, "refus : l'exécution d'un plan est réservée à l'humain")
        return 2
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("refus : exécution réservée à un humain dans une console interactive")
        return 2
    d = json.loads((FACTORY / a.fichier).read_text(encoding="utf-8"))
    ctx = d.get("context") or {}
    print(d.get("purpose", ""))
    if input(f"Tapez « EXECUTE {ctx.get('plan_id')} » pour lancer ces étapes exactes : ").strip() \
            != f"EXECUTE {ctx.get('plan_id')}":
        print("confirmation non conforme : rien n'est exécuté")
        return 2
    try:
        r = X.executer(d, FACTORY / pol["records"], pol["execution_roles"],
                       float(pol.get("execution_max_age_hours", 24)), Journal(FACTORY / "audit" / "journal.jsonl"),
                       {"type": "human", "id": "console"})
    except X.RefusPlan as e:
        print(f"refus : {e}")
        return 2
    for s in r["etapes"]:
        print(f"--- étape {s['etape']} : code {s['code']}\n{s['sortie']}")
    print(f"{r['plan_id']} : {'SUCCEEDED' if r['succes'] else 'FAILED'}")
    return 0 if r["succes"] else 1


def parseur() -> argparse.ArgumentParser:
    """Grammaire de la CLI (exposée pour vérifier qu'une documentation ne cite aucune commande inventée)."""
    p = argparse.ArgumentParser(prog="factory", description="CLI de la Software Factory")
    p.add_argument("--json", action="store_true")
    s = p.add_subparsers(dest="commande", required=True)
    s.add_parser("check")
    v = s.add_parser("validate"); v.add_argument("fichier", nargs="?"); v.add_argument("--type")
    b = s.add_parser("bootstrap"); b.add_argument("mode", choices=["check"]); b.add_argument("--projet")
    b.add_argument("--sans-rapport", action="store_true")
    r = s.add_parser("registry"); r.add_argument("action", choices=["list"]); r.add_argument("type", nargs="?")
    r.add_argument("--etat")
    po = s.add_parser("policy"); po.add_argument("action", choices=["check"]); po.add_argument("demande")
    st = s.add_parser("state"); st.add_argument("action", choices=["check"])
    e = s.add_parser("env"); e.add_argument("action", choices=["list", "create", "vars", "reset", "destroy", "sql"])
    e.add_argument("env", nargs="?"); e.add_argument("--projet"); e.add_argument("--profil", default="LOCAL_TEST")
    e.add_argument("--execution"); e.add_argument("--base"); e.add_argument("--id")
    e.add_argument("--sql"); e.add_argument("--fichier")
    e.add_argument("--bail"); e.add_argument("--agent"); e.add_argument("--ticket")
    m = s.add_parser("mission"); m.add_argument("action", choices=["plan", "run"]); m.add_argument("fichier")
    m.add_argument("--espace"); m.add_argument("--reel", action="store_true")
    pi = s.add_parser("pin"); pi.add_argument("action", choices=["status", "request"])
    k = s.add_parser("key"); k.add_argument("action", choices=["status", "init"])
    de = s.add_parser("decide"); de.add_argument("action", choices=["list", "show", "prune", "request"])
    de.add_argument("nom", nargs="?"); de.add_argument("--projet"); de.add_argument("--id"); de.add_argument("--question")
    de.add_argument("--reponse")
    pl = s.add_parser("plan"); pl.add_argument("action", choices=["request", "execute"]); pl.add_argument("fichier")
    pj = s.add_parser("project"); pj.add_argument("action", choices=["init"]); pj.add_argument("dossier")
    pj.add_argument("--id"); pj.add_argument("--nom")
    ev = s.add_parser("eval"); ev.add_argument("action", choices=["plan", "selftest", "run", "report", "request", "apply"])
    ev.add_argument("cible"); ev.add_argument("--agent"); ev.add_argument("--modele")
    ex = s.add_parser("exception"); ex.add_argument("action", choices=["request", "list", "revoke"])
    ex.add_argument("cible", nargs="?"); ex.add_argument("--heures", type=float); ex.add_argument("--usages", type=int)
    ex.add_argument("--motif")
    ti = s.add_parser("ticket"); ti.add_argument("action", choices=["check"]); ti.add_argument("projet")
    ti.add_argument("ticket", nargs="?"); ti.add_argument("--prompt", action="store_true")
    return p


def _evolution(nom: str):
    def lancer(a) -> int:
        from fournisseurs import cablage                     # core/fournisseurs/cablage.py (évolution E)
        return getattr(cablage, nom)(a, lambda donnees, texte: _sortir(donnees, a.json, texte))
    return lancer


def _projet(a) -> int:
    from fournisseurs import projet_init                            # core/fournisseurs (rattachement, ADR-0001)
    return projet_init.cmd_project(a, lambda donnees, texte: _sortir(donnees, a.json, texte))


def _evaluation(a) -> int:
    from fournisseurs import evaluation_campagne                   # core/fournisseurs (G4, Playbook §12.6)
    return evaluation_campagne.cmd_eval(a, lambda donnees, texte: _sortir(donnees, a.json, texte))


def main(argv=None) -> int:
    p = parseur()
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 3 if e.code else 0
    return {"check": cmd_check, "validate": cmd_validate, "bootstrap": cmd_bootstrap, "registry": cmd_registry,
            "policy": cmd_policy, "state": cmd_state, "env": _evolution("cmd_env"),
            "mission": _evolution("cmd_mission"), "pin": cmd_pin, "exception": cmd_exception,
            "key": _evolution("cmd_key"), "decide": cmd_decide, "plan": cmd_plan, "eval": _evaluation,
            "project": _projet, "ticket": cmd_ticket}[a.commande](a)


if __name__ == "__main__":
    sys.exit(main())
