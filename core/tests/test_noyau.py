"""Tests du cœur : agrégation des états, masquage, liste blanche, périmètre."""
import tempfile
import unittest
from pathlib import Path

from tests import aide  # noqa: F401  (chemin d'import)
from noyau.commandes import Executeur
from noyau.masquage import contient_secret, masquer
from noyau.modele import Constat, etat_factory, etat_phase
from noyau.perimetre import AccesRefuse, Perimetre, Racine, canonique, resoudre_racine


def constat(statut, critique=False, bloque=("EXECUTION",), domaine="capability", nature="VERIFIED"):
    return Constat(id="x", domaine=domaine, element="e", statut=statut, nature=nature, critique=critique,
                   bloque=list(bloque))


class Agregation(unittest.TestCase):
    def test_critique_inconnu_bloque(self):
        # Jamais READY si une dépendance critique n'est pas prouvée (Playbook §7.3).
        self.assertEqual(etat_phase([constat("UNKNOWN", critique=True)], "EXECUTION"), "BLOCKED")

    def test_echec_non_critique_bloque_sa_phase(self):
        self.assertEqual(etat_phase([constat("FAILED")], "EXECUTION"), "BLOCKED")

    def test_phase_non_concernee_reste_prete(self):
        # Décision K5 : un blocage d'exécution ne bloque pas l'analyse.
        self.assertEqual(etat_phase([constat("FAILED")], "PROJECT_ANALYSIS"), "READY")

    def test_avertissements_seuls(self):
        self.assertEqual(etat_phase([constat("WARNING")], "EXECUTION"), "READY")

    def test_degrade(self):
        self.assertEqual(etat_phase([constat("DEGRADED")], "EXECUTION"), "DEGRADED")

    def test_factory_bloquee_par_critique(self):
        self.assertEqual(etat_factory([constat("BLOCKED", critique=True, domaine="factory")]), "BLOCKED")

    def test_etat_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            constat("OK")


class Masquage(unittest.TestCase):
    CAS = [
        "postgres://utilisateur:Tr3sS3cret@localhost:5432/base",
        "PGPASSWORD=Tr3sS3cret",
        "password: Tr3sS3cret",
        'JWT_SECRET="Tr3sS3cret"',
        "Authorization: Bearer Tr3sS3cret",
        "api_key=Tr3sS3cret",
    ]

    def test_aucune_valeur_ne_survit(self):
        for cas in self.CAS:
            with self.subTest(cas=cas):
                self.assertNotIn("Tr3sS3cret", masquer(cas))
                self.assertTrue(contient_secret(cas))

    def test_texte_ordinaire_intact(self):
        for texte in ("git version 2.55.0", "mot de passe à définir", "token_limit", "https://example.org/doc"):
            self.assertEqual(masquer(texte), texte)


class ListeBlanche(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        racine = Racine("PROJECT_ROOT", canonique(self.dir.name))
        self.p = Perimetre({"PROJECT_ROOT": racine}, [".env"], ["sauvegardes"], ["node_modules"], [])
        self.e = Executeur(autorisees=[["git", "--version"], ["git", "status", "--short", "--branch"],
                                       ["git", "log", "--oneline", "-n", "<N>"]],
                           jokers={"<N>": "^[0-9]{1,3}$"}, perimetre=self.p, options_repertoire={"git": "-C"})

    def tearDown(self):
        self.dir.cleanup()

    def test_commande_absente_refusee_sans_execution(self):
        for argv in (["git", "push"], ["git", "commit", "-m", "x"], ["cargo", "build"], ["psql", "-c", "select 1"],
                     ["claude", "mcp", "list"]):
            with self.subTest(argv=argv):
                r = self.e.lancer(argv)
                self.assertFalse(r.autorisee)
                self.assertFalse(r.executee)

    def test_metacaractere_refuse(self):
        self.assertFalse(self.e.autorisee(["git", "--version;", "rm"])[0])

    def test_joker_contraint(self):
        self.assertTrue(self.e.autorisee(["git", "log", "--oneline", "-n", "5"])[0])
        self.assertFalse(self.e.autorisee(["git", "log", "--oneline", "-n", "5; x"])[0])

    def test_git_C_dans_le_perimetre_seulement(self):
        self.assertTrue(self.e.autorisee(["git", "-C", self.dir.name, "status", "--short", "--branch"])[0])
        dehors = tempfile.gettempdir()
        self.assertFalse(self.e.autorisee(["git", "-C", dehors, "status", "--short", "--branch"])[0])

    def test_commande_autorisee_executee(self):
        r = self.e.lancer(["git", "--version"])
        self.assertTrue(r.autorisee)
        self.assertIn("git version", r.sortie)


class PerimetreLecture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        base = Path(self.dir.name)
        (base / "src").mkdir()
        (base / "src" / "a.txt").write_text("lisible", encoding="utf-8")
        (base / ".env").write_text("SECRET=valeur", encoding="utf-8")
        (base / "sauvegardes").mkdir()
        (base / "sauvegardes" / "b.sql").write_text("donnees", encoding="utf-8")
        (base / "docs").mkdir()
        (base / "docs" / "c.txt").write_text("motif", encoding="utf-8")
        racine = Racine("PROJECT_ROOT", canonique(base), sensibles=["docs/c.txt"])
        self.p = Perimetre({"PROJECT_ROOT": racine}, [".env", "*.pem"], ["sauvegardes"], ["node_modules"], [])
        self.base = base

    def tearDown(self):
        self.dir.cleanup()

    def test_lecture_permise(self):
        self.assertEqual(self.p.lire_texte(self.base / "src" / "a.txt"), "lisible")

    def test_fichier_sensible_jamais_ouvert(self):
        for f in (self.base / ".env", self.base / "sauvegardes" / "b.sql", self.base / "docs" / "c.txt"):
            with self.subTest(f=f), self.assertRaises(AccesRefuse):
                self.p.lire_texte(f)
        self.assertEqual(len(self.p.lectures), 0)

    def test_hors_racine_refuse(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as h:
            h.write("ailleurs")
        try:
            with self.assertRaises(AccesRefuse):
                self.p.lire_texte(h.name)
            with self.assertRaises(AccesRefuse):
                self.p.lire_texte(self.base / ".." / Path(h.name).name)   # remontée par « .. »
        finally:
            Path(h.name).unlink()

    def test_existence_d_un_sensible_permise(self):
        self.assertTrue(self.p.existe(self.base / ".env"))

    def test_resolution_racine(self):
        (self.base / "marque.txt").write_text('id: projet-x', encoding="utf-8")
        r, rejets = resoudre_racine("P", str(self.base), [{"file": "marque.txt", "pattern": "^id: projet-x"}])
        self.assertIsNotNone(r)
        r, rejets = resoudre_racine("P", str(self.base), [{"file": "marque.txt", "pattern": "^id: autre"}])
        self.assertIsNone(r)
        self.assertTrue(rejets)
        r, rejets = resoudre_racine("P", str(self.base / "absent"), [])
        self.assertEqual(rejets, ["inexistant"])


if __name__ == "__main__":
    unittest.main()
