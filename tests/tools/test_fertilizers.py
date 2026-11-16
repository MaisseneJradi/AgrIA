import unittest

from tests.tools import _path  # noqa: F401
from fertilizers import get_fertilizers

DEFICIENCIES = ["B", "Ca", "Fe", "K", "Mg", "Mn", "N", "P", "Zn"]


class TestFertilizers(unittest.TestCase):
    def test_every_deficiency_has_products_and_questions(self):
        for d in DEFICIENCIES:
            r = get_fertilizers(d)
            self.assertTrue(r["produits"], d)
            self.assertTrue(r["questions_confirmation"], d)
            self.assertLessEqual(len(r["produits"]), 5)

    def test_healthy_gets_no_fertilizer(self):
        self.assertEqual(get_fertilizers("healthy")["produits"], [])

    def test_mono_crop_deficiency_on_another_crop_is_a_hypothesis(self):
        for d in ("Zn", "B", "Ca"):  # each seen on one crop only (pepper or coffee)
            r = get_fertilizers(d, crop="olivier")
            self.assertEqual(r["fiabilite"], "hypothese", d)
            self.assertFalse(r["culture_vue"])
            self.assertIn("hypothèse", r["message"])

    def test_seen_crop_keeps_its_level(self):
        r = get_fertilizers("K", crop="poivron")
        self.assertTrue(r["culture_vue"])
        self.assertEqual(r["fiabilite"], "fiable")

    def test_soil_rule_and_eddha_on_calcareous_soil(self):
        r = get_fertilizers("Fe", crop="olivier", governorate="Kairouan")  # pH 7.83
        self.assertTrue(r["sol"]["favorable_a_la_carence"])
        self.assertEqual(r["produits"][0]["chelate"], "EDDHA")
        self.assertFalse(get_fertilizers("Fe", governorate="Tunis")["sol"]["favorable_a_la_carence"])  # pH 7.67

    def test_trace_products_come_last(self):
        contents = [p["teneur_pct"] for p in get_fertilizers("Fe", governorate="Kairouan")["produits"]]
        self.assertTrue(all(c is None or c >= 1 for c in contents))

    def test_known_model_confusion_is_reported(self):
        self.assertIn("zinc", get_fertilizers("Zn", crop="piment")["avertissement_modele"])
        self.assertIsNone(get_fertilizers("Mn", crop="palmier")["avertissement_modele"])

    def test_errors(self):
        with self.assertRaises(ValueError):
            get_fertilizers("Xx")
        with self.assertRaises(ValueError):
            get_fertilizers("Fe", governorate="Paris")


if __name__ == "__main__":
    unittest.main()
