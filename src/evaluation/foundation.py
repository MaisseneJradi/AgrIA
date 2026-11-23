"""Frozen foundation-model features + a small head (step 6 of the improvement plan).

Backbones (downloaded once, frozen, never fine-tuned):
  bioclip   BioCLIP ViT-B/16 (open_clip hf-hub:imageomics/bioclip, MIT): CLIP trained on the Tree of Life
            (TreeOfLife-10M, many plant photos taken in the wild), image embedding 512
  dinov2    DINOv2 ViT-S/14 (timm vit_small_patch14_dinov2.lvd142m, Apache 2.0) at 224 px, class token 384
Features are computed once per photo and cached in data/processed/features/<backbone>/<task>_<split>.npz (float16).
The train split is the raw one without the val_field photos (as train.py --train-set raw --field-val); field photos
weigh --field-weight (5) in the loss, like the CNN recipe.
Heads: "linear" (logistic regression) and "mlp" (one hidden layer of 512, dropout 0.3), AdamW, seed 42, epoch chosen
on the field validation accuracy (val_field), never on test.
Output, like a CNN model folder so that src/evaluation/compare.py works: models/<task>_<backbone>_<head>/
  head.pt, labels.json, metrics.json (+ CPU latency of backbone + head), predictions_<split>.csv.

Usage:
  python src/evaluation/foundation.py --task diseases --backbone dinov2 bioclip --head linear mlp
  python src/evaluation/compare.py --new models/diseases_dinov2_mlp --current models/diseases
  python src/evaluation/foundation.py --task diseases --backbone dinov2 --head mlp --loso plantdoc plantwild potato_field
  python src/evaluation/foundation.py --task diseases --blend models/diseases_dinov2_mlp models/diseases_blend_dinov2
"""
import argparse
import json
import os
import random
import sys
import time

import numpy as np
import pandas as pd
import torch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "vision"))
sys.path.insert(0, os.path.dirname(__file__))
from dataset import FIELD_SOURCES, class_names, load_split  # noqa: E402

FEAT = os.path.join(ROOT, "data", "processed", "features")
SPLITS = ("train", "val", "val_field", "test", "test_field")
SEED = 42


