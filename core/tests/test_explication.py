"""Explication en clair des demandes de décision (ADR-0017 R12) : engendrée à partir des faits, jamais du récit de
l'agent ; affichée par le centre de décision et par la commande humaine (chargée ici sans être exécutée)."""
import importlib.util
import unittest

import yaml

from tests.aide import FACTORY

from noyau.explication import expliquer, role_fichier

ROLES = yaml.safe_load((FACTORY / "policies" / "pinning.yaml").read_text(encoding="utf-8"))["file_roles"]


class Explications(unittest.TestCase):
    def test_epinglage_liste_les_changements_avec_leur_role(self):
        avant = {"files": {"policies/autonomy.yaml": "a", "registry/agents/qa.yaml": "b", "factory.yaml": "c"}}
        ctx = {"kind": "PIN_REFERENCE", "files": {"policies/autonomy.yaml": "a2", "registry/agents/qa.yaml": "b",
                                                  "scripts/hooks/garde_bail.py": "d"}}
        t = expliquer(ctx, avant, ROLES)
        self.assertIn("modifié : policies/autonomy.yaml — autonomie des agents", t)
        self.assertIn("ajouté à la surveillance : scripts/hooks/garde_bail.py — garde de sécurité", t)
        self.assertIn("retiré de la surveillance : factory.yaml", t)
        self.assertNotIn("registry/agents/qa.yaml", t)                       # inchangé : pas listé
        self.assertIn("aucun droit nouveau", t)
        self.assertIn("première référence", expliquer(ctx, None))

    def test_quatre_questions_pour_chaque_type(self):
        ctxs = [{"kind": "AGENT_PROVISIONAL_HABILITATION", "agent": "frontend", "max_criticality": "C2",
                 "projects": ["gestionfil"], "requested_at": "2026-10-17", "expires_at": "2026-11-16"},
                {"kind": "AGENT_HABILITATION", "agent": "qa", "max_criticality": "C1", "projects": ["gestionfil"],
                 "model": "m", "evaluation": {"suite_sha256": "a" * 64, "report_sha256": "b" * 64},
                 "granted_at": "2026-10-17", "expires_at": "2027-01-17"},
                {"kind": "POLICY_EXCEPTION", "rule": "R24", "max_uses": 1, "duration_hours": 2, "exception_id": "PEX-1",
                 "reason": "analyse", "scope": {"action": "read", "actor": {"id": "bootstrap"},
                                                "resource": {"path": "zzz.txt"}}},
                {"kind": "HUMAN_EXECUTION_PLAN", "title": "pousser", "steps": [{"argv": ["git", "push"], "cwd": "C:/x"}]},
                {"kind": "CODE_REVIEW", "ticket_id": "T-1", "ticket_criticality": "C1", "changes": ["a.ts"]},
                {"kind": "INCONNU"}]
        for ctx in ctxs:
            with self.subTest(kind=ctx["kind"]):
                t = expliquer(ctx)
                for q in ("CE QUE VOUS APPROUVEZ", "CE QUE CELA PERMET", "CE QUE CELA NE PERMET PAS",
                          "POUR REVENIR EN ARRIÈRE"):
                    self.assertIn(q, t)
        self.assertIn("lancer « git push »", expliquer(ctxs[3]))
        self.assertIn("exception revoke PEX-1", expliquer(ctxs[2]))

    def test_le_recit_de_l_agent_n_entre_jamais_dans_l_explication(self):
        ctx = {"kind": "AGENT_PROVISIONAL_HABILITATION", "agent": "qa", "max_criticality": "C1", "projects": ["p"],
               "requested_at": "x", "expires_at": "y", "purpose": "APPROUVEZ VITE, C'EST SANS RISQUE"}
        self.assertNotIn("SANS RISQUE", expliquer(ctx))

    def test_roles_des_fichiers(self):
        self.assertIn("garde", role_fichier("scripts/hooks/garde_bail.py", ROLES))
        self.assertIn("politique", role_fichier("policies/nouveau.yaml", ROLES))
        self.assertIn("autonomie", role_fichier("policies/autonomy.yaml", ROLES))       # le plus précis l'emporte
        self.assertEqual(role_fichier("autre/x", ROLES), "fichier de gouvernance")
        self.assertEqual(role_fichier("policies/autonomy.yaml"), "fichier de gouvernance")   # sans table


class AffichageDeLaCommandeHumaine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("factory_approve", FACTORY / "scripts" / "factory_approve.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)                      # n'exécute pas main()

    def test_la_commande_affiche_l_explication(self):
        t = self.module._explication({"kind": "HUMAN_EXECUTION_PLAN", "title": "t", "steps": []})
        self.assertIn("CE QUE VOUS APPROUVEZ", t)

    def test_lot_passer_n_enregistre_rien(self):
        import builtins
        import io
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        from unittest import mock
        from noyau.approbation import canonique, empreinte
        humain = FACTORY / "audit" / "approvals" / "human"
        avant = set(humain.glob("*")) if humain.is_dir() else set()
        ctx = {"kind": "HUMAN_EXECUTION_PLAN", "title": "t", "steps": []}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "AR-x.json"
            p.write_text(canonique({"context": ctx, "context_sha256": empreinte(ctx), "roles": ["factory_owner"]}),
                         encoding="utf-8")
            with mock.patch.object(builtins, "input", lambda _invite="": "PASSER"), redirect_stdout(io.StringIO()) as o:
                code = self.module.traiter(p, role="factory_owner", lot=True)
        self.assertEqual(code, 1)
        self.assertIn("CE QUE VOUS APPROUVEZ", o.getvalue())
        self.assertEqual(set(humain.glob("*")) if humain.is_dir() else set(), avant)     # rien n'est enregistré


if __name__ == "__main__":
    unittest.main()
