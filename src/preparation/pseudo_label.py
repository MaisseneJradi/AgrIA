"""Pseudo-labels for unlabeled field photos, written to a CSV FOR REVIEW ONLY (step 8 of the improvement plan).

Nothing is added to the datasets here. For each photo of --images (any folder tree of unlabeled photos):
  - the deployed disease model and the leaf model give their answer (test-time augmentation, src/vision/evaluate.py);
  - the photo is proposed only if both agree, the confidence of the disease model is >= --min-conf (0.95 by
    default; with --temperature T the confidence is the temperature-scaled one of step 7) and the photo is not the
    same picture (MD5 or dHash + pixels) as any val / val_field / test / test_field / field_tn image (no leak);
  - the rest is listed too, with the reason, so the reviewer sees what was left out.
Output: data/pseudo/review_<date>.csv with columns path, md5, pred, confidence, leaf_pred, leaf_confidence, agree,
proposed, reason, label (pre-filled with pred when proposed) and valide (empty: to fill with "oui" by hand).

After the review (never before), `promote` copies the rows with valide = oui to data/raw/pseudo_<date>/<label>/ and
appends their mapping rows (split "train": pseudo-labels never go to an evaluation split) to
docs/extra_class_mapping.csv; then src/preparation/add_source.py pseudo_<date> adds them like any other source.

Usage:
  python src/preparation/pseudo_label.py propose --images D:/photos_terrain --min-conf 0.95
  python src/preparation/pseudo_label.py promote data/pseudo/review_2026-11-22.csv
  python src/preparation/add_source.py pseudo_2026-11-22
"""
import argparse
import csv
import datetime
import os
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "vision"))
sys.path.insert(0, str(ROOT / "src" / "evaluation"))
OUT = ROOT / "data" / "pseudo"
EXT = (".jpg", ".jpeg", ".png")
COLS = ["path", "md5", "pred", "confidence", "leaf_pred", "leaf_confidence", "agree", "proposed", "reason", "label",
        "valide"]


def list_images(folder):
    return sorted(str(Path(r) / f) for r, _, fs in os.walk(folder) for f in fs if f.lower().endswith(EXT))


def decide(pred, conf, leaf_pred, leaf_conf, leaked, min_conf):
    """(proposed, reason) for one photo."""
    if leaked:
        return False, "même photo qu'une image d'évaluation"
    if leaf_pred is not None and leaf_pred != pred:
        return False, f"désaccord avec le modèle feuille ({leaf_pred})"
    if conf < min_conf:
        return False, f"confiance {conf:.2f} < {min_conf}"
    return True, ""


def eval_paths(task="diseases"):
    from dataset import load_split
    out = []
    for split in ("val", "val_field", "test", "test_field", "field_tn"):
        out += load_split(task, split)["path"].tolist()
    return out


def leaked_paths(paths, task="diseases"):
    """Photos of `paths` that are the same picture as an evaluation image of `task`."""
    from leakage import find_leaks
    leaks = find_leaks({"train": paths, "eval": eval_paths(task)})
    return set(leaks["train"])


def predict(task, paths, temperature=1.0, folder=None):
    """(classes, probabilities) of a model on photos, with test-time augmentation; logits divided by temperature."""
    import torch
    from PIL import Image
    from dataset import make_transform
    from evaluate import load_model, tta_views
    dev = torch.device(os.environ.get("AGRIA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu"))
    net, classes = load_model(str(folder or ROOT / "models" / task), dev)
    tf = make_transform(train=False, size=net.input_size)
    probs = []
    with torch.no_grad():
        for p in paths:
            with Image.open(p) as im:
                x = tf(im.convert("RGB")).unsqueeze(0).to(dev)
            probs.append(torch.stack([torch.softmax(net(v).float() / temperature, 1)[0]
                                      for v in tta_views(x)]).mean(0).cpu().numpy())
    return classes, np.array(probs).reshape(len(paths), len(classes))


def propose(images, min_conf=0.95, temperature=1.0, today=None, out=OUT):
    from leakage import hashes
    paths = list_images(images)
    if not paths:
        return None, 0, 0
    dcls, dp = predict("diseases", paths, temperature)
    lcls, lp = predict("leaf", paths)
    leaked = leaked_paths(paths)
    rows = []
    for i, p in enumerate(paths):
        pred, conf = dcls[dp[i].argmax()], float(dp[i].max())
        lpred, lconf = lcls[lp[i].argmax()], float(lp[i].max())
        ok, why = decide(pred, conf, lpred if lpred in dcls else None, lconf, p in leaked, min_conf)
        rows.append({"path": p, "md5": hashes(p)[0], "pred": pred, "confidence": round(conf, 4), "leaf_pred": lpred,
                     "leaf_confidence": round(lconf, 4), "agree": "oui" if lpred == pred else "non",
                     "proposed": "oui" if ok else "non", "reason": why, "label": pred if ok else "", "valide": ""})
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"review_{today or datetime.date.today().isoformat()}.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, COLS)
        w.writeheader()
        w.writerows(rows)
    return path, len(rows), sum(r["proposed"] == "oui" for r in rows)


def promote(review_csv, today=None, raw=ROOT / "data" / "raw", mapping=ROOT / "docs" / "extra_class_mapping.csv",
            known_classes=None):
    """Copy the reviewed rows (valide = oui) to data/raw/pseudo_<date>/<label>/ and add their mapping rows."""
    if known_classes is None:
        import json
        known_classes = set(json.loads((ROOT / "models" / "diseases" / "labels.json").read_text(encoding="utf-8")))
    source = f"pseudo_{today or datetime.date.today().isoformat()}"
    if (raw / source).exists():
        raise SystemExit(f"{raw / source} existe déjà : une source pseudo_<date> n'est jamais modifiée après coup")
    with open(review_csv, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("valide", "").strip().lower() == "oui"]
    bad = [r["label"] for r in rows if r["label"] not in known_classes]
    if bad:
        raise SystemExit(f"classes inconnues : {sorted(set(bad))}")
    labels = sorted({r["label"] for r in rows})
    for r in rows:
        dst = raw / source / r["label"] / (r["md5"] + Path(r["path"]).suffix.lower())
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r["path"], dst)
    if labels:
        with open(mapping, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            for lab in labels:
                crop, status = lab.split("__", 1)
                w.writerow(["diseases", lab, crop, "healthy" if status == "healthy" else "diseased",
                            f"{source}/{lab}", "train"])
    return source, len(rows), labels


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--images", required=True)
    p.add_argument("--min-conf", type=float, default=0.95)
    p.add_argument("--temperature", type=float, default=1.0)
    q = sub.add_parser("promote")
    q.add_argument("review_csv")
    a = ap.parse_args()
    if a.cmd == "propose":
        path, n, k = propose(a.images, a.min_conf, a.temperature)
        if path is None:
            sys.exit(f"aucune photo dans {a.images}")
        print(f"{n} photos lues, {k} proposées : {path}\nÀ relire : remplir `valide` (oui) et corriger `label` si "
              f"besoin, puis : python src/preparation/pseudo_label.py promote {path}")
    else:
        source, n, labels = promote(a.review_csv)
        print(f"{n} photos copiées dans data/raw/{source}/ ({len(labels)} classes), lignes ajoutées à "
              f"docs/extra_class_mapping.csv.\nPuis : python src/preparation/add_source.py {source}")


if __name__ == "__main__":
    main()
