"""Phyto plan, step 7: missing DARs (phi_report.py, docs/phi_completions.csv, validated rows only), the date of the
official list in the answers (rule 19), the check of a newer DGSVCIA list (check_dgsvcia_list.py, report only), MRLs
chosen by the market (mrl.py: EU, Tunisian list, Codex) and rule 20."""
import csv
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.agent import paths  # noqa: F401
from src.agent.redaction import P, compose
from src.evaluation import eval_phyto as E
from src.preparation import check_dgsvcia_list as C
from src.preparation.phi_report import read_dar
import mrl  # noqa: E402  (src/tools)
import treatments as T  # noqa: E402
from safety import check_answer  # noqa: E402
from tests.review_state import proposed_copy

PPE = "Protection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes"
LIST = f"Produits homologués en Tunisie pour ce cas (liste DGSVCIA du {T.LIST_DATE}) :"


def validated_copy(src, tmp, keep=lambda r: True):
    with open(src, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [dict(r, status="validated") if keep(r) else r for r in rows]
    path = Path(tmp) / Path(src).name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


class TestPhi(unittest.TestCase):
    def test_read_dar(self):
        self.assertEqual(read_dar("DAR:07 jours (COMM 28/12/2023)"), (7, "7 jours"))
        self.assertEqual(read_dar("DAR: non requis (COMM 28/12/2023)"), (0, "non requis"))
        self.assertEqual(read_dar("DAR:N/A -l'application"), (0, "non requis"))
        self.assertEqual(read_dar("DAR:4 heures"), (1, "4 heures"))  # rounded up: never an earlier harvest
        self.assertEqual(read_dar("DAR:3 jours30 cc/hl(300 cc/ha)"), (3, "3 jours"))
        self.assertIsNone(read_dar("DAR:7 jours(plein champ) DAR:3 jours (sous serre)"))  # two values: review
        self.assertIsNone(read_dar(None))

    def test_completions_are_proposed_and_unused(self):
        with open(T.COMPLETIONS, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows)
        self.assertLessEqual({r["status"] for r in rows}, {"proposed", "validated", "rejected"})  # rows the reviewer validates or rejects stay valid
        tmp = tempfile.mkdtemp()
        saved = T.COMPLETIONS
        try:
            T.COMPLETIONS = proposed_copy(saved, tmp)  # the completions back to 'proposed' (reviewed since)
            T._completions.cache_clear()
            u = next(u for u in T.get_treatments("olive__peacock_spot", "olive") if u["produit"] == "DECIBEL MAX WG")
            self.assertIsNone(u["dar_jours"])
            self.assertEqual(u["dar_message"], "DAR non indiqué : vérifiez l'étiquette")
        finally:
            T.COMPLETIONS = saved
            T._completions.cache_clear()
            shutil.rmtree(tmp)

    def test_validated_completion_is_used_and_said(self):
        tmp = tempfile.mkdtemp()
        saved = T.COMPLETIONS
        try:
            T.COMPLETIONS = validated_copy(saved, tmp, lambda r: r["produit"] == "DECIBEL MAX WG")
            T._completions.cache_clear()
            u = next(u for u in T.get_treatments("olive__peacock_spot", "olive") if u["produit"] == "DECIBEL MAX WG")
            self.assertEqual((u["dar_jours"], u["dar_source"], u["dar_texte"]), (0, "complement", "non requis"))
            from src.agent.redaction import dar_text
            self.assertIn("non requis (complété d'après liste DGSVCIA",
                          dar_text(u, P["fr"]))
            base = {"task": "diseases", "classe": "olive__peacock_spot", "culture": "olive", "fiable": True}
            good = {"nom": "DECIBEL MAX WG", "dose": u["dose"], "dar_jours": 0}
            line = (f"- DECIBEL MAX WG (x) : dose {u['dose']} ; délai avant récolte : non requis"
                    " ; classe de toxicité OMS II (modérément dangereux)")  # rule 15 (WHO table validated)
            text = "\n".join([LIST, line, PPE])
            self.assertTrue(check_answer(dict(base, produits=[good], texte=text))["valide"])
            bad = check_answer(dict(base, produits=[dict(good, dar_jours=5)], texte=text))
            self.assertFalse(bad["valide"])  # rule 3 still blocks a DAR that differs from the validated source
        finally:
            T.COMPLETIONS = saved
            T._completions.cache_clear()
            shutil.rmtree(tmp)


class TestListDate(unittest.TestCase):
    BASE = {"task": "diseases", "classe": "tomato__late_blight", "culture": "tomate", "fiable": True}
    GOOD = {"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}
    LINE = ("- CIMOXATE C WG (Cymoxanil + Copper oxychloride) : dose 3 kg/ha (300 g/hl) ; délai avant récolte : 3 jours"
            " ; classe de toxicité OMS II (modérément dangereux)")  # rule 15, since the WHO table is validated

    def test_rule_19(self):
        ok = check_answer(dict(self.BASE, produits=[self.GOOD], texte="\n".join([LIST, self.LINE, PPE])))
        self.assertTrue(ok["valide"], ok["raisons"])
        r = check_answer(dict(self.BASE, produits=[self.GOOD], texte="\n".join([self.LINE, PPE])))
        self.assertTrue(any("date de la liste" in x for x in r["raisons"]), r["raisons"])
        old = LIST.replace(T.LIST_DATE, "19/04/2023")
        r = check_answer(dict(self.BASE, produits=[self.GOOD], texte="\n".join([old, self.LINE, PPE])))
        self.assertTrue(any("fausse" in x for x in r["raisons"]), r["raisons"])

    def test_every_phyto_answer_gives_the_date(self):
        for cls, crop in (("tomato__late_blight", "tomato"), ("tomato__septoria_leaf_spot", "tomato")):
            out, _ = E.run_case({"crop": crop, "disease_or_deficiency": cls, "governorate": "Nabeul"})
            self.assertIn(f"liste DGSVCIA du {T.LIST_DATE}", out["reponse"]["texte"])
            self.assertTrue(out["reponse"]["verification"]["valide"])
            self.assertIn(f"DGSVCIA بتاريخ {T.LIST_DATE}", compose(out["brouillon"]["faits"], "ar"))


class TestNewList(unittest.TestCase):
    def test_dates_in_file_names(self):
        self.assertEqual(C.date_of("liste-des-produits-pesticides-homologues-16-juillet-2025-vf-1.pdf"),
                         datetime.date(2025, 7, 16))
        self.assertEqual(C.date_of("liste-des-produits-homologues-22-mai-2024.pdf"), datetime.date(2024, 5, 22))
        self.assertEqual(C.date_of("liste-des-pesticides-homologues-27-dec-2022-.pdf"), datetime.date(2022, 12, 27))
        self.assertEqual(C.date_of("liste-des-pesticides-homologues-en-tunisie_13-02-2020.pdf"),
                         datetime.date(2020, 2, 13))
        self.assertIsNone(C.date_of("liste.pdf"))

    def test_registration_numbers(self):
        self.assertEqual(C.reg_key("F.010-11/21"), "F|10-11-21")
        self.assertEqual(C.reg_key("126-11/21 F."), "F|126-11-21")
        self.assertEqual(C.reg_key("I.A.F.017-16"), "IAF|17-16")
        self.assertEqual(C.reg_key("03-24.I"), "I|3-24")
        self.assertIsNone(C.reg_key("2024"))

    def test_diff_added_withdrawn_changed(self):
        old = pd.DataFrame([{"n_homologation": "F.001-20", "nom_commercial": "A", "substance": "s", "n_usages": 2},
                            {"n_homologation": "F.002-20", "nom_commercial": "B", "substance": "s", "n_usages": 1}])
        new = pd.DataFrame([{"n_homologation": "F.001-20", "nom_commercial": "A", "substance": "s", "n_usages": 3},
                            {"n_homologation": "I.009-25", "nom_commercial": "C", "substance": "t", "n_usages": 1}])
        d = C.diff(old, new).set_index("nom_commercial")["changement"].to_dict()
        self.assertEqual(d, {"C": "ajouté", "B": "retiré", "A": "modifié"})


class TestMrl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.saved = mrl.MAPPING
        mrl.MAPPING = validated_copy(cls.saved, cls.tmp)
        mrl._mapping.cache_clear()

    @classmethod
    def tearDownClass(cls):
        mrl.MAPPING = cls.saved
        mrl._mapping.cache_clear()
        shutil.rmtree(cls.tmp)

    def usage(self, name, cls="tomato__late_blight", crop="tomato"):
        return next(u for u in T.get_treatments(cls, crop) if u["produit"] == name)

    def test_market_decides_the_source(self):
        u = self.usage("Hidrocure WG")
        self.assertEqual(mrl.applicable_mrl(u, "tomato", None), [])
        eu = mrl.applicable_mrl(u, "tomato", "export")
        self.assertEqual((eu[0]["source"], eu[0]["valeur"]), ("UE", 10.0))
        local = mrl.applicable_mrl(u, "tomato", "local")
        self.assertTrue(all(m["source"] in ("Codex", "liste DGSVCIA") for m in local))

    def test_sulphur_needs_no_eu_mrl(self):
        u = self.usage("Agrosoufre", "cherry__powdery_mildew", "cherry")
        m = mrl.applicable_mrl(u, "cherry", "export")
        self.assertTrue(m[0].get("non_requise"), m)  # "No MRL required" (Annex IV) is said, not "not found"
        # a use whose commodities have no EU row at all: nothing can be claimed, "not found" is said
        u = next(u for u in T.get_treatments("squash__powdery_mildew", "squash") if "Sulphur" in str(u["substances"]))
        self.assertFalse(mrl.applicable_mrl(u, "squash", "export")[0].get("non_requise"))

    def test_codex_group_exception_is_respected(self):
        v, denree = mrl.codex_mrl("Acetamiprid", "grape")  # "Berries and other small fruits: Except grapes"
        self.assertNotEqual(denree, "Berries and other small fruits")

    def test_tunisian_mrl_of_the_list(self):
        self.assertEqual(mrl.tunisian_mrl({"substances": "X", "lmr_tn_texte": "-DAR :21 jours -LMR :0.05 mg/kg"}), 0.05)
        self.assertIsNone(mrl.tunisian_mrl({"substances": "X + Y", "lmr_tn_texte": "LMR :0.05 mg/kg"}))

    def test_rule_20_and_answer(self):
        out, _ = E.run_case({"crop": "tomato", "disease_or_deficiency": "tomato__spider_mites", "governorate": "Nabeul",
                             "market": "export", "days_to_harvest": "30", "organic": "n", "stage": "spread"})
        r = out["reponse"]
        self.assertTrue(r["verification"]["valide"], r["verification"])
        lines = [x for x in r["texte"].splitlines() if x.strip().startswith("LMR de")]
        self.assertTrue(lines)
        self.assertIn("(UE, export vers l'Union européenne)", lines[0])
        draft = dict(out["brouillon"])
        draft["texte"] = draft["texte"].replace(" mg/kg", "0 mg/kg", 1)  # one MRL written ten times higher
        bad = check_answer(draft)
        self.assertTrue(any("LMR" in x for x in bad["raisons"]), bad["raisons"])


if __name__ == "__main__":
    unittest.main()