def seed_everything(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def backbone(name, device):
    """(frozen network giving one embedding per image, preprocessing of a PIL image)."""
    if name == "bioclip":
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms("hf-hub:imageomics/bioclip")
        net = model.visual
    elif name == "dinov2":
        import timm
        net = timm.create_model("vit_small_patch14_dinov2.lvd142m", pretrained=True, img_size=224, num_classes=0)
        cfg = timm.data.resolve_data_config({}, model=net)
        cfg.update(input_size=(3, 224, 224), crop_pct=1.0)
        preprocess = timm.data.create_transform(**cfg)
    else:
        raise ValueError(name)
    for p in net.parameters():
        p.requires_grad_(False)
    return net.to(device).eval(), preprocess


class Images(torch.utils.data.Dataset):
    def __init__(self, paths, preprocess):
        self.paths, self.preprocess = paths, preprocess

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        from PIL import Image
        with Image.open(self.paths[i]) as im:
            return self.preprocess(im.convert("RGB"))


def split_rows(task, split):
    if split == "train":
        return load_split(task, "train", balanced=False, field_holdout=True)
    return load_split(task, split)


def features(name, task, split, device, batch=64, workers=4):
    """(features float32 (N, D), rows) of one split, cached."""
    rows = split_rows(task, split).reset_index(drop=True)
    cache = os.path.join(FEAT, name, f"{task}_{split}.npz")
    if os.path.exists(cache):
        d = np.load(cache, allow_pickle=True)
        if list(d["paths"]) == rows["path"].tolist():
            return d["x"].astype(np.float32), rows
    net, pre = backbone(name, device)
    dl = torch.utils.data.DataLoader(Images(rows["path"].tolist(), pre), batch, num_workers=workers)
    out, t0 = [], time.time()
    with torch.no_grad():
        for i, x in enumerate(dl):
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                f = net(x.to(device))
            out.append(f.float().cpu().numpy())
            if i % 100 == 0:
                print(f"  {name} {task} {split}: {min(len(rows), (i + 1) * batch)}/{len(rows)} "
                      f"({time.time() - t0:.0f} s)", flush=True)
    x = np.concatenate(out)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.savez_compressed(cache, x=x.astype(np.float16), paths=np.array(rows["path"].tolist(), dtype=object))
    return x, rows


def make_head(kind, d, n):
    if kind == "linear":
        return torch.nn.Linear(d, n)
    return torch.nn.Sequential(torch.nn.Linear(d, 512), torch.nn.GELU(), torch.nn.Dropout(0.3), torch.nn.Linear(512, n))


def normalise(x, mean, std):
    return (x - mean) / std


def train_head(kind, xtr, ytr, wtr, xval, yval, n, epochs=40, lr=1e-3, wd=1e-4, batch=256, device="cpu"):
    """Head trained on (xtr, ytr) with sample weights wtr; the epoch with the best accuracy on (xval, yval) is kept."""
    seed_everything()
    head = make_head(kind, xtr.shape[1], n).to(device)
    opt = torch.optim.AdamW(head.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    X, Y, W = (torch.tensor(xtr, device=device), torch.tensor(ytr, device=device),
               torch.tensor(wtr, dtype=torch.float32, device=device))
    Xv = torch.tensor(xval, device=device)
    best, best_state, best_ep, g = -1.0, None, 0, torch.Generator().manual_seed(SEED)
    for ep in range(epochs):
        head.train()
        for idx in torch.randperm(len(X), generator=g).split(batch):
            idx = idx.to(device)
            loss = (torch.nn.functional.cross_entropy(head(X[idx]), Y[idx], reduction="none",
                                                      label_smoothing=0.1) * W[idx]).sum() / W[idx].sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        head.eval()
        with torch.no_grad():
            acc = float((head(Xv).argmax(1).cpu().numpy() == yval).mean())
        if acc > best:
            best, best_ep = acc, ep + 1
            best_state = {k: v.detach().clone() for k, v in head.state_dict().items()}
    head.load_state_dict(best_state)
    return head.eval(), best, best_ep


def cpu_latency(name, head, mean, std, paths, n=10):
    """Median seconds per photo on CPU: preprocessing + backbone + head."""
    from PIL import Image
    torch.set_num_threads(4)
    net, pre = backbone(name, torch.device("cpu"))
    head = head.cpu()
    ts = []
    with torch.no_grad():
        for p in paths[:n + 2]:
            t0 = time.perf_counter()
            with Image.open(p) as im:
                x = pre(im.convert("RGB")).unsqueeze(0)
            f = net(x).numpy()
            head(torch.tensor(normalise(f, mean, std), dtype=torch.float32))
            ts.append(time.perf_counter() - t0)
    return round(float(np.median(ts[2:])), 4)


def run(task, name, heads, device, field_weight=5, workers=4):
    from leakage import check
    if not check(task, field_val=True).empty:  # rule 3: never train on an evaluation photo
        sys.exit(f"STOP: training photos of {task} are also in an evaluation set")
    classes = class_names(task)
    idx = {c: i for i, c in enumerate(classes)}
    data = {s: features(name, task, s, device, workers=workers) for s in SPLITS}
    xtr, rtr = data["train"]
    mean, std = xtr.mean(0), xtr.std(0) + 1e-6
    ytr = rtr["class"].map(idx).to_numpy()
    wtr = np.where(rtr["source"].isin(FIELD_SOURCES), float(field_weight), 1.0)
    xs = {s: normalise(data[s][0], mean, std).astype(np.float32) for s in SPLITS}
    ys = {s: data[s][1]["class"].map(idx).to_numpy() for s in SPLITS}
    results = {}
    for kind in heads:
        t0 = time.time()
        head, val_acc, ep = train_head(kind, xs["train"], ytr, wtr, xs["val_field"], ys["val_field"], len(classes),
                                       device=device)
        out = os.path.join(ROOT, "models", f"{task}_{name}_{kind}")
        os.makedirs(out, exist_ok=True)
        torch.save({"backbone": name, "head": kind, "classes": classes, "state_dict": head.cpu().state_dict(),
                    "mean": mean, "std": std}, os.path.join(out, "head.pt"))
        with open(os.path.join(out, "labels.json"), "w", encoding="utf-8") as f:
            json.dump(classes, f, indent=1)
        metrics = {"backbone": name, "head": kind, "best_epoch": ep, "val_field_acc_selected": round(val_acc, 4),
                   "train_seconds": round(time.time() - t0, 1)}
        with torch.no_grad():
            for s in ("val", "val_field", "test", "test_field"):
                p = torch.softmax(head(torch.tensor(xs[s])).float(), 1).numpy()
                df = data[s][1][["path", "class", "crop", "source"]].rename(columns={"class": "true"}).copy()
                df["pred"] = [classes[i] for i in p.argmax(1)]
                df["confidence"] = p.max(1)
                df[["path", "true", "pred", "confidence", "crop", "source"]].to_csv(
                    os.path.join(out, f"predictions_{s}.csv"), index=False)
                metrics[f"{s}_acc"] = round(float((df["true"] == df["pred"]).mean()), 4)
        metrics["cpu_seconds_per_photo"] = cpu_latency(name, head, mean, std, data["test_field"][1]["path"].tolist())
        metrics["head_kb"] = round(os.path.getsize(os.path.join(out, "head.pt")) / 1024, 1)
        with open(os.path.join(out, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=1)
        print(f"{task} {name} {kind}: {metrics}", flush=True)
        results[kind] = metrics
    return results


def loso(task, name, kind, sources, device, field_weight=5):
    """Head trained without one field source, scored on ALL its photos (train + val_field + test_field): the same
    question as src/evaluation/loso.py for the CNN (how good on a source never seen?)."""
    classes = class_names(task)
    idx = {c: i for i, c in enumerate(classes)}
    data = {s: features(name, task, s, device, workers=0) for s in SPLITS}
    out = {}
    for src in sources:
        keep = {s: (data[s][1]["source"] != src).to_numpy() for s in SPLITS}
        xtr, rtr = data["train"][0][keep["train"]], data["train"][1][keep["train"]]
        mean, std = xtr.mean(0), xtr.std(0) + 1e-6
        w = np.where(rtr["source"].isin(FIELD_SOURCES), float(field_weight), 1.0)
        xv, rv = data["val_field"][0][keep["val_field"]], data["val_field"][1][keep["val_field"]]
        head, _, _ = train_head(kind, normalise(xtr, mean, std).astype(np.float32), rtr["class"].map(idx).to_numpy(),
                                w, normalise(xv, mean, std).astype(np.float32), rv["class"].map(idx).to_numpy(),
                                len(classes), device=device)
        head = head.cpu()
        held = [(data[s][0][~keep[s]], data[s][1][~keep[s]]) for s in ("train", "val_field", "test_field")]
        x = np.concatenate([h[0] for h in held])
        y = pd.concat([h[1] for h in held])["class"].map(idx).to_numpy()
        with torch.no_grad():
            p = torch.softmax(head(torch.tensor(normalise(x, mean, std).astype(np.float32))), 1).numpy()
        tf = data["test_field"][1]["source"].to_numpy() == src
        with torch.no_grad():
            pt = head(torch.tensor(normalise(data["test_field"][0][tf], mean, std).astype(np.float32))).argmax(1)
        out[src] = {"photos": int(len(y)), "acc_all": round(float((p.argmax(1) == y).mean()), 4),
                    "test_field_acc": round(float((pt.numpy() == data["test_field"][1]["class"][tf].map(idx)
                                                   .to_numpy()).mean()), 4),
                    "mean_conf": round(float(p.max(1).mean()), 4)}
        print(f"LOSO {task} {name} {kind} sans {src}: {out[src]}", flush=True)
    return out


def blend(task, head_dir, cnn_dir, out_dir):
    """Weighted mean of the CNN and head probabilities, weight chosen on val_field (0, 0.1, ..., 1), written as a
    model folder (predictions_*.csv) for compare.py. Needs predictions_<split>.csv WITH probabilities: recomputed."""
    import json as _json
    sys.path.insert(0, os.path.join(ROOT, "src", "vision"))
    from dataset import ManifestDataset
    from evaluate import load_model, predict_all
    dev = torch.device(os.environ.get("AGRIA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu"))
    net, classes = load_model(cnn_dir, dev)
    ck = torch.load(os.path.join(head_dir, "head.pt"), map_location="cpu", weights_only=False)
    assert ck["classes"] == classes
    head = make_head(ck["head"], len(ck["mean"]), len(classes))
    head.load_state_dict(ck["state_dict"])
    head.eval()
    probs = {}
    for s in ("val", "val_field", "test", "test_field"):
        pc = predict_all(net, ManifestDataset(task, s, classes, size=net.input_size), dev, 64, 0)
        x, rows = features(ck["backbone"], task, s, dev, workers=0)
        with torch.no_grad():
            ph = torch.softmax(head(torch.tensor(normalise(x, ck["mean"], ck["std"]).astype(np.float32))), 1).numpy()
        probs[s] = (pc, ph, rows)
    idx = {c: i for i, c in enumerate(classes)}
    yv = probs["val_field"][2]["class"].map(idx).to_numpy()
    grid = [round(w, 1) for w in np.arange(0, 1.01, 0.1)]
    accs = {w: float((((1 - w) * probs["val_field"][0] + w * probs["val_field"][1]).argmax(1) == yv).mean()) for w in grid}
    w = max(grid, key=lambda k: (accs[k], -k))
    os.makedirs(out_dir, exist_ok=True)
    for s, (pc, ph, rows) in probs.items():
        p = (1 - w) * pc + w * ph
        df = rows[["path", "class", "crop", "source"]].rename(columns={"class": "true"}).copy()
        df["pred"] = [classes[i] for i in p.argmax(1)]
        df["confidence"] = p.max(1)
        df[["path", "true", "pred", "confidence", "crop", "source"]].to_csv(
            os.path.join(out_dir, f"predictions_{s}.csv"), index=False)
    with open(os.path.join(out_dir, "blend.json"), "w", encoding="utf-8") as f:
        _json.dump({"cnn": cnn_dir, "head": head_dir, "weight_head": w, "val_field_acc_by_weight": accs}, f, indent=1)
    print(f"mélange {cnn_dir} + {head_dir}: poids tête {w} (val terrain {accs[w]:.4f}, CNN seul {accs[0.0]:.4f})")
    return w


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="diseases")
    ap.add_argument("--backbone", nargs="+", default=["dinov2", "bioclip"])
    ap.add_argument("--head", nargs="+", default=["linear", "mlp"])
    ap.add_argument("--field-weight", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4, help="0 = images read in the main process (less memory)")
    ap.add_argument("--loso", nargs="*", default=None, help="field sources to hold out, one at a time")
    ap.add_argument("--blend", nargs=2, metavar=("HEAD_DIR", "OUT_DIR"), default=None,
                    help="mix the deployed CNN (models/<task>) with a trained head")
    a = ap.parse_args()
    dev = torch.device(os.environ.get("AGRIA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu"))
    if a.blend:
        blend(a.task, a.blend[0], os.path.join(ROOT, "models", a.task), a.blend[1])
        return
    for name in a.backbone:
        if a.loso is not None:
            for kind in a.head:
                loso(a.task, name, kind, a.loso, dev, a.field_weight)
        else:
            run(a.task, name, a.head, dev, a.field_weight, a.workers)


if __name__ == "__main__":
    main()
