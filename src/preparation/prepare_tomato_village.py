"""Clean copy of Tomato-Village (variant a, classification) before add_source.py: one image per leaf.

Usage: python src/preparation/prepare_tomato_village.py
Reads   data/raw/tomato_village/Variant-a(Multiclass Classification)/<split>/<class>/*.jpg   (never changed)
Writes  data/raw/tomato_village/clean/<split>/<class>/*.jpg                                   (copies)

The authors' folders hold their own augmented copies of each leaf: mirrored, flipped, rotated by 90/180/270 degrees
or by any angle (black corners), sometimes the same picture twice; 217 such pairs sit in different splits (train vs
test), which would inflate every test score. Here:
  - images are grouped when one equals another up to a mirror, a flip or a right-angle rotation (same 64-bit dHash);
  - one image is kept per group: the first one without black corners, in the order train > val > test of the
    authors' split, so a leaf seen in train is never tested;
  - images rotated by any angle (2+ black corners) are left out: their original cannot be matched reliably.
Only the deficiency and healthy classes are kept (the diseases of the dataset are not used here).
"""
import collections
import os
import shutil

from PIL import Image, ImageOps

SRC = os.path.join("data", "raw", "tomato_village", "Variant-a(Multiclass Classification)")
OUT = os.path.join("data", "raw", "tomato_village", "clean")
CLASSES = ("Healthy", "Magnesium Deficiency", "Nitrogen Deficiency", "Pottassium Deficiency")
ORDER = {"train": 0, "val": 1, "test": 2}


def dhash(im):
    g = im.convert("L").resize((9, 8))
    px = list(g.getdata())
    return sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])


def variants(im):
    return {dhash(im), dhash(ImageOps.mirror(im)), dhash(ImageOps.flip(im)), dhash(im.rotate(180)),
            dhash(im.rotate(90, expand=True)), dhash(im.rotate(270, expand=True))}


def black_corners(im):
    g = im.convert("L")
    w, h = g.size
    return sum(g.getpixel(p) < 20 for p in [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)]) >= 2


def main():
    items = []
    for split in ORDER:
        for cls in CLASSES:
            folder = os.path.join(SRC, split, cls)
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(".jpg"):
                    with Image.open(os.path.join(folder, f)) as im:
                        im = im.convert("RGB")
                        items.append({"split": split, "cls": cls, "file": f, "hashes": variants(im),
                                      "rotated": black_corners(im)})
    parent = list(range(len(items)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    by_hash = collections.defaultdict(list)
    for i, it in enumerate(items):
        for h in it["hashes"]:
            by_hash[h].append(i)
    for ids in by_hash.values():
        for j in ids[1:]:
            parent[root(j)] = root(ids[0])
    groups = collections.defaultdict(list)
    for i in range(len(items)):
        groups[root(i)].append(i)

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    kept, stats = 0, collections.Counter()
    for ids in groups.values():
        candidates = sorted((i for i in ids if not items[i]["rotated"]), key=lambda i: ORDER[items[i]["split"]])
        if not candidates:
            stats["groupe sans original"] += 1
            continue
        keep = items[candidates[0]]
        labels = {items[i]["cls"] for i in ids}
        if len(labels) > 1:  # same leaf under two labels: true label unknown
            stats["conflit d'étiquette"] += 1
            continue
        dst = os.path.join(OUT, keep["split"], keep["cls"])
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(os.path.join(SRC, keep["split"], keep["cls"], keep["file"]), dst)
        kept += 1
        stats[(keep["split"], keep["cls"])] += 1
    print(f"{len(items)} images, {len(groups)} feuilles distinctes, {kept} gardées")
    for k, v in sorted(stats.items(), key=str):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
