"""Prepare the three FIELD photo sources added on 20/11/2026 (user request: more real field photos, only the 14 crops).

Sources (downloaded into data/raw/_downloads/, only the project crops extracted):
  plantwild     PlantWild v2 (Wei et al., 2024, huggingface.co/datasets/uqtwei2/PlantWild, CC BY-NC-ND 4.0):
                in-the-wild photos, 49 classes of the project crops kept out of 115 (6,774 photos).
  gvlid         GVLiD (Mendeley 10.17632/wkymf8bhcg.5, CC BY 4.0): grapevine leaves in the vineyard (3,477 photos).
  potato_field  Potato Leaf Disease Dataset in Uncontrolled Environment (Shabrina et al., 2024,
                Mendeley 10.17632/ptz377bwb8.1, CC BY 4.0): potato plants on farms, Java (3,076 photos).
Not used: PlantSeg (all its photos are already in PlantWild, same authors: only its masks are kept,
data/raw/plantseg/masks); the Mendeley "Tomato Leaf and Fruit" set (leaves on white paper, not field photos).

What this script does, for each source: data/raw/<source>/original/<class>/ -> data/raw/<source>/leaf/<class>/
  - the ROUTER (models/routing) reads every photo: only photos it sees as a LEAF are kept (fruits, ears, stems and
    photos without a leaf are set aside, as the app does);
  - the EXIF orientation of phone photos is applied, the photo is saved as RGB JPEG (longest side 1024 px).
Report: docs/field_sources_routing.csv (one row per class: kept, set aside). Nothing in data/processed is touched:
the photos are then added with add_source.py (split "auto_field": 85 % train, 15 % test_field).

Usage: python src/preparation/prepare_field_sources.py [plantwild gvlid potato_field]
"""
import csv
import os
import shutil
import sys

from PIL import Image, ImageOps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vision"))
from predict import probabilities  # noqa: E402

RAW = os.path.join("data", "raw")
EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
SOURCES = {"plantwild": "", "gvlid": "DATASET", "potato_field": ""}  # sub-folder that holds the class folders
REPORT = os.path.join("docs", "field_sources_routing.csv")
MAX_SIDE = 1024


def originals(source):
    """Move the extracted class folders under <source>/original/ once (first run), return that folder."""
    base = os.path.join(RAW, source)
    orig = os.path.join(base, "original")
    if not os.path.isdir(orig):
        src = os.path.join(base, SOURCES[source]) if SOURCES[source] else base
        classes = [d for d in os.listdir(src) if os.path.isdir(os.path.join(src, d)) and d not in ("docs", "original",
                                                                                                 "leaf")]
        os.makedirs(orig)
        for c in classes:
            shutil.move(os.path.join(src, c), os.path.join(orig, c))
    return orig


def prepare(source, report):
    orig, out = originals(source), os.path.join(RAW, source, "leaf")
    for cls in sorted(os.listdir(orig)):
        files = sorted(f for f in os.listdir(os.path.join(orig, cls)) if f.lower().endswith(EXT))
        kept = aside = 0
        os.makedirs(os.path.join(out, cls), exist_ok=True)
        for f in files:
            p = os.path.join(orig, cls, f)
            try:
                route = probabilities("routing", p)
            except Exception as e:
                print(f"  illisible : {p} ({e})")
                aside += 1
                continue
            if max(route, key=route.get) != "leaf":
                aside += 1
                continue
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                im.save(os.path.join(out, cls, os.path.splitext(f)[0] + ".jpg"), "JPEG", quality=92)
            kept += 1
        report.append({"source": source, "class": cls, "photos": len(files), "feuille_gardee": kept,
                       "ecartee_routeur": aside})
        print(f"  {source:<13} {cls:<45} {kept:5d} gardées / {len(files)}", flush=True)


if __name__ == "__main__":
    rows = []
    for s in sys.argv[1:] or SOURCES:
        prepare(s, rows)
    old = []
    if os.path.exists(REPORT):
        with open(REPORT, encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r["source"] not in {r2["source"] for r2 in rows}]
    with open(REPORT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source", "class", "photos", "feuille_gardee", "ecartee_routeur"])
        w.writeheader()
        w.writerows(old + rows)
    print("rapport :", REPORT)
