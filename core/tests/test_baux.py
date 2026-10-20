"""Capability Manager et baux (Master Evolution Prompt v4 §5, §6 ; ADR-0016 proposé)."""
import datetime as dt
import json
import secrets
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.aide import FACTORY

from noyau import contexte
from noyau.audit import Journal
from noyau.baux import GestionnaireCapacites, RefusBail

CYCLE = yaml.safe_load((FACTORY / "core" / "schemas" / "lifecycles.yaml").read_text(encoding="utf-8"))["capability_lease"]
PLAFOND = {"max_duration_s": 7200, "max_parallel_operations": 4}
AGENT = {"type": "agent", "id": "database"}
TICKET = {"id": "T-1", "project_id": "projet-a", "criticality": "C1"}
EXE = {"id": "EX-1"}


class PolitiqueDouble:
    """Double de test du Policy Engine : décisions programmées par (capacité, ressource)."""

    def __init__(self, defaut="ALLOW", **exceptions):
        self.defaut, self.exceptions, self.demandes = defaut, exceptions, []

    def decider(self, d):
        self.demandes.append(d)
        dec = self.exceptions.get(d["capability"], self.defaut)
        return {"decision": dec, "regle": "RX", "motifs": [f"double : {dec}"], "empreinte_contexte": "x"}


