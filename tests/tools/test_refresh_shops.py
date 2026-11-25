"""Phyto plan, step 12: refresh of the shop catalogue (src/preparation/refresh_shops.py), removed products, rule 28.
Nothing here touches the network: the HTTP answers are simulated."""
import io
import sys
import tempfile
import time
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import pandas as pd

from tests.tools import _path  # noqa: F401
import shop
from safety import check_answer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "preparation"))
import refresh_shops as R  # noqa: E402

COLS = ["id", "name", "shop_category", "description", "technical_sheet", "price", "stock_status", "stock_quantity",
        "image_url", "product_url", "source", "last_updated", "slug", "fiches_pdf"]


def catalogue(rows):
    df = pd.DataFrame([{c: "" for c in COLS} | r for r in rows], columns=COLS).astype(str)
    for c in R.EXTRA:
        df[c] = ""
    return df


OLD = catalogue([
    {"id": "agriclic:1", "name": "FER 6", "description": "Fe EDDHA 6 %", "price": "30.0", "stock_status": "en_stock",
     "product_url": "https://www.agriclic.tn/1-fer.html"},
    {"id": "agriclic:2", "name": "NPK 20", "description": "NPK 20-20-20", "price": "12.0", "stock_status": "en_stock",
     "product_url": "https://www.agriclic.tn/2-npk.html"},
    {"id": "agrishop:3", "name": "SCORE", "description": "Difenoconazole 250 g/l", "price": "80.0",
     "stock_status": "en_stock"},
])


class FakeHTTP:
    """urlopen replacement: robots.txt text and a status per page; records the time of each page request."""

    def __init__(self, robots="User-agent: *\nDisallow: /private\n", pages=None, offline=False):
        self.robots, self.pages, self.offline, self.calls = robots, pages or {}, offline, []

    def __call__(self, req, timeout=None):
        url = req.full_url
        if self.offline:
            raise urllib.error.URLError("no route to host")
        if url.endswith("/robots.txt"):
            return io.BytesIO(self.robots.encode())
        self.calls.append((time.time(), req.get_method(), url))
        code = self.pages.get(url, 200)
        if code != 200:
            raise urllib.error.HTTPError(url, code, "x", {}, None)
        r = io.BytesIO(b"")
        r.status = 200
        return r


class TestCompare(unittest.TestCase):
    def test_new_changed_removed(self):
        new = OLD.copy()
        new = new[new["id"] != "agriclic:2"]                                             # removed
        new.loc[new["id"] == "agriclic:1", "price"] = "32.0"                              # price only
        new.loc[new["id"] == "agrishop:3", "description"] = "Difenoconazole 125 g/l"      # text: review again
        new = pd.concat([new, catalogue([{"id": "agriclic:9", "name": "ZINC"}])], ignore_index=True)
        d = R.compare(OLD, new, "2026-12-01").set_index("id")
        self.assertEqual(d.at["agriclic:9", "etat"], "nouveau")
        self.assertEqual(d.at["agriclic:2", "etat"], "retire")
        self.assertEqual((d.at["agriclic:1", "champs"], bool(d.at["agriclic:1", "a_relire"])), ("price", False))
        self.assertEqual((d.at["agrishop:3", "champs"], bool(d.at["agrishop:3", "a_relire"])), ("description", True))

        cat = R.merge_catalogue(OLD, new, d.reset_index(), "2026-12-01").set_index("id")
        self.assertEqual(cat.at["agriclic:2", "stock_status"], "retire")      # kept, never shown
        self.assertEqual(cat.at["agriclic:2", "retire_le"], "2026-12-01")
        self.assertEqual(len(cat), 4)
        # a later refresh does not report it again
        self.assertTrue(R.compare(cat.reset_index(), new, "2026-12-02").empty)

    def test_review_is_kept(self):
        before = {"mapping": pd.DataFrame([
            {"shop_product_id": "agriclic:1", "target_id": "besoin:Fe", "status": "validated", "note": ""},
            {"shop_product_id": "agriclic:2", "target_id": "besoin:N", "status": "validated", "note": ""},
            {"shop_product_id": "agrishop:3", "target_id": "homo-fon-107", "status": "validated", "note": ""}])}
        after = {"mapping": pd.DataFrame([      # the rules write every row again as 'proposed'
            {"shop_product_id": "agriclic:1", "target_id": "besoin:Fe", "status": "proposed", "note": ""},
            {"shop_product_id": "agrishop:3", "target_id": "", "status": "proposed", "note": ""},
            {"shop_product_id": "agriclic:9", "target_id": "besoin:Zn", "status": "proposed", "note": ""}])}
        diff = pd.DataFrame([{"id": "agriclic:2", "etat": "retire", "a_relire": False},
                             {"id": "agrishop:3", "etat": "modifie", "a_relire": True},
                             {"id": "agriclic:9", "etat": "nouveau", "a_relire": True}])
        m = R.merge_reviewed(before, after, diff, "2026-12-01")["mapping"].set_index("shop_product_id")
        self.assertEqual(m.at["agriclic:1", "status"], "validated")                     # unchanged: review kept
        self.assertEqual(m.at["agriclic:2", "status"], "validated")                     # removed: kept, noted
        self.assertIn("retiré du site le 2026-12-01", m.at["agriclic:2", "note"])
        self.assertEqual(m.at["agrishop:3", "status"], "proposed")                      # text changed: review again
        self.assertIn("produit modifié", m.at["agrishop:3", "note"])
        self.assertEqual(m.at["agriclic:9", "status"], "proposed")                      # new


