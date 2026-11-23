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
         --select         epoch kept on: val (lab macro-F1), val_field (field macro-F1), mean of both, or
                          val_field_acc (field accuracy: the default with --field-val since 21/11/2026, plan step 2)
         --exclude-source S  leave source S out of training and of val_field (leave-one-source-out, loso.py)
         --aug field2     plan step 3: crop 0.4-1, shadow, brightness/contrast +-20 %, blur, motion blur, JPEG 40-95,
                          erasing; never hue or saturation (dataset.field_transform)
         --mix P          CutMix or MixUp (one of the two at random) on a share P of the training batches
Plan step 4 (defaults leave the training unchanged):
         --size S         input side in pixels (224; 300 or 384 need --batch 12-16 and --accum on 4 GB)
         --accum K        gradient accumulation: one optimizer step every K batches (effective batch = batch x K)
         --label-smoothing E   cross-entropy label smoothing (0.1 in the plan)
         --ema D          exponential moving average of the weights (decay D, e.g. 0.999): the EMA weights are
                          scored and saved
         --warmup W       linear warm-up of the learning rate over W epochs, then cosine
Plan step 5: --leaf-crop crops the field photos on their leaf box (src/preparation/leaf_boxes.py) at read time; the
         checkpoint then says leaf_crop and predict.py runs the leaf detector before the model.
Before training, src/evaluation/leakage.py checks that no training image is also in val, val_field, test or
test_field (same MD5, or same picture by dHash + pixels): a leak stops the run.

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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evaluation"))
from leakage import check as leakage_check  # noqa: E402

SEED = 42


