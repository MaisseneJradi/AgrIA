"""Phyto plan, step 11: sheets cut into sections, hybrid retrieval (BM25 + local vectors), citations (rule 27)."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from tests.tools import _path  # noqa: F401
import rag
from common import fold, query
from safety import check_answer, citation_rules

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "src" / "preparation"))
import build_sections as B  # noqa: E402


class TestSections(unittest.TestCase):
    def test_rules_of_the_split(self):
        sheet = {"id": "x", "nom": "X", "description": "Une maladie des feuilles.",
                 "symptomes": None, "biologie": "Les spores hivernent dans le sol et sont dispersées par la pluie.",
                 "lutte": "Moyens de lutte\nLes fongicides cupriques limitent la maladie. Pratiquez une rotation de "
                          "trois ans et détruisez les débris de culture.\nPrévention\nAérez bien les plantations."
                          "\n== References ==\nSmith 2001, Plant Disease.",
                 "repartition": None}
        out = {r["section"]: r for r in B.split_sheet(sheet)}
        self.assertIn("fongicides cupriques", out["lutte"]["texte"])
        self.assertIn("rotation", out["prevention"]["texte"])       # sentence of a control text: prevention
        self.assertIn("Aérez", out["prevention"]["texte"])          # under the heading "Prévention"
        self.assertNotIn("Smith", " ".join(r["texte"] for r in out.values()))  # references dropped
        self.assertEqual(out["biologie"]["texte"], sheet["biologie"])

    def test_table_of_sections(self):
        rows = query("SELECT fiche, section, source FROM fiche_sections")
        self.assertGreater(len(rows), 150)
        self.assertEqual({r["section"] for r in rows}, set(rag.SECTIONS))
        self.assertGreaterEqual(len({r["fiche"] for r in rows if r["section"] == "prevention"}), 20)
        self.assertTrue(all(str(r["source"]).startswith("http") for r in rows))


class TestRetrieval(unittest.TestCase):
    def test_every_passage_names_its_section(self):
        r = rag.search_knowledge("comment éviter l'oïdium de la vigne", k=3)
        self.assertTrue(r)
        for x in r:
            self.assertIn(x["section"], rag.SECTIONS)
            self.assertTrue(x["source"].startswith("http"))

    def test_intent_words_are_folded(self):
        # the question is folded before the INTENT patterns (أ -> ا, ة -> ه): they must match the folded words
        import re
        for word, sec in [("أعراض", "symptomes"), ("دورة الحياة", "biologie"), ("كيف أحمي", "prevention"),
                          ("l3alamat", "symptomes"), ("comment éviter", "prevention"), ("كيف أكافح", "lutte")]:
            self.assertTrue(re.search(rag.INTENT[sec], fold(word)), word)

    def test_methods_and_fallback(self):
        for m in ("tfidf", "bm25"):
            self.assertTrue(rag.search_knowledge("mildiou de la vigne", method=m))
            self.assertEqual(rag.method_used(), m)
        with mock.patch.object(rag, "_vectors", lambda model=None: None):  # no vectors: BM25, said
            self.assertTrue(rag.search_knowledge("mildiou de la vigne", method="hybrid"))
            self.assertEqual(rag.method_used(), "bm25")

    def test_stale_vectors_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "v.npz"
            np.savez(p, vectors=np.zeros((2, 4)), key="old")
            with mock.patch.object(rag, "vector_path", lambda model=None: p):
                rag._vectors.cache_clear()
                try:
                    self.assertIsNone(rag._vectors("e5-small"))
                finally:
                    rag._vectors.cache_clear()

    @unittest.skipUnless(rag.vector_path().exists(), "vecteurs absents : python src/preparation/build_rag_index.py")
    def test_hybrid_is_the_default_and_refuses_off_topic(self):
        self.assertTrue(rag.search_knowledge("comment lutter contre la mouche de l'olive"))
        self.assertEqual(rag.method_used(), "hybrid")
        self.assertEqual(rag.search_knowledge("comment apprendre l'anglais rapidement"), [])


class TestGoldQueries(unittest.TestCase):
    def test_50_queries_with_existing_sections(self):
        with open(ROOT / "tests" / "rag_gold" / "queries.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        on = [r for r in rows if r["kind"] == "sujet"]
        self.assertEqual(len(on), 50)
        self.assertEqual({r["langue"] for r in on}, {"fr", "ar", "darija"})
        self.assertTrue(all(sum(r["langue"] == lang for r in on) >= 10 for lang in ("fr", "ar", "darija")))
        known = {(r["fiche"], r["section"]) for r in query("SELECT fiche, section FROM fiche_sections")}
        for r in on:
            pairs = {(f, s) for f in r["expected_fiche"].split("|") for s in r["expected_section"].split("|")}
            self.assertTrue(pairs & known, r["query_id"])
        self.assertTrue(any(r["kind"] == "hors_sujet" for r in rows))


class TestCitations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = query("SELECT nom, source FROM fiche_sections WHERE fiche = 'alternariose_solanacees' "
                  "AND section = 'prevention'")[0]
        cls.nom, cls.lien = r["nom"], r["source"]

    def test_rule_27(self):
        good = f"Source : fiche « {self.nom} », section prévention : {self.lien}"
        self.assertEqual(citation_rules(good), [])
        self.assertEqual(citation_rules(f"المصدر: بطاقة «{self.nom}»، قسم الوقاية: {self.lien}"), [])
        for bad in (good.replace("prévention", "répartition"),            # section the sheet does not have
                    good.replace(self.nom, "Fiche inventée"),             # sheet that does not exist
                    good.replace(self.lien, "https://example.com/x")):    # link of another source
            self.assertTrue(citation_rules(bad), bad)
        r = check_answer({"task": "diseases", "classe": "tomato__mosaic_virus", "fiable": True,
                          "texte": "Aucun produit ne guérit la mosaïque.\n" + good.replace("prévention", "biologie")})
        self.assertFalse(r["valide"])
        self.assertTrue(any("citation inconnue" in x for x in r["raisons"]), r["raisons"])

    def test_answers_cite_sheet_and_section(self):
        from src.evaluation import eval_phyto as E
        c = {x["case_id"]: x for x in E.read_cases()}["c037"]
        out, _ = E.run_case(c)
        self.assertTrue(out["reponse"]["verification"]["valide"], out["reponse"]["verification"]["raisons"])
        self.assertRegex(out["reponse"]["texte"], r"Source : fiche « [^»]+ », section \w+")
        self.assertTrue(all(s.get("section") in rag.SECTIONS for s in out["reponse"]["sources"]))


if __name__ == "__main__":
    unittest.main()
