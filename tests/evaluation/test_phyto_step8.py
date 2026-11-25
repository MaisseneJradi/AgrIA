"""Phyto plan, step 8: every shop product in the table shop_products, its class (classify_shop_products.py, proposed),
the products that claim a protection effect without a registered product (docs/shop_unapproved_claims.csv) and
Vérificateur rule 21."""
import csv
import re
import unittest

from src.agent import paths  # noqa: F401
from src.preparation import classify_shop_products as K
from common import query  # noqa: E402  (src/tools)
from fertilizers import get_fertilizers  # noqa: E402
from safety import _claim_names, _same_product, check_answer  # noqa: E402

CATEGORIES = {"pesticide", "engrais_amendement", "biostimulant", "semence", "equipement", "autre"}
PPE = "Protection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes"


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestTable(unittest.TestCase):
    def test_every_product_of_both_shops(self):
        rows = query("SELECT * FROM shop_products")
        self.assertEqual(len(rows), 614)
        self.assertEqual(len({r["id"] for r in rows}), len(rows))
        for col in ("id", "name", "shop_category", "description", "technical_sheet", "price", "stock_status",
                    "image_url", "product_url", "source", "last_updated"):
            self.assertIn(col, rows[0])
        agrishop = [r for r in rows if r["id"].startswith("agrishop:")]
        agriclic = [r for r in rows if r["id"].startswith("agriclic:")]
        self.assertEqual((len(agrishop), len(agriclic)), (383, 231))
        # agrishop: the export has no page address; since phyto step 12 it comes from the sitemap of the site, the page
        # whose last part is EXACTLY the slug (never built from a pattern); no image address
        self.assertTrue(all(not r["image_url"] for r in agrishop))
        for r in agrishop:
            if r["product_url"]:
                self.assertRegex(r["product_url"], r"^https://www\.agrishop\.tn/store/category/[^/]+/[^/]+/"
                                 + re.escape(r["slug"]) + "/$")
        self.assertTrue(all(str(r["product_url"]).startswith("https://www.agriclic.tn/") for r in agriclic))
        self.assertTrue({r["stock_status"] for r in rows} <= {"en_stock", "rupture", "inactif", "inconnu", "retire"})


class TestClasses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {r["name"]: r for r in read(K.CLASSES)}

    def test_one_proposed_class_per_product(self):
        rows = read(K.CLASSES)
        self.assertEqual(len(rows), 614)
        self.assertEqual(len({r["shop_product_id"] for r in rows}), 614)
        for r in rows:
            self.assertIn(r["category_agria"], CATEGORIES)
            self.assertEqual(r["status"], "proposed")

    def test_known_products(self):
        expected = {"Motoculteur Stihl MH 610": "equipement", "MANCHON PET UNIDELTA": "equipement",
                    "GENERAL 1L": "engrais_amendement",  # "fertirrigation" is not irrigation equipment
                    "ATLANTIS": "biostimulant",  # same name as a registered herbicide: the match is set aside
                    "MITOVER SC": "pesticide", "Gib Gro 20 %": "pesticide",  # registered regulator (substance found)
                    "CYTOQUININE 250 CC": "autre", "GROWESTRENE 6% EDDHA": "engrais_amendement"}
        for name, cat in expected.items():
            self.assertEqual(self.rows[name]["category_agria"], cat, name)
        self.assertTrue(self.rows["ATLANTIS"]["liste_correspondance"].startswith("écarté"))
        self.assertTrue(any(r["category_agria"] == "semence" for r in self.rows.values()))


class TestClaims(unittest.TestCase):
    @staticmethod
    def claim(text):
        return K.claims({"name": "X", "description": text, "technical_sheet": ""})[0]

    def test_claims_and_non_claims(self):
        self.assertTrue(self.claim("X est un fongicide préventif à action systémique."))
        self.assertTrue(self.claim("Protège la plante contre le mildiou et l'oïdium."))
        self.assertTrue(self.claim("Lutte alternative contre les maladies et ravageurs."))
        self.assertFalse(self.claim("Le produit ne possède pas d'action fongicide, insecticide ou curative."))
        self.assertFalse(self.claim("Compatible avec la plupart des fongicides et insecticides usuels."))
        self.assertFalse(self.claim("Améliore la résistance des plantes au stress hydrique."))
        self.assertFalse(self.claim("Calcium contre la pourriture apicale de la tomate."))
        self.assertFalse(self.claim("maintenir une nutrition avant une évolution éventuelle vers une formule"))

    def test_claim_list(self):
        rows = read(K.CLAIMS)
        self.assertGreater(len(rows), 10)
        self.assertEqual({r["status"] for r in rows}, {"proposed"})
        self.assertIn("MITOVER SC", {r["name"] for r in rows})  # sold as a pesticide, not in the official list

    def test_no_claiming_product_in_the_agronomist_answers(self):
        claims = _claim_names()
        for c in ("B", "Ca", "Fe", "K", "Mg", "Mn", "N", "P", "Zn"):
            for p in get_fertilizers(f"{c}_deficiency", max_products=3)["produits"]:
                self.assertFalse(any(_same_product(p["nom"], x) for x in claims), p["nom"])


class TestRule21(unittest.TestCase):
    BASE = {"task": "deficiency", "classe": "P_deficiency", "culture": "tomate", "fiable": True}

    def test_claiming_product_blocked_as_fertilizer_or_in_text(self):
        r = check_answer(dict(self.BASE, engrais=[{"nom": "ROMBI PHOS EXTRA"}], texte="- ROMBI PHOS EXTRA\n" + PPE))
        self.assertTrue(any("allégation" in x for x in r["raisons"]), r["raisons"])
        r = check_answer({"task": "diseases", "classe": "tomato__spider_mites", "culture": "tomate", "fiable": True,
                          "produits": [], "texte": "Vous pouvez essayer MITOVER SC."})
        self.assertFalse(r["valide"])
        self.assertTrue(any("allégation" in x for x in r["raisons"]), r["raisons"])


if __name__ == "__main__":
    unittest.main()
