"""Error analysis of the deployed vision models on their FIELD test set (improvement plan, step 1). No training.

Reads models/<model>/predictions_<split>.csv, written by src/vision/evaluate.py (path, true, pred, confidence, crop,
source), and writes into reports/error_analysis/<model>/:
  per_class.csv          support, correct, accuracy (= recall: one label per photo), precision, F1, mean confidence
                         when right / wrong, the class it is most often taken for
  per_class_source.csv   accuracy of each class in each source (is a failure tied to one source?)
  per_source.csv         accuracy and macro-F1 per source
  confusion.csv          rows = true class, columns = predicted class
  top_confusions.csv     the most frequent (true -> predicted) errors, with their share of the true class
  summary.json / .md     overall scores, ECE, weak classes (used by gradcam.py)
A WEAK class = field recall < WEAK_RECALL with at least MIN_SUPPORT photos.

Usage:
  python src/evaluation/error_analysis.py                       diseases, leaf, crop, routing on test_field
  python src/evaluation/error_analysis.py --models diseases --split test_field
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "vision"))
from calibrate import ece  # noqa: E402

WEAK_RECALL, MIN_SUPPORT, TOP_PAIRS = 0.6, 5, 10
OUT = os.path.join(ROOT, "reports", "error_analysis")


def per_class(df):
    rows = []
    for c in sorted(set(df["true"]) | set(df["pred"])):
        t, p = df["true"] == c, df["pred"] == c
        n, tp = int(t.sum()), int((t & p).sum())
        prec = tp / int(p.sum()) if p.any() else 0.0
        rec = tp / n if n else 0.0
        wrong = df[t & ~p]
        rows.append({"class": c, "support": n, "correct": tp, "accuracy": round(rec, 4), "recall": round(rec, 4),
                     "precision": round(prec, 4), "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
                     "conf_right": round(float(df.loc[t & p, "confidence"].mean()), 4) if tp else None,
                     "conf_wrong": round(float(wrong["confidence"].mean()), 4) if len(wrong) else None,
                     "most_confused_with": wrong["pred"].value_counts().index[0] if len(wrong) else None,
                     "n_predicted": int(p.sum())})
    out = pd.DataFrame(rows)
    return out[out["support"] > 0].sort_values(["recall", "support"], ascending=[True, False]).reset_index(drop=True)


def top_confusions(df, k=TOP_PAIRS):
    err = df[df["true"] != df["pred"]]
    if err.empty:
        return pd.DataFrame(columns=["true", "pred", "n", "share_of_true"])
    pairs = err.groupby(["true", "pred"]).size().rename("n").reset_index()
    support = df["true"].value_counts()
    pairs["share_of_true"] = (pairs["n"] / pairs["true"].map(support)).round(4)
    return pairs.sort_values(["n", "share_of_true"], ascending=False).head(k).reset_index(drop=True)


def per_source(df):
    rows = []
    for s, g in df.groupby("source"):
        labels = sorted(set(g["true"]))
        rows.append({"source": s, "n": len(g), "accuracy": round(float((g["true"] == g["pred"]).mean()), 4),
                     "macro_f1": round(f1_score(g["true"], g["pred"], labels=labels, average="macro",
                                                zero_division=0), 4)})
    return pd.DataFrame(rows)


def per_class_source(df):
    acc = df.assign(ok=df["true"] == df["pred"]).groupby(["true", "source"])["ok"].agg(["mean", "size"])
    acc["mean"] = acc["mean"].round(4)
    return acc.rename(columns={"mean": "accuracy", "size": "n"}).reset_index().rename(columns={"true": "class"})


def weak_classes(pc):
    w = pc[(pc["recall"] < WEAK_RECALL) & (pc["support"] >= MIN_SUPPORT)]
    return w["class"].tolist()


def analyse(df):
    """All tables for one predictions file (DataFrame with true, pred, confidence, source)."""
    labels = sorted(set(df["true"]))
    pc = per_class(df)
    correct = (df["true"] == df["pred"]).to_numpy()
    summary = {"n": int(len(df)), "accuracy": round(float(correct.mean()), 4),
               "macro_f1": round(f1_score(df["true"], df["pred"], labels=labels, average="macro", zero_division=0), 4),
               "ece": ece(df["confidence"].to_numpy(), correct),
               "weak_rule": f"recall < {WEAK_RECALL} with >= {MIN_SUPPORT} photos",
               "weak_classes": weak_classes(pc)}
    classes = sorted(set(df["true"]) | set(df["pred"]))
    confusion = pd.crosstab(df["true"], df["pred"]).reindex(index=labels, columns=classes, fill_value=0)
    return {"summary": summary, "per_class": pc, "top_confusions": top_confusions(df), "per_source": per_source(df),
            "per_class_source": per_class_source(df), "confusion": confusion}


def md_table(df, cols):
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df[cols].itertuples(index=False):
        lines.append("| " + " | ".join("" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
                                       for v in r) + " |")
    return "\n".join(lines)


def write(model, split, res, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name in ("per_class", "top_confusions", "per_source", "per_class_source"):
        res[name].to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)
    res["confusion"].to_csv(os.path.join(out_dir, "confusion.csv"))
    s = res["summary"] | {"model": model, "split": split}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    pc = res["per_class"]
    md = [f"# Analyse des erreurs : {model} · {split}", "",
          f"{s['n']} photos · exactitude {s['accuracy']:.1%} · macro-F1 {s['macro_f1']} · ECE {s['ece']}", "",
          f"Classes faibles ({s['weak_rule']}) : {', '.join(s['weak_classes']) or 'aucune'}", "",
          "## Par source", "", md_table(res["per_source"], ["source", "n", "accuracy", "macro_f1"]), "",
          f"## Les {TOP_PAIRS} confusions les plus fréquentes", "",
          md_table(res["top_confusions"], ["true", "pred", "n", "share_of_true"]), "",
          "## Par classe (de la plus faible à la plus forte)", "",
          md_table(pc, ["class", "support", "recall", "precision", "f1", "conf_right", "conf_wrong",
                        "most_confused_with"])]
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=["diseases", "leaf", "crop", "routing"])
    ap.add_argument("--split", default="test_field")
    a = ap.parse_args()
    for m in a.models:
        path = os.path.join(ROOT, "models", m, f"predictions_{a.split}.csv")
        if not os.path.exists(path):
            print(f"{m}: {path} absent, run src/vision/evaluate.py --task <task> --model-dir models/{m} "
                  f"--splits {a.split}")
            continue
        s = write(m, a.split, analyse(pd.read_csv(path)), os.path.join(OUT, m))
        print(f"{m:10s} {a.split}: n={s['n']} acc {s['accuracy']:.1%} macro-F1 {s['macro_f1']} ECE {s['ece']} "
              f"| classes faibles : {len(s['weak_classes'])}")
    print("rapports :", OUT)


if __name__ == "__main__":
    main()
