import unittest

import pandas as pd

from tests.tools import _path  # noqa: F401
from common import PROC, query
from treatments import NO_DAR, get_treatments


def model_classes():
    out = set()
    for task in ("diseases", "fruits"):
        out |= set(pd.read_csv(PROC / f"{task}_manifest.csv")["class"])
    return sorted(out)


class TestTreatments(unittest.TestCase):
    def test_every_model_class_answers(self):
        for cls in model_classes():
            self.assertIsInstance(get_treatments(cls), list, cls)

    def test_healthy_has_nothing(self):
        for cls in model_classes():
            if cls.endswith("healthy"):
                self.assertEqual(get_treatments(cls), [], cls)

    def test_28_classes_without_registered_product(self):
        sick = [c for c in model_classes() if not c.endswith("healthy")]
        empty = [c for c in sick if not get_treatments(c)]
        self.assertEqual(len(sick), 48)
        self.assertEqual(len(empty), 28)  # an empty list is the answer "no registered product", not an error
        self.assertIn("tomato__mosaic_virus", empty)

    def test_crop_filter_never_advises_an_unregistered_crop(self):
        self.assertTrue(get_treatments("tomato__late_blight", "tomate"))
        self.assertEqual(get_treatments("tomato__late_blight", "piment"), [])
        for u in get_treatments("squash__powdery_mildew", "concombre"):
            self.assertNotIn("melon", u["culture"].lower().replace("concombre", ""))

    def test_unknown_crop_is_an_error(self):
        with self.assertRaises(ValueError):
            get_treatments("tomato__late_blight", "culture imaginaire")

    def test_missing_dar_is_never_estimated(self):
        usages = [u for c in model_classes() for u in get_treatments(c)]
        missing = [u for u in usages if u["dar_jours"] is None]
        self.assertGreater(len(missing) / len(usages), 0.5)  # most usages of the list give no DAR
        for u in missing:
            self.assertEqual(u["dar_message"], NO_DAR)

    def test_order_direct_first_and_relation_explained(self):
        rank = {"direct": 0, "vecteur": 1, "groupe": 2, "proche": 3}
        for cls in ("tomato__late_blight", "apple__scab", "datepalm__leaf_spots"):
            ranks = [rank[u["relation"]] for u in get_treatments(cls)]
            self.assertEqual(ranks, sorted(ranks), cls)
        for u in get_treatments("tomato__yellow_leaf_curl_virus"):
            self.assertEqual(u["relation"], "vecteur")
            self.assertIn("insecte", u["relation_sens"])

    def test_provisional_authorisation_is_flagged(self):
        u = [u for u in get_treatments("tomato__spider_mites") if u["produit"] == "VALMEC EC"]
        self.assertTrue(u and u[0]["autorisation_provisoire"])

    def test_restricted_products_are_never_proposed(self):
        restricted = {r["product_id"] for r in query(
            "SELECT product_id FROM pesticides_produits WHERE statut = 'restriction_campagnes_nationales'")}
        for cls in model_classes():
            for u in get_treatments(cls):
                self.assertNotIn(u["product_id"], restricted)
                self.assertEqual(u["statut"], "homologue")

    def test_usage_fields_of_the_contract(self):
        u = get_treatments("tomato__late_blight", "tomate")[0]
        for key in ("produit", "substances", "dose", "unite", "dar_jours", "lmr", "relation", "restriction"):
            self.assertIn(key, u)


if __name__ == "__main__":
    unittest.main()
