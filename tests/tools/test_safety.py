import unittest

from tests.tools import _path  # noqa: F401
from safety import check_answer

# line required with any pesticide since phyto step 6 (rule 17)
PPE = "Protection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes"
BASE = {"task": "diseases", "classe": "tomato__late_blight", "culture": "tomate", "fiable": True}
GOOD = {"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}


class TestSafety(unittest.TestCase):
    def assertBlocked(self, answer, word):
        r = check_answer(answer)
        self.assertFalse(r["valide"])
        self.assertTrue(any(word in x for x in r["raisons"]), r["raisons"])

    def test_registered_answer_passes(self):
        r = check_answer(dict(BASE, produits=[GOOD], texte="Traitez avec CIMOXATE C WG, dose 3 kg/ha (300 g/hl).\n"
                                                           + PPE))
        self.assertTrue(r["valide"], r["raisons"])
        self.assertEqual(r["produits_verifies"][0]["product_id"], "homo-fon-092")

    def test_blocks_unregistered_product(self):
        self.assertBlocked(dict(BASE, produits=[{"nom": "MITOVER SC"}]), "homologué")

    def test_blocks_unregistered_product_named_in_text_only(self):
        self.assertBlocked(dict(BASE, texte="Vous pouvez aussi utiliser Minecto Pro."), "texte cite")

    def test_ordinary_word_is_not_a_product(self):
        self.assertTrue(check_answer(dict(BASE, texte="L'impact du mildiou est fort."))["valide"])

    def test_blocks_product_on_unregistered_crop(self):
        self.assertBlocked(dict(BASE, culture="piment", produits=[GOOD]), "piment")

    def test_blocks_wrong_dose(self):
        self.assertBlocked(dict(BASE, produits=[dict(GOOD, dose="5 kg/ha")]), "dose")

    def test_blocks_dose_changed_in_the_text(self):
        self.assertBlocked(dict(BASE, produits=[GOOD], texte="CIMOXATE C WG : 3 كغ/هكتار (300 جم/لتر)"), "modifiée")
        shuffled = "3 kg/ha (300 g/hl) : CYCLO MAX SC\nCIMOXATE C WG : 300 cc/hl"  # dose moved to another product
        self.assertBlocked(dict(BASE, produits=[GOOD], texte=shuffled), "séparée")

    def test_blocks_wrong_or_invented_dar(self):
        self.assertBlocked(dict(BASE, produits=[dict(GOOD, dar_jours=7)]), "délai")
        no_dar = {"task": "diseases", "classe": "squash__powdery_mildew", "culture": "concombre", "fiable": True,
                  "produits": [{"nom": "Flint", "dar_jours": 3}]}
        self.assertBlocked(no_dar, "inventé")
        ok = check_answer(dict(no_dar, produits=[{"nom": "Flint"}]))
        self.assertTrue(any("étiquette" in w for w in ok["avertissements"]))

    def test_blocks_products_for_healthy_or_unreliable(self):
        self.assertBlocked({"task": "diseases", "classe": "tomato__healthy", "fiable": True, "produits": [GOOD]}, "saine")
        self.assertBlocked(dict(BASE, fiable=False, produits=[GOOD]), "non fiable")

    def test_class_without_product_and_honest_text_passes(self):
        r = check_answer({"task": "diseases", "classe": "tomato__mosaic_virus", "fiable": True,
                          "texte": "Aucun produit ne guérit la mosaïque : arrachez les plants atteints."})
        self.assertTrue(r["valide"])

    def test_deficiency_on_unseen_crop_must_be_a_hypothesis(self):
        a = {"task": "deficiency", "classe": "Fe_deficiency", "culture": "olivier", "fiable": True,
             "engrais": [{"nom": "Sequestrene 138 FE"}]}
        self.assertBlocked(a, "hypothèse")
        self.assertTrue(check_answer(dict(a, hypothese=True))["valide"])

    def test_blocks_invented_fertilizer(self):
        self.assertBlocked({"task": "deficiency", "classe": "Fe_deficiency", "culture": "piment", "fiable": True,
                            "engrais": [{"nom": "SuperFer 3000"}]}, "catalogue")

    def test_vector_and_provisional_warnings(self):
        r = check_answer({"task": "diseases", "classe": "tomato__yellow_leaf_curl_virus", "culture": "tomate",
                          "fiable": True, "produits": [{"nom": "LYNO EC"}]})
        self.assertTrue(r["valide"])
        self.assertTrue(any("insecte" in w for w in r["avertissements"]))
        r = check_answer({"task": "diseases", "classe": "tomato__spider_mites", "culture": "tomate", "fiable": True,
                          "produits": [{"nom": "VALMEC EC"}]})
        self.assertTrue(any("provisoire" in w for w in r["avertissements"]))


if __name__ == "__main__":
    unittest.main()
