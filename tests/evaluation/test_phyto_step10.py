"""Phyto plan, step 10: shop offers in the answers (after the ranking) and the Vérificateur rules 22-26.

The mappings of docs/shop_product_mapping.csv are all 'proposed' until the reviewer validates them: the tests give a
validated row with mock.patch.object(shop, "_mapping", ...), exactly what a validated row of the CSV gives.
"""
import copy
import unittest
from unittest import mock

from src.evaluation import eval_phyto as E
from tests.evaluation.test_phyto_eval import case

import shop  # noqa: E402  (src/tools, on the path through src.agent.paths)
from safety import check_answer  # noqa: E402

GOLD = {c["case_id"]: c for c in E.read_cases()}
SCAB = GOLD["c037"]  # tomato early blight: Score 250 EC (homo-fon-107) is among the products shown
IRON = case("Fe_deficiency", "pepper", "deficiency", governorate="Tozeur", acceptable_products="nutriment:Fe")


def ids(name):
    return [sid for sid, p in shop._products().items() if p["name"] == name]


def run(c, mapping=None, lang="fr"):
    """E.run_case, with an optional validated mapping and the answer language."""
    def go():
        if lang == "fr":
            return E.run_case(c)[0]
        ctx = E.normalize_context(c)
        state = {"contexte": ctx, "photo": None, "message": "", "gouvernorat": c["governorate"], "culture": c["crop"],
                 "langue": lang, "mois": 5, "langue_reponse": lang, "culture_code": c["crop"],
                 "culture_source": "agriculteur", "gouvernorat_officiel": c["governorate"],
                 "diagnostic": E.forced_diagnosis(c["disease_or_deficiency"]), "issue": "conseil", "questions": [],
                 "essais": 0, "sources": [], "trace": []}
        return E.pipeline().invoke(state)
    if mapping is None:
        return go()
    with mock.patch.object(shop, "_mapping", lambda: mapping):
        return go()


def shop_line(out, start="En boutique pour "):
    return next((l for l in out["reponse"]["texte"].splitlines() if start in l), None)


class TestShopModule(unittest.TestCase):
    def test_summary_is_written_by_code(self):
        self.assertEqual(shop.summary(ids("CAPITOL 80 WG")[0]), "Captan 80 %, WG")
        s = shop.summary(ids("FERROSTRENE K PREMIUM")[0])
        self.assertIn("Fe 6 %", s)
        self.assertIn("chélate EDDHA", s)

    def test_registry_composition_is_what_to_ask_for(self):
        self.assertEqual(shop.registry_composition("homo-fon-048"), "Captan 80%")
        self.assertEqual(shop.registry_composition("no-such-product"), "")

    def test_no_offer_without_a_validated_row(self):
        with mock.patch.object(shop, "_mapping", lambda: {}):
            self.assertEqual(shop.pesticide_offers({"product_id": "homo-fon-048"}), [])
            self.assertEqual(shop.fertiliser_offers("Fe_deficiency", calcareous=True), [])

    def test_claim_product_is_never_an_offer(self):
        claimed = sorted(shop._claims() & set(shop._products()))
        self.assertTrue(claimed)
        with mock.patch.object(shop, "_mapping", lambda: {"homo-fon-048": claimed[:3]}):
            self.assertEqual(shop.pesticide_offers({"product_id": "homo-fon-048"}), [])

    def test_offers_are_capped_and_filtered_by_registered_name(self):
        sid = ids("CAPITOL 80 WG")
        with mock.patch.object(shop, "_mapping", lambda: {"homo-fon-048": sid}):
            self.assertEqual([o["nom"] for o in shop.pesticide_offers({"product_id": "homo-fon-048"})],
                             ["CAPITOL 80 WG"])
            self.assertEqual(shop.pesticide_offers({"product_id": "homo-fon-048"}, lambda name: False), [])


