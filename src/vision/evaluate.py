"""Evaluate a trained model on its test sets: overall, per class, per crop and per source.

Usage:
  python src/vision/evaluate.py --task routing
  python src/vision/evaluate.py --task diseases --splits test test_field
Splits evaluated by default: test, plus test_field when the task has one (real field photos never trained on).
Per crop and per source show where the model is weak: field vs lab sources, tomato and citrus fruits in the router,
crops seen for each deficiency.
Output in models/<task>/: eval_<split>.json (scores), confusion_<split>.csv (rows = true class, columns = predicted).
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.dirname(__file__))
from dataset import ROOT, ManifestDataset, load_split  # noqa: E402
from models import build  # noqa: E402


def load_model(folder, device):
    ckpt = torch.load(os.path.join(folder, "model.pt"), map_location="cpu")  # opens on machines without a GPU too
    net = build(ckpt["arch"], len(ckpt["classes"]), pretrained=False)
    net.load_state_dict(ckpt["state_dict"])
    return net.to(device).eval(), ckpt["classes"]


@torch.no_grad()
def predict_all(net, ds, device, batch, workers):
    """Softmax probabilities for every image of `ds` (in order)."""
    probs = []
    for x, _ in DataLoader(ds, batch, num_workers=workers, pin_memory=True):
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            probs.append(torch.softmax(net(x.to(device)).float(), 1).cpu())
    return torch.cat(probs).numpy()


def group_scores(df, col):
    """Accuracy and size of each value of `col` (crop or source)."""
    g = df.groupby(col)
    return {k: {"n": int(len(v)), "accuracy": round(float((v["true"] == v["pred"]).mean()), 4)} for k, v in g}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=["routing", "diseases", "deficiency", "fruits", "leaf"])
    ap.add_argument("--model-dir", default=None)
    ap.add_argument("--splits", nargs="+", default=None)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    folder = args.model_dir or str(ROOT / "models" / args.task)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net, classes = load_model(folder, device)

    splits = args.splits or ["test"] + (["test_field"] if len(load_split(args.task, "test_field")) else [])
    for split in splits:
        ds = ManifestDataset(args.task, split, classes)
        probs = predict_all(net, ds, device, args.batch, args.workers)
        df = ds.df.copy()
        df["true"] = df["class"]
        df["pred"] = [classes[i] for i in probs.argmax(1)]
        df["confidence"] = probs.max(1)
        present = sorted(set(df["true"]))
        report = classification_report(df["true"], df["pred"], labels=present, output_dict=True, zero_division=0)
        result = {
            "task": args.task, "split": split, "n": int(len(df)),
            "accuracy": round(accuracy_score(df["true"], df["pred"]), 4),
            "macro_f1": round(f1_score(df["true"], df["pred"], labels=present, average="macro", zero_division=0), 4),
            "mean_confidence_correct": round(float(df.loc[df["true"] == df["pred"], "confidence"].mean()), 4),
            "mean_confidence_wrong": round(float(df.loc[df["true"] != df["pred"], "confidence"].mean()), 4)
            if (df["true"] != df["pred"]).any() else None,
            "per_class": {c: {"precision": round(report[c]["precision"], 4), "recall": round(report[c]["recall"], 4),
                              "f1": round(report[c]["f1-score"], 4), "n": int(report[c]["support"])} for c in present},
            "per_crop": group_scores(df, "crop"),
            "per_source": group_scores(df, "source"),
        }
        with open(os.path.join(folder, f"eval_{split}.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        cm = confusion_matrix(df["true"], df["pred"], labels=classes)
        pd.DataFrame(cm, index=classes, columns=classes).to_csv(os.path.join(folder, f"confusion_{split}.csv"))
        df[["path", "true", "pred", "confidence", "crop", "source"]].to_csv(
            os.path.join(folder, f"predictions_{split}.csv"), index=False)

        print(f"\n== {args.task} · {split}: {result['n']} images · accuracy {result['accuracy']} · "
              f"macro-F1 {result['macro_f1']}")
        worst = sorted(result["per_class"].items(), key=lambda kv: kv[1]["f1"])[:5]
        print("   weakest classes:", ", ".join(f"{c} {v['f1']}" for c, v in worst))
        print("   per source:", ", ".join(f"{k} {v['accuracy']} (n={v['n']})" for k, v in result["per_source"].items()))
    print(f"\nfiles written in {folder}")


if __name__ == "__main__":
    main()
