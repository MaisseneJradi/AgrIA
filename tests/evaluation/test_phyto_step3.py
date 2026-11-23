"""Phyto plan, step 3: context of the plot (state, Linguistique, API), filters and ranking (src/tools/ranking.py),
reasons and questions written by code, Vérificateur rules 10-12."""
import os
import unittest

os.environ.setdefault("AGRIA_DEVICE", "cpu")

from fastapi import HTTPException  # noqa: E402

from src.agent import paths  # noqa: F401,E402
from src.agent.agents.linguistique import context_from_message, normalize_context  # noqa: E402
from src.agent.redaction import compose  # noqa: E402
from src.api.main import _context  # noqa: E402
from src.evaluation import eval_phyto as E  # noqa: E402
import ranking as R  # noqa: E402  (src/tools)
from safety import chemical_terms, check_answer  # noqa: E402
from treatments import get_treatments, readable_name  # noqa: E402


def use(name, dar=None, bio=False, ue=True, relation="direct", subs="X"):
    return {"produit": name, "dar_jours": dar, "bio_ue": bio, "ue_approuve": ue, "relation": relation,
            "substances": subs}


class TestRanking(unittest.TestCase):
    def test_dar_longer_than_harvest_is_set_aside(self):
        r = R.rank([use("A", dar=14), use("B", dar=3), use("C")], {"days_to_harvest": 7})
        self.assertEqual([u["produit"] for u in r["retenus"]], ["B", "C"])  # known short DAR before unknown
        self.assertEqual(r["ecartes"], [{"produit": "A", "raisons": ["dar_long"]}])

    def test_unknown_dar_set_aside_when_every_known_dar_of_the_product_is_too_long(self):
        r = R.rank([use("A", dar=21), use("A"), use("B")], {"days_to_harvest": 7})
        self.assertEqual([u["produit"] for u in r["retenus"]], ["B"])

    def test_export_and_organic_filters(self):
        uses = [use("A", ue=False), use("B", ue=None), use("C", ue=True, bio=True), use("D", ue=True)]
        self.assertEqual([u["produit"] for u in R.rank(uses, {"market": "export"})["retenus"]], ["C", "D"])
        self.assertEqual([u["produit"] for u in R.rank(uses, {"organic": "y"})["retenus"]], ["C"])
        causes = {e["produit"]: e["raisons"] for e in R.rank(uses, {"market": "export"})["ecartes"]}
        self.assertEqual(causes, {"A": ["non_ue"], "B": ["ue_inconnu"]})

    def test_early_stage_puts_organic_first_and_relation_stays_first(self):
        uses = [use("A", dar=1), use("B", dar=10, bio=True), use("C", bio=True, relation="groupe")]
        self.assertEqual([u["produit"] for u in R.rank(uses, {})["retenus"]], ["A", "B", "C"])
        self.assertEqual([u["produit"] for u in R.rank(uses, {"stage": "early"})["retenus"]], ["B", "A", "C"])

    def test_reasons_are_codes(self):
        top = R.rank([use("B", dar=3, bio=True)], {"stage": "early", "days_to_harvest": 7, "market": "export"})
        self.assertEqual(top["retenus"][0]["raisons"],
                         [("relation", "direct"), ("bio_debut",), ("dar", 3, 7), ("ue",)])

    def test_questions_only_when_the_answer_changes(self):
        uses = [use("A", dar=14), use("B", dar=3), use("C", bio=True), use("D", dar=1, ue=False)]
        q = R.decisive_fields(uses, {})
        self.assertEqual(q, ["days_to_harvest", "market", "organic"])  # at most 3, in order
        # a product not approved in the EU but outside the top 3 would not change the answer: no market question
        self.assertNotIn("market", R.decisive_fields(uses[:3] + [use("E", ue=False)], {}))
        self.assertEqual(R.decisive_fields(uses, {"days_to_harvest": 30, "market": "local", "organic": "n"}),
                         ["stage"])
        same = [use("A", dar=1, bio=True), use("B", dar=1, bio=True)]  # nothing would change: no question
        self.assertEqual(R.decisive_fields(same, {}), [])

    def test_no_moa_data_no_rotation_question(self):
        self.assertNotIn("last_treatment_group", R.decisive_fields([use("A"), use("B", dar=2)], {}))


class TestContext(unittest.TestCase):
    def test_message(self):
        self.assertEqual(context_from_message("Je récolte dans 5 jours, c'est pour l'export"),
                         {"market": "export", "days_to_harvest": 5})
        self.assertEqual(context_from_message("nhassad ba3d 2 jmo3a, ana bio")["days_to_harvest"], 14)
        self.assertEqual(context_from_message("ana bio")["organic"], "y")
        self.assertEqual(context_from_message("pas en bio")["organic"], "n")
        self.assertEqual(context_from_message("الجني بعد ٣ أيام")["days_to_harvest"], 3)
        # a number that is not the harvest is never taken as one
        self.assertNotIn("days_to_harvest", context_from_message("taches depuis 10 jours, la récolte sera bientôt"))
        self.assertNotIn("greenhouse", context_from_message("la récolte sera bonne"))

    def test_form_values(self):
        self.assertEqual(normalize_context({"days_to_harvest": "7", "market": "export", "organic": "oui",
                                            "greenhouse": "non", "stage": "début", "area": "0,5"}),
                         {"days_to_harvest": 7, "market": "export", "organic": "y", "greenhouse": "n",
                          "stage": "early", "area": 0.5})
        self.assertEqual(normalize_context({"days_to_harvest": "beaucoup", "market": "chine"}), {})

    def test_api_checks_the_values(self):
        self.assertEqual(_context(7, "export", "oui", None, "early", " Ortiva ", None),
                         {"market": "export", "organic": "oui", "stage": "early", "days_to_harvest": 7,
                          "last_treatment_group": "Ortiva"})
        for bad in ((400, None, None, None, None, None, None), (None, "chine", None, None, None, None, None),
                    (None, None, "peut-etre", None, None, None, None), (None, None, None, None, None, None, -1)):
            with self.assertRaises(HTTPException):
                _context(*bad)


