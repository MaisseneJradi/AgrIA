"""Square copy of the olive webcam set (Kaggle serhathoca/zeytin) before add_source.py (crop task only).

Usage: python src/preparation/prepare_olive_cam.py
Reads   data/raw/olive_cam/{sağlam,hastalıklı}/*.png   (1920 x 540 strips: one olive leaf lying on a table)
Writes  data/raw/olive_cam/square/{healthy,diseased}/*.jpg

add_source.py resizes every image to 224 x 224 without keeping its proportions: a 1920 x 540 strip would be squeezed
3.5 times and an olive leaf would look oval, teaching the crop model a wrong leaf shape. Here each strip is padded to a
square with the median colour of its border, then saved at 1024 px at most. Licence of the set: not given on Kaggle.
"""
import os
import shutil

import numpy as np
from PIL import Image

SRC = os.path.join("data", "raw", "olive_cam")
OUT = os.path.join(SRC, "square")
CLASSES = {"sağlam": "healthy", "hastalıklı": "diseased"}


def pad_square(im):
    a = np.asarray(im)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    colour = tuple(int(v) for v in np.median(border, axis=0))
    side = max(im.size)
    out = Image.new("RGB", (side, side), colour)
    out.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    out.thumbnail((1024, 1024))
    return out


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for src, dst in CLASSES.items():
        os.makedirs(os.path.join(OUT, dst))
        files = sorted(f for f in os.listdir(os.path.join(SRC, src)) if f.lower().endswith((".png", ".jpg")))
        for f in files:
            with Image.open(os.path.join(SRC, src, f)) as im:
                pad_square(im.convert("RGB")).save(os.path.join(OUT, dst, os.path.splitext(f)[0] + ".jpg"), quality=92)
        print(f"{dst}: {len(files)}")


if __name__ == "__main__":
    main()
