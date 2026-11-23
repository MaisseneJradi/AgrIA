"""Phyto plan, step 1: the gold set and the measures of src/evaluation/eval_phyto.py."""
import copy
import unittest

from src.evaluation import eval_phyto as E

REQUIRED = ["crop", "disease_or_deficiency", "governorate", "stage", "market", "days_to_harvest", "organic",
            "greenhouse", "last_treatment_group", "acceptable_products", "must_not_contain", "expected_shop_link"]


def case(cls="tomato__late_blight", crop="tomato", kind="disease", **kw):
    c = {"case_id": "t1", "crop": crop, "disease_or_deficiency": cls, "governorate": "Nabeul", "stage": "early",
         "market": "local", "days_to_harvest": "30", "organic": "n", "greenhouse": "n", "last_treatment_group": "",
         "acceptable_products": "", "must_not_contain": "", "expected_shop_link": "", "kind": kind}
    c.update(kw)
    return c


class TestGoldSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = E.read_cases()

    def test_size_columns_and_status(self):
        self.assertTrue(60 <= len(self.cases) <= 100, len(self.cases))
        for col in REQUIRED:
            self.assertIn(col, self.cases[0])
        self.assertEqual({c["status"] for c in self.cases}, {"to_validate"})
        self.assertEqual(len({c["case_id"] for c in self.cases}), len(self.cases))

    def test_acceptable_products_are_registered_on_the_crop(self):
        for c in self.cases:
            if c["kind"] in ("deficiency", "healthy"):
                continue
            for p in E._split(c["acceptable_products"]):
                self.assertTrue(E.registered_on_crop(p, c["crop"]), (c["case_id"], p))

    def test_crop_traps_are_not_registered_on_the_crop(self):
        for c in self.cases:
            for p in E._split(c["must_not_contain"]):
                self.assertFalse(E.registered_on_crop(p, c["crop"]), (c["case_id"], p))


class TestMeasures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = case(acceptable_products="CIMOXATE C WG")
        cls.out, cls.ms = E.run_case(cls.c)

    def test_real_answer_is_safe_valid_and_exact(self):
        r = E.score(self.c, self.out, self.ms)
        self.assertTrue(self.out["reponse"]["verification"]["valide"])
        self.assertEqual(r["unsafe"], "")
        self.assertTrue(r["covered"])
        self.assertEqual(r["n_exact"], r["n_shown"])

    def test_unregistered_product_in_text_is_unsafe(self):
        out = copy.deepcopy(self.out)
        out["reponse"]["texte"] += "\nEssayez MITOVER SC."  # agrishop product, not registered on tomato
        self.assertIn("MITOVER", E.score(self.c, out, 1)["unsafe"])

    def test_must_not_contain_is_unsafe(self):
        name = self.out["reponse"]["produits"][0]["nom"]
        self.assertIn("interdit", E.score(dict(self.c, must_not_contain=name), self.out, 1)["unsafe"])

    def test_any_pesticide_on_a_deficiency_is_unsafe(self):
        self.assertIn("sans objet", E.score(case("Fe_deficiency", "pepper", "deficiency"), self.out, 1)["unsafe"])

    def test_wrong_dose_or_dar_is_not_exact(self):
        out = copy.deepcopy(self.out)
        p = out["traitements"]["produits"][0]
        p["dose"] = "999 g/hl"
        r = E.score(self.c, out, 1)
        self.assertLess(r["n_exact"], r["n_shown"])
        out = copy.deepcopy(self.out)
        out["traitements"]["produits"][0]["dar_jours"] = 999
        r = E.score(self.c, out, 1)
        self.assertLess(r["n_exact"], r["n_shown"])

    def test_context_violations(self):
        out = copy.deepcopy(self.out)
        out["traitements"]["produits"][0]["dar_jours"] = 20
        r = E.score(dict(self.c, days_to_harvest="3", organic="y"), out, 1)
        self.assertTrue(r["dar_trop_long"])
        self.assertTrue(r["bio_non_bio"] or all(E._product_info()[p["product_id"]]["bio"]
                                                for p in out["traitements"]["produits"]))

    def test_shop_links_counted(self):
        out = copy.deepcopy(self.out)
        out["reponse"]["texte"] += "\nhttps://www.agriclic.tn/1-x.html"
        r = E.score(dict(self.c, expected_shop_link="https://www.agriclic.tn/1-x.html"), out, 1)
        self.assertTrue(r["link_ok"])
        r = E.score(self.c, out, 1)
        self.assertEqual(r["link_wrong"], ["https://www.agriclic.tn/1-x.html"])

    def test_fertiliser_need_read_through_oxides(self):
        c = case("P_deficiency", kind="deficiency", acceptable_products="nutriment:P")
        out, ms = E.run_case(c)
        r = E.score(c, out, ms)
        self.assertTrue(r["fert_ok"], r["engrais"])  # agriclic gives P2O5: it counts as P
        self.assertEqual(r["unsafe"], "")

    def test_no_product_case_says_so(self):
        c = case("tomato__mosaic_virus", kind="virus")
        out, ms = E.run_case(c)
        r = E.score(c, out, ms)
        self.assertTrue(r["absence_dite"])
        self.assertEqual(r["unsafe"], "")


if __name__ == "__main__":
    unittest.main()
