"""Turn the pepper dataset (flat photo folder + Pascal VOC XML) into one folder per split/class for add_source.py.

Usage: python src/preparation/organize_pepper.py   then   python src/preparation/add_source.py pepper

The XML boxes are named "<deficiency>_<organ>" (fe_leaf, n_stem, healthy_root...). The model works on the
whole plant, so every image is kept and labelled with its deficiency prefix, whatever the organ.
Corrections: names are stripped (some end with \\t or \\n), photos are found by DSC number (one XML is
named "DSC02573,.xml"); unreadable XML, XML without boxes and images
mixing several deficiencies are excluded.
Split: photos are numbered in shooting order and each run of consecutive numbers is one session of one
class (near-duplicate shots), so whole runs go to train/val/test (~70/15/15 per class) to avoid leakage.
Images are hard-linked (no extra disk space) into data/raw/pepper/by_split/<split>/<class>/.
"""
import os
import random
import re
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict

SEED, SPLIT = 42, (0.70, 0.15, 0.15)
BASE = os.path.join("data", "raw", "pepper", "Pepper Nutrient Deficiency Dataset", "pepper", "pepper")
LABELS, PHOTOS = os.path.join(BASE, "Labels"), os.path.join(BASE, "pepper_photo")
OUT = os.path.join("data", "raw", "pepper", "by_split")


def label_of(xml_path):
    """Deficiency prefix of the image, or (None, reason) when it cannot be trusted."""
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return None, "unreadable xml"
    prefixes = {o.findtext("name").strip().split("_")[0] for o in root.iter("object")}
    if not prefixes:
        return None, "no box"
    if len(prefixes) > 1:
        return None, "mixed labels " + "+".join(sorted(prefixes))
    return prefixes.pop(), root.findtext("filename").strip()


def main():
    labelled, excluded = [], []
    for name in sorted(os.listdir(LABELS), key=lambda n: int(re.search(r"\d+", n).group())):
        cls, info = label_of(os.path.join(LABELS, name))
        photo = os.path.join(PHOTOS, "DSC" + re.search(r"\d+", name).group() + ".JPG")  # "DSC02573,.xml" exists
        if cls is None:
            excluded.append((name, info))
        elif not os.path.exists(photo):
            excluded.append((name, "photo not found"))
        else:
            labelled.append((cls, photo))

    # Runs of consecutive photos of the same class = one shooting session.
    runs = []
    for cls, photo in labelled:
        if runs and runs[-1][0] == cls:
            runs[-1][1].append(photo)
        else:
            runs.append((cls, [photo]))
    by_class = defaultdict(list)
    for cls, photos in runs:
        by_class[cls].append(photos)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    rng = random.Random(SEED)
    for cls in sorted(by_class):
        sessions = by_class[cls]
        rng.shuffle(sessions)
        total, done, counts = sum(len(s) for s in sessions), 0, defaultdict(int)
        for photos in sessions:
            frac = done / total
            split = "train" if frac < SPLIT[0] else "val" if frac < SPLIT[0] + SPLIT[1] else "test"
            d = os.path.join(OUT, split, cls)
            os.makedirs(d, exist_ok=True)
            for p in photos:
                dst = os.path.join(d, os.path.basename(p))
                try:
                    os.link(p, dst)
                except OSError:
                    shutil.copy2(p, dst)
            done += len(photos)
            counts[split] += len(photos)
        print(f"  {cls:<8} {len(sessions):>3} sessions  train {counts['train']:>4}  val {counts['val']:>4}  test {counts['test']:>4}")

    print(f"kept {len(labelled)} images, excluded {len(excluded)}:")
    for name, why in excluded:
        print(f"  {name}: {why}")


if __name__ == "__main__":
    main()