class TestNetwork(unittest.TestCase):
    def test_robots_and_one_request_per_second(self):
        http = FakeHTTP(pages={"https://www.agriclic.tn/2-npk.html": 404})
        polite = R.Polite(delay=0.3, opener=http)
        df = OLD.copy()
        df.loc[df["id"] == "agriclic:1", "product_url"] = "https://www.agriclic.tn/private/1-fer.html"  # forbidden
        out, report = R.check_links(df, polite, "2026-12-01")
        out = out.set_index("id")
        self.assertEqual(out.at["agriclic:2", "stock_status"], "retire")      # 404: removed, loses its link
        self.assertEqual(out.at["agriclic:2", "lien_http"], "404")
        self.assertEqual(out.at["agriclic:1", "stock_status"], "en_stock")    # robots.txt: not requested
        self.assertNotIn("private", " ".join(u for _, _, u in http.calls))
        self.assertIn("interdit par robots.txt", report["http"].astype(str).tolist())

        http = FakeHTTP()
        polite = R.Polite(delay=0.3, opener=http)
        for _ in range(3):
            polite.status("https://www.agriclic.tn/1-fer.html")
        gaps = [b[0] - a[0] for a, b in zip(http.calls, http.calls[1:])]
        self.assertTrue(all(g >= 0.29 for g in gaps), gaps)

    def test_crawl_delay_of_robots_is_obeyed(self):
        polite = R.Polite(delay=0.0, opener=FakeHTTP(robots="User-agent: *\nCrawl-delay: 2\n"))
        polite._robots("https://www.agriclic.tn/x")
        with mock.patch.object(R.time, "sleep") as sleep:
            polite.last = time.time()
            polite.wait("https://www.agriclic.tn/x")
        self.assertGreater(sleep.call_args[0][0], 1.5)

    def test_no_network_is_quiet(self):
        with self.assertRaises(R.NoNetwork):
            R.check_links(OLD, R.Polite(opener=FakeHTTP(offline=True)))
        polite = R.Polite
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(R, "REPORTS", Path(d)), \
                mock.patch.object(R.urllib.request, "urlopen", FakeHTTP(offline=True)), \
                mock.patch.object(R, "Polite", lambda: polite(opener=FakeHTTP(offline=True))):
            before = R.SHOP.read_bytes()
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(R.main(["--check-links"]), 0)
                self.assertEqual(R.main(["--agriclic"]), 0)
            self.assertIn("réseau indisponible", buf.getvalue())
            self.assertEqual(R.SHOP.read_bytes(), before)        # nothing changed


class TestApply(unittest.TestCase):
    def test_apply_writes_catalogue_and_keeps_review(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            shop_csv, mapping = d / "shop.csv", d / "mapping.csv"
            OLD.to_csv(shop_csv, index=False)
            pd.DataFrame([{"shop_product_id": "agriclic:1", "target_id": "besoin:Fe", "status": "validated",
                           "note": ""}]).to_csv(mapping, index=False)
            new = OLD[OLD["id"] != "agriclic:2"].copy()

            def rules():  # what the scripts of steps 8-9 do: every row again, 'proposed'
                pd.DataFrame([{"shop_product_id": "agriclic:1", "target_id": "besoin:Fe", "status": "proposed",
                               "note": ""}]).to_csv(mapping, index=False)

            with mock.patch.object(R, "SHOP", shop_csv), mock.patch.object(R, "REPORTS", d), \
                    mock.patch.object(R, "REVIEWED", {"mapping": mapping}), mock.patch.object(R, "OTHER_DOCS", []), \
                    mock.patch.object(R.B, "build", lambda export=None, raw=None: new[R.B.COLUMNS]), \
                    mock.patch.object(R, "rerun_rules", rules), mock.patch.object(R.subprocess, "run") as run, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(R.main(["--apply"]), 0)
            cat = pd.read_csv(shop_csv, keep_default_na=False, dtype=str).set_index("id")
            self.assertEqual(cat.at["agriclic:2", "stock_status"], "retire")
            self.assertEqual(pd.read_csv(mapping).at[0, "status"], "validated")
            self.assertTrue(run.called)  # build_db.py


class TestRemovedProducts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.evaluation.test_phyto_step10 import SCAB, ids, run
        cls.sid = ids("Score 250 EC")
        cls.mapping = {"homo-fon-107": cls.sid}
        cls.out = run(SCAB, cls.mapping)

    def retired(self):
        products = {k: dict(v) for k, v in shop._products().items()}
        for s in self.sid:
            products[s]["stock_status"] = "retire"
        return mock.patch.object(shop, "_products", lambda: products)

    def test_no_offer_for_a_removed_product(self):
        with self.retired(), mock.patch.object(shop, "_mapping", lambda: self.mapping):
            self.assertEqual(shop.pesticide_offers({"product_id": "homo-fon-107"}), [])

    def test_rule_28(self):
        a = dict(self.out["brouillon"])
        with mock.patch.object(shop, "_mapping", lambda: self.mapping):
            self.assertTrue(check_answer(a)["valide"])
            with self.retired():
                r = check_answer(a)
        self.assertFalse(r["valide"])
        self.assertTrue(any("retiré du site" in x for x in r["raisons"]), r["raisons"])


if __name__ == "__main__":
    unittest.main()
