"""Tests of a mechanism ("a proposed row is never used") must not depend on what the reviewer has validated since:
they run on a copy of the table where the rows are back to 'proposed'."""
import csv
from pathlib import Path


def proposed_copy(src, folder, keep=lambda r: True):
    """Copy of the CSV src in folder, with status 'proposed' on the rows where keep(row) is true."""
    with open(src, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [dict(r, status="proposed") if keep(r) else r for r in rows]
    path = Path(folder) / Path(src).name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path
