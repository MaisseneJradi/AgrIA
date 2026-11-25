"""Phyto plan, step 2: disease -> registry target mapping (docs/disease_target_mapping.csv), prevention advice without
any product (docs/conseils_prevention.csv), Vérificateur rule 9 (no chemistry outside the registered products)."""
import csv
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.agent import paths  # noqa: F401
from src.agent.redaction import compose
from src.evaluation import eval_phyto as E
import build_db  # noqa: E402  (src/tools)
import prevention  # noqa: E402
import target_mapping as TM  # noqa: E402
from safety import chemical_terms, check_answer  # noqa: E402
from treatments import get_treatments  # noqa: E402
from tests.review_state import proposed_copy

ROOT = Path(__file__).resolve().parents[2]
USAGES = ROOT / "data" / "processed" / "pesticides" / "tn_usages.csv"
KEY = ["unified_class", "relation", "product_id", "usage_idx"]


def read_advice():
    with open(prevention.ADVICE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.usages = pd.read_csv(USAGES)
        cls.rows = TM.load(statuses=TM.STATUSES)

    def test_validated_rows_give_back_the_links_used_before(self):
        old = pd.read_csv(ROOT / "data" / "processed" / "clean" / "classe_traitements.csv")
        new = TM.usage_classes(self.usages, TM.load())
        # every link used before step 2 is given back; rows validated by the review since then add links
        self.assertLessEqual(set(map(tuple, old[KEY].values)), set(map(tuple, new[KEY].values)))

    def test_table_traitements_built_from_validated_rows_only(self):
        ct = build_db.class_treatments()
        self.assertEqual(len(ct), len(TM.usage_classes(self.usages, TM.load())))
        # "rouillle" (spelling of the list): while its row is not validated, COMET PLUS EC is not linked to leaf rust
        rows = [r for r in self.rows if r["status"] == "validated" and r["nom"] != "rouillle"]
        linked = TM.usage_classes(self.usages, rows)
        self.assertNotIn("COMET PLUS EC", set(linked.loc[linked["unified_class"] == "wheat__leaf_rust",
                                                          "nom_commercial"]))

    def test_a_row_counts_once_validated(self):
        row = next(r for r in self.rows if r["nom"] == "rouillle")
        linked = TM.usage_classes(self.usages, [dict(row, status="validated")])
        self.assertIn("COMET PLUS EC", set(linked["nom_commercial"]))

    def test_every_row_is_well_formed(self):
        self.assertTrue(all(r["status"] in TM.STATUSES for r in self.rows))
        self.assertTrue(all(r["relation"] in ("direct", "vecteur", "proche") for r in self.rows))
        for r in self.rows:
            re.compile(r["motif"])
        classes = {r["unified_class"] for r in self.rows if r["status"] == "validated"}
        self.assertEqual(len(classes), 45)  # 48 classes - 2 physiological disorders - ToMV (no vector, no target)

    def test_unknown_status_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.csv"
            shutil.copy(TM.MAPPING, p)
            text = p.read_text(encoding="utf-8").replace(",validated,", ",peut-etre,", 1)
            p.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                TM.load(p)

    def test_exclusion_and_group_relation(self):
        row = {"unified_class": "tomato__spider_mites", "crops": "tomato", "motif": "acarien", "exclure": "aculops",
               "relation": "direct"}
        self.assertIsNone(TM.row_matches(row, "tomato", "Acariens (Aculops lycopersici)"))
        self.assertEqual(TM.row_matches(row, "tomato", "Acariens"), "direct")
        self.assertEqual(TM.row_matches(row, "vegetables", "Acariens"), "groupe")
        self.assertIsNone(TM.row_matches(row, "citrus", "Acariens"))


class TestPrevention(unittest.TestCase):
    def test_only_validated_advice_is_given(self):
        with tempfile.TemporaryDirectory() as d:
            # the rows back to 'proposed': no advice is given
            p = proposed_copy(prevention.ADVICE, d)
            self.assertEqual(prevention.prevention_advice("tomato__septoria_leaf_spot", p), [])
            p = Path(d) / "c.csv"
            rows = [dict(r, status="proposed") for r in read_advice()]  # as before the review...
            rows[0]["status"] = "validated"                                # ...then one row validated
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            got = prevention.prevention_advice(rows[0]["unified_class"], p)
            self.assertEqual([g["fr"] for g in got], [rows[0]["conseil_fr"]])

    def test_advice_file_has_no_product_chemistry_or_number(self):
        rows = read_advice()
        self.assertEqual(len({r["unified_class"] for r in rows}), 28)
        for r in rows:
            self.assertEqual(chemical_terms(r["conseil_fr"]), [], r)
            self.assertFalse(re.search(r"\d", r["conseil_fr"] + r["conseil_ar"]), r)
            self.assertTrue(r["conseil_ar"].strip(), r)

    def test_quoted_sentences_are_cleaned(self):
        p = [{"langue": "fr", "extrait": "La lutte passe par les fongicides, notamment l'azoxystrobine. Des mesures de "
                                         "prévention consistent à observer une rotation des cultures sur la parcelle. "
                                         "Il faut un intervalle de 3 ans entre deux solanées sur la parcelle. "
                                         "Sur verger à risques : il faut traiter après la taille, après un gel."},
             {"langue": "en", "extrait": "Remove infected leaves and burn them as soon as possible please."}]
        self.assertEqual(prevention.cultural_sentences(p),
                         ["Des mesures de prévention consistent à observer une rotation des cultures sur la parcelle."])


class TestRule9(unittest.TestCase):
    BASE = {"task": "diseases", "classe": "tomato__late_blight", "culture": "tomate", "fiable": True}
    GOOD = {"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}

    def test_chemistry_outside_product_lines_is_blocked(self):
        r = check_answer(dict(self.BASE, produits=[], texte="Traitez au cuivre dès les premiers symptômes."))
        self.assertFalse(r["valide"])
        self.assertTrue(any("lutte chimique" in x for x in r["raisons"]), r["raisons"])
        r = check_answer(dict(self.BASE, classe="tomato__septoria_leaf_spot", produits=[],
                              texte="Aucun produit n'est homologué.\nUn fongicide peut aider."))
        self.assertFalse(r["valide"])

    def test_substances_on_the_line_of_a_registered_product_pass(self):
        text = ("- CIMOXATE C WG (Cymoxanil + Copper oxychloride) : dose 3 kg/ha (300 g/hl) ; délai avant récolte : 3 jours"
            " ; classe de toxicité OMS II (modérément dangereux)"  # rule 15, since the WHO table is validated
                "\nProtection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes\nListe DGSVCIA du 22/05/2024")  # rule 17
        r = check_answer(dict(self.BASE, produits=[self.GOOD], texte=text))
        self.assertTrue(r["valide"], r["raisons"])


class TestAnswers(unittest.TestCase):
    def test_no_product_case_gets_crda_referral_and_no_chemistry(self):
        for cls, crop in (("tomato__septoria_leaf_spot", "tomato"), ("olive__knot_disease", "olive"),
                          ("potato__early_blight", "potato")):
            c = {"crop": crop, "disease_or_deficiency": cls, "governorate": "Nabeul"}
            out, _ = E.run_case(c)
            text = out["reponse"]["texte"]
            self.assertIn("Aucun produit", text)
            self.assertIn("examen sur place", text)
            self.assertIn("CRDA de Nabeul", text)
            self.assertNotIn("Respectez la dose", text)  # no product: no dose to respect
            self.assertEqual(chemical_terms(text), [], text)
            self.assertTrue(out["reponse"]["verification"]["valide"])

    def test_product_case_keeps_its_closing_line(self):
        out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__late_blight", "governorate": "Nabeul"})
        self.assertIn("Respectez la dose", out["reponse"]["texte"])
        self.assertNotIn("examen sur place", out["reponse"]["texte"])

    def test_arabic_prevention_and_referral_written_by_code(self):
        facts = {"issue": "conseil", "diagnostic": {"classe": "tomato__mosaic_virus", "nom": "ToMV", "confiance": 90},
                 "aucun_produit": True, "orientation_crda": True, "gouvernorat": "Sousse",
                 "prevention": [{"fr": "Arrachez les plants atteints.", "ar": "اقلع النباتات المصابة."}]}
        text = compose(facts, "ar")
        self.assertIn("إجراءات وقائية", text)
        self.assertIn("اقلع النباتات المصابة.", text)
        self.assertIn("سوسة", text)
        self.assertNotIn("Arrachez", text)


if __name__ == "__main__":
    unittest.main()
