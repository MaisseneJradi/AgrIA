"""Add ONE new image source to the processed datasets, without touching what is already there.

Usage: python src/preparation/add_source.py wheat

Reads the rows of docs/extra_class_mapping.csv whose folder starts with "<source>/", resizes the images
(224x224 RGB JPEG) into data/processed/<task>/<split>/<class>/ and APPENDS them to the manifests.
Existing images, manifests and the label-audit removals are left untouched (unlike prepare_images.py,
which rebuilds everything from scratch). Split "auto" = 70/15/15 per class; otherwise the source's split is kept.
"""
import csv
import os
import random
import re
import sys

from PIL import Image

SEED, SIZE, SPLIT = 42, (224, 224), (0.70, 0.15, 0.15)
EXT = (".jpg", ".jpeg", ".png")
RAW, OUT = os.path.join("data", "raw"), os.path.join("data", "processed")


def as_path(*parts):
    flat = []
    for p in parts:
        flat += p.replace("\\", "/").split("/")
    return os.path.join(*flat)


def list_images(folder):
    if not os.path.isdir(folder):
        print(f"  WARNING: folder not found: {folder}")
        return []
    return sorted(os.path.join(r, f) for r, _, fs in os.walk(folder) for f in fs if f.lower().endswith(EXT))


def next_index(task, cls, rows):
    """First free number for <cls>_NNNNN.jpg, so new files never overwrite old ones."""
    nums = [int(m.group(1)) for r in rows if r["class"] == cls
            for m in [re.search(r"_(\d+)\.jpg$", r["path"])] if m]
    return max(nums, default=-1) + 1


def main(source):
    rng = random.Random(SEED)
    with open(os.path.join("docs", "extra_class_mapping.csv"), encoding="utf-8-sig") as f:
        mapping = [m for m in csv.DictReader(f)
                   if m["folder"].replace("\\", "/").split("/")[0] == source and m["unified_class"] != "EXCLUDE"]
    if not mapping:
        sys.exit(f"No rows for source '{source}' in docs/extra_class_mapping.csv")

    for task in sorted({m["task"] for m in mapping}):
        man = os.path.join(OUT, f"{task}_manifest.csv")
        with open(man, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if any(r["source"] == source for r in rows):
            sys.exit(f"{task}: source '{source}' is already in the manifest, nothing done.")
        new = []
        for m in mapping:
            if m["task"] != task:
                continue
            files = list_images(as_path(RAW, m["folder"]))
            if m["split"] == "auto":
                rng.shuffle(files)
                a, b = int(len(files) * SPLIT[0]), int(len(files) * (SPLIT[0] + SPLIT[1]))
                jobs = [(f, "train") for f in files[:a]] + [(f, "val") for f in files[a:b]] + [(f, "test") for f in files[b:]]
            else:
                jobs = [(f, m["split"]) for f in files]
            cls, idx = m["unified_class"], next_index(task, m["unified_class"], rows + new)
            for src, split in jobs:
                d = os.path.join(OUT, task, split, cls)
                os.makedirs(d, exist_ok=True)
                dst = os.path.join(d, f"{cls}_{idx:05d}.jpg")
                try:
                    with Image.open(src) as im:
                        im.convert("RGB").resize(SIZE).save(dst, "JPEG", quality=92)
                except Exception as e:
                    print(f"  skipped {src}: {e}")
                    continue
                new.append({"path": dst, "split": split, "class": cls, "crop": m["crop"], "source": source})
                idx += 1
            print(f"  {task:<11} {cls:<22} +{len(jobs)} ({m['folder']})")
        with open(man, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["path", "split", "class", "crop", "source"]).writerows(new)
        print(f"{task}: +{len(new)} images, manifest now {len(rows) + len(new)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python src/preparation/add_source.py <source>")
    main(sys.argv[1])
