"""Step 8: pseudo-labels are only proposed; promote copies reviewed rows to a new train-only source."""
import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.preparation import pseudo_label as P


class TestDecide(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(P.decide("a", 0.99, "a", 0.9, False, 0.95), (True, ""))
        self.assertFalse(P.decide("a", 0.99, "a", 0.9, True, 0.95)[0])  # duplicate of an evaluation image
        self.assertIn("désaccord", P.decide("a", 0.99, "b", 0.9, False, 0.95)[1])
        self.assertIn("confiance", P.decide("a", 0.90, "a", 0.9, False, 0.95)[1])
        self.assertTrue(P.decide("a", 0.99, None, 0.0, False, 0.95)[0])  # leaf answer outside the disease classes


class TestPromote(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        b = Path(self.tmp.name)
        self.raw, self.mapping = b / "raw", b / "mapping.csv"
        self.mapping.write_text("task,unified_class,crop,status,folder,split\n", encoding="utf-8")
        self.review = b / "review.csv"
        rows = []
        for i, (lab, ok) in enumerate([("tomato__healthy", "oui"), ("tomato__early_blight", "oui"),
                                       ("tomato__early_blight", "")]):
            p = b / f"img{i}.jpg"
            Image.new("RGB", (32, 32), (i * 50, 120, 40)).save(p)
            rows.append({c: "" for c in P.COLS} | {"path": str(p), "md5": f"m{i}", "label": lab, "valide": ok})
        with open(self.review, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, P.COLS)
            w.writeheader()
            w.writerows(rows)
        self.known = {"tomato__healthy", "tomato__early_blight"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_promote_reviewed_rows_only_to_train(self):
        source, n, labels = P.promote(self.review, "2026-11-22", self.raw, self.mapping, self.known)
        self.assertEqual((source, n), ("pseudo_2026-11-22", 2))
        self.assertEqual(len(list((self.raw / source).rglob("*.jpg"))), 2)
        with open(self.mapping, encoding="utf-8", newline="") as fh:
            m = list(csv.DictReader(fh))
        self.assertEqual({r["split"] for r in m}, {"train"})
        self.assertEqual({r["status"] for r in m}, {"healthy", "diseased"})
        with self.assertRaises(SystemExit):  # the source is never modified afterwards
            P.promote(self.review, "2026-11-22", self.raw, self.mapping, self.known)

    def test_unknown_class_refused(self):
        with self.assertRaises(SystemExit):
            P.promote(self.review, "2026-11-23", self.raw, self.mapping, {"tomato__healthy"})


if __name__ == "__main__":
    unittest.main()
