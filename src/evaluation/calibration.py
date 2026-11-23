"""Calibration of the deployed models: is a confidence of 90 % right 90 % of the time? (improvement plan, step 2)

For each model and split (predictions_<split>.csv written by src/vision/evaluate.py):
  ECE   expected calibration error: mean gap between confidence and accuracy, weighted by the photos of each bin
        (15 equal bins, the definition of src/vision/calibrate.py)
  MCE   maximum gap over the bins holding at least MIN_BIN photos
  over  mean confidence - accuracy (> 0 = the model is too sure of itself)
  reliability diagram: accuracy per confidence bin against the diagonal, with the number of photos per bin.
Output: reports/calibration/<model>/<split>.csv and .png, reports/calibration/summary.csv and summary.md.

Usage:
  python src/evaluation/calibration.py
  python src/evaluation/calibration.py --models diseases leaf --splits val val_field test test_field
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "reports", "calibration")
BINS, MIN_BIN = 15, 10
NAMES = {"val": "validation labo", "val_field": "validation terrain", "test": "test labo",
         "test_field": "test terrain"}


def reliability(conf, correct, bins=BINS):
    """One row per non-empty bin: lo, hi, n, mean confidence, accuracy, gap."""
    conf, correct = np.asarray(conf, dtype=float), np.asarray(correct, dtype=bool)
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            rows.append({"lo": round(lo, 4), "hi": round(hi, 4), "n": int(m.sum()),
                         "confidence": round(float(conf[m].mean()), 4), "accuracy": round(float(correct[m].mean()), 4),
                         "gap": round(float(conf[m].mean() - correct[m].mean()), 4)})
    return pd.DataFrame(rows, columns=["lo", "hi", "n", "confidence", "accuracy", "gap"])


def scores(conf, correct, bins=BINS):
    r = reliability(conf, correct, bins)
    n = r["n"].sum()
    big = r[r["n"] >= MIN_BIN]
    return {"n": int(n), "accuracy": round(float(np.mean(correct)), 4),
            "mean_confidence": round(float(np.mean(conf)), 4),
            "ece": round(float((r["n"] / n * r["gap"].abs()).sum()), 4) if n else None,
            "mce": round(float(big["gap"].abs().max()), 4) if len(big) else None,
            "over": round(float(np.mean(conf) - np.mean(correct)), 4)}


def plot(r, s, title, path):
    fig, (ax, axh) = plt.subplots(2, 1, figsize=(5, 6), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    ax.plot([0, 1], [0, 1], color="#888888", lw=1, ls="--", label="calibration parfaite")
    ax.bar(r["confidence"], r["accuracy"], width=1 / BINS * 0.9, color="#3b6ea5", alpha=0.85,
           label="exactitude réelle")
    ax.set_ylabel("exactitude")
    ax.set_ylim(0, 1)
    ax.set_title(f"{title}\nECE {s['ece']} · confiance moyenne {s['mean_confidence']:.0%} · "
                 f"exactitude {s['accuracy']:.0%}", fontsize=9)
    ax.legend(fontsize=8, loc="upper left")
    axh.bar(r["confidence"], r["n"], width=1 / BINS * 0.9, color="#999999")
    axh.set_xlabel("confiance du modèle")
    axh.set_ylabel("photos")
    axh.set_xlim(0, 1)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=["routing", "diseases", "leaf", "crop", "fruits", "deficiency"])
    ap.add_argument("--splits", nargs="+", default=["val", "val_field", "test", "test_field"])
    a = ap.parse_args()
    rows = []
    for m in a.models:
        for sp in a.splits:
            p = os.path.join(ROOT, "models", m, f"predictions_{sp}.csv")
            if not os.path.exists(p):
                continue
            df = pd.read_csv(p)
            conf, ok = df["confidence"].to_numpy(), (df["true"] == df["pred"]).to_numpy()
            r, s = reliability(conf, ok), scores(conf, ok)
            d = os.path.join(OUT, m)
            os.makedirs(d, exist_ok=True)
            r.to_csv(os.path.join(d, f"{sp}.csv"), index=False)
            plot(r, s, f"{m} · {NAMES.get(sp, sp)} ({s['n']} photos)", os.path.join(d, f"{sp}.png"))
            rows.append({"model": m, "split": sp} | s)
    out = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    out.to_csv(os.path.join(OUT, "summary.csv"), index=False)
    lines = ["# Calibration des modèles déployés", "",
             "ECE = écart moyen entre confiance et exactitude ; « trop sûr » = confiance moyenne − exactitude.", "",
             "| modèle | jeu | photos | exactitude | confiance moyenne | ECE | MCE | trop sûr |", "|---|---|---|---|---|---|---|---|"]
    for r in out.itertuples(index=False):
        lines.append(f"| {r.model} | {NAMES.get(r.split, r.split)} | {r.n} | {r.accuracy:.1%} | {r.mean_confidence:.1%} "
                     f"| {r.ece} | {r.mce} | {r.over:+.3f} |")
    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
