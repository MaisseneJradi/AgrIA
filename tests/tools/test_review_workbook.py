"""Review workbook (src/preparation/review_workbook.py): export of the proposed rows, decisions written back."""
import csv
import difflib
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from tests.tools import _path  # noqa: F401
import prevention
import target_mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "preparation"))
import review_workbook as W  # noqa: E402


def statuses(path):
    with open(path, encoding="utf-8") as f:
        return [r["status"] for r in csv.DictReader(f)]


class TestReviewWorkbook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self.tmp.name) / "docs"
        self.docs.mkdir()
        for spec in W.SPECS:
            # the tables as before the review (every row 'proposed'), byte for byte otherwise (quoted cells kept)
            text = (W.DOCS / spec.file).read_bytes().decode("utf-8")
            text = text.replace(",validated,", ",proposed,").replace(",rejected,", ",proposed,")
            (self.docs / spec.file).write_bytes(text.encode("utf-8"))
        self.xlsx, self.counts = W.export(Path(self.tmp.name) / "r.xlsx", docs=self.docs)

    def tearDown(self):
        self.tmp.cleanup()

    def fill(self, sheet, row, decision, note=None):
        wb = load_workbook(self.xlsx)
        ws = wb[sheet]
        head = [c.value for c in ws[1]]
        ws.cell(row=row, column=head.index("Décision") + 1, value=decision)
        if note:
            ws.cell(row=row, column=head.index("Note du relecteur") + 1, value=note)
        wb.save(self.xlsx)
        return ws.cell(row=row, column=1).value  # line of the CSV

    def test_export_has_every_proposed_row(self):
        wb = load_workbook(self.xlsx)
        self.assertEqual(wb.sheetnames[0], "Mode_d_emploi")
        for spec, (sheet, n) in zip(W.SPECS, self.counts):
            proposed = [r for r in csv.DictReader(open(self.docs / spec.file, encoding="utf-8"))
                        if r["status"] == "proposed" and (spec.keep is None or spec.keep(r))]
            self.assertEqual(n, len(proposed), sheet)
            self.assertEqual(wb[sheet].max_row - 1, n)
            self.assertEqual(len(wb[sheet].data_validations.dataValidation), 1)

    def test_import_writes_only_the_decided_rows(self):
        dar = self.docs / "phi_completions.csv"
        prev = self.docs / "conseils_prevention.csv"      # a file with quoted Arabic cells
        before_dar, before_prev = dar.read_text(encoding="utf-8"), prev.read_text(encoding="utf-8")
        before_claims = statuses(self.docs / "shop_unapproved_claims.csv")
        l1 = self.fill("2_DAR_completes", 2, "validé", "COMM 28/12/2023 vérifiée")
        l2 = self.fill("2_DAR_completes", 3, "rejeté")
        self.fill("6_Prevention", 2, "Validé")             # case and accents do not matter
        self.fill("9_Allegations", 2, "peut-être")         # unknown: reported, not written
        decisions, errors = W.read_decisions(self.xlsx)
        self.assertEqual(len(errors), 1)
        report = W.apply_decisions(decisions, docs=self.docs, date="2026-12-01", write=False)
        self.assertEqual(dar.read_text(encoding="utf-8"), before_dar)  # report only: nothing written
        self.assertEqual((report["phi_completions.csv"]["validated"], report["phi_completions.csv"]["rejected"]),
                         (1, 1))
        W.apply_decisions(decisions, docs=self.docs, date="2026-12-01", write=True)
        st = statuses(dar)
        self.assertEqual((st[l1 - 2], st[l2 - 2]), ("validated", "rejected"))
        row = list(csv.DictReader(open(dar, encoding="utf-8")))[l1 - 2]
        self.assertIn("relecture 2026-12-01 : COMM 28/12/2023 vérifiée", row["note"])
        # only the decided lines changed, every other byte is the same
        for path, before, n in ((dar, before_dar, 2), (prev, before_prev, 1)):
            changed = [x for x in difflib.ndiff(before.splitlines(), path.read_text(encoding="utf-8").splitlines())
                       if x.startswith("+ ")]
            self.assertEqual(len(changed), n, path.name)
        self.assertEqual(statuses(self.docs / "shop_unapproved_claims.csv"), before_claims)  # unknown decision

    def test_a_row_changed_since_export_is_never_overwritten(self):
        line = self.fill("7_LMR_Codex", 2, "validé")
        path = self.docs / "codex_commodity_mapping.csv"
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        rows[line - 2]["denree_codex"] = "autre denrée"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\r\n")
            w.writeheader()
            w.writerows(rows)
        decisions, _ = W.read_decisions(self.xlsx)
        report = W.apply_decisions(decisions, docs=self.docs, write=True)
        self.assertEqual(report["codex_commodity_mapping.csv"]["validated"], 0)
        self.assertIn("modifiée depuis l'export", report["codex_commodity_mapping.csv"]["ignorees"][0])
        self.assertEqual(statuses(path)[line - 2], "proposed")

    def test_loaders_accept_rejected_rows_and_never_use_them(self):
        line = self.fill("6_Prevention", 2, "rejeté")
        self.fill("1_Cibles_maladies", 2, "rejeté")
        decisions, _ = W.read_decisions(self.xlsx)
        W.apply_decisions(decisions, docs=self.docs, write=True)
        rows = prevention._rows.__wrapped__(self.docs / "conseils_prevention.csv")
        self.assertEqual(rows[line - 2]["status"], "rejected")
        cls = rows[line - 2]["unified_class"]
        self.assertFalse(any(r["status"] == "rejected" for r in
                             [x for x in rows if x["unified_class"] == cls and x["status"] == "validated"]))
        target_mapping.load(self.docs / "disease_target_mapping.csv")  # no "unknown status" error


if __name__ == "__main__":
    unittest.main()
