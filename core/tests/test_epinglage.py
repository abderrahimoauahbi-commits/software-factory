"""Épinglage L1 des artefacts de gouvernance (ADR-0017, étape G1 ; annexe E « Épinglage »).

Les enregistrements d'approbation sont fabriqués dans un dossier temporaire (doubles de la commande humaine) :
le test prouve la vérification, pas la création, qui reste un acte humain W1."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from noyau import epinglage as E
from noyau.approbation import CANAL, TYPE, canonique, empreinte_enregistrement

MOTIFS = ["policies/*.yaml", "factory.yaml"]
ROLES = ["factory_owner"]


class Epinglage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name) / "factory"
        (self.racine / "policies").mkdir(parents=True)
        (self.racine / "policies" / "a.yaml").write_text("a: 1\n", encoding="utf-8")
        (self.racine / "policies" / "b.yaml").write_text("b: 2\n", encoding="utf-8")
        (self.racine / "factory.yaml").write_text("f: 0\n", encoding="utf-8")
        self.approbations = Path(self.tmp.name) / "human"
        self.approbations.mkdir()
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def approuver(self, demande, decision="APPROVED", role="factory_owner", quand=None, **alterations):
        """Double de la commande humaine : même forme d'enregistrement, dans un dossier de test."""
        self.n += 1
        quand = quand or dt.datetime(2026, 10, 16, 12, self.n, tzinfo=dt.timezone.utc)
        e = {"kind": TYPE, "channel": CANAL, "id": f"HA-T{self.n:03d}", "decision": decision, "approver_role": role,
             "context": demande["context"], "context_sha256": demande["context_sha256"], "request": "AR-PIN-x.json",
             "created_at": quand.isoformat(timespec="seconds")}
        e["record_sha256"] = empreinte_enregistrement(e)
        e.update(alterations)
        (self.approbations / f"{e['id']}.json").write_text(canonique(e), encoding="utf-8")
        return e["id"]

    def etat(self):
        return E.verifier(self.racine, self.approbations, ROLES)

    def test_sans_reference_unpinned(self):
        self.assertEqual(self.etat().statut, E.UNPINNED)

    def test_reference_approuvee_puis_conforme(self):
        ident = self.approuver(E.demande(self.racine, MOTIFS, ROLES))
        e = self.etat()
        self.assertEqual((e.statut, e.reference, e.ecarts), (E.PINNED, ident, []))

    def test_modification_ajout_suppression_bloquent(self):
        self.approuver(E.demande(self.racine, MOTIFS, ROLES))
        (self.racine / "policies" / "a.yaml").write_text("a: 2\n", encoding="utf-8")
        (self.racine / "policies" / "c.yaml").write_text("c: 3\n", encoding="utf-8")
        (self.racine / "policies" / "b.yaml").unlink()
        e = self.etat()
        self.assertEqual(e.statut, E.BLOCKED)
        self.assertEqual(e.ecarts, ["modifié : policies/a.yaml", "supprimé : policies/b.yaml",
                                    "ajouté : policies/c.yaml"])

    def test_nouvelle_reference_humaine_leve_le_blocage(self):
        self.approuver(E.demande(self.racine, MOTIFS, ROLES))
        (self.racine / "factory.yaml").write_text("f: 1\n", encoding="utf-8")
        self.assertEqual(self.etat().statut, E.BLOCKED)
        ident = self.approuver(E.demande(self.racine, MOTIFS, ROLES))
        self.assertEqual((self.etat().statut, self.etat().reference), (E.PINNED, ident))

    def test_references_non_valides_ignorees(self):
        d = E.demande(self.racine, MOTIFS, ROLES)
        self.approuver(d, decision="REJECTED")
        self.approuver(d, role="agent")
        self.approuver(d, channel="fichier")
        self.approuver(d, decision="APPROVED", record_sha256="0" * 64)
        self.assertEqual(self.etat().statut, E.UNPINNED)

    def test_contexte_altere_ignore(self):
        d = E.demande(self.racine, MOTIFS, ROLES)
        faux = dict(d, context=dict(d["context"], files={}))            # couverture vidée après coup
        self.approuver(faux)
        self.assertEqual(self.etat().statut, E.UNPINNED)

    def test_motifs_de_la_reference_et_non_de_la_politique_courante(self):
        self.approuver(E.demande(self.racine, MOTIFS, ROLES))
        (self.racine / "factory.yaml").write_text("f: 9\n", encoding="utf-8")
        # Réduire la couverture dans la politique courante ne masque rien : la référence garde ses motifs.
        self.assertIn("modifié : factory.yaml", self.etat().ecarts)

    def test_derniere_reference_par_date(self):
        ancienne = E.demande(self.racine, MOTIFS, ROLES)
        (self.racine / "factory.yaml").write_text("f: 1\n", encoding="utf-8")
        recente = E.demande(self.racine, MOTIFS, ROLES)
        self.approuver(recente, quand=dt.datetime(2026, 10, 16, 13, tzinfo=dt.timezone.utc))
        self.approuver(ancienne, quand=dt.datetime(2026, 10, 16, 11, tzinfo=dt.timezone.utc))
        self.assertEqual(self.etat().statut, E.PINNED)


class PolitiqueDEpinglage(unittest.TestCase):
    def test_politique_couvre_la_gouvernance(self):
        pol = yaml.safe_load((FACTORY / "policies" / "pinning.yaml").read_text(encoding="utf-8"))
        self.assertEqual(pol["roles"], ["factory_owner"])
        fichiers = E.releve(FACTORY, pol["patterns"])
        self.assertNotIn("factory.yaml", fichiers)          # plus maintenu (Factory Owner, 17/10/2026)
        for attendu in ("policies/pinning.yaml", "policies/autonomy.yaml", "docs/playbook/playbook-v3.3.md",
                        "policies/rule-catalog.yaml", "core/schemas/lifecycles.yaml"):
            self.assertIn(attendu, fichiers)


if __name__ == "__main__":
    unittest.main()
