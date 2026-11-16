"""Train one vision task and save the best model on the validation set.

Usage:
  python src/vision/train.py --task routing                              full run, efficientnet_b0
  python src/vision/train.py --task routing --limit 500 --epochs 1      quick check of the whole chain
  python src/vision/train.py --task diseases --model vit_b_16 --batch 16 --lr 5e-5
  python src/vision/train.py --task diseases --train-set raw --out models/diseases_raw      without balancing (H3)
Options: --epochs (20) --batch (32) --lr (3e-4) --patience (4) --workers (4) --limit (none) --out (models/<task>)
         --train-set balanced (default: balanced set + class weights) | raw (manifest train split, plain loss)
Field photos (H1):
  python src/vision/train.py --task diseases --train-set raw --field-val --field-weight 5 --aug field --out models/diseases_field
         --field-val      hold out 15 % of the field photos of train as val_field, scored every epoch
         --field-weight K field photos seen K times per epoch
         --aug field      stronger framing / blur changes, never a colour change
         --select         epoch kept on: val (lab macro-F1), val_field, or mean of both (default with --field-val)

Pretrained backbone, AdamW with a cosine schedule, cross-entropy weighted by class, mixed precision on GPU,
early stopping on the validation macro-F1 (rare classes count as much as common ones). Seed 42 everywhere.
Output in models/<task>/: model.pt (weights + settings), labels.json (class order), metrics.json (history, best epoch).
"""
import argparse
import json
import os
import random
import sys
import time

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.dirname(__file__))
from dataset import ROOT, ManifestDataset, class_names, class_weights, save_labels  # noqa: E402
from models import build  # noqa: E402

SEED = 42


def seed_everything(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def run_epoch(net, loader, device, loss_fn, optimizer=None, scaler=None):
    """One pass over `loader`; trains when an optimizer is given. Returns (loss, true labels, predicted labels)."""
    train = optimizer is not None
    net.train(train)
    total, y_true, y_pred = 0.0, [], []
    with torch.set_grad_enabled(train):
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                out = net(x)
                loss = loss_fn(out, y)
            if train:
                optimizer.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            total += loss.item() * len(y)
            y_true += y.tolist()
            y_pred += out.argmax(1).tolist()
    return total / len(loader.dataset), y_true, y_pred


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=["routing", "diseases", "deficiency", "fruits", "leaf"])
    ap.add_argument("--model", default="efficientnet_b0")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--patience", type=int, default=4)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None, help="use only N images per split (quick check)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--train-set", choices=["balanced", "raw"], default="balanced")
    ap.add_argument("--field-val", action="store_true")
    ap.add_argument("--field-weight", type=int, default=1)
    ap.add_argument("--aug", choices=["standard", "field"], default="standard")
    ap.add_argument("--select", choices=["val", "val_field", "mean"], default=None)
    args = ap.parse_args()
    out = args.out or str(ROOT / "models" / args.task)

    seed_everything()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    classes = class_names(args.task)
    balanced = args.train_set == "balanced"
    args.select = args.select or ("mean" if args.field_val else "val")
    train_ds = ManifestDataset(args.task, "train", classes, limit=args.limit, balanced=balanced,
                               field_holdout=args.field_val, field_weight=args.field_weight, aug=args.aug)
    val_ds = ManifestDataset(args.task, "val", classes, limit=args.limit)
    g = torch.Generator().manual_seed(SEED)
    train_dl = DataLoader(train_ds, args.batch, shuffle=True, num_workers=args.workers, pin_memory=True,
                          generator=g, persistent_workers=args.workers > 0)
    val_dl = DataLoader(val_ds, args.batch * 2, num_workers=args.workers, pin_memory=True,
                        persistent_workers=args.workers > 0)
    field_dl = None
    if args.field_val:
        # small set: 2 short-lived workers at most (each Windows worker copies the process: memory runs out)
        field_dl = DataLoader(ManifestDataset(args.task, "val_field", classes), args.batch * 2,
                              num_workers=min(2, args.workers), pin_memory=True)
    print(f"{args.task}: {len(classes)} classes, train {len(train_ds)}, val {len(val_ds)} images, "
          f"{args.model}, {args.train_set} train set, field val {len(field_dl.dataset) if field_dl else 0}, "
          f"field weight {args.field_weight}, aug {args.aug}, select on {args.select}, on {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))

    net = build(args.model, len(classes)).to(device)
    weights = class_weights(args.task, classes).to(device) if balanced else None
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=0.05)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")

    os.makedirs(out, exist_ok=True)
    save_labels(classes, out)
    history, best, wait = [], -1.0, 0
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        tr_loss, tr_y, tr_p = run_epoch(net, train_dl, device, loss_fn, optimizer, scaler)
        va_loss, va_y, va_p = run_epoch(net, val_dl, device, loss_fn)
        scheduler.step()
        row = {"epoch": epoch, "train_loss": round(tr_loss, 4), "train_acc": round(accuracy_score(tr_y, tr_p), 4),
               "val_loss": round(va_loss, 4), "val_acc": round(accuracy_score(va_y, va_p), 4),
               "val_macro_f1": round(f1_score(va_y, va_p, average="macro"), 4)}
        if field_dl is not None:
            _, fy, fp = run_epoch(net, field_dl, device, loss_fn)
            row["val_field_acc"] = round(accuracy_score(fy, fp), 4)
            row["val_field_macro_f1"] = round(f1_score(fy, fp, labels=sorted(set(fy)), average="macro"), 4)
        row["score"] = {"val": row["val_macro_f1"], "val_field": row.get("val_field_macro_f1"),
                        "mean": round((row["val_macro_f1"] + row.get("val_field_macro_f1", 0)) / 2, 4)}[args.select]
        row["seconds"] = round(time.time() - t0)
        history.append(row)
        print(" | ".join(f"{k} {v}" for k, v in row.items()), flush=True)
        if row["score"] > best:
            best, wait = row["score"], 0
            torch.save({"arch": args.model, "classes": classes, "state_dict": net.state_dict()},
                       os.path.join(out, "model.pt"))
        else:
            wait += 1
            if wait >= args.patience:
                print(f"early stop: no gain for {args.patience} epochs")
                break
    best_row = max(history, key=lambda r: r["score"])
    with open(os.path.join(out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"task": args.task, "model": args.model, "args": vars(args), "device": str(device),
                   "best": best_row, "history": history}, f, indent=1)
    print(f"best epoch {best_row['epoch']}: val macro-F1 {best_row['val_macro_f1']}, "
          f"val_field macro-F1 {best_row.get('val_field_macro_f1', '-')}, saved in {out}")


if __name__ == "__main__":
    main()
