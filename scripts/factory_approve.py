"""Approbation humaine (décision W1) — À LANCER PAR L'HUMAIN, dans son propre terminal.

    python -P scripts/factory_approve.py audit/approvals/requests/<demande>.json
    python -P scripts/factory_approve.py --ouvertes        # toutes les demandes ouvertes, l'une après l'autre

Chaque demande est d'abord expliquée en clair (ce que vous approuvez, ce que cela permet, ce que cela ne permet pas,
comment revenir en arrière), texte engendré à partir des faits de la demande et non du récit de l'agent.

La commande affiche le contexte exact à approuver et son empreinte, demande le rôle de l'approbateur, puis exige
de taper les 8 premiers caractères de l'empreinte suivis de APPROUVE (ou REFUSE). L'enregistrement est créé en
écriture exclusive dans audit/approvals/human/ et porte sa propre empreinte : toute modification l'invalide.

Refus si l'entrée ou la sortie ne sont pas une console interactive, ou si l'environnement est celui d'un agent.
Ces gardes sont PROCÉDURALES, pas une frontière de sécurité : la fermeture de W1 exige des règles de refus côté
agent sur ce script et sur audit/approvals/human/ (ADR-0006).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY / "core"))

import yaml  # noqa: E402

from noyau.approbation import CANAL, TYPE, canonique, empreinte, empreinte_enregistrement  # noqa: E402

# Variables posées par un runtime d'agent connu : leur présence suffit à refuser (liste dans la politique).
POLITIQUE = FACTORY / "policies" / "human-approval.yaml"


def _explication(ctx: dict) -> str:
    """Ce que vous approuvez, en clair (noyau.explication, épinglé) : faits du contexte, jamais le récit de l'agent."""
    try:
        from noyau.explication import expliquer
        reference = None
        pol = yaml.safe_load((FACTORY / "policies" / "pinning.yaml").read_text(encoding="utf-8"))
        if ctx.get("kind") == "PIN_REFERENCE":
            from noyau import epinglage
            ref = epinglage.derniere_reference(FACTORY / "audit" / "approvals" / "human", pol["roles"])
            reference = ref["context"] if ref else None
        return expliquer(ctx, reference, pol.get("file_roles"))
    except Exception as e:                    # l'explication n'est qu'une aide : son absence n'empêche pas de lire
        return f"(explication indisponible : {type(e).__name__} — lisez le contexte exact ci-dessous)"


def refuser(message: str) -> int:
    print(f"REFUS : {message}", file=sys.stderr)
    return 2


def diff_de_revue(ctx: dict, artefacts: Path) -> tuple[Path | None, str | None]:
    """Revue de code (T-FACTORY-018) : l'humain relit le diff exact couvert par l'empreinte, rien d'autre."""
    nom = str(ctx.get("diff_file") or "")
    if not nom or "/" in nom or "\\" in nom or ".." in nom:
        return None, "demande de revue sans fichier de diff valide"
    diff = artefacts / nom
    if not diff.is_file() or hashlib.sha256(diff.read_bytes()).hexdigest() != ctx.get("diff_sha256"):
        return None, "diff introuvable ou modifié depuis la demande : rien à relire"
    return diff, None


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    with open(POLITIQUE, encoding="utf-8") as f:
        politique = yaml.safe_load(f)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return refuser("commande réservée à un humain dans une console interactive (entrée et sortie)")
    marqueurs = [v for v in politique.get("agent_environment_markers", []) if v in os.environ]
    if marqueurs:
        return refuser("environnement d'agent détecté : l'approbation doit venir du terminal de l'humain")
    if argv == ["--ouvertes"]:
        return traiter_ouvertes(politique)
    if len(argv) != 1:
        return refuser("usage : factory_approve.py <demande.json>  |  factory_approve.py --ouvertes")
    return traiter(Path(argv[0]))


def traiter_ouvertes(politique: dict) -> int:
    """Toutes les demandes sans décision, l'une après l'autre : même cérémonie pour chacune (explication, contexte,
    empreinte à retaper), rôle demandé une fois. « PASSER » laisse une demande ouverte sans rien enregistrer."""
    from noyau.centre_decision import OPEN, etats
    ouvertes = [e for e in etats(FACTORY / politique["requests"], FACTORY / politique["records"]) if e.statut == OPEN]
    if not ouvertes:
        print("Aucune demande ouverte.")
        return 0
    print(f"{len(ouvertes)} demande(s) ouverte(s) : " + ", ".join(e.nom for e in ouvertes))
    role = input("Votre rôle (vérifié pour chaque demande) : ").strip()
    bilan = []
    for i, e in enumerate(ouvertes, 1):
        print(f"\n######## Demande {i}/{len(ouvertes)} : {e.nom}")
        code = traiter(FACTORY / politique["requests"] / e.nom, role=role, lot=True)
        bilan.append(f"{e.nom} : {'enregistrée' if code == 0 else 'passée' if code == 1 else 'refus de la commande'}")
    print("\nBilan :\n  " + "\n  ".join(bilan))
    return 0


