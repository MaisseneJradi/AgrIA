import csv
import os
import tempfile
import unittest

import numpy as np
from PIL import Image

from src.evaluation import calibration, experiments, leakage, stats


class TestMcNemar(unittest.TestCase):
    def test_counts_and_p(self):
        a = [True, True, False, False, True]
        b = [True, False, True, True, True]
        r = stats.mcnemar(a, b)
        self.assertEqual((r["gains"], r["losses"]), (2, 1))
        self.assertAlmostEqual(r["p"], 1.0)
        r = stats.mcnemar([False] * 12, [True] * 12)
        self.assertLess(r["p"], 0.001)
        self.assertEqual(stats.mcnemar([True], [True])["p"], 1.0)

    def test_same_photos_required(self):
        with self.assertRaises(ValueError):
            stats.mcnemar([True, False], [True])


class TestCalibration(unittest.TestCase):
    def test_perfect(self):
        conf = np.array([0.9] * 10)
        right = np.array([True] * 9 + [False])
        s = calibration.scores(conf, right)
        self.assertAlmostEqual(s["ece"], 0.0, places=6)
        self.assertAlmostEqual(s["over"], 0.0, places=6)

    def test_overconfident(self):
        s = calibration.scores(np.array([0.95] * 10), np.array([True] * 5 + [False] * 5))
        self.assertAlmostEqual(s["ece"], 0.45, places=4)
        self.assertGreater(s["over"], 0)
        r = calibration.reliability([0.05, 0.95, 0.96], [False, True, True])
        self.assertEqual(r["n"].sum(), 3)
        self.assertEqual(len(r), 2)


class TestExperimentsLog(unittest.TestCase):
    def test_log_and_schema(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "exp.csv")
            experiments.log({"date": "2026-11-21", "model": "x", "field_acc": 0.8}, p)
            experiments.log({"date": "2026-11-22", "model": "y"}, p)
            rows = list(csv.DictReader(open(p, encoding="utf-8")))
            self.assertEqual([r["model"] for r in rows], ["x", "y"])
            self.assertEqual(rows[1]["field_acc"], "")
            with self.assertRaises(ValueError):
                experiments.log({"model": "z", "nope": 1}, p)


class TestLeakage(unittest.TestCase):
    def test_exact_and_near_copies_are_found(self):
        with tempfile.TemporaryDirectory() as d:
            def save(name, arr, q=95):
                p = os.path.join(d, name)
                Image.fromarray(arr).save(p, quality=q)
                return p
            def smooth(seed):  # a photo-like image: smooth colour gradients (noise changes too much once re-saved)
                g = np.random.default_rng(seed)
                y, x = np.mgrid[0:128, 0:128] / 127.0
                ch = [np.sin(g.uniform(1, 6) * x + g.uniform(1, 6) * y + g.uniform(0, 6)) for _ in range(3)]
                return ((np.stack(ch, 2) + 1) * 127).astype(np.uint8)
            a, b, c = smooth(1), smooth(2), smooth(3)
            ta, tb = save("a.jpg", a), save("b.jpg", b)
            exact = os.path.join(d, "a_copy.jpg")
            with open(ta, "rb") as f, open(exact, "wb") as g:
                g.write(f.read())
            near = save("b_resaved.jpg", b, q=90)  # same picture, other bytes
            other = save("c.jpg", c)
            leaks = leakage.find_leaks({"train": [ta, tb], "test": [exact, near, other]})
            kinds = dict(zip(leaks["eval"], leaks["kind"]))
            self.assertEqual(kinds.get(exact), "exact")
            self.assertEqual(kinds.get(near), "near")
            self.assertNotIn(other, kinds)
            self.assertTrue(leakage.find_leaks({"train": [ta], "test": [other]}).empty)


if __name__ == "__main__":
    unittest.main()


class TestExcludeSource(unittest.TestCase):
    def test_source_left_out_everywhere(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "vision"))
        from dataset import PROC, load_split
        if not (PROC / "diseases_manifest.csv").exists():
            self.skipTest("no local data")
        full = load_split("diseases", "val_field")
        part = load_split("diseases", "val_field", exclude_sources=["plantdoc"])
        self.assertIn("plantdoc", set(full["source"]))
        self.assertNotIn("plantdoc", set(part["source"]))
        self.assertEqual(len(part), int((full["source"] != "plantdoc").sum()))  # the other field photos unchanged
