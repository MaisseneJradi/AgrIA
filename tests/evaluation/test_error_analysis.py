import os
import tempfile
import unittest

import pandas as pd

from src.evaluation import error_analysis as ea


def toy():
    """10 photos, 3 classes: a 4/4 right, b 2/4 right (twice taken for c), c 1/2 right (once for a)."""
    rows = [("a", "a", 0.9, "s1")] * 4 + [("b", "b", 0.8, "s1")] * 2 + [("b", "c", 0.7, "s2")] * 2 \
        + [("c", "c", 0.6, "s2"), ("c", "a", 0.95, "s2")]
    return pd.DataFrame(rows, columns=["true", "pred", "confidence", "source"])


class TestErrorAnalysis(unittest.TestCase):
    def test_per_class(self):
        pc = ea.per_class(toy()).set_index("class")
        self.assertEqual(pc.loc["b", "support"], 4)
        self.assertAlmostEqual(pc.loc["b", "recall"], 0.5)
        self.assertAlmostEqual(pc.loc["c", "precision"], 1 / 3, places=3)
        self.assertEqual(pc.loc["b", "most_confused_with"], "c")
        self.assertAlmostEqual(pc.loc["a", "precision"], 0.8)
        self.assertEqual(list(ea.per_class(toy())["class"])[:2], ["b", "c"])  # weakest first, larger support first

    def test_top_confusions(self):
        top = ea.top_confusions(toy())
        self.assertEqual((top.loc[0, "true"], top.loc[0, "pred"], top.loc[0, "n"]), ("b", "c", 2))
        self.assertAlmostEqual(top.loc[0, "share_of_true"], 0.5)
        self.assertEqual(len(top), 2)

    def test_summary_and_weak_classes(self):
        res = ea.analyse(toy())
        self.assertAlmostEqual(res["summary"]["accuracy"], 0.7)
        self.assertEqual(res["summary"]["weak_classes"], [])  # b and c are under 0.6 but have < 5 photos
        df = pd.concat([toy()] * 2)
        self.assertEqual(ea.analyse(df)["summary"]["weak_classes"], ["b"])  # b: 8 photos, recall 0.5; c: 4 photos
        self.assertEqual(int(res["confusion"].loc["b", "c"]), 2)
        self.assertEqual(int(res["confusion"].values.sum()), 10)

    def test_per_source(self):
        ps = ea.per_source(toy()).set_index("source")
        self.assertAlmostEqual(ps.loc["s1", "accuracy"], 1.0)
        self.assertAlmostEqual(ps.loc["s2", "accuracy"], 0.25)

    def test_write(self):
        with tempfile.TemporaryDirectory() as d:
            s = ea.write("toy", "test_field", ea.analyse(toy()), d)
            self.assertEqual(s["n"], 10)
            for f in ("per_class.csv", "top_confusions.csv", "confusion.csv", "summary.json", "summary.md"):
                self.assertTrue(os.path.exists(os.path.join(d, f)), f)


if __name__ == "__main__":
    unittest.main()
