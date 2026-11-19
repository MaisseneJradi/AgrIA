import unittest

from tests.tools import _path  # noqa: F401
from common import governorate
from lexicon import crop_code, normalize_terms
from rag import search_knowledge


class TestLexicon(unittest.TestCase):
    def test_crops_in_four_writings(self):
        for name, code in [("Tomate", "tomato"), ("tomates", "tomato"), ("طماطم", "tomato"), ("tmatem", "tomato"),
                           ("felfel", "pepper"), ("zitoun", "olive"), ("palmier", "datepalm"), ("blé", "wheat"),
                           ("TOMATE SOUS SERRE", "tomato"), ("datepalm", "datepalm")]:
            self.assertEqual(crop_code(name), code, name)
        self.assertIsNone(crop_code("xyz"))

    def test_darija_message(self):
        r = normalize_terms("el tmatem fiha mildiou w wra9 msaffer")
        self.assertEqual(r["langue"], "arabizi")
        self.assertEqual([e["concept"] for e in r["cultures"]], ["tomate"])
        self.assertIn("tomato__late_blight", r["classes_possibles"])
        self.assertTrue(r["a_valider"])  # darija spellings still to be checked by a Tunisian speaker

    def test_arabic_message(self):
        r = normalize_terms("الطماطم فيها الصدى")
        self.assertEqual(r["langue"], "ar")
        self.assertEqual([e["concept"] for e in r["maladies"]], ["rouille"])

    def test_french_slash_means_alternative_word(self):
        r = normalize_terms("Mes tomates ont des taches noires sur les feuilles")
        self.assertEqual([e["concept"] for e in r["organes"]], ["feuille"])
        self.assertNotIn("chute", [e["concept"] for e in r["symptomes"]])

    def test_nothing_recognised(self):
        r = normalize_terms("bonjour")
        self.assertEqual(r["classes_possibles"], [])
        self.assertEqual(r["cultures"], [])

    def test_governorates(self):
        self.assertEqual(governorate("gabes"), "Gabès")
        self.assertEqual(governorate("صفاقس"), "Sfax")
        with self.assertRaises(ValueError):
            governorate("Paris")


class TestRag(unittest.TestCase):
    def test_passages_keep_their_source(self):
        r = search_knowledge("cycle de vie de la mineuse Tuta absoluta")
        self.assertEqual(r[0]["fiche"], "tuta_absoluta")
        for x in r:
            self.assertTrue(x["source"].startswith("http"))
            self.assertIn("licence", x)

    def test_darija_question_finds_the_sheet(self):
        self.assertEqual(search_knowledge("tmatem fiha mildiou")[0]["fiche"], "mildiou_tomate_pdt")
        self.assertEqual(search_knowledge("الصدى في القمح")[0]["fiche"], "rouille_brune_ble")

    def test_off_topic_returns_nothing(self):
        self.assertEqual(search_knowledge("recette de couscous"), [])

    def test_class_filter_and_section(self):
        r = search_knowledge("comment traiter", classe="olive__knot_disease")
        self.assertTrue(r)
        self.assertTrue(all("olive__knot_disease" in x["classes"] for x in r))
        self.assertEqual(r[0]["section"], "lutte")


if __name__ == "__main__":
    unittest.main()
