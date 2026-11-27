"""React plan, A2: the answer cut into cards. compose() is the cards joined: the text the Vérificateur checks is
unchanged; answer_cards() gives the cards only when they are exactly that text."""
import os
import unittest

os.environ.setdefault("AGRIA_METEO", "0")

from src.agent.redaction import answer_cards, compose, compose_sections, join_sections  # noqa: E402
from src.evaluation import eval_phyto as E  # noqa: E402


class TestCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = E.read_cases()[:30]

    def test_cards_join_into_the_text_and_carry_the_shop_links(self):
        seen = set()
        for c in self.cases:
            out, _ = E.run_case(c)
            r = out["reponse"]
            self.assertEqual(join_sections(r["cartes"]), r["texte"], c["case_id"])
            self.assertNotEqual(r["cartes"][0]["type"], "texte")  # the real cards, not the fallback
            for card in r["cartes"]:
                seen.add(card["type"])
                if card.get("elements") is not None:
                    self.assertEqual(card["texte"], card["titre"] + "\n" + "\n".join(f"- {x}" for x in card["elements"]))
                for p in card.get("produits") or []:
                    self.assertEqual(p["lignes"][0]["role"], "produit")
                    for line in p["lignes"]:
                        self.assertIn(line["texte"], card["texte"])
        self.assertTrue({"diagnostic", "traitements", "securite"} <= seen, seen)

    def test_fallback_when_the_text_is_not_the_cards(self):
        facts = {"issue": "crda", "gouvernorat": "Sfax"}
        text = compose(facts, "fr")
        self.assertEqual([c["type"] for c in answer_cards(facts, "fr", text)], ["crda"])
        fixed = "Je ne peux pas vous conseiller de produit pour ce cas."
        self.assertEqual(answer_cards(facts, "fr", fixed), [{"type": "texte", "texte": fixed}])
        self.assertEqual(answer_cards(None, "fr", fixed), [{"type": "texte", "texte": fixed}])
        self.assertEqual(join_sections(compose_sections(facts, "ar")), compose(facts, "ar"))


if __name__ == "__main__":
    unittest.main()
