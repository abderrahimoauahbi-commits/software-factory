"""Portes humaines (Executable Schemas §32) : PENDING tant qu'aucune approbation humaine valide n'existe.

L'agent ouvre une porte (et la demande d'approbation qui va avec) ; seule une approbation créée par la commande
humaine et liée au même contexte la résout. Aucune approbation automatique, aucun héritage entre tickets,
projets ou contextes ; l'absence de réponse laisse la porte PENDING jusqu'à expiration (EXPIRED).
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from .approbation import canonique, empreinte


class Portes:
    def __init__(self, repertoire: Path, demandes: Path, duree_h: int = 72):
        self.repertoire, self.demandes, self.duree_h = Path(repertoire), Path(demandes), duree_h

    def _chemin(self, ident: str) -> Path:
        return self.repertoire / f"{ident}.json"

    def ouvrir(self, contexte: dict, roles: list[str], demandeur: dict) -> dict:
        h = empreinte(contexte)
        ident = f"HG-{h[:16]}"
        existante = self.lire(ident)
        if existante:
            return existante                               # même contexte : même porte, jamais une nouvelle approbation
        maintenant = _dt.datetime.now(_dt.timezone.utc)
        porte = {"id": ident, "type": "TRANSITION", "context": contexte, "context_sha256": h, "required_roles": roles,
                 "requested_by": demandeur, "status": "PENDING", "created_at": maintenant.isoformat(timespec="seconds"),
                 "expires_at": (maintenant + _dt.timedelta(hours=self.duree_h)).isoformat(timespec="seconds"),
                 "decided_at": None, "approval_ref": None}
        self.repertoire.mkdir(parents=True, exist_ok=True)
        with open(self._chemin(ident), "x", encoding="utf-8") as f:
            f.write(canonique(porte))
        # Demande lisible par la commande humaine (scripts/factory_approve.py).
        self.demandes.mkdir(parents=True, exist_ok=True)
        demande = self.demandes / f"AR-{ident}.json"
        if not demande.exists():
            demande.write_text(canonique({"context": contexte, "context_sha256": h, "roles": roles,
                                          "human_gate": ident}), encoding="utf-8")
        return porte

    def lire(self, ident: str) -> dict | None:
        p = self._chemin(ident)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def statut(self, ident: str, maintenant: _dt.datetime | None = None) -> str:
        porte = self.lire(ident)
        if porte is None:
            return "UNKNOWN"
        if porte["status"] != "PENDING":
            return porte["status"]
        maintenant = maintenant or _dt.datetime.now(_dt.timezone.utc)
        return "EXPIRED" if maintenant > _dt.datetime.fromisoformat(porte["expires_at"]) else "PENDING"

    def resoudre(self, ident: str, approval_id: str) -> None:
        """Appelé seulement après vérification de l'approbation par le moteur d'états. Trace la résolution
        dans un fichier compagnon, sans réécrire la porte (ajout seul)."""
        trace = self.repertoire / f"{ident}.resolution.json"
        if not trace.exists():
            trace.write_text(canonique({"gate": ident, "status": "APPROVED", "approval_ref": approval_id,
                                        "decided_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")}),
                             encoding="utf-8")

    def resolue(self, ident: str) -> bool:
        return (self.repertoire / f"{ident}.resolution.json").is_file()
