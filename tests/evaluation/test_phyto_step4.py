"""Phyto plan, step 4: resistance management. FRAC / IRAC groups (docs/moa_groups.csv, proposed rows unused), the last
treatment of the farmer, no repeat of its group when an alternative exists (ranking.py, Vérificateur rule 13), one line
on rotation written by code."""
import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from src.agent import paths  # noqa: F401
from src.agent.redaction import P, compose
from src.evaluation import eval_phyto as E
import ranking as R  # noqa: E402  (src/tools)
from safety import chemical_terms, check_answer  # noqa: E402
from unittest import mock
from tests.review_state import proposed_copy

ROOT = Path(__file__).resolve().parents[2]


def read_groups():
    with open(R.MOA, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class WithValidated(unittest.TestCase):
    """Runs with a copy of docs/moa_groups.csv where every row is validated (the real file stays proposed)."""
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        rows = [dict(r, status="validated") for r in read_groups()]
        path = Path(cls.dir) / "moa_groups.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        cls.saved = R.MOA
        R.MOA = path
        R._moa.cache_clear()

    @classmethod
    def tearDownClass(cls):
        R.MOA = cls.saved
        R._moa.cache_clear()
        shutil.rmtree(cls.dir)


class TestTable(unittest.TestCase):
    def test_rows_are_well_formed_and_proposed(self):
        rows = read_groups()
        self.assertGreater(len(rows), 100)
        self.assertLessEqual({r["status"] for r in rows}, {"proposed", "validated", "rejected"})  # rows the reviewer validates or rejects stay valid
        for r in rows:
            self.assertRegex(r["groupe"], r"^(FRAC|IRAC) [A-Z]{0,2}\d{0,3}[A-Z]?$|^IRAC UN$", r)
            self.assertEqual(r["faible_risque"] == "oui", R.low_risk(r["groupe"]), r)

    def test_known_groups(self):
        g = {}
        for r in read_groups():
            g.setdefault(r["substance"], set()).add(r["groupe"])
        expected = {"Tebuconazole": "FRAC 3", "Azoxystrobin": "FRAC 11", "Metalaxyl-M": "FRAC 4",
                    "Cymoxanil": "FRAC 27", "Mandipropamid": "FRAC 40", "Chlorantraniliprole": "IRAC 28",
                    "Spinosad": "IRAC 5", "Imidacloprid": "IRAC 4A", "Copper hydroxide": "FRAC M01",
                    "Sulphur": "FRAC M02", "Chlorothalonil": "FRAC M05", "Emamectin": "IRAC 6"}
        for s, grp in expected.items():
            self.assertIn(grp, g.get(s, set()), s)

    def test_proposed_rows_change_nothing(self):
        # the table with its rows back to 'proposed' (the review has validated them since)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(R, "MOA", proposed_copy(R.MOA, d)):
            R._moa.cache_clear()
            R._last_groups.cache_clear()
            try:
                self.assertEqual(R.moa_groups({"substances": "Tebuconazole"}), set())
                out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__late_blight",
                                     "governorate": "Nabeul", "last_treatment_group": "FRAC 27"})
                self.assertNotIn("Alternez", out["reponse"]["texte"])
            finally:
                R._moa.cache_clear()
                R._last_groups.cache_clear()


class TestLastTreatment(WithValidated):
    def test_codes_products_and_substances(self):
        self.assertEqual(R.last_groups("FRAC 3"), {"FRAC 3"})
        self.assertEqual(R.last_groups("irac 4a"), {"IRAC 4A"})
        self.assertEqual(R.last_groups("groupe M1"), {"FRAC M01", "IRAC M01"})
        self.assertEqual(R.last_groups("27"), {"FRAC 27", "IRAC 27"})  # a code alone is the whole answer
        self.assertEqual(R.last_groups("traité il y a 10 jours"), set())  # a number in a sentence is not a code
        self.assertEqual(R.last_groups("CARIAL TOP"), {"FRAC 40", "FRAC 3"})  # mandipropamid + difenoconazole
        self.assertEqual(R.last_groups("du cymoxanil"), {"FRAC 27"})

    def test_low_risk_groups_never_count_and_irac_number_covers_its_letters(self):
        self.assertEqual(R.shared_groups({"FRAC M01"}, {"FRAC M01"}), set())
        self.assertEqual(R.shared_groups({"IRAC 4A"}, {"IRAC 4"}), {"IRAC 4A"})
        self.assertEqual(R.shared_groups({"FRAC 3", "FRAC 11"}, {"FRAC 11"}), {"FRAC 11"})


