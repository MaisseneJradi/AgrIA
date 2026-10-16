"""Build the processed image datasets for AgrIA.

Reads the class-mapping CSVs in docs/ and writes resized RGB images to:
  data/processed/diseases/{train,val,test,test_field}/<unified_class>/
  data/processed/deficiency/{train,val,test}/<unified_class>/
plus one manifest CSV per task (path, split, class, crop, source).

Rules
- PlantVillage (lab): stratified split 70/15/15 per class.
- PlantDoc train (field): added to train. PlantDoc test (field): kept apart as "test_field".
- Extra sources (docs/extra_class_mapping.csv: olive, citrus, date palm):
  split "auto" = 70/15/15 per class; split train/val/test = keep the split given by the source (Roboflow olive).
- Deficiency: "EXCLUDE" rows are skipped; split 70/15/15 per class.
- Deficiency "healthy" is topped up with healthy leaves sampled from PlantVillage.
- The output folders are rebuilt from scratch at each run.
"""
import csv
import os
import random
import shutil

from PIL import Image

SEED = 42
SIZE = (224, 224)
SPLIT = (0.70, 0.15, 0.15)
HEALTHY_PER_CROP = 50          # PlantVillage healthy leaves added to the deficiency "healthy" class
EXT = (".jpg", ".jpeg", ".png")

RAW = os.path.join("data", "raw")
PV_ROOT = os.path.join(RAW, "plantvillage", "plantvillage dataset", "color")
PD_ROOT = os.path.join(RAW, "plantdoc")
DEF_ROOT = os.path.join(RAW, "deficiency")
OUT_ROOT = os.path.join("data", "processed")
DOCS = "docs"


def as_path(*parts):
    """Join path parts, accepting / or \\ inside the CSV values (works on Windows and Linux)."""
    flat = []
    for p in parts:
        flat += p.replace("\\", "/").split("/")
    return os.path.join(*flat)


def list_images(folder):
    if not os.path.isdir(folder):
        print(f"  WARNING: folder not found: {folder}")
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


def read_mapping(name):
    path = os.path.join(DOCS, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:   # utf-8-sig handles the BOM from PowerShell
        return list(csv.DictReader(f))


def add_extra_jobs(task, jobs, rng):
    """Add olive / citrus / date palm images from extra_class_mapping.csv to jobs[class]."""
    for m in read_mapping("extra_class_mapping.csv"):
        if m["task"] != task or m["unified_class"] == "EXCLUDE":
            continue
        cls, crop = m["unified_class"], m["crop"]
        source = m["folder"].replace("\\", "/").split("/")[0]      # olive, citrus or datepalm
        files = list_images(as_path(RAW, m["folder"]))
        if m["split"] == "auto":
            for split, part in split_list(files, rng).items():
                jobs.setdefault(cls, []).extend((f, split, source, crop) for f in part)
        else:
            jobs.setdefault(cls, []).extend((f, m["split"], source, crop) for f in files)


def save_all(task, jobs):
    out = os.path.join(OUT_ROOT, task)
    if os.path.isdir(out):
        shutil.rmtree(out)                      # rebuild from scratch: no stale files
    rows = []
    for cls in sorted(jobs):
        for i, (src, split, source, crop) in enumerate(jobs[cls]):
            dst = save_image(src, task, split, cls, i)
            if dst:
                rows.append({"path": dst, "split": split, "class": cls, "crop": crop, "source": source})
        print(f"  {cls:<35} {len(jobs[cls])} images")
    path = os.path.join(OUT_ROOT, f"{task}_manifest.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "split", "class", "crop", "source"])
        w.writeheader()
        w.writerows(rows)
    print(f"{task}: {len(rows)} images -> {path}")


def build_diseases(rng):
    jobs = {}
    for m in read_mapping("disease_class_mapping.csv"):
        cls, crop = m["unified_class"], m["crop"]
        for split, files in split_list(list_images(os.path.join(PV_ROOT, m["plantvillage_folder"])), rng).items():
            jobs.setdefault(cls, []).extend((f, split, "plantvillage", crop) for f in files)
        if m["plantdoc_folder"]:
            jobs[cls] += [(f, "train", "plantdoc", crop) for f in list_images(os.path.join(PD_ROOT, "train", m["plantdoc_folder"]))]
            jobs[cls] += [(f, "test_field", "plantdoc", crop) for f in list_images(os.path.join(PD_ROOT, "test", m["plantdoc_folder"]))]
    add_extra_jobs("diseases", jobs, rng)
    save_all("diseases", jobs)


def build_deficiency(rng):
    pools = {}   # class -> list of (src, source, crop)
    for m in read_mapping("deficiency_class_mapping.csv"):
        if m["unified_class"] == "EXCLUDE":
            continue
        files = list_images(as_path(DEF_ROOT, m["dataset"], m["original_class"]))
        pools.setdefault(m["unified_class"], []).extend((f, m["dataset"], m["crop"]) for f in files)
    for m in read_mapping("extra_class_mapping.csv"):
        if m["task"] == "deficiency" and m["unified_class"] != "EXCLUDE":
            files = list_images(as_path(RAW, m["folder"]))
            pools.setdefault(m["unified_class"], []).extend((f, "datepalm", m["crop"]) for f in files)
    # Top up "healthy" with PlantVillage healthy leaves (several crops)
    for m in read_mapping("disease_class_mapping.csv"):
        if m["status"] == "healthy":
            files = list_images(os.path.join(PV_ROOT, m["plantvillage_folder"]))
            picked = rng.sample(files, min(HEALTHY_PER_CROP, len(files)))
            pools.setdefault("healthy", []).extend((f, "plantvillage", m["crop"]) for f in picked)

    jobs = {}
    for cls, items in pools.items():
        for split, part in split_list(items, rng).items():
            jobs.setdefault(cls, []).extend((f, split, source, crop) for f, source, crop in part)
    save_all("deficiency", jobs)


if __name__ == "__main__":
    rng = random.Random(SEED)
    print("== Diseases ==")
    build_diseases(rng)
    print("== Deficiency ==")
    build_deficiency(rng)
    print("Done.")
