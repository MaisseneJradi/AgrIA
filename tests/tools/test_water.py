import unittest
from unittest import mock

from tests.tools import _path  # noqa: F401
import water
from water import get_water_need


class TestWater(unittest.TestCase):
    def test_need_in_season(self):
        r = get_water_need("Kairouan", "olivier", 7)
        self.assertTrue(r["en_saison"])
        self.assertAlmostEqual(r["besoin_mm"], r["et0_mm"] * r["kc"], delta=0.2)
        self.assertEqual(r["deficit_m3_ha"], round(r["deficit_mm"] * 10))
        self.assertGreaterEqual(r["deficit_mm"], 0)

    def test_out_of_season(self):
        r = get_water_need("Sfax", "tomate", 1)
        self.assertFalse(r["en_saison"])
        self.assertNotIn("besoin_mm", r)

    def test_names_in_any_language(self):
        a = get_water_need("القيروان", "zitoun", 7)
        b = get_water_need("Kairouan", "Olivier", 7)
        self.assertEqual(a["besoin_mm"], b["besoin_mm"])
        self.assertEqual(get_water_need("le kef", "blé", 1)["gouvernorat"], "Le Kef")

    def test_errors(self):
        for args in [("Paris", "tomate", 5), ("Tunis", "café", 5), ("Tunis", "tomate", 13)]:
            with self.assertRaises(ValueError):
                get_water_need(*args)

    def test_forecast_failure_keeps_the_monthly_answer(self):
        with mock.patch.object(water.urllib.request, "urlopen", side_effect=OSError("offline")):
            r = get_water_need("Kairouan", "olivier", 7, forecast=True)
        self.assertIn("erreur", r["prevision"])
        self.assertTrue(r["en_saison"])


if __name__ == "__main__":
    unittest.main()
