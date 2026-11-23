"""Leaf boxes of the field photos, for cropping on the leaf (step 5 of the improvement plan).

Field photos (PlantDoc, PlantWild, ...) often show a whole plant, soil, hands or background; the model only sees a
small leaf. A small open-vocabulary detector, OWL-ViT base patch32 (google/owlvit-base-patch32, Apache 2.0, about
0.45 s per photo on CPU), finds the box of "a photo of a leaf". The best box and its score are stored for every
field photo (train, val_field, test_field, field_tn) of the tasks; lab photos are already one centred leaf and are
not cropped. Nothing is written over the images: src/vision/dataset.py crops at read time (--leaf-crop) with the
rule of crop_box() below, so the rule can change without recomputing the boxes.

Usage:
  python src/preparation/leaf_boxes.py --tasks diseases leaf      (resumable: photos already in the CSV are skipped)
Output: data/processed/leaf_boxes.csv (path, x0, y0, x1, y1 in pixels of the processed image, width, height, score)
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "vision"))
OUT = ROOT / "data" / "processed" / "leaf_boxes.csv"
MODEL = "google/owlvit-base-patch32"
QUERY = "a photo of a leaf"
COLS = ["path", "x0", "y0", "x1", "y1", "width", "height", "score"]
MIN_SCORE, MIN_AREA, MAX_AREA, MARGIN = 0.1, 0.15, 0.85, 0.1


def crop_box(box, width, height, score, min_score=MIN_SCORE, min_area=MIN_AREA, max_area=MAX_AREA, margin=MARGIN):
    """Box to crop (x0, y0, x1, y1) with a margin, or None to keep the whole photo (unsure detection, box too
    small to be the leaf, or box covering almost all the photo anyway)."""
    x0, y0, x1, y1 = (max(0.0, box[0]), max(0.0, box[1]), min(float(width), box[2]), min(float(height), box[3]))
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0) / float(width * height)
    if score < min_score or not min_area <= area <= max_area:
        return None
    mx, my = margin * (x1 - x0), margin * (y1 - y0)
    return (int(max(0, x0 - mx)), int(max(0, y0 - my)), int(min(width, x1 + mx + 0.5)), int(min(height, y1 + my + 0.5)))


class LeafDetector:
    def __init__(self, device="cpu"):
        import torch
        from transformers import OwlViTForObjectDetection, OwlViTProcessor
        self.torch, self.device = torch, torch.device(device)
        self.proc = OwlViTProcessor.from_pretrained(MODEL)
        self.model = OwlViTForObjectDetection.from_pretrained(MODEL).to(self.device).eval()

    def __call__(self, images):
        """Best leaf box (x0, y0, x1, y1) and score of each PIL image."""
        torch = self.torch
        inp = self.proc(text=[[QUERY]] * len(images), images=images, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model(**inp)
        sizes = torch.tensor([im.size[::-1] for im in images], device=self.device)
        res = self.proc.post_process_object_detection(out, threshold=0.0, target_sizes=sizes)
        best = []
        for r in res:
            i = int(r["scores"].argmax())
            best.append(([float(v) for v in r["boxes"][i]], float(r["scores"][i])))
        return best


def field_paths(tasks):
    from dataset import FIELD_SOURCES, load_split
    paths = []
    for task in tasks:
        for split in ("train", "val_field", "test_field", "field_tn"):
            d = load_split(task, split, balanced=False)
            if split in ("train",):
                d = d[d["source"].isin(FIELD_SOURCES)]
            paths += d["path"].tolist()
    return list(dict.fromkeys(paths))


def load_boxes(path=OUT):
    """{image path: (box, width, height, score)}"""
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["path"]: ([float(r[k]) for k in ("x0", "y0", "x1", "y1")], int(r["width"]), int(r["height"]),
                            float(r["score"])) for r in csv.DictReader(fh)}


def main():
    from PIL import Image
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", nargs="+", default=["diseases", "leaf"])
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default=os.environ.get("AGRIA_DEVICE", "cpu"))
    a = ap.parse_args()
    done = load_boxes()
    todo = [p for p in field_paths(a.tasks) if p not in done]
    print(f"{len(done)} boîtes déjà calculées, {len(todo)} photos terrain à traiter", flush=True)
    det = LeafDetector(a.device)
    new = not OUT.exists()
    t0 = time.time()
    with open(OUT, "a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COLS)
        for i in range(0, len(todo), a.batch):
            chunk = todo[i:i + a.batch]
            ims = []
            for p in chunk:
                with Image.open(p) as im:
                    ims.append(im.convert("RGB"))
            for p, im, (box, score) in zip(chunk, ims, det(ims)):
                w.writerow([p] + [round(v, 1) for v in box] + [im.size[0], im.size[1], round(score, 4)])
            fh.flush()
            if (i // a.batch) % 50 == 0:
                print(f"{i + len(chunk)}/{len(todo)} en {time.time() - t0:.0f} s", flush=True)
    print("terminé", flush=True)


if __name__ == "__main__":
    main()
