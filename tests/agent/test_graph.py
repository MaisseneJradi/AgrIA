"""End-to-end tests of the six agents on real test photos (models on CPU, template LLM: no network)."""
import os
import unittest
from unittest import mock

os.environ.setdefault("AGRIA_DEVICE", "cpu")  # leave the GPU to trainings

from src.agent.graph import diagnose  # noqa: E402
from src.agent.llm import TemplateLLM  # noqa: E402

P = "data/processed/{}/test/{}/{}.jpg"
OTHER = P.format("routing", "other", "other_03785")
LATE_BLIGHT = P.format("diseases", "tomato__late_blight", "tomato__late_blight_01622")
MOSAIC = P.format("diseases", "tomato__mosaic_virus", "tomato__mosaic_virus_00316")
HEALTHY = P.format("diseases", "tomato__healthy", "tomato__healthy_01351")
FE_PEPPER = P.format("deficiency", "Fe_deficiency", "Fe_deficiency_00957")
POMEGRANATE = P.format("fruits", "pomegranate__anthracnose", "pomegranate__anthracnose_00991")

AGENTS = {"Coordinateur", "Linguistique", "Diagnostic", "Phytosanitaire", "Agronome", "Vérificateur"}


def agents_of(r):
    return {t["agent"] for t in r["trace"]}


class TestAgents(unittest.TestCase):
    def test_disease_with_registered_products(self):
        r = diagnose(LATE_BLIGHT, "tmatem fiha mildiou, chnowa na3mel ?", "Nabeul")
        self.assertEqual(r["issue"], "conseil")
        self.assertEqual(r["diagnostic"]["classe"], "tomato__late_blight")
        self.assertTrue(r["produits"])
        self.assertTrue(r["verification"]["valide"])
        self.assertEqual(agents_of(r), AGENTS)  # the six agents took part
        self.assertTrue(all(p["nom"] in r["texte"] for p in r["produits"]))
        self.assertTrue(r["sources"])

    def test_other_photo_and_no_photo(self):
        self.assertEqual(diagnose(OTHER, "chnowa hadha ?")["issue"], "autre_photo")
        r = diagnose(None, "ma tomate a des taches")
        self.assertEqual(r["issue"], "autre_photo")
        self.assertIn("besoin d'une photo", r["texte"])

    def test_no_registered_product_is_said_not_invented(self):
        r = diagnose(MOSAIC, "", "Sousse")
        self.assertEqual(r["produits"], [])
        self.assertIn("Aucun produit", r["texte"])
        self.assertTrue(r["verification"]["valide"])

    def test_healthy_plant_gets_no_product_but_water(self):
        r = diagnose(HEALTHY, "", "Nabeul", mois=5)
        self.assertEqual(r["produits"], [])
        self.assertIn("saine", r["texte"])
        self.assertIn("Irrigation", r["texte"])

    def test_crop_contradiction_asks_questions(self):
        r = diagnose(LATE_BLIGHT, "mon olivier est malade", culture="olivier")
        self.assertEqual(r["issue"], "question")
        self.assertEqual(r["produits"], [])
        self.assertTrue(r["questions"])

    def test_deficiency_goes_to_the_agronomist(self):
        r = diagnose(FE_PEPPER, "felfel msaffer", "Kairouan", mois=6)
        self.assertEqual(r["diagnostic"]["task"], "deficiency")
        self.assertTrue(r["engrais"])
        self.assertEqual(r["produits"], [])

    def test_fruit_photo_uses_the_fruit_model(self):
        r = diagnose(POMEGRANATE, "الرمان فيه بقع", "Gabès")
        self.assertEqual(r["diagnostic"]["task"], "fruits")

    def test_language_without_llm_stays_french_and_says_so(self):
        r = diagnose(LATE_BLIGHT, "الطماطم فيها مرض")
        self.assertEqual(r["langue"], "fr")
        self.assertTrue(any("indisponible sans LLM" in t["action"] for t in r["trace"]))


class RogueLLM(TemplateLLM):
    """An LLM that slips an unregistered product into every answer."""
    name = "rogue"

    def write(self, task, data):
        text = super().write(task, data)
        return text if task == "traduire" else text + "\nVous pouvez aussi pulvériser MITOVER SC."


class TestVerifierLoop(unittest.TestCase):
    def test_unregistered_product_from_the_llm_ends_at_the_crda(self):
        rogue = RogueLLM()
        with mock.patch("src.agent.agents.coordinateur.get_llm", return_value=rogue), \
                mock.patch("src.agent.agents.linguistique.get_llm", return_value=rogue):
            r = diagnose(LATE_BLIGHT, "", "Nabeul")
        blocked = [t for t in r["trace"] if t["agent"] == "Vérificateur" and "bloquée" in t["action"]]
        self.assertEqual(len(blocked), 3)  # first answer + 2 rewrites, all blocked
        self.assertEqual(r["issue"], "crda")
        self.assertEqual(r["produits"], [])
        self.assertIn("CRDA de Nabeul", r["texte"])
        self.assertNotIn("Vous pouvez aussi pulvériser MITOVER SC", r["texte"].split("CRDA")[0] + "")


if __name__ == "__main__":
    unittest.main()


class RogueTranslator(TemplateLLM):
    """An LLM whose translation always adds an unregistered product, even to the CRDA message."""
    name = "rogue-translator"

    def write(self, task, data):
        text = super().write(task, data)
        return text + " Essayez MITOVER SC." if task == "traduire" else text


class TestLastResort(unittest.TestCase):
    def test_graph_always_ends_with_a_safe_text(self):
        rogue = RogueTranslator()
        with mock.patch("src.agent.agents.coordinateur.get_llm", return_value=rogue), \
                mock.patch("src.agent.agents.linguistique.get_llm", return_value=rogue):
            r = diagnose(LATE_BLIGHT, "الطماطم مريضة", "Nabeul")  # Arabic: the answer goes through translation
        self.assertNotIn("MITOVER", r["texte"])
        self.assertIn("CRDA", r["texte"])
        self.assertTrue(r["verification"].get("secours"))
