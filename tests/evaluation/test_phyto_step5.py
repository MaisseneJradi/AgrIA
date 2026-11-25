"""Phyto plan, step 5: practical dose (src/tools/dose_calc.py) and Vérificateur rule 14.

Every unit pair: (g, gr, kg, cc, ml, cl, l) x (per hl, per 100 l, per 10 l, per l, per ha) -> sprayer of 16 L and area,
with the expected amounts computed here from a factor table written independently of the module."""
import sqlite3
import unittest

from src.agent import paths  # noqa: F401
from src.agent.redaction import P, practical_line
from src.evaluation import eval_phyto as E
import dose_calc as D  # noqa: E402  (src/tools)
from common import DB_PATH  # noqa: E402
from safety import check_answer  # noqa: E402

TO_G_OR_ML = {"g": (1, "g"), "gr": (1, "g"), "kg": (1000, "g"), "cc": (1, "ml"), "ml": (1, "ml"), "cl": (10, "ml"),
              "l": (1000, "ml")}
PER_VOLUME = {"hl": 100, "100 l": 100, "10 l": 10, "l": 1}


class TestEveryUnitPair(unittest.TestCase):
    def test_per_volume_to_sprayer(self):
        for unit, (f, base) in TO_G_OR_ML.items():
            for basis, litres in PER_VOLUME.items():
                with self.subTest(unit=unit, basis=basis):
                    r = D.practical_dose(f"2,5 {unit}/{basis}", area_ha=3)
                    self.assertAlmostEqual(r["pulverisateur"]["min"], 2.5 * f * 16 / litres)
                    self.assertEqual(r["pulverisateur"]["base"], base)
                    self.assertIsNone(r["surface"])  # never per volume -> per hectare
                    self.assertEqual(r["surface_absente"], "volume_par_ha")

    def test_per_hectare_to_area(self):
        for unit, (f, base) in TO_G_OR_ML.items():
            with self.subTest(unit=unit):
                r = D.practical_dose(f"0.4 {unit}/ha", area_ha=2.5)
                self.assertAlmostEqual(r["surface"]["min"], 0.4 * f * 2.5)
                self.assertEqual(r["surface"]["base"], base)
                self.assertIsNone(r["pulverisateur"])  # never per hectare -> sprayer
                self.assertEqual(r["pulverisateur_absent"], "volume_par_ha")

    def test_both_bases_and_written_amounts(self):
        r = D.practical_dose("3 kg/ha (300 g/hl)", area_ha=0.5)
        self.assertEqual((r["pulverisateur"]["texte"], r["surface"]["texte"]), ("48 g", "1,5 kg"))
        self.assertEqual(D.practical_dose("300 cc/hl (03 l/ha)", 0.5)["surface"]["texte"], "1,5 l")
        self.assertEqual(D.practical_dose("30-50 cc/hl")["pulverisateur"]["texte"], "4,8 à 8 ml")
        self.assertEqual(D.practical_dose("2 ml/hl")["pulverisateur"]["texte"], "0,32 ml")
        self.assertEqual(D.practical_dose("1 Kg/hl")["pulverisateur"]["texte"], "160 g")
        self.assertEqual(D.practical_dose("75 cc/ hl")["pulverisateur"]["texte"], "12 ml")
        self.assertEqual(D.practical_dose("2 l/havolume", 1.5)["surface"]["texte"], "3 l")
        # the second per-hectare part is the volume of water, not the dose
        self.assertEqual(D.practical_dose("0.5 l/ha (300-500 l/ha)", 0.25)["surface"]["texte"], "125 ml")

    def test_what_is_not_converted(self):
        for dose in ("1 L/300 à", "30 pièges/ha", "20 ml/100 Kg", "50 cc", "2 %", "1000 diffuseurs/ha", "", None):
            self.assertIsNone(D.practical_dose(dose, 1), dose)