class Horloge:
    def __init__(self):
        self.t = dt.datetime(2026, 10, 15, 12, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.t


CLE = secrets.token_bytes(32)                       # clé jetable de test : aucune clé réelle n'existe


def gestionnaire(d, politique, horloge=None, journal=None, cle=CLE, empreinte="pol-1"):
    return GestionnaireCapacites(Path(d) / "leases", politique, CYCLE, PLAFOND, journal, horloge, cle=cle,
                                 empreinte_politique=empreinte)


class BauxAvecLaVraiePolitique(unittest.TestCase):
    def test_refus_sans_ressource_enregistree(self):
        """Vrai moteur, vraie politique : une ressource que le registre ne connaît pas n'obtient aucun bail."""
        moteur, _ = contexte.moteur(FACTORY)
        # Agent réellement non habilité : indépendant des habilitations provisoires approuvées dans la vraie Factory.
        agents = moteur.registre.objets["agents"]
        agents[AGENT["id"]] = {k: v for k, v in agents[AGENT["id"]].items() if k != "provisional_habilitation"}
        with tempfile.TemporaryDirectory() as d:
            g = gestionnaire(d, moteur)
            b, s = g.demander(AGENT, "gestionfil", TICKET, EXE, "env-1", ["DATABASE_DROP"], ["env-1-db-1"])
            self.assertEqual((b.state, s["decision"], s["lease"]), ("DENIED", "DENY", None))
            self.assertIn(b.decisions[0]["rule"], ("R04", "R32"))           # agent non évalué hors ressource jetable


class Baux(unittest.TestCase):
    def test_emission_et_controle_de_chaque_dimension(self):
        with tempfile.TemporaryDirectory() as d:
            j = Journal(Path(d) / "j.jsonl")
            g = gestionnaire(d, PolitiqueDouble(), journal=j)
            b, s = g.demander(AGENT, "projet-a", TICKET, EXE, "env-1",
                              ["DATABASE_MIGRATION", "DATABASE_RESET"], ["env-1-db-1"], duree_s=10**6)
            self.assertEqual((b.state, s["decision"]), ("ACTIVE", "ALLOW"))
            self.assertEqual(b.limits["max_duration_s"], 7200)              # plafonné
            ok = lambda **k: g.verifier(b.id, **{**dict(acteur_id="database", execution_id="EX-1",
                                                       capacite="DATABASE_RESET", ressource="env-1-db-1"), **k})
            self.assertTrue(ok()[0])
            self.assertFalse(ok(acteur_id="backend")[0])
            self.assertFalse(ok(execution_id="EX-2")[0])
            self.assertFalse(ok(capacite="DATABASE_DROP")[0])
            self.assertFalse(ok(ressource="autre-db")[0])
            self.assertTrue(j.verifier().valide)

    def test_un_seul_refus_ou_approbation_et_aucun_bail(self):
        with tempfile.TemporaryDirectory() as d:
            g = gestionnaire(d, PolitiqueDouble(DATABASE_DROP="DENY"))
            b, s = g.demander(AGENT, "projet-a", TICKET, EXE, None, ["DATABASE_READ", "DATABASE_DROP"], ["db"])
            self.assertEqual((b.state, s["decision"]), ("DENIED", "DENY"))
            g = gestionnaire(d, PolitiqueDouble(PACKAGE_INSTALL="APPROVAL_REQUIRED"))
            b, s = g.demander(AGENT, "projet-a", TICKET, EXE, None, ["BUILD", "PACKAGE_INSTALL"], ["ws"])
            self.assertEqual((b.state, s["decision"]), ("DENIED", "APPROVAL_REQUIRED"))
            g2 = gestionnaire(d, PolitiqueDouble(defaut="PEUT-ÊTRE"))
            self.assertEqual(g2.demander(AGENT, "projet-a", TICKET, EXE, None, ["BUILD"], ["ws"])[0].state, "DENIED")

    def test_expiration_liberation_revocation(self):
        with tempfile.TemporaryDirectory() as d:
            h = Horloge()
            g = gestionnaire(d, PolitiqueDouble(), h)
            b, _ = g.demander(AGENT, "projet-a", TICKET, EXE, None, ["TEST"], ["ws"], duree_s=60)
            h.t += dt.timedelta(seconds=61)
            self.assertEqual(g.verifier(b.id, "database", "EX-1", "TEST", "ws"), (False, "bail EXPIRED"))
            b2, _ = g.demander(AGENT, "projet-a", TICKET, EXE, None, ["TEST"], ["ws"])
            b3, _ = g.demander(AGENT, "projet-a", TICKET, {"id": "EX-9"}, None, ["TEST"], ["ws"])
            self.assertEqual(g.liberer("EX-1"), [b2.id])                    # fin d'exécution : ses baux seulement
            self.assertEqual(g.obtenir(b3.id).state, "ACTIVE")
            g.revoquer(b3.id, "révocation par le superviseur")
            self.assertEqual(g.obtenir(b3.id).state, "REVOKED")
            self.assertFalse(g.verifier(b3.id, "database", "EX-9", "TEST", "ws")[0])

    def test_politique_reinterrogee_a_chaque_operation(self):
        with tempfile.TemporaryDirectory() as d:
            p = PolitiqueDouble()
            g = gestionnaire(d, p)
            b, _ = g.demander(AGENT, "projet-a", TICKET, EXE, None, ["DATABASE_RESET"], ["db"])
            args = (b.id, AGENT, "projet-a", TICKET, EXE, "DATABASE_RESET", "db")
            self.assertEqual(g.autoriser_operation(*args)["decision"], "ALLOW")
            p.defaut = "DENY"                                               # identité perdue, politique changée…
            self.assertEqual(g.autoriser_operation(*args)["decision"], "DENY")
            self.assertEqual(g.obtenir(b.id).operations, 1)

    def test_identifiant_de_bail_force(self):
        with tempfile.TemporaryDirectory() as d:
            g = gestionnaire(d, PolitiqueDouble())
            self.assertIsNone(g.obtenir("../../audit/journal"))
            self.assertFalse(g.verifier("lease-inexistant", "database", "EX-1", "TEST", "ws")[0])



class BauxAuthentifies(unittest.TestCase):
    """ADR-0017 D7, P18 ; étape G1 : authenticité L1 (altération détectée), invalidation sur changement de politique."""

    def emettre(self, d, **k):
        g = gestionnaire(d, PolitiqueDouble(), **k)
        b, s = g.demander(AGENT, "projet-a", TICKET, EXE, None, ["TEST"], ["ws"])
        self.assertEqual(s["decision"], "ALLOW")
        return g, b

    def reecrire(self, g, b, **modifs):
        f = g._fiche(b.id)
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc.update(modifs)
        f.write_text(json.dumps(doc), encoding="utf-8")

    def test_sans_cle_aucun_bail(self):
        with tempfile.TemporaryDirectory() as d:
            g = gestionnaire(d, PolitiqueDouble(), cle=None)
            with self.assertRaises(RefusBail):
                g.demander(AGENT, "projet-a", TICKET, EXE, None, ["TEST"], ["ws"])
            self.assertFalse((Path(d) / "leases").exists())

    def test_bail_altere_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            g, b = self.emettre(d)
            self.reecrire(g, b, capabilities=["DATABASE_DROP", "TEST"])
            ok, motif = g.verifier(b.id, "database", "EX-1", "DATABASE_DROP", "ws")
            self.assertFalse(ok)
            self.assertIn("non authentifié", motif)
            self.assertEqual(g.liberer("EX-1"), [])

    def test_bail_refuse_rendu_actif_a_la_main_reste_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            g = gestionnaire(d, PolitiqueDouble(TEST="DENY"))
            b, _ = g.demander(AGENT, "projet-a", TICKET, EXE, None, ["TEST"], ["ws"])
            self.reecrire(g, b, state="ACTIVE")
            self.assertFalse(g.verifier(b.id, "database", "EX-1", "TEST", "ws")[0])
            self.assertEqual(g.autoriser_operation(b.id, AGENT, "projet-a", TICKET, EXE, "TEST", "ws")["decision"],
                             "DENY")

    def test_bail_forge_sans_mac_ou_autre_cle(self):
        with tempfile.TemporaryDirectory() as d:
            g, b = self.emettre(d)
            autre = gestionnaire(d, PolitiqueDouble(), cle=secrets.token_bytes(32))
            self.assertFalse(autre.verifier(b.id, "database", "EX-1", "TEST", "ws")[0])
            self.assertFalse(gestionnaire(d, PolitiqueDouble(), cle=None).verifier(b.id, "database", "EX-1", "TEST",
                                                                                  "ws")[0])
            self.reecrire(g, b, mac="")
            self.assertFalse(g.verifier(b.id, "database", "EX-1", "TEST", "ws")[0])

    def test_autorite_et_empreinte_portees_par_le_bail(self):
        with tempfile.TemporaryDirectory() as d:
            g, b = self.emettre(d)
            self.assertEqual(b.authority, {"kind": "POLICY", "rules": ["RX"]})
            self.assertEqual((b.policy_fingerprint, b.lease_schema_version), ("pol-1", 1))
            self.assertTrue(g.authentique(g.obtenir(b.id)))

    def test_politique_modifiee_invalide_le_bail(self):
        with tempfile.TemporaryDirectory() as d:
            g, b = self.emettre(d)
            g2 = gestionnaire(d, PolitiqueDouble(), empreinte="pol-2")
            self.assertEqual(g2.verifier(b.id, "database", "EX-1", "TEST", "ws"), (False, "bail INVALIDATED"))
            self.assertEqual(g.obtenir(b.id).state, "INVALIDATED")
            self.assertFalse(g.verifier(b.id, "database", "EX-1", "TEST", "ws")[0])     # terminal


class EmpreinteDePolitique(unittest.TestCase):
    def test_stable_et_sensible_a_chaque_fichier(self):
        e = contexte.empreinte_politique(FACTORY)
        self.assertEqual(e, contexte.empreinte_politique(FACTORY))
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            for rel in contexte.FICHIERS_DE_POLITIQUE:
                (r / rel).parent.mkdir(parents=True, exist_ok=True)
                (r / rel).write_bytes((FACTORY / rel).read_bytes())
            self.assertEqual(contexte.empreinte_politique(r), e)
            autonomie = r / "policies" / "autonomy.yaml"
            autonomie.write_bytes(b"# modifie\n" + autonomie.read_bytes())
            self.assertNotEqual(contexte.empreinte_politique(r), e)


if __name__ == "__main__":
    unittest.main()
