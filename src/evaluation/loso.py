"""Leave-one-source-out evaluation (improvement plan, step 2): how good is a model on a SOURCE IT NEVER SAW?

The field test of each source comes from the same source as part of the training (same farms, cameras, web
style), so it flatters the model. Here, for each field source S, a model is trained WITHOUT any photo of S (train and
val_field), with a short schedule, then tested on S:
  S test_field   the photos the deployed models are measured on; compared with a BASELINE trained the same way
                 on all sources (same schedule), McNemar on the same photos
  S all          every photo of S (its train and test_field splits): larger, seen by no fold model
"learnable" = photos whose class exists in the training set of the fold (a class only S has cannot be learnt).
The lab test is measured too, to check that removing S changes nothing there.

Runs are resumable: a model already trained (model.pt + metrics.json in models/loso/<run>) is not retrained.
Usage:
  python src/evaluation/loso.py --task diseases --sources plantdoc plantwild potato_field --epochs 5
Output: models/loso/<task>_all, <task>_minus_<S>; reports/loso/<task>/summary.csv, summary.md,
per_class_<S>.csv; one row per run in docs/experiments.csv.
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import f1_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "vision"))
sys.path.insert(0, os.path.dirname(__file__))
from calibrate import ece  # noqa: E402
from dataset import load_split, local_path, make_transform, manifest  # noqa: E402
from evaluate import load_model, predict_all  # noqa: E402
from experiments import log  # noqa: E402
from stats import mcnemar  # noqa: E402

OUT = os.path.join(ROOT, "reports", "loso")
RECIPE = ["--train-set", "raw", "--field-val", "--field-weight", "5", "--aug", "field"]  # recipe of diseases_v2


class Frame(torch.utils.data.Dataset):
    """(image, class index) from a DataFrame of paths and classes, with the evaluation transform."""

    def __init__(self, df, classes):
        self.paths, self.y = df["path"].tolist(), [classes.index(c) if c in classes else -1 for c in df["class"]]
        self.t = make_transform(train=False)

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        with Image.open(self.paths[i]) as im:
            return self.t(im.convert("RGB")), self.y[i]


def run_name(task, source):
    return f"{task}_all" if source is None else f"{task}_minus_{source}"


def train(task, source, epochs, workers):
    out = os.path.join(ROOT, "models", "loso", run_name(task, source))
    if os.path.exists(os.path.join(out, "model.pt")) and os.path.exists(os.path.join(out, "metrics.json")):
        print(f"{run_name(task, source)} : déjà entraîné, repris", flush=True)
        return out
    cmd = [sys.executable, "-u", "-W", "ignore", os.path.join(ROOT, "src", "vision", "train.py"), "--task", task,
           *RECIPE, "--epochs", str(epochs), "--patience", str(epochs), "--workers", str(workers), "--out", out]
    if source:
        cmd += ["--exclude-source", source]
    os.makedirs(os.path.join(ROOT, "models", "logs"), exist_ok=True)
    logf = os.path.join(ROOT, "models", "logs", f"loso_{run_name(task, source)}.log")
    t0 = time.time()
    with open(logf, "w", encoding="utf-8") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True, cwd=ROOT,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    print(f"{run_name(task, source)} : entraîné en {(time.time() - t0) / 60:.0f} min ({logf})", flush=True)
    return out


def score(net, classes, df, device, workers):
    probs = predict_all(net, Frame(df, classes), device, 64, workers)
    pred = [classes[i] for i in probs.argmax(1)]
    conf = probs.max(1)
    right = np.array([p == t for p, t in zip(pred, df["class"])])
    labels = sorted(set(df["class"]))
    return {"n": len(df), "accuracy": round(float(right.mean()), 4),
            "macro_f1": round(f1_score(df["class"], pred, labels=labels, average="macro", zero_division=0), 4),
            "ece": ece(conf, right)}, right, pred


def source_rows(task, source):
    m = manifest(task)
    m = m[m["source"] == source].copy()
    m["path"] = m["path"].map(local_path)
    return m.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="diseases")
    ap.add_argument("--sources", nargs="+", default=["plantdoc", "plantwild", "potato_field"])
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    base_dir = train(a.task, None, a.epochs, a.workers)
    base, base_classes = load_model(base_dir, device)
    lab = load_split(a.task, "test")
    base_lab, _, _ = score(base, base_classes, lab, device, a.workers)
    rows, today = [], time.strftime("%Y-%m-%d")
    for s in a.sources:
        fold_dir = train(a.task, s, a.epochs, a.workers)
        net, classes = load_model(fold_dir, device)
        seen = set(load_split(a.task, "train", balanced=False, field_holdout=True, exclude_sources=[s])["class"])
        allp = source_rows(a.task, s)
        tf = allp[allp["split"] == "test_field"].reset_index(drop=True)
        f_all, r_all, p_all = score(net, classes, allp, device, a.workers)
        f_tf, r_tf, _ = score(net, classes, tf, device, a.workers)
        b_tf, rb_tf, _ = score(base, base_classes, tf, device, a.workers)
        f_lab, _, _ = score(net, classes, lab, device, a.workers)
        learn = allp["class"].isin(seen).to_numpy()
        test = mcnemar(rb_tf, r_tf)
        pc = allp.assign(pred=p_all, right=r_all).groupby("class").agg(n=("right", "size"), recall=("right", "mean"),
                                                                       most_predicted=("pred", lambda x: x.mode()[0]))
        pc["learnable"] = pc.index.isin(seen)
        os.makedirs(os.path.join(OUT, a.task), exist_ok=True)
        pc.sort_values("recall").round(4).to_csv(os.path.join(OUT, a.task, f"per_class_{s}.csv"))
        row = {"source": s, "photos_all": f_all["n"], "learnable_share": round(float(learn.mean()), 4),
               "loso_all_acc": f_all["accuracy"], "loso_all_learnable_acc": round(float(r_all[learn].mean()), 4)
               if learn.any() else None, "loso_all_macro_f1": f_all["macro_f1"], "loso_all_ece": f_all["ece"],
               "test_field_n": f_tf["n"], "baseline_test_field_acc": b_tf["accuracy"],
               "loso_test_field_acc": f_tf["accuracy"], "gap_points": round(100 * (b_tf["accuracy"] - f_tf["accuracy"]), 1),
               "mcnemar_p": round(test["p"], 6), "baseline_lab_acc": base_lab["accuracy"], "loso_lab_acc": f_lab["accuracy"]}
        rows.append(row)
        log({"date": today, "model": run_name(a.task, s), "change": f"leave-one-source-out: {s} jamais vu, "
             f"{a.epochs} époques, recette diseases_v2", "lab_acc": f_lab["accuracy"], "field_acc": f_tf["accuracy"],
             "plantdoc_acc": f_tf["accuracy"] if s == "plantdoc" else "", "field_macro_f1": f_tf["macro_f1"],
             "field_ece": f_tf["ece"], "mcnemar_p_vs_previous": f"{test['p']:.2g} (vs {run_name(a.task, None)})",
             "notes": f"source tenue à l'écart ; toutes ses photos {f_all['accuracy']:.1%} (n={f_all['n']}), "
                      f"classes apprenables {row['loso_all_learnable_acc']}"})
        print(json.dumps(row), flush=True)
    b_tf_all = {}
    for s in a.sources:
        tf = source_rows(a.task, s).query("split == 'test_field'").reset_index(drop=True)
        b_tf_all[s] = score(base, base_classes, tf, device, a.workers)[0]["accuracy"]
    log({"date": today, "model": run_name(a.task, None), "change": f"référence LOSO : toutes les sources, {a.epochs} "
         "époques, recette diseases_v2", "lab_acc": base_lab["accuracy"],
         "notes": "test terrain par source : " + ", ".join(f"{k} {v:.1%}" for k, v in b_tf_all.items())})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, a.task, "summary.csv"), index=False)
    lines = [f"# Leave-one-source-out : {a.task} ({a.epochs} époques)", "",
             "| source tenue à l'écart | photos | classes apprenables | exactitude (toutes ses photos) | "
             "test terrain : référence → sans la source | écart | McNemar p | labo : référence → sans la source |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['source']} | {r['photos_all']} | {r['learnable_share']:.0%} | {r['loso_all_acc']:.1%} "
                     f"(apprenables {r['loso_all_learnable_acc']:.1%}) | {r['baseline_test_field_acc']:.1%} → "
                     f"{r['loso_test_field_acc']:.1%} | {r['gap_points']:+.1f} pts | {r['mcnemar_p']:.2g} | "
                     f"{r['baseline_lab_acc']:.1%} → {r['loso_lab_acc']:.1%} |")
    with open(os.path.join(OUT, a.task, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
