"""Duplicate / leakage check on the processed images. Reports only: nothing is deleted.

Two kinds of groups, per task:
  exact  same file bytes (MD5): the same source image imported twice
  near   same 64-bit difference hash (dHash, 9x8 grayscale): resized / re-encoded copies, burst shots
For each kind it counts the groups, the groups spread over several splits (leakage between train/val/test)
and the groups with several classes (label conflicts).

Usage: python src/preparation/check_duplicates.py
Output: docs/duplicates.csv (one row per image in a group). Remove confirmed duplicates with remove_images.py only.
"""
import hashlib
import os

import pandas as pd
from PIL import Image

PROC = os.path.join("data", "processed")
TASKS = ["diseases", "deficiency"] + (["fruits"] if os.path.exists(os.path.join(PROC, "fruits_manifest.csv")) else [])
OUT = os.path.join("docs", "duplicates.csv")


def hashes(path):
    with open(path, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    with Image.open(path) as im:
        px = list(im.convert("L").resize((9, 8), Image.BILINEAR).getdata())
    bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
    return md5, f"{int(bits, 2):016x}"


def main():
    found = []
    for task in TASKS:
        df = pd.read_csv(os.path.join(PROC, f"{task}_manifest.csv"))
        df["md5"], df["dhash"] = zip(*(hashes(p) for p in df["path"]))
        print(f"\n{task}: {len(df)} images")
        for kind, col in [("exact", "md5"), ("near", "dhash")]:
            dup = df[df.duplicated(col, keep=False)].copy()
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
