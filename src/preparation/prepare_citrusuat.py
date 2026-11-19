"""Leaf-centred copy of CitrusUAT (orange leaves, Mexico, CC BY 4.0) before add_source.py.

Usage: python src/preparation/prepare_citrusuat.py
Reads   data/raw/_downloads/CitrusUAT_dataset.zip   (Zenodo 10.5281/zenodo.8294078, MD5 a0e11bc52508dfc816628b6cbc240cd6)
Writes  data/raw/citrusuat/clean/<class>/<name>.jpg         deficiencies and healthy leaves (deficiency task)
        data/raw/citrusuat/clean_other/<class>/<name>.jpg   diseases and pests: used only by the crop model, to show
                                                            it citrus leaves photographed in orchards

Each photo is 4128 x 3096 with one leaf on a dark board: resized as such to 224 x 224, the leaf would be a few pixels.
The dataset's leaf mask (Masks/<name>_mask.png) gives the leaf: the photo is cropped to the mask's box plus a 10 % margin,
made square, and saved at 1024 px at most. Deficiency classes and healthy leaves (Fe, Mg, Mn, N, Zn, Healthy) go to
clean/ for the deficiency task; the diseases and pests (HLB, greasy spot, mites, scales, leafminer) go to clean_other/
and are used only by the crop model (task "crop"): they are not classes of the diagnosis models.
"""
import io
import os
import shutil
import zipfile

import numpy as np
from PIL import Image

ZIP = os.path.join("data", "raw", "_downloads", "CitrusUAT_dataset.zip")
OUT = os.path.join("data", "raw", "citrusuat", "clean")
CLASSES = ("Fe", "Mg", "Mn", "N", "Zn", "Healthy")
OTHER = ("HLB", "Greasy_spot", "Texas_mite", "Red_scale", "Red_scale_sequelae", "Citrus_leafminer")
OUT_OTHER = os.path.join("data", "raw", "citrusuat", "clean_other")
MARGIN, MAX_SIDE = 0.10, 1024


def leaf_box(mask, size):
    m = np.array(mask.convert("L")) > 127
    if not m.any():
        return (0, 0) + size
    ys, xs = np.where(m)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    side = max(x1 - x0, y1 - y0) * (1 + 2 * MARGIN)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = size
    side = min(side, w, h)
    left = int(min(max(cx - side / 2, 0), w - side))
    top = int(min(max(cy - side / 2, 0), h - side))
    return left, top, left + int(side), top + int(side)


def main():
    for folder in (OUT, OUT_OTHER):
        if os.path.exists(folder):
            shutil.rmtree(folder)
    counts = {}
    with zipfile.ZipFile(ZIP) as z:
        for name in sorted(z.namelist()):
            if not (name.startswith("CitrusUAT_dataset/Images/") and name.lower().endswith(".jpg")):
                continue
            stem = os.path.basename(name)[:-4]
            cls = stem.rsplit("_", 1)[0]
            if cls not in CLASSES + OTHER:
                continue
            out = OUT if cls in CLASSES else OUT_OTHER
            img = Image.open(io.BytesIO(z.read(name))).convert("RGB")
            mask = Image.open(io.BytesIO(z.read(f"CitrusUAT_dataset/Masks/{stem}_mask.png")))
            crop = img.crop(leaf_box(mask, img.size))
            crop.thumbnail((MAX_SIDE, MAX_SIDE))
            os.makedirs(os.path.join(out, cls), exist_ok=True)
            crop.save(os.path.join(out, cls, f"{stem}.jpg"), quality=95)
            counts[cls] = counts.get(cls, 0) + 1
    print(f"{sum(counts.values())} feuilles recadrées : {counts}")


if __name__ == "__main__":
    main()
