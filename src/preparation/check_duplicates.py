"""Duplicate / leakage check on the processed images. Reports only: nothing is deleted.

Two kinds of groups, per task:
  exact  same file bytes (MD5): the same source image imported twice
  near   same 64-bit difference hash (dHash, 9x8 grayscale) AND confirmed pixel by pixel: mean absolute
         difference < NEAR_MAE on 64x64 RGB, black background ignored. The hash alone gives false alarms
         on thin leaves over black (wheat): different leaves, same hash.
For each kind it counts the groups, the groups spread over several splits (leakage between train/val/test)
and the groups with several classes (label conflicts).

Usage: python src/preparation/check_duplicates.py
Output: docs/duplicates.csv (one row per image in a group). Clean with clean_duplicates.py (uses remove_images.py).
Hashes are cached in data/processed/hash_cache.csv, so a rerun only hashes new images.
"""
import hashlib
import os

import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm

PROC = os.path.join("data", "processed")
TASKS = ["diseases", "deficiency"] + (["fruits"] if os.path.exists(os.path.join(PROC, "fruits_manifest.csv")) else [])
OUT = os.path.join("docs", "duplicates.csv")
CACHE = os.path.join(PROC, "hash_cache.csv")
NEAR_MAE, BLACK = 5.0, 25


def hashes(path):
    with open(path, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    with Image.open(path) as im:
        px = list(im.convert("L").resize((9, 8), Image.BILINEAR).getdata())
    bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
    return md5, f"{int(bits, 2):016x}"


def small(path):
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB").resize((64, 64)), dtype=np.float32)


def same_picture(a, b):
    fg = (a.mean(2) > BLACK) | (b.mean(2) > BLACK)
    return fg.any() and np.abs(a - b)[fg].mean() < NEAR_MAE


def confirmed_groups(paths):
    """Split one dHash bucket into groups of images that really are the same picture (union-find)."""
    arrs, parent = [small(p) for p in paths], list(range(len(paths)))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            if root(i) != root(j) and same_picture(arrs[i], arrs[j]):
                parent[root(j)] = root(i)
    return [root(i) for i in range(len(paths))]


def load_hashes(paths):
    cache = pd.read_csv(CACHE, dtype=str).set_index("path") if os.path.exists(CACHE) else pd.DataFrame(columns=["md5", "dhash"])
    todo = [p for p in paths if p not in cache.index]
    if todo:
        new = pd.DataFrame([hashes(p) for p in tqdm(todo, desc="hashing", unit="img")], columns=["md5", "dhash"], index=todo)
        cache = pd.concat([cache, new])
        cache[~cache.index.duplicated()].rename_axis("path").to_csv(CACHE)
    return cache.loc[paths]


def main():
    found = []
    for task in TASKS:
        df = pd.read_csv(os.path.join(PROC, f"{task}_manifest.csv"))
        h = load_hashes(df["path"].tolist())
        df["md5"], df["dhash"] = h["md5"].values, h["dhash"].values
        cand = df[df.duplicated("dhash", keep=False)]
        df["near"] = None
        for key, grp in tqdm(cand.groupby("dhash"), desc=f"{task}: confirming", unit="group"):
            for idx, r in zip(grp.index, confirmed_groups(grp["path"].tolist())):
                df.at[idx, "near"] = f"{key}-{r}"
        print(f"\n{task}: {len(df)} images")
        for kind, col in [("exact", "md5"), ("near", "near")]:
            dup = df[df[col].notna() & df.duplicated(col, keep=False)].copy()
            g = dup.groupby(col)
            cross, conflict = g["split"].nunique() > 1, g["class"].nunique() > 1
            print(f"  {kind:<5} {g.ngroups:>5} groups ({len(dup)} images) | cross-split {int(cross.sum()):>5} "
                  f"| label conflicts {int(conflict.sum()):>4}")
            if conflict.any():
                pairs = dup[dup[col].isin(conflict[conflict].index)].groupby(col)["class"].apply(lambda c: " / ".join(sorted(set(c))))
                for pair, n in pairs.value_counts().head(5).items():
                    print(f"        {n:>4} x {pair}")
            dup["task"], dup["kind"], dup["group"] = task, kind, dup[col]
            dup["cross_split"], dup["label_conflict"] = dup[col].map(cross), dup[col].map(conflict)
            found.append(dup[["task", "kind", "group", "path", "split", "class", "source", "cross_split", "label_conflict"]])
    pd.concat(found).sort_values(["task", "kind", "group"]).to_csv(OUT, index=False)
    print(f"\nDetails saved in {OUT}")


if __name__ == "__main__":
    main()
