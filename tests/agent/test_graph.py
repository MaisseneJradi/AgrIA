"""End-to-end tests of the six agents on real test photos (models on CPU, template LLM: no network)."""
import os
import unittest
from unittest import mock

os.environ.setdefault("AGRIA_DEVICE", "cpu")  # leave the GPU to trainings

from src.agent.graph import diagnose  # noqa: E402
from src.agent.redaction import compose  # noqa: E402

P = "data/processed/{}/test/{}/{}.jpg"
OTHER = P.format("routing", "other", "other_03785")
LATE_BLIGHT = P.format("diseases", "tomato__late_blight", "tomato__late_blight_01622")
MOSAIC = P.format("diseases", "tomato__mosaic_virus", "tomato__mosaic_virus_00316")
HEALTHY = P.format("diseases", "tomato__healthy", "tomato__healthy_01351")
FE_PEPPER = P.format("deficiency", "Fe_deficiency", "Fe_deficiency_00957")
POMEGRANATE = P.format("fruits", "pomegranate__anthracnose", "pomegranate__anthracnose_00991")

AGENTS = {"Coordinateur", "Linguistique", "Identification", "Diagnostic", "Phytosanitaire", "Agronome",
          "Vérificateur"}


def agents_of(r):
    return {t["agent"] for t in r["trace"]}


class TestAgents(unittest.TestCase):
    def test_disease_with_registered_products(self):
        r = diagnose(LATE_BLIGHT, "tmatem fiha mildiou, chnowa na3mel ?", "Nabeul")
        self.assertEqual(r["issue"], "conseil")
        self.assertEqual(r["diagnostic"]["classe"], "tomato__late_blight")
        self.assertTrue(r["produits"])
        self.assertTrue(r["verification"]["valide"])
        self.assertEqual(agents_of(r), AGENTS)  # the seven agents took part
        self.assertTrue(all(p["nom"] in r["texte"] for p in r["produits"]))
        self.assertTrue(r["sources"])

    def test_other_photo_and_no_photo(self):
        self.assertEqual(diagnose(OTHER, "chnowa hadha ?")["issue"], "autre_photo")
        r = diagnose(None, "ma tomate a des taches")
        self.assertEqual(r["issue"], "autre_photo")
        self.assertIn("besoin d'une photo", r["texte"])

    def test_no_registered_product_is_said_not_invented(self):
        r = diagnose(MOSAIC, "", "Sousse", culture="tomato")
        self.assertEqual(r["produits"], [])
        self.assertIn("Aucun produit", r["texte"])
        self.assertTrue(r["verification"]["valide"])

    def test_healthy_plant_gets_no_product_but_water(self):
        r = diagnose(HEALTHY, "", "Nabeul", culture="tomato", mois=5)
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
        self.assertEqual(r["produits"], [])  # never a pesticide for a deficiency
        if r["diagnostic"]["fiable"]:
            self.assertTrue(r["engrais"])
        else:  # below the 0.95 threshold of deficiencies: confirmation questions first, no fertilizer yet
            self.assertEqual(r["engrais"], [])
            self.assertTrue(r["questions"])

    def test_deficiency_model_never_overrides_a_diseased_leaf(self):
        # without words about a deficiency, the disease model decides (the deficiency model never saw diseased leaves)
        r = diagnose(LATE_BLIGHT, "", "Nabeul")
        self.assertEqual(r["diagnostic"]["task"], "diseases")

    def test_named_crop_restricts_the_diagnosis(self):
        r = diagnose(LATE_BLIGHT, "", "Nabeul", culture="tomate")
        # only tomato classes, plus the deficiencies when the single leaf model is used (not tied to a crop)
        self.assertTrue(all(c.startswith("tomato__") or c.endswith("_deficiency") for c, _ in r["diagnostic"]["top3"]))

    def test_crop_not_given_is_proposed_not_imposed(self):
        r = diagnose(LATE_BLIGHT, "", "Nabeul")  # no crop: the agent proposes "tomato" but asks to confirm it
        self.assertEqual(r["issue"], "question")
        self.assertEqual(r["produits"], [])
        self.assertEqual(r["culture"]["proposee"], "tomato")
        r = diagnose(LATE_BLIGHT, "", "Nabeul", culture="tomato")  # confirmed by the farmer: full diagnosis
        self.assertEqual(r["issue"], "conseil")
        self.assertEqual(r["diagnostic"]["classe"], "tomato__late_blight")

    def test_fruit_photo_uses_the_fruit_model(self):
        r = diagnose(POMEGRANATE, "الرمان فيه بقع", "Gabès")
        self.assertEqual(r["diagnostic"]["task"], "fruits")

    def test_arabizi_message_gets_an_arabic_answer_with_arabic_questions(self):
        # "msafra" (yellow) is a deficiency word of the lexicon: the deficiency model is used; Fe never seen on olive
        r = diagnose(FE_PEPPER, "zitouna msafra", "Kairouan", culture="olivier", mois=6)
        self.assertEqual(r["langue"], "ar")
        self.assertIn("هل تلاحظ", r["texte"])  # confirmation questions in Arabic (written in code)
        self.assertNotIn("Voyez-vous", r["texte"])
        self.assertTrue(r["verification"]["valide"])

    def test_arabic_answer_facts_written_by_code(self):
        r = diagnose(LATE_BLIGHT, "الطماطم فيها مرض")
        self.assertEqual(r["langue"], "ar")
        self.assertIn("التشخيص", r["texte"])
        self.assertIn("بالفرنسية", r["texte"])  # sheets given as links, not translated
        self.assertIn("https://", r["texte"])
        self.assertTrue(r["verification"]["valide"])
        for p in r["produits"]:  # each dose stays on the line of its product
            self.assertTrue(any(p["nom"] in line and p["dose"] in line for line in r["texte"].splitlines()))


def rogue_compose(facts, lang="fr"):
    """A faulty writer that slips an unregistered product into every answer, even the CRDA one."""
    return compose(facts, lang) + "\nEssayez MITOVER SC."


class TestVerifierLoop(unittest.TestCase):
    def test_unregistered_product_is_always_blocked_and_the_graph_ends(self):
        with mock.patch("src.agent.agents.linguistique.compose", side_effect=rogue_compose):
            r = diagnose(LATE_BLIGHT, "الطماطم مريضة", "Nabeul")  # Arabic: the answer is rewritten by linguistique
        blocked = [t for t in r["trace"] if t["agent"] == "Vérificateur" and "bloquée" in t["action"]]
        self.assertEqual(len(blocked), 4)  # first answer + 2 rewrites + the CRDA message, all blocked
        self.assertNotIn("MITOVER", r["texte"])
        self.assertIn("CRDA", r["texte"])
        self.assertEqual(r["produits"], [])
        self.assertTrue(r["verification"].get("secours"))  # fixed last-resort text

    def test_blocked_crda_message_goes_to_the_fixed_text(self):
        from src.agent.graph import _after_check
        self.assertEqual(_after_check({"verification": {"valide": False}, "issue": "crda", "essais": 4}), "secours")


if __name__ == "__main__":
    unittest.main()
