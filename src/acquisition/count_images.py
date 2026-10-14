"""Count images per class for each image dataset (first EDA check)."""
import os
from collections import Counter

ROOTS = ["data/raw/plantvillage", "data/raw/plantdoc", "data/raw/deficiency"]
EXT = (".jpg", ".jpeg", ".png")

for root in ROOTS:
    counts = Counter()
    for folder, _, files in os.walk(root):
        n = sum(f.lower().endswith(EXT) for f in files)
        if n:
            rel = os.path.relpath(folder, root)
            counts[rel] += n
    print(f"\n=== {root}: {sum(counts.values())} images, {len(counts)} folders ===")
    for cls, n in sorted(counts.items()):
        print(f"  {cls:<70} {n}")