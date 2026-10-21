"""Build the routing ("aiguillage") dataset for the orchestrator: what does the photo show?

Classes:
  leaf   leaves sampled from the diseases and deficiency manifests, at most PER_SOURCE per source so that
         lab (PlantVillage) and field sources weigh the same (pepper excluded: its photos include roots, stems)
  fruit  every image of the fruits manifest
  other  no leaf, no fruit: COCO val2017 photos (people, animals, objects, streets, rooms...) without any
         plant, fruit or vegetable annotation -> the agent answers "send me a photo of the leaf or fruit"
Leaf and fruit rows point to the existing processed files (same split, no copy, so no leakage between the
routing split and the task splits). Other images are resized to 224x224 into data/processed/routing/<split>/other/.

Usage: python src/preparation/build_routing.py      (rebuilds data/processed/routing_manifest.csv)
Needs data/raw/coco/val2017/ and data/raw/coco/annotations/instances_val2017.json.
"""
import json
import os
import random
import shutil

import pandas as pd
from PIL import Image

SEED, SIZE, SPLIT, PER_SOURCE = 42, (224, 224), (0.70, 0.15, 0.15), 700
PROC, COCO = os.path.join("data", "processed"), os.path.join("data", "raw", "coco")
# COCO categories that show a plant, a fruit or a vegetable (or usually flowers, for vase)
PLANT_CATS = {"potted plant", "broccoli", "carrot", "banana", "apple", "orange", "vase"}


def leaves():
    df = pd.concat([pd.read_csv(os.path.join(PROC, f"{t}_manifest.csv")) for t in ("diseases", "deficiency")])
    df = df[df["source"] != "pepper"].drop_duplicates("path")
    df = df.sample(frac=1, random_state=SEED).groupby("source").head(PER_SOURCE)
    return df.assign(**{"class": "leaf"})


def others():
    ann = json.load(open(os.path.join(COCO, "annotations", "instances_val2017.json"), encoding="utf-8"))
    plant_ids = {c["id"] for c in ann["categories"] if c["name"] in PLANT_CATS}
    bad = {a["image_id"] for a in ann["annotations"] if a["category_id"] in plant_ids}
    files = sorted(im["file_name"] for im in ann["images"] if im["id"] not in bad)
    random.Random(SEED).shuffle(files)
    a, b = int(len(files) * SPLIT[0]), int(len(files) * (SPLIT[0] + SPLIT[1]))
    out = os.path.join(PROC, "routing")
    if os.path.isdir(out):
        shutil.rmtree(out)
    rows = []
    for i, name in enumerate(files):
        split = "train" if i < a else "val" if i < b else "test"
        d = os.path.join(out, split, "other")
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f"other_{i:05d}.jpg")
        with Image.open(os.path.join(COCO, "val2017", name)) as im:
            im.convert("RGB").resize(SIZE).save(dst, "JPEG", quality=92)
        rows.append({"path": dst, "split": split, "class": "other", "crop": "none", "source": "coco"})
    print(f"COCO: {len(ann['images'])} images, {len(bad)} with a plant/fruit/vegetable excluded, {len(files)} kept")
    return pd.DataFrame(rows)


def main():
    fruit = pd.read_csv(os.path.join(PROC, "fruits_manifest.csv")).assign(**{"class": "fruit"})
    df = pd.concat([leaves(), fruit, others()])[["path", "split", "class", "crop", "source"]]
    df.to_csv(os.path.join(PROC, "routing_manifest.csv"), index=False)
    print(df.groupby(["class", "split"]).size().unstack(fill_value=0).to_string())
    print(f"routing_manifest.csv: {len(df)} images")


if __name__ == "__main__":
    main()
