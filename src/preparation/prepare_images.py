"""Build the processed image datasets for AgrIA.

Reads the two class-mapping CSVs in docs/ and writes resized RGB images to:
  data/processed/diseases/{train,val,test,test_field}/<unified_class>/
  data/processed/deficiency/{train,val,test}/<unified_class>/
plus one manifest CSV per task (path, split, class, crop, source).

Rules
- PlantVillage (lab) images: stratified split 70/15/15 per class.
- PlantDoc train (field) images: added to train, so the model also sees field photos.
- PlantDoc test (field) images: kept apart as "test_field" to measure the lab -> field gap.
- Deficiency: "EXCLUDE" classes are skipped; split 70/15/15 per class.
- Deficiency "healthy" has only 6 images, so it is topped up with healthy leaves sampled from PlantVillage.
"""
import csv
import os
import random

from PIL import Image

SEED = 42
SIZE = (224, 224)
SPLIT = (0.70, 0.15, 0.15)
HEALTHY_PER_CROP = 50          # PlantVillage healthy leaves added to the deficiency "healthy" class
EXT = (".jpg", ".jpeg", ".png")

PV_ROOT = os.path.join("data", "raw", "plantvillage", "plantvillage dataset", "color")
PD_ROOT = os.path.join("data", "raw", "plantdoc")
DEF_ROOT = os.path.join("data", "raw", "deficiency")
OUT_ROOT = os.path.join("data", "processed")
DOCS = "docs"


def list_images(folder):
    if not os.path.isdir(folder):
        return []
    found = []
    for root, _, files in os.walk(folder):
        found += [os.path.join(root, f) for f in files if f.lower().endswith(EXT)]
    return sorted(found)


def split_list(items, rng):
    items = items[:]
    rng.shuffle(items)
    n = len(items)
    n_train, n_val = int(n * SPLIT[0]), int(n * SPLIT[1])
    return {"train": items[:n_train],
            "val": items[n_train:n_train + n_val],
            "test": items[n_train + n_val:]}


def save_image(src, task, split, cls, idx):
    """Resize to SIZE, convert to RGB, save as JPEG. Returns the new path, or None if the file is corrupt."""
    dst_dir = os.path.join(OUT_ROOT, task, split, cls)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{cls}_{idx:05d}.jpg")
    try:
        with Image.open(src) as im:
            im.convert("RGB").resize(SIZE).save(dst, "JPEG", quality=92)
        return dst
    except Exception as e:  # corrupt or unreadable image
        print(f"  skipped {src}: {e}")
        return None


def write_manifest(rows, task):
    path = os.path.join(OUT_ROOT, f"{task}_manifest.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "split", "class", "crop", "source"])
        w.writeheader()
        w.writerows(rows)
    print(f"{task}: {len(rows)} images -> {path}")


def read_mapping(name):
    with open(os.path.join(DOCS, name), encoding="utf-8-sig") as f:   # utf-8-sig handles the BOM from PowerShell
        return list(csv.DictReader(f))


def build_diseases(rng):
    rows = []
    for m in read_mapping("disease_class_mapping.csv"):
        cls, crop = m["unified_class"], m["crop"]
        jobs = []
        for split, files in split_list(list_images(os.path.join(PV_ROOT, m["plantvillage_folder"])), rng).items():
            jobs += [(f, split, "plantvillage") for f in files]
        if m["plantdoc_folder"]:
            jobs += [(f, "train", "plantdoc") for f in list_images(os.path.join(PD_ROOT, "train", m["plantdoc_folder"]))]
            jobs += [(f, "test_field", "plantdoc") for f in list_images(os.path.join(PD_ROOT, "test", m["plantdoc_folder"]))]
        for i, (src, split, source) in enumerate(jobs):
            dst = save_image(src, "diseases", split, cls, i)
            if dst:
                rows.append({"path": dst, "split": split, "class": cls, "crop": crop, "source": source})
        print(f"  {cls:<35} {len(jobs)} images")
    write_manifest(rows, "diseases")


def build_deficiency(rng):
    by_class = {}   # unified_class -> list of (src, crop, source)
    for m in read_mapping("deficiency_class_mapping.csv"):
        if m["unified_class"] == "EXCLUDE":
            continue
        parts = m["original_class"].replace("\\", "/").split("/")   # works on Windows and Linux
        files = list_images(os.path.join(DEF_ROOT, m["dataset"], *parts))
        by_class.setdefault(m["unified_class"], []).extend((f, m["crop"], m["dataset"]) for f in files)

    # Top up "healthy" with PlantVillage healthy leaves (several crops)
    for m in read_mapping("disease_class_mapping.csv"):
        if m["status"] == "healthy":
            files = list_images(os.path.join(PV_ROOT, m["plantvillage_folder"]))
            picked = rng.sample(files, min(HEALTHY_PER_CROP, len(files)))
            by_class.setdefault("healthy", []).extend((f, m["crop"], "plantvillage") for f in picked)

    rows = []
    for cls in sorted(by_class):
        for split, items in split_list(by_class[cls], rng).items():
            for i, (src, crop, source) in enumerate(items):
                dst = save_image(src, "deficiency", split, cls, i)
                if dst:
                    rows.append({"path": dst, "split": split, "class": cls, "crop": crop, "source": source})
        print(f"  {cls:<20} {len(by_class[cls])} images")
    write_manifest(rows, "deficiency")


if __name__ == "__main__":
    rng = random.Random(SEED)
    print("== Diseases ==")
    build_diseases(rng)
    print("== Deficiency ==")
    build_deficiency(rng)
    print("Done.")