class TestAnswers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capitol = {"homo-fon-107": ids("Score 250 EC")}
        cls.iron = ids("FERROSTRENE K PREMIUM") + ids("ULTRAFERRO 5 KG")
        cls.scab_real = run(SCAB)
        cls.scab_shop = run(SCAB, cls.capitol)
        cls.iron_real = run(IRON)
        cls.iron_shop = run(IRON, {"besoin:Fe_deficiency": cls.iron, "besoin:Fe_deficiency:calcaire": cls.iron})

    def test_without_mapping_the_answer_says_what_to_ask_for(self):
        out = self.scab_real
        self.assertTrue(out["reponse"]["verification"]["valide"], out["reponse"]["verification"]["raisons"])
        self.assertIn("Pour Score 250 EC : non trouvé sur agrishop.tn : demandez un produit à base de Difenoconazole 250 g/L",
                      out["reponse"]["texte"])
        self.assertIsNone(shop_line(out))

    def test_validated_offer_line(self):
        out = self.scab_shop
        self.assertTrue(out["reponse"]["verification"]["valide"], out["reponse"]["verification"]["raisons"])
        line = shop_line(out)
        self.assertEqual(line.strip(), "En boutique pour Score 250 EC : Score 250 EC (Difenoconazole 250 g/l, EC) — en stock — "
                                       "agrishop.tn (adresse de la page non disponible)")

    def test_offers_do_not_change_the_ranking(self):
        names = [p["nom"] for p in self.scab_real["traitements"]["produits"]]
        self.assertEqual([p["nom"] for p in self.scab_shop["traitements"]["produits"]], names)

    def test_fertiliser_need_without_mapping(self):
        text = self.iron_real["reponse"]["texte"]
        self.assertIn("Besoin : un apport de fer (Fe) ; sur sol calcaire, un chélate EDDHA", text)
        self.assertIn("Non trouvé sur agrishop.tn ni agriclic.tn : demandez un produit à base de fer (Fe), en chélate",
                      text)
        self.assertTrue(self.iron_real["reponse"]["verification"]["valide"])
        self.assertEqual(E.score(IRON, self.iron_real, 1)["unsafe"], "")

    def test_fertiliser_offers_with_mapping(self):
        out = self.iron_shop
        text = out["reponse"]["texte"]
        self.assertTrue(out["reponse"]["verification"]["valide"], out["reponse"]["verification"]["raisons"])
        self.assertIn("FERROSTRENE K PREMIUM (Fe 6 %, chélate EDDHA)", text)
        # the dose ranges are 'proposed': no manufacturer's dose is shown before they are validated
        self.assertNotIn("Dose indiquée par le fabricant", text)
        self.assertIn("Dose : suivez l'étiquette / demandez au CRDA", text)
        self.assertTrue(E.score(IRON, out, 1)["fert_ok"])

    def test_arabic(self):
        out = run(SCAB, self.capitol, "ar")
        self.assertTrue(out["reponse"]["verification"]["valide"], out["reponse"]["verification"]["raisons"])
        line = shop_line(out, "في المتجر لـ")
        self.assertIn("Score 250 EC (Difenoconazole 250 g/l, EC)", line)
        self.assertIn("(رابط الصفحة غير متوفر)", line)
        out = run(IRON, {"besoin:Fe_deficiency": self.iron, "besoin:Fe_deficiency:calcaire": self.iron}, "ar")
        self.assertTrue(out["reponse"]["verification"]["valide"], out["reponse"]["verification"]["raisons"])
        self.assertIn("FERROSTRENE K PREMIUM (Fe 6 %, مخلّب EDDHA)", out["reponse"]["texte"])
        self.assertNotIn("chélate", out["reponse"]["texte"])
        out = run(SCAB, {}, "ar")
        self.assertIn("غير موجود في agrishop.tn: اطلب منتجًا يحتوي على Difenoconazole 250 g/L", out["reponse"]["texte"])


class TestRules22to26(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capitol = {"homo-fon-107": ids("Score 250 EC")}
        cls.scab = run(SCAB, cls.capitol)
        cls.iron = ids("FERROSTRENE K PREMIUM")
        cls.fe = {"besoin:Fe_deficiency": cls.iron, "besoin:Fe_deficiency:calcaire": cls.iron}
        cls.iron_out = run(IRON, cls.fe)

    def check(self, out, text, mapping):
        a = copy.deepcopy(out["brouillon"])
        a["texte"] = text
        with mock.patch.object(shop, "_mapping", lambda: mapping):
            return check_answer(a)

    def assertBlocked(self, r, word):
        self.assertFalse(r["valide"])
        self.assertTrue(any(word in x for x in r["raisons"]), r["raisons"])

    def test_untouched_answer_passes(self):
        self.assertTrue(self.check(self.scab, self.scab["brouillon"]["texte"], self.capitol)["valide"])

    def test_22_unknown_shop_address(self):
        text = self.scab["brouillon"]["texte"] + "\nhttps://www.agriclic.tn/999-produit-invente.html"
        self.assertBlocked(self.check(self.scab, text, self.capitol), "adresse de boutique inconnue")

    def test_23_link_without_validated_mapping(self):
        self.assertBlocked(self.check(self.scab, self.scab["brouillon"]["texte"], {}), "sans correspondance validée")

    def test_23_fertiliser_without_validated_mapping(self):
        self.assertBlocked(self.check(self.iron_out, self.iron_out["brouillon"]["texte"], {}),
                           "engrais sans correspondance validée")

    def test_24_other_substance_or_concentration(self):
        other = ids("CAPITOL 80 WG")
        text = self.scab["brouillon"]["texte"].replace(": Score 250 EC (Difenoconazole 250 g/l, EC)",
                                                       ": CAPITOL 80 WG (Captan 80 %, WG)")
        self.assertBlocked(self.check(self.scab, text, {"homo-fon-107": other}), "différentes de Score 250 EC")

    def test_25_dose_on_a_shop_line(self):
        text = self.scab["brouillon"]["texte"].replace("(Difenoconazole 250 g/l, EC)", "(Difenoconazole 250 g/l, EC, 0,5 l/ha)")
        self.assertBlocked(self.check(self.scab, text, self.capitol), "dose écrite sur une ligne de boutique")

    def test_25_shop_line_for_a_product_not_in_the_answer(self):
        text = self.scab["brouillon"]["texte"] + "\nEn boutique pour SUPERFONGI : Score 250 EC"
        self.assertBlocked(self.check(self.scab, text, self.capitol), "sans produit homologué")

    def test_26_manufacturer_dose_not_validated(self):
        text = self.iron_out["brouillon"]["texte"].replace("Dose : suivez l'étiquette / demandez au CRDA",
                                                           "Dose indiquée par le fabricant : 99 kg/ha", 1)
        self.assertIn("99 kg/ha", text)
        self.assertBlocked(self.check(self.iron_out, text, self.fe), "dose du fabricant non validée")


if __name__ == "__main__":
    unittest.main()