class TestCheck(unittest.TestCase):
    def test_exact_wrong_and_missing(self):
        exp = D.practical_dose("3 kg/ha (300 g/hl)", area_ha=0.5)
        self.assertEqual(D.check("Dose pratique : 48 g pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha", exp), [])
        self.assertTrue(D.check("Dose pratique : 4,8 g pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha", exp))
        self.assertTrue(D.check("Dose pratique : 48 g pour un pulvérisateur de 16 L", exp))
        self.assertTrue(D.check("Dose pratique : 48 ml pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha", exp))
        rng = D.practical_dose("20 - 25 g/100L")  # a range: both bounds are checked
        self.assertEqual(D.check("Dose pratique : 3,2 à 4 g pour un pulvérisateur de 16 L", rng), [])
        self.assertTrue(D.check("Dose pratique : 2,5 à 4 g pour un pulvérisateur de 16 L", rng))

    def test_every_registered_dose_round_trips(self):
        """The line written for each dose of the table traitements passes the check, in French and in Arabic."""
        with sqlite3.connect(DB_PATH) as con:
            doses = [r[0] for r in con.execute("SELECT DISTINCT dose FROM traitements")]
        n = 0
        for dose in doses:
            exp = D.practical_dose(dose, area_ha=0.37)
            if exp is None:
                continue
            n += 1
            for lang in ("fr", "ar"):
                self.assertEqual(D.check(practical_line(exp, P[lang], lang), exp), [], (dose, lang))
        self.assertGreater(n, 140)


class TestRule14(unittest.TestCase):
    BASE = {"task": "diseases", "classe": "tomato__late_blight", "culture": "tomate", "fiable": True,
            "contexte": {"area": 0.5}}
    GOOD = {"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}
    LINE = ("- CIMOXATE C WG (Cymoxanil + Copper oxychloride) : dose 3 kg/ha (300 g/hl) ; délai avant récolte : 3 jours"
            " ; classe de toxicité OMS II (modérément dangereux)")  # rule 15, since the WHO table is validated

    def answer(self, practical):
        return dict(self.BASE, produits=[self.GOOD], texte=self.LINE + "\n  " + practical
                    + "\nProtection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes\nListe DGSVCIA du 22/05/2024")

    def test_exact_practical_dose_passes(self):
        r = check_answer(self.answer("Dose pratique : 48 g pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha"))
        self.assertTrue(r["valide"], r["raisons"])

    def test_wrong_or_incomplete_practical_dose_blocked(self):
        for line in ("Dose pratique : 480 g pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha",
                     "Dose pratique : 48 g pour un pulvérisateur de 16 L ; 3 kg pour vos 0,5 ha",
                     "Dose pratique : 48 g pour un pulvérisateur de 10 L ; 1,5 kg pour vos 0,5 ha",
                     "Dose pratique : 48 g pour un pulvérisateur de 16 L"):
            r = check_answer(self.answer(line))
            self.assertFalse(r["valide"], line)
            self.assertTrue(any("dose pratique" in x for x in r["raisons"]), r["raisons"])

    def test_practical_dose_outside_a_product_blocked(self):
        r = check_answer(dict(self.BASE, produits=[self.GOOD],
                              texte=self.LINE + "\n\nDose pratique : 48 g pour un pulvérisateur de 16 L"))
        self.assertFalse(r["valide"])


class TestAnswers(unittest.TestCase):
    def test_answer_gives_the_practical_dose_and_passes_the_verifier(self):
        out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__late_blight", "governorate": "Nabeul",
                             "area": "0.5", "days_to_harvest": "15", "market": "local", "organic": "n",
                             "stage": "spread"})
        r = out["reponse"]
        self.assertTrue(r["verification"]["valide"], r["verification"])
        # the products shown depend on the ranking (toxicity first since the WHO table is validated); the exact
        # quantities are checked by the Vérificateur (rule 14), passed above
        self.assertRegex(r["texte"], r"Dose pratique : [^\n]+ pour un pulvérisateur de 16 L ; [^\n]+ pour vos 0,5 ha")

    def test_without_area_only_the_sprayer(self):
        out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__late_blight", "governorate": "Nabeul"})
        self.assertNotIn(" ha ;", out["reponse"]["texte"])
        self.assertIn("pour un pulvérisateur de 16 L", out["reponse"]["texte"])


if __name__ == "__main__":
    unittest.main()
