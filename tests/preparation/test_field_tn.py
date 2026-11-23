"""Step 9: Tunisian field test set from the app journal (consent only, frozen once added)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.preparation import field_tn as F

CLASSES = {"diseases": {"tomato__septoria_leaf_spot", "tomato__healthy"}, "deficiency": {"K_deficiency"}}


def entry(journal, jid, keep, correct=True, classe="tomato__septoria_leaf_spot", colour=(40, 140, 60)):
    Image.new("RGB", (64, 64), colour).save(journal / f"{jid}.jpg")
    rec = {"id": jid, "entree": {"culture": "tomate", "gouvernorat": "Nabeul", "mois": 11},
           "diagnostic": {"task": "diseases", "classe": classe, "confiance": 91},
           "avis": {"correct": correct, "vraie_reponse": None if correct else "mildiou", "garder_photo": keep,
                    "date": "2026-11-22T10:00:00"}}
    (journal / f"{jid}.json").write_text(json.dumps(rec), encoding="utf-8")


class TestFieldTN(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.journal, self.out = base / "journal", base / "field_tn"
        self.journal.mkdir()
        entry(self.journal, "20261122-100000-aaaaaa", keep=True)
        entry(self.journal, "20261122-100001-bbbbbb", keep=False, colour=(200, 10, 10))
        entry(self.journal, "20261122-100002-cccccc", keep=True, correct=False, colour=(10, 10, 200))
        old = {"id": "20261122-100003-dddddd", "avis": {"correct": True}}  # feedback from before the consent box
        (self.journal / "20261122-100003-dddddd.json").write_text(json.dumps(old), encoding="utf-8")
        Image.new("RGB", (8, 8)).save(self.journal / "20261122-100003-dddddd.jpg")

    def tearDown(self):
        self.tmp.cleanup()

    def review(self):
        path, n = F.export(self.journal, self.out, today="2026-11-22")
        with open(path, encoding="utf-8", newline="") as fh:
            return path, list(csv.DictReader(fh))

    def test_export_only_kept_photos(self):
        _, rows = self.review()
        self.assertEqual([r["id"] for r in rows], ["20261122-100000-aaaaaa", "20261122-100002-cccccc"])
        self.assertEqual(rows[0]["label"], "tomato__septoria_leaf_spot")  # right answer pre-filled
        self.assertEqual(rows[1]["label"], "")  # wrong answer: label left to the reviewer
        self.assertEqual(rows[1]["vraie_reponse"], "mildiou")

    def write(self, path, rows):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, F.REVIEW_COLS)
            w.writeheader()
            w.writerows(rows)

    def test_freeze_validated_rows_then_frozen(self):
        path, rows = self.review()
        rows[0]["valide"] = "oui"
        rows[1].update(label="tomato__late_blight", valide="oui")  # unknown class: refused
        self.write(path, rows)
        added, refused = F.freeze(path, self.out, CLASSES, today="2026-11-22")
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["task"], "diseases")
        self.assertTrue((self.out / added[0]["file"]).exists())
        self.assertIn("classe inconnue", refused[0][1])
        self.assertEqual(F.verify(self.out), [])
        # second freeze of the same CSV adds nothing, the manifest is unchanged
        before = (self.out / "manifest.csv").read_text(encoding="utf-8")
        added2, refused2 = F.freeze(path, self.out, CLASSES)
        self.assertEqual(added2, [])
        self.assertIn("déjà gelée", [w for _, w in refused2])
        self.assertEqual((self.out / "manifest.csv").read_text(encoding="utf-8"), before)
        # frozen photos are not exported again
        _, again = self.review()
        self.assertEqual([r["id"] for r in again], ["20261122-100002-cccccc"])

    def test_verify_detects_change(self):
        path, rows = self.review()
        rows[0]["valide"] = "oui"
        self.write(path, rows)
        added, _ = F.freeze(path, self.out, CLASSES)
        Image.new("RGB", (64, 64), (0, 0, 0)).save(self.out / added[0]["file"])
        self.assertEqual(F.verify(self.out), [(added[0]["id"], "modifiée")])


if __name__ == "__main__":
    unittest.main()
