"""Experiment log of the improvement plan (rule 6): one row per experiment in docs/experiments.csv.

  from experiments import log
  log({"date": "2026-11-21", "model": "diseases_v3", "change": "...", "lab_acc": 0.99, "field_acc": 0.81, ...})
Missing columns are left empty; unknown keys are refused so that the file keeps one schema.
"""
import csv
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOG = os.path.join(ROOT, "docs", "experiments.csv")
COLUMNS = ["date", "model", "change", "lab_acc", "field_acc", "plantdoc_acc", "field_macro_f1", "field_ece",
           "mcnemar_p_vs_previous", "notes"]


def log(row, path=LOG):
    unknown = set(row) - set(COLUMNS)
    if unknown:
        raise ValueError(f"unknown columns {sorted(unknown)}, expected {COLUMNS}")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in COLUMNS})
