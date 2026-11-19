"""Choose the confidence threshold of a model, which sets the `reliable` field of predict().

Usage (after evaluate.py has written predictions_val.csv, predictions_test.csv and, if any, predictions_test_field.csv):
  python src/vision/evaluate.py --task diseases --splits val
  python src/vision/calibrate.py --task diseases
Options: --model-dir (models/<task>) --target (0.98) --floor (0.5)
         --calib-split val (default) | val_field (field photos held out by train.py --field-val: the threshold is
         then chosen on real photos, which is what the app receives)

Rule: the threshold is the lowest value, never below --floor, at which the predictions kept on the VALIDATION set are
right at least --target of the time. Test and test_field never choose anything: they only show what the threshold
gives on unseen images (coverage = share of photos answered, accuracy of those, share of errors caught).
Below the threshold the agent does not give a diagnosis: it asks for another photo or for confirmation questions.
Also reports the calibration error (ECE: gap between confidence and real accuracy, 15 bins).
Output: "threshold" and "calibration" added to models/<task>/metrics.json, details in calibration.json.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from dataset import ROOT  # noqa: E402

SHOWN = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def ece(conf, correct, bins=15):
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return round(float(total), 4)


def at_threshold(conf, correct, t):
    keep = conf >= t
    n_err = int((~correct).sum())
    return {"threshold": t, "coverage": round(float(keep.mean()), 4),
            "accuracy_kept": round(float(correct[keep].mean()), 4) if keep.any() else None,
            "errors_caught": round(float((~correct & ~keep).sum() / n_err), 4) if n_err else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=["routing", "diseases", "deficiency", "fruits", "leaf", "crop"])
    ap.add_argument("--model-dir", default=None)
    ap.add_argument("--target", type=float, default=0.98)
    ap.add_argument("--floor", type=float, default=0.5)
    ap.add_argument("--calib-split", default="val", choices=["val", "val_field"])
    args = ap.parse_args()
    folder = args.model_dir or str(ROOT / "models" / args.task)

    def load(split):
        path = os.path.join(folder, f"predictions_{split}.csv")
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path)
        return df["confidence"].to_numpy(), (df["true"] == df["pred"]).to_numpy()

    val = load(args.calib_split)
    if val is None:
        sys.exit(f"missing {folder}/predictions_{args.calib_split}.csv: "
                 f"run evaluate.py --task {args.task} --splits {args.calib_split} first")
    conf, correct = val
    grid = np.round(np.arange(args.floor, 0.996, 0.005), 3)
    ok = [t for t in grid if correct[conf >= t].mean() >= args.target]
    threshold = float(ok[0]) if ok else float(grid[-1])

    report = {"rule": f"lowest threshold >= {args.floor} with {args.calib_split} accuracy of kept predictions "
                      f">= {args.target}",
              "threshold": threshold, "splits": {}}
    for split in ("val", "val_field", "test", "test_field"):
        data = load(split)
        if data is None:
            continue
        c, k = data
        report["splits"][split] = {
            "n": int(len(c)), "accuracy": round(float(k.mean()), 4), "ece": ece(c, k),
            "chosen": at_threshold(c, k, threshold),
            "curve": [at_threshold(c, k, t) for t in SHOWN]}
    with open(os.path.join(folder, "calibration.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    mpath = os.path.join(folder, "metrics.json")
    metrics = json.load(open(mpath, encoding="utf-8"))
    metrics["threshold"] = threshold
    metrics["calibration"] = {s: v["chosen"] | {"ece": v["ece"]} for s, v in report["splits"].items()}
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=1)

    print(f"{args.task}: threshold {threshold} ({report['rule']})")
    for s, v in report["splits"].items():
        ch = v["chosen"]
        print(f"  {s:10s} n={v['n']:5d} acc {v['accuracy']} ece {v['ece']} | kept {ch['coverage']} "
              f"acc kept {ch['accuracy_kept']} errors caught {ch['errors_caught']}")


if __name__ == "__main__":
    main()
