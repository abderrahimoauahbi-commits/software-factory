"""Approbations humaines liées au contexte exact (décision W1, menace T14).

- Le contexte approuvé (projet, ticket, criticité, acteur, action, ressource, commande, outil, MCP, périmètre) est
  réduit à une empreinte SHA-256 canonique. Tout changement de contexte change l'empreinte : l'approbation ne
  vaut plus.
- Une approbation n'est valable que si elle a été créée par la commande humaine (`scripts/factory_approve.py`,
  canal « interactive-console ») ; son enregistrement porte sa propre empreinte : toute modification l'invalide.
- L'agent peut DEMANDER (écrire une demande) et LIRE ; il ne crée ni ne modifie une approbation.

Limite v1 (ADR-0006) : sans règle de refus côté agent sur `audit/approvals/human/` et sur la commande
d'approbation, un agent compromis pourrait forger un enregistrement. W1 est atténuée, pas fermée.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

CANAL = "interactive-console"
TYPE = "HUMAN_APPROVAL"


def canonique(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def empreinte(obj) -> str:
    return hashlib.sha256(canonique(obj).encode("utf-8")).hexdigest()


def contexte(demande: dict, criticite_effective: str) -> dict:
    """Ce qu'une approbation couvre — et rien d'autre. Champs absents = None, jamais omis."""
    ticket = demande.get("ticket") or {}
    ressource = demande.get("resource") or {}
    return {
        "project_id": demande.get("project_id"),
        "ticket_id": ticket.get("id"),
        "ticket_criticality": ticket.get("criticality"),
        "effective_criticality": criticite_effective,
        "actor": {"type": (demande.get("actor") or {}).get("type"), "id": (demande.get("actor") or {}).get("id")},
        "action": demande.get("action"),
        "resource": {k: ressource.get(k) for k in ("kind", "path", "id", "environment")},
        "command": demande.get("command"),
        "tool": demande.get("tool"),
        "mcp": demande.get("mcp"),
        "scope": sorted(((ticket.get("scope") or {}).get("paths") or [])),
    }


def empreinte_enregistrement(enreg: dict) -> str:
    return empreinte({k: v for k, v in enreg.items() if k != "record_sha256"})


@dataclass
class Verification:
    valide: bool
    motif: str


class Magasin:
    """Lecture des approbations humaines. Aucune méthode d'écriture : seule la commande humaine en crée."""

    def __init__(self, repertoire: Path):
        self.repertoire = Path(repertoire)

    def lire(self, ident: str) -> dict | None:
        if not ident or "/" in ident or "\\" in ident or ".." in ident:
            return None
        p = self.repertoire / f"{ident}.json"
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return None

    def trouver(self, ctx: dict, roles_admis: list[str], age_max_h: int) -> Verification:
        """Cherche une approbation valide pour CE contexte exact (habilitations : aucun identifiant transmis)."""
        if not self.repertoire.is_dir():
            return Verification(False, "aucune approbation humaine enregistrée")
        h, dernier = empreinte(ctx), None
        for p in sorted(self.repertoire.glob("HA-*.json")):
            try:
                e = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if e.get("context_sha256") == h:
                dernier = self.verifier(p.stem, ctx, roles_admis, age_max_h)
                if dernier.valide:
                    return dernier
        return dernier or Verification(False, "aucune approbation humaine pour ce contexte")

    def verifier(self, ident: str | None, ctx: dict, roles_admis: list[str], age_max_h: int,
                 maintenant: _dt.datetime | None = None) -> Verification:
        if not ident:
            return Verification(False, "aucune approbation fournie (l'absence de réponse n'est jamais un accord)")
        e = self.lire(ident)
        if e is None:
            return Verification(False, f"approbation {ident} introuvable")
        if e.get("kind") != TYPE or e.get("channel") != CANAL:
            return Verification(False, "enregistrement qui n'émane pas de la commande humaine")
        if e.get("record_sha256") != empreinte_enregistrement(e):
            return Verification(False, "enregistrement modifié après sa création")
        if e.get("decision") != "APPROVED":
            return Verification(False, f"décision humaine : {e.get('decision')}")
        if e.get("context_sha256") != empreinte(ctx):
            return Verification(False, "le contexte a changé depuis l'approbation (ticket, criticité, ressource, action…)")
        if e.get("approver_role") not in roles_admis:
            return Verification(False, f"rôle {e.get('approver_role')!r} non habilité pour ce niveau")
        maintenant = maintenant or _dt.datetime.now(_dt.timezone.utc)
        try:
            cree = _dt.datetime.fromisoformat(e["created_at"])
        except (KeyError, ValueError):
            return Verification(False, "date d'approbation illisible")
        if maintenant - cree > _dt.timedelta(hours=age_max_h) or cree > maintenant + _dt.timedelta(minutes=5):
            return Verification(False, "approbation expirée ou datée du futur")
        return Verification(True, f"approbation {ident} valide ({e.get('approver_role')})")