class TestRules10to12(unittest.TestCase):
    BASE = {"task": "diseases", "classe": "tomato__late_blight", "culture": "tomate", "fiable": True}
    GOOD = {"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}
    TEXT = ("- CIMOXATE C WG (Cymoxanil + Copper oxychloride) : dose 3 kg/ha (300 g/hl) ; délai avant récolte : 3 jours"
            "\nProtection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes")

    def check(self, **ctx):
        return check_answer(dict(self.BASE, produits=[self.GOOD], texte=self.TEXT, contexte=ctx))

    def test_dar_longer_than_harvest_blocked(self):
        self.assertTrue(self.check(days_to_harvest=7)["valide"])
        r = self.check(days_to_harvest=1)
        self.assertFalse(r["valide"])
        self.assertTrue(any("plus long" in x for x in r["raisons"]), r["raisons"])

    def test_export_and_organic(self):
        usage = next(u for u in get_treatments("tomato__late_blight", "tomate") if u["produit"] == "CIMOXATE C WG")
        self.assertEqual(self.check(market="export")["valide"], bool(usage["ue_approuve"]))
        self.assertFalse(self.check(organic="y")["valide"])  # cymoxanil is not allowed in organic farming


class TestAnswers(unittest.TestCase):
    def test_reasons_written_below_each_product_and_no_chemistry_in_them(self):
        out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__late_blight", "governorate": "Nabeul",
                             "days_to_harvest": "7", "stage": "early", "market": "local", "organic": "n"})
        text = out["reponse"]["texte"]
        self.assertTrue(out["reponse"]["verification"]["valide"], out["reponse"]["verification"])
        why = [line for line in text.splitlines() if line.strip().startswith("Pourquoi")]
        self.assertEqual(len(why), len(out["reponse"]["produits"]))
        self.assertEqual(chemical_terms("\n".join(why)), [])
        for p in out["traitements"]["produits"]:
            self.assertTrue(p["dar_jours"] is None or p["dar_jours"] <= 7)

    def test_missing_context_gives_questions_not_a_refusal(self):
        out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__late_blight", "governorate": "Nabeul"})
        r = out["reponse"]
        self.assertTrue(r["produits"])  # the safe ranked list is always given
        self.assertTrue(1 <= len(r["questions_contexte"]) <= 3)
        self.assertIn("Pour affiner ma réponse", r["texte"])
        self.assertIn("Dans combien de jours pensez-vous récolter ?", r["texte"])

    def test_nothing_fits_says_why_and_sends_to_crda(self):
        out, _ = E.run_case({"crop": "apple", "disease_or_deficiency": "apple__scab", "governorate": "Kasserine",
                             "days_to_harvest": "0", "organic": "y"})
        r = out["reponse"]
        if not r["produits"]:
            self.assertIn("ne convient à votre situation", r["texte"])
            self.assertIn("examen sur place", r["texte"])
        self.assertTrue(r["verification"]["valide"])

    def test_arabic_reasons_and_questions(self):
        facts = {"issue": "conseil", "diagnostic": {"classe": "tomato__late_blight", "nom": "Mildiou", "confiance": 90},
                 "produits": [{"nom": "X WG", "substances": "S", "dose": "1 kg/ha", "dar_jours": 3,
                               "raisons": [("relation", "direct"), ("dar", 3, 7)]}],
                 "contexte": {"days_to_harvest": 7}, "ecartes": [{"produit": "Y", "raisons": ["dar_long"]}],
                 "questions_contexte": ["market"]}
        text = compose(facts, "ar")
        self.assertIn("لماذا: مصادق عليه ضد هذه المشكلة على زراعتك؛ مدة قبل الجني 3 أيام", text)
        self.assertIn("أطول من 7 يومًا", text)
        self.assertIn("هل محصولك موجّه للتصدير", text)

    def test_end_to_end_with_a_photo_and_the_form_context(self):
        from src.agent.graph import diagnose
        photo = "data/processed/diseases/test/tomato__late_blight/tomato__late_blight_01622.jpg"
        r = diagnose(photo, "récolte dans 2 jours", "Nabeul", culture="tomato", contexte={"market": "local"})
        self.assertEqual(r["contexte"], {"days_to_harvest": 2, "market": "local"})  # message + form
        self.assertTrue(r["verification"]["valide"])
        for p in r["produits"]:
            self.assertTrue(p["dar_jours"] is None or p["dar_jours"] <= 2, p)
        self.assertTrue(any("contexte : days_to_harvest=2" in t["action"] for t in r["trace"]))

    def test_misread_trade_names_are_never_advised(self):
        self.assertFalse(readable_name("50"))
        self.assertFalse(readable_name("SC"))
        self.assertTrue(readable_name("T-77 WP"))
        self.assertNotIn("50", {u["produit"] for u in get_treatments("potato__late_blight", "potato")})


if __name__ == "__main__":
    unittest.main()