class TestRanking(WithValidated):
    @staticmethod
    def use(name, subs, dar=None):
        return {"produit": name, "substances": subs, "dar_jours": dar, "bio_ue": False, "ue_approuve": True,
                "relation": "direct"}

    def test_same_group_set_aside_when_an_alternative_exists(self):
        uses = [self.use("A", "Cymoxanil", 1), self.use("B", "Mandipropamid", 5), self.use("C", "Tebuconazole")]
        r = R.rank(uses, {"last_treatment_group": "FRAC 27"})
        self.assertEqual([u["produit"] for u in r["retenus"]], ["B", "C"])
        self.assertEqual(r["ecartes"], [{"produit": "A", "raisons": ["meme_groupe"]}])
        self.assertFalse(r["rotation_impossible"])
        self.assertIn(("rotation", "FRAC 40", "FRAC 27"), r["retenus"][0]["raisons"])

    def test_no_alternative_keeps_the_product_and_says_so(self):
        # rotation alone: toxicity (ranked before it since step 6) is left out of this test
        with mock.patch.object(R, "_hazard", lambda: {}):
            r = R.rank([self.use("A", "Cymoxanil"), self.use("U", "Unknown substance")],
                       {"last_treatment_group": "FRAC 27"})
        self.assertEqual([u["produit"] for u in r["retenus"]], ["U", "A"])  # unknown group first, same group last
        self.assertTrue(r["rotation_impossible"])

    def test_low_risk_group_can_be_repeated(self):
        r = R.rank([self.use("K", "Copper hydroxide"), self.use("B", "Mandipropamid")],
                   {"last_treatment_group": "FRAC M01"})
        self.assertEqual({u["produit"] for u in r["retenus"]}, {"K", "B"})
        k = next(u for u in r["retenus"] if u["produit"] == "K")
        # never written "different from the last treatment" when the low-risk group is the same
        self.assertIn(("groupe_faible_risque", "FRAC M01", "FRAC M01"), k["raisons"])

    def test_question_on_the_last_treatment_when_it_changes_the_answer(self):
        uses = [self.use("A", "Cymoxanil", 1), self.use("B", "Mandipropamid", 5)]
        self.assertIn("last_treatment_group", R.decisive_fields(uses, {"days_to_harvest": 30, "market": "local",
                                                                        "organic": "n", "stage": "spread"}))


class TestRule13AndAnswer(WithValidated):
    BASE = {"task": "diseases", "classe": "tomato__late_blight", "culture": "tomate", "fiable": True}
    GOOD = {"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}  # cymoxanil (27) + copper (M01)
    TEXT = ("- CIMOXATE C WG (Cymoxanil + Copper oxychloride) : dose 3 kg/ha (300 g/hl) ; délai avant récolte : 3 jours"
            " ; classe de toxicité OMS II (modérément dangereux)"  # rule 15, since the WHO table is validated
            "\nProtection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes\nListe DGSVCIA du 22/05/2024")

    def test_repeating_the_last_group_is_blocked(self):
        ok = check_answer(dict(self.BASE, produits=[self.GOOD], texte=self.TEXT,
                               contexte={"last_treatment_group": "FRAC 40"}))
        self.assertTrue(ok["valide"], ok["raisons"])
        r = check_answer(dict(self.BASE, produits=[self.GOOD], texte=self.TEXT,
                              contexte={"last_treatment_group": "FRAC 27"}))
        self.assertFalse(r["valide"])
        self.assertTrue(any("même groupe (FRAC 27)" in x for x in r["raisons"]), r["raisons"])

    def test_answer_rotates_and_explains(self):
        out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__late_blight", "governorate": "Nabeul",
                             "last_treatment_group": "FRAC 27", "days_to_harvest": "30", "market": "local",
                             "organic": "n", "stage": "spread"})
        r = out["reponse"]
        self.assertTrue(r["verification"]["valide"], r["verification"])
        for p in out["traitements"]["produits"]:
            self.assertFalse(R.shared_groups(R.moa_groups(p), {"FRAC 27"}), p)
        self.assertIn(P["fr"]["rotation"], r["texte"])
        self.assertIn("même groupe que votre dernier traitement (FRAC 27)", r["texte"])
        self.assertEqual(chemical_terms(P["fr"]["rotation"]), [])

    def test_arabic_rotation_line(self):
        facts = {"issue": "conseil", "diagnostic": {"classe": "tomato__late_blight", "nom": "M", "confiance": 90},
                 "produits": [{"nom": "X WG", "substances": "S", "dose": "1 kg/ha", "dar_jours": 3,
                               "raisons": [("relation", "direct"), ("groupe", "FRAC 40")]}],
                 "rotation_conseil": True, "dernier_groupe": ["FRAC 27"],
                 "ecartes": [{"produit": "Y", "raisons": ["meme_groupe"]}]}
        text = compose(facts, "ar")
        self.assertIn("مجموعة FRAC 40", text)
        self.assertIn("نفس مجموعة آخر مداواة (FRAC 27): 1 منتج", text)
        self.assertIn("غيّر مجموعة طريقة التأثير", text)
        self.assertNotIn("Alternez", text)  # the Arabic answer carries no French sentence


if __name__ == "__main__":
    unittest.main()