def traiter(chemin: Path, role: str | None = None, lot: bool = False) -> int:
    """Une demande : explication en clair, contexte exact, empreinte à retaper. → 0 enregistrée, 1 passée, 2 refus."""
    demande = json.loads(Path(chemin).read_text(encoding="utf-8"))
    ctx = demande.get("context")
    if not isinstance(ctx, dict) or demande.get("context_sha256") != empreinte(ctx):
        return refuser("demande incohérente : l'empreinte ne correspond pas au contexte")
    h = demande["context_sha256"]
    if ctx.get("kind") == "CODE_REVIEW":
        diff, motif = diff_de_revue(ctx, FACTORY / "compliance" / "evidence" / "artifacts")
        if motif:
            return refuser(motif)
        print("=" * 72)
        print(f"REVUE DE CODE — ticket {ctx.get('ticket_id')} ({ctx.get('ticket_criticality')}), "
              f"auteur {ctx.get('author')}, branche {ctx.get('branch')}")
        print("Fichiers : " + ", ".join(ctx.get("changes") or []))
        if ctx.get("extraction_unchanged"):
            print("Écartés (différences d'extraction, contenu inchangé depuis la création de l'espace — ADR-0013) : "
                  + ", ".join(ctx["extraction_unchanged"]))
        if ctx.get("gate_outputs"):
            print("Produits par les gates (à ne pas commiter) : " + ", ".join(ctx["gate_outputs"]))
        print("Preuves : " + ", ".join(f"{p['id']} {p['result']}" for p in ctx.get("evidence") or []))
        print("-" * 72)
        print(diff.read_text(encoding="utf-8"))
        print("APPROUVE = revue favorable ; REFUSE = modifications demandées.")
    print("=" * 72)
    print(_explication(ctx))                                  # en clair, engendré à partir du contexte haché
    print("-" * 72)
    print("APPROBATION HUMAINE — contexte exact couvert par cette approbation :")
    print(json.dumps(ctx, ensure_ascii=False, indent=2))
    print(f"Empreinte du contexte : {h}")
    print(f"Rôles habilités : {', '.join(demande.get('roles', []))}")
    print("=" * 72)
    role = role if role is not None else input("Votre rôle : ").strip()
    if role not in demande.get("roles", []):
        return refuser(f"rôle {role!r} non habilité pour cette demande")
    invite = f"Tapez « {h[:8]} APPROUVE » pour approuver, ou « {h[:8]} REFUSE »"
    reponse = input(invite + (" (ou PASSER pour la laisser ouverte)" if lot else "") + " : ").strip()
    if lot and reponse.upper() in ("PASSER", ""):
        print("Passée : rien n'est enregistré, la demande reste ouverte.")
        return 1
    if reponse not in (f"{h[:8]} APPROUVE", f"{h[:8]} REFUSE"):
        return refuser("confirmation non conforme : rien n'est enregistré (l'absence de réponse n'est pas un accord)")
    maintenant = _dt.datetime.now(_dt.timezone.utc)
    enreg = {"kind": TYPE, "channel": CANAL, "id": f"HA-{maintenant:%Y%m%dT%H%M%S}-{h[:8]}",
             "decision": "APPROVED" if reponse.endswith("APPROUVE") else "REJECTED", "approver_role": role,
             "context": ctx, "context_sha256": h, "request": Path(chemin).name,
             "created_at": maintenant.isoformat(timespec="seconds")}
    enreg["record_sha256"] = empreinte_enregistrement(enreg)
    dossier = FACTORY / "audit" / "approvals" / "human"
    dossier.mkdir(parents=True, exist_ok=True)
    with open(dossier / f"{enreg['id']}.json", "x", encoding="utf-8") as f:   # jamais d'écrasement
        f.write(canonique(enreg))
    print(f"Enregistré : {enreg['id']} — {enreg['decision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