def seed_everything(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def run_epoch(net, loader, device, loss_fn, optimizer=None, scaler=None, mixer=None, mix_p=0.0, accum=1, ema=None):
    """One pass over `loader`; trains when an optimizer is given. Returns (loss, true labels, predicted labels).
    mixer (CutMix/MixUp) is applied to a share mix_p of the training batches: the loss then uses the mixed soft
    labels, the accuracy the labels of the original images."""
    train = optimizer is not None
    net.train(train)
    total, y_true, y_pred, step = 0.0, [], [], 0
    if train:
        optimizer.zero_grad(set_to_none=True)
    with torch.set_grad_enabled(train):
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            target = y
            if train and mixer is not None and torch.rand(1).item() < mix_p:
                x, target = mixer(x, y)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                out = net(x)
                loss = loss_fn(out, target)
            if train:
                scaler.scale(loss / accum).backward()
                step += 1
                if step % accum == 0 or step == len(loader):
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
                    if ema is not None:
                        ema.update_parameters(net)
            total += loss.item() * len(y)
            y_true += y.tolist()
            y_pred += out.argmax(1).tolist()
    return total / len(loader.dataset), y_true, y_pred


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=["routing", "diseases", "deficiency", "fruits", "leaf", "crop"])
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
    ap.add_argument("--aug", choices=["standard", "field", "field2", "crop"], default="standard")
    ap.add_argument("--mix", type=float, default=0.0, help="share of batches with CutMix or MixUp")
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--leaf-crop", action="store_true", help="crop field photos on the leaf box (step 5)")
    ap.add_argument("--accum", type=int, default=1)
    ap.add_argument("--label-smoothing", type=float, default=0.0)
    ap.add_argument("--ema", type=float, default=0.0)
    ap.add_argument("--warmup", type=int, default=0)
    ap.add_argument("--sampler", choices=["none", "source"], default="none",
                    help="source: each class weighs the same, and inside a class each source weighs sqrt(its size), "
                         "so that one big source (PlantVillage) does not teach its photo style; loss unweighted")
    ap.add_argument("--select", choices=["val", "val_field", "mean", "val_field_acc"], default=None)
    ap.add_argument("--exclude-source", nargs="*", default=[])
    args = ap.parse_args()
    out = args.out or str(ROOT / "models" / args.task)

    seed_everything()
    device = torch.device(os.environ.get("AGRIA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu"))
    classes = class_names(args.task)
    balanced = args.train_set == "balanced"
    args.select = args.select or ("val_field_acc" if args.field_val else "val")
    if args.select.startswith("val_field") and not args.field_val:
        sys.exit("--select val_field / val_field_acc needs --field-val")
    leaks = leakage_check(args.task, args.field_val, args.exclude_source)
    if len(leaks):
        leaks.to_csv(os.path.join(ROOT, "reports", f"leaks_{args.task}.csv"), index=False)
        sys.exit(f"STOP: {len(leaks)} training images are also in an evaluation set (reports/leaks_{args.task}.csv)")
    ex = args.exclude_source
    train_ds = ManifestDataset(args.task, "train", classes, limit=args.limit, balanced=balanced,
                               field_holdout=args.field_val, field_weight=args.field_weight, aug=args.aug,
                               exclude_sources=ex, size=args.size, leaf_crop=args.leaf_crop)
    val_ds = ManifestDataset(args.task, "val", classes, limit=args.limit, exclude_sources=ex, size=args.size)
    g = torch.Generator().manual_seed(SEED)
    sampler = None
    if args.sampler == "source":
        df = train_ds.df
        n_group = df.groupby(["class", "source"])["path"].transform("size")
        group_mass = np.sqrt(n_group)
        class_mass = df.assign(m=group_mass).groupby(["class", "source"])["m"].first().groupby("class").sum()
        w = group_mass / n_group / df["class"].map(class_mass)
        sampler = torch.utils.data.WeightedRandomSampler(torch.tensor(w.to_numpy(), dtype=torch.double), len(df),
                                                         replacement=True, generator=g)
    train_dl = DataLoader(train_ds, args.batch, shuffle=sampler is None, sampler=sampler, num_workers=args.workers,
                          pin_memory=True, generator=g if sampler is None else None,
                          persistent_workers=args.workers > 0)
    val_dl = DataLoader(val_ds, args.batch * 2, num_workers=args.workers, pin_memory=True,
                        persistent_workers=args.workers > 0)
    field_dl = None
    if args.field_val:
        # small set: 2 short-lived workers at most (each Windows worker copies the process: memory runs out)
        field_dl = DataLoader(ManifestDataset(args.task, "val_field", classes, exclude_sources=ex, size=args.size,
                                              leaf_crop=args.leaf_crop), args.batch * 2,
                              num_workers=min(2, args.workers), pin_memory=True)
    print(f"{args.task}: {len(classes)} classes, train {len(train_ds)}, val {len(val_ds)} images, "
          f"{args.model}, {args.train_set} train set, field val {len(field_dl.dataset) if field_dl else 0}, "
          f"field weight {args.field_weight}, aug {args.aug}, sampler {args.sampler}, select on {args.select}, "
          f"excluded sources {ex or '-'}, mix {args.mix}, size {args.size}, accum {args.accum}, "
          f"label smoothing {args.label_smoothing}, ema {args.ema}, warmup {args.warmup}, "
          f"on {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))

    net = build(args.model, len(classes)).to(device)
    weights = class_weights(args.task, classes).to(device) if balanced and args.sampler == "none" else None
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights, label_smoothing=args.label_smoothing)
    optimizer = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=0.05)
    if args.warmup > 0:
        scheduler = torch.optim.lr_scheduler.SequentialLR(optimizer, [
            torch.optim.lr_scheduler.LinearLR(optimizer, start_factor=0.1, total_iters=args.warmup),
            torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs - args.warmup))],
            milestones=[args.warmup])
    else:
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    ema = None
    if args.ema > 0:
        from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn
        ema = AveragedModel(net, multi_avg_fn=get_ema_multi_avg_fn(args.ema), use_buffers=True)
    scored = ema.module if ema is not None else net  # the network evaluated and saved
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    mixer = None
    if args.mix > 0:
        from torchvision.transforms import v2
        mixer = v2.RandomChoice([v2.CutMix(num_classes=len(classes)), v2.MixUp(num_classes=len(classes))])

    os.makedirs(out, exist_ok=True)
    save_labels(classes, out)
    history, best, wait = [], -1.0, 0
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        tr_loss, tr_y, tr_p = run_epoch(net, train_dl, device, loss_fn, optimizer, scaler, mixer, args.mix,
                                        args.accum, ema)
        va_loss, va_y, va_p = run_epoch(scored, val_dl, device, loss_fn)
        scheduler.step()
        row = {"epoch": epoch, "train_loss": round(tr_loss, 4), "train_acc": round(accuracy_score(tr_y, tr_p), 4),
               "val_loss": round(va_loss, 4), "val_acc": round(accuracy_score(va_y, va_p), 4),
               "val_macro_f1": round(f1_score(va_y, va_p, average="macro"), 4)}
        if field_dl is not None:
            _, fy, fp = run_epoch(scored, field_dl, device, loss_fn)
            row["val_field_acc"] = round(accuracy_score(fy, fp), 4)
            row["val_field_macro_f1"] = round(f1_score(fy, fp, labels=sorted(set(fy)), average="macro"), 4)
        row["score"] = {"val": row["val_macro_f1"], "val_field": row.get("val_field_macro_f1"),
                        "mean": round((row["val_macro_f1"] + row.get("val_field_macro_f1", 0)) / 2, 4),
                        "val_field_acc": row.get("val_field_acc")}[args.select]
        row["seconds"] = round(time.time() - t0)
        history.append(row)
        print(" | ".join(f"{k} {v}" for k, v in row.items()), flush=True)
        if row["score"] > best:
            best, wait = row["score"], 0
            torch.save({"arch": args.model, "classes": classes, "state_dict": scored.state_dict(),
                        "size": args.size, "leaf_crop": args.leaf_crop},
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
