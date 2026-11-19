"""Tables of docs/results_vision.md, built from the files written by evaluate.py and calibrate.py.

Usage: python src/vision/report_vision.py > C:/.../tables.md
  H1  lab test vs field photos (diseases test_field), per class on the field
  H2  deficiency recall per crop: on the crop that dominates the class vs the other crops where it is seen
  H3  balanced set vs raw set: macro-F1 and recall of the rarest classes
Folders read: models/<name>/ for every name below that exists (balanced and raw variants; the retained model of
each task is also copied to models/<task>/).
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from dataset import PROC, ROOT, load_split, local_path  # noqa: E402

M = ROOT / "models"


def ev(name, split):
    p = M / name / f"eval_{split}.json"
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


def md(df):
    if not len(df):
        return "_(no data)_"
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def overview(names):
    rows = []
    for n in names:
        met = M / n / "metrics.json"
        if not met.exists():
            continue
        m = json.load(open(met, encoding="utf-8"))
        for split in ("test", "test_field"):
            e = ev(n, split)
            if e:
                rows.append({"model": n, "arch": m["model"], "train set": m["args"].get("train_set", "manifest"),
                             "best epoch": m["best"]["epoch"], "split": split, "n": e["n"],
                             "accuracy": e["accuracy"], "macro-F1": e["macro_f1"],
                             "threshold": m.get("threshold", "-")})
    return pd.DataFrame(rows)


def h1(name):
    e = ev(name, "test_field")
    if not e:
        return pd.DataFrame()
    lab = ev(name, "test")["per_class"]
    rows = [{"class": c, "field n": v["n"], "field recall": v["recall"], "field F1": v["f1"],
             "lab recall": lab.get(c, {}).get("recall")} for c, v in e["per_class"].items()]
    return pd.DataFrame(rows).sort_values("field recall")


def h2(name):
    p = M / name / "predictions_test.csv"
    if not p.exists():
        return pd.DataFrame(), pd.DataFrame()
    pred = pd.read_csv(p)
    info = pd.read_csv(PROC / "balanced" / "deficiency_test_by_crop.csv")
    info["path"] = info["path"].map(local_path)
    df = pred.merge(info[["path", "culture_dominante_de_la_classe"]], on="path", how="left")
    df["ok"] = df["true"] == df["pred"]
    df["on dominant crop"] = df["crop"] == df["culture_dominante_de_la_classe"]
    by_crop = (df.groupby(["true", "crop"]).agg(n=("ok", "size"), recall=("ok", "mean")).reset_index()
               .rename(columns={"true": "class"}))
    by_crop["recall"] = by_crop["recall"].round(3)
    dom = (df.groupby(["true", "on dominant crop"]).agg(n=("ok", "size"), recall=("ok", "mean")).reset_index()
           .rename(columns={"true": "class"}))
    dom["recall"] = dom["recall"].round(3)
    return dom, by_crop


def h3(task, balanced, raw, k=10):
    rows = []
    counts = load_split(task, "train", balanced=False)["class"].value_counts()
    rare = list(counts.sort_values().index[:k])
    for split in ("test", "test_field"):
        a, b = ev(balanced, split), ev(raw, split)
        if not (a and b):
            continue
        ra = [a["per_class"][c]["recall"] for c in rare if c in a["per_class"]]
        rb = [b["per_class"][c]["recall"] for c in rare if c in b["per_class"]]
        rows.append({"task": task, "split": split, "macro-F1 balanced": a["macro_f1"], "macro-F1 raw": b["macro_f1"],
                     "accuracy balanced": a["accuracy"], "accuracy raw": b["accuracy"],
                     f"mean recall {k} rarest balanced": round(sum(ra) / len(ra), 4) if ra else None,
                     f"mean recall {k} rarest raw": round(sum(rb) / len(rb), 4) if rb else None})
    detail = []
    a, b = ev(balanced, "test"), ev(raw, "test")
    if a and b:
        for c in rare:
            if c in a["per_class"]:
                detail.append({"class": c, "raw train images": int(counts[c]), "test n": a["per_class"][c]["n"],
                               "recall balanced": a["per_class"][c]["recall"], "recall raw": b["per_class"][c]["recall"]})
    return pd.DataFrame(rows), pd.DataFrame(detail)


def main():
    names = ["routing", "diseases_effnet", "diseases_mobilenet", "diseases_vit", "diseases_raw",
             "deficiency_balanced", "deficiency_raw", "fruits_balanced", "fruits_raw"]
    print("## Overview\n\n" + md(overview(names)))
    for n in ("diseases_raw", "diseases_effnet", "diseases_mobilenet", "diseases_vit"):
        t = h1(n)
        if len(t):
            print(f"\n## H1 · {n} on field photos\n\n" + md(t))
    dom, by_crop = h2("deficiency_raw")
    print("\n## H2 · deficiency, dominant crop vs other crops\n\n" + md(dom))
    print("\n### H2 · deficiency recall per class and crop\n\n" + md(by_crop))
    for task in ("diseases", "deficiency", "fruits"):
        bal = "diseases_effnet" if task == "diseases" else f"{task}_balanced"
        summary, detail = h3(task, bal, f"{task}_raw")
        print(f"\n## H3 · {task}, balanced vs raw\n\n" + md(summary) + "\n\n" + md(detail))


if __name__ == "__main__":
    main()
