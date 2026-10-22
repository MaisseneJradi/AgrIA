"""Class balance of the TRAIN split of each image task, without changing any manifest or the val / test splits.

  cap    classes above CAP train images are under-sampled; the images kept are drawn in turn from each
         (crop, source) group, so no crop or source of the class is lost (diversity first, then random).
         In the deficiency task the cap is applied per (class, crop) as well, so pepper (the source of most
         deficiency images) cannot outweigh the other crops inside N, K, Mg, P and healthy.
  floor  classes below FLOOR get augmented copies of their own TRAIN images (never val/test: no leakage):
         flip, rotation +-20 deg, crop-zoom 85-100 %, brightness / contrast +-15 %. Hues are never changed:
         yellowing, chlorosis and spot colours are the symptoms. At most MAX_FACTOR x the real images.
  weights  class weights for the loss, from the balanced counts: effective number of samples
         (Cui et al. 2019, beta 0.999), normalised to mean 1.
val / test keep the real distribution: the model is judged on what it will meet.

Usage: python src/preparation/balance_training.py
Output: data/processed/balanced/<task>_train.csv   (path, class, crop, source, origin = real | augmented)
        data/processed/balanced/<task>_class_weights.csv
        data/processed/augmented/<task>/<class>/aug_<n>.jpg
        docs/class_balance.csv  (before / after per class)
"""
import os
import random

import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance, ImageOps

SEED = 42
PROC = os.path.join("data", "processed")
OUT = os.path.join(PROC, "balanced")
AUG = os.path.join(PROC, "augmented")
# task -> (cap, floor, cap per (class, crop) or None)
POLICY = {"diseases": (1200, 300, None), "deficiency": (1200, 300, 600), "fruits": (400, 100, None)}
MAX_FACTOR = 5
BETA = 0.999


def diverse_sample(df, n, rng):
    """n rows drawn in turn from each (crop, source) group, random inside a group."""
    groups = [g.sample(frac=1, random_state=rng.randrange(10**9)).index.tolist()
              for _, g in df.groupby(["crop", "source"])]
    out = []
    while len(out) < n:
        for g in groups:
            if g and len(out) < n:
                out.append(g.pop())
    return df.loc[out]


def augment(img, rng):
    if rng.random() < 0.5:
        img = ImageOps.mirror(img)
    if rng.random() < 0.3:
        img = ImageOps.flip(img)
    img = img.rotate(rng.uniform(-20, 20), resample=Image.BILINEAR, fillcolor=(0, 0, 0))
    s = rng.uniform(0.85, 1.0)
    w, h = img.size
    cw, ch = int(w * s), int(h * s)
    x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
    img = img.crop((x, y, x + cw, y + ch)).resize((w, h), Image.BILINEAR)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.85, 1.15))
    return ImageEnhance.Contrast(img).enhance(rng.uniform(0.85, 1.15))


def balance(task, cap, floor, cap_crop, rng):
    df = pd.read_csv(os.path.join(PROC, f"{task}_manifest.csv"))
    train = df[df["split"] == "train"].copy()
    before = train["class"].value_counts()
    kept, aug_rows = [], []
    for cls, g in train.groupby("class"):
        if cap_crop:  # deficiency: no crop may exceed cap_crop images inside one class
            g = pd.concat([diverse_sample(c, min(len(c), cap_crop), rng) for _, c in g.groupby("crop")])
        if len(g) > cap:
            g = diverse_sample(g, cap, rng)
        kept.append(g.assign(origin="real"))
        target = min(floor, MAX_FACTOR * len(g))
        if len(g) < target:
            folder = os.path.join(AUG, task, cls)
            os.makedirs(folder, exist_ok=True)
            src = g.to_dict("records")
            for k in range(target - len(g)):
                r = src[k % len(src)]  # every real image is used before any is used twice
                path = os.path.join(folder, f"aug_{k:05d}.jpg")
                with Image.open(r["path"]) as im:
                    augment(im.convert("RGB"), rng).save(path, "JPEG", quality=92)
                aug_rows.append({**r, "path": path, "origin": "augmented"})
    bal = pd.concat(kept + [pd.DataFrame(aug_rows)], ignore_index=True)
    bal = bal.sample(frac=1, random_state=SEED)[["path", "class", "crop", "source", "origin"]]
    os.makedirs(OUT, exist_ok=True)
    bal.to_csv(os.path.join(OUT, f"{task}_train.csv"), index=False)
    after = bal["class"].value_counts()
    eff = (1 - BETA ** after) / (1 - BETA)
    w = (1 / eff) / (1 / eff).mean()
    pd.DataFrame({"class": w.index, "weight": w.round(4).values, "n_train_balanced": after[w.index].values}) \
        .sort_values("class").to_csv(os.path.join(OUT, f"{task}_class_weights.csv"), index=False)
    rep = pd.DataFrame({"task": task, "class": before.index, "train_avant": before.values})
    rep["train_apres"] = rep["class"].map(after)
    rep["dont_augmentees"] = rep["class"].map(bal[bal["origin"] == "augmented"]["class"].value_counts()).fillna(0) \
        .astype(int)
    print(f"{task:10} train {len(train):>6} -> {len(bal):>6} | max/min {before.max() / before.min():5.0f}x -> "
          f"{after.max() / after.min():4.1f}x | augmented {len(aug_rows)}")
    return rep


def main():
    rng = random.Random(SEED)
    np.random.seed(SEED)
    rep = pd.concat([balance(t, *p, rng) for t, p in POLICY.items()], ignore_index=True)
    rep.to_csv(os.path.join("docs", "class_balance.csv"), index=False)


if __name__ == "__main__":
    main()
