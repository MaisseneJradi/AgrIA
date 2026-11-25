"""Phyto plan, step 9: composition of the shop products (extract_composition.py), matching to the official list, to
the needs of the Agronome and to the variety catalogue (match_shop_products.py), fertilizer dose ranges
(src/tools/fertiliser_dose.py). Every row is proposed; nothing is shown to a farmer yet (step 10)."""
import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from src.agent import paths  # noqa: F401
from src.preparation import extract_composition as X
from src.preparation import match_shop_products as M
import fertiliser_dose as F  # noqa: E402  (src/tools)


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = X.substance_patterns()

    def test_pesticide_substances_and_concentrations(self):
        r = X.pesticide("MITOVER SC Bifenazate 300 g/l + Etoxazole 150 g/l SC, un acaricide.", "MITOVER SC",
                        self.patterns)
        self.assertEqual(r["substances"], "Bifenazate 300 g/l + Etoxazole 150 g/l")
        self.assertEqual(r["formulation"], "SC")
        r = X.pesticide("Composition : 480 g/L Chlorpyriphos-éthyl", "CHARTER 1 L", self.patterns)
        self.assertEqual(r["substances"], "Chlorpyrifos 480 g/l")
        r = X.pesticide("Matières actives 80% Captane.", "CAPITOL 80 WG", self.patterns)
        self.assertEqual((r["substances"], r["formulation"]), ("Captan 80 %", "WG"))

    def test_fertiliser_contents(self):
        self.assertEqual(X.nutrients("", "Agrifol 13-40-13 1 KG"), {"N": 13.0, "P2O5": 40.0, "K2O": 13.0})
        self.assertEqual(X.nutrients("Bore (B) 15 % soluble dans l'eau", "Agriabore")["B"], 15.0)
        self.assertEqual(X.label_doses("Dose : 150 à 300 cc/hl ou 2-3 kg par hectare"), "150-300 cc/hl | 2-3 kg/ha")

    def test_file(self):
        rows = read(X.OUT)
        from common import query
        self.assertEqual(len(rows), len(query("SELECT id FROM shop_products")))  # one row per product
        self.assertLessEqual({r["status"] for r in rows}, {"proposed", "validated", "rejected"})  # rows the reviewer validates or rejects stay valid


class TestMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read(M.OUT)

    def test_trade_name_alone_never_matches(self):
        reg = M.registry()
        # same name as the registered product, other composition: no pesticide row
        row = {"name": "MITOVER SC", "substances": "Imidacloprid 200 g/l", "formulation": "SL"}
        self.assertFalse([r for r in M.match_pesticide(row, reg) if "MITOVER" in r["target_label"].upper()])
        # same substances, other concentration: no row
        row = {"name": "X", "substances": "Abamectin (aka avermectin) 999 g/l", "formulation": ""}
        self.assertEqual(M.match_pesticide(row, reg), [])

    def test_same_composition_matches(self):
        reg = M.registry()
        got = M.match_pesticide({"name": "Y", "substances": "Glyphosate 360 g/l", "formulation": "SL"}, reg)
        self.assertTrue(any(r["verdict"] == "apparié" and r["match_score"] == 1.0 for r in got))
        self.assertTrue(all("Glyphosate 360 g/l" in r["target_label"] for r in got))
        self.assertTrue(M.same_conc((5.0, "%"), (50.0, "g/kg")))
        self.assertFalse(M.same_conc((5.0, "%"), (50.0, "g/l")))  # density unknown: never compared

    def test_missing_concentration_needs_close_names(self):
        reg = M.registry()
        far = M.match_pesticide({"name": "Minecto Pro", "substances": "Cyantraniliprole", "formulation": ""}, reg)
        self.assertEqual(far, [])  # same substance only: not enough
        self.assertFalse(M.similar_names("Decis Expert", "D66"))

    def test_fertiliser_needs_and_calcareous_soil(self):
        need = M.needs()
        eddha = M.match_fertiliser({"Fe": 6.0, "chelate": "EDDHA"}, need)
        edta = M.match_fertiliser({"Fe": 6.0, "chelate": "EDTA"}, need)
        self.assertIn(("besoin:Fe_deficiency:calcaire", "apparié"), {(r["target_id"], r["verdict"]) for r in eddha})
        self.assertIn(("besoin:Fe_deficiency:calcaire", "non_apparié"), {(r["target_id"], r["verdict"]) for r in edta})
        low = M.match_fertiliser({"Fe": 0.5, "chelate": ""}, need)
        self.assertEqual(low[0]["verdict"], "incertain")

    def test_file_is_proposed_with_reasons(self):
        self.assertLessEqual({r["status"] for r in self.rows}, {"proposed", "validated", "rejected"})  # rows the reviewer validates or rejects stay valid
        self.assertTrue(all(r["reasons"] for r in self.rows))
        seeds = [r for r in self.rows if r["kind"] == "semence" and r["verdict"] == "apparié"]
        self.assertTrue(any("Rio grande" in r["target_label"] for r in seeds))


class TestDoseRanges(unittest.TestCase):
    def test_proposed_ranges_show_nothing(self):
        self.assertFalse(F.label_dose("10-20 kg/ha", "Fe")["montrer"])

    def test_validated_ranges(self):
        tmp = tempfile.mkdtemp()
        saved = F.RANGES
        try:
            rows = [dict(r, status="validated") for r in read(saved)]
            path = Path(tmp) / "r.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            F.RANGES = path
            F._ranges.cache_clear()
            self.assertTrue(F.label_dose("10-20 kg/ha | 10-20 g/plant", "Fe")["montrer"])
            self.assertFalse(F.label_dose("1000 kg/ha", "Fe")["montrer"])  # outside the range
            self.assertFalse(F.label_dose("0 g/hl", "Zn")["montrer"])  # a misread label dose
            self.assertFalse(F.label_dose("3 sachets", "Zn")["montrer"])  # unreadable: never shown
        finally:
            F.RANGES = saved
            F._ranges.cache_clear()
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
