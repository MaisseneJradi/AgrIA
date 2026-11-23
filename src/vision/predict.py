"""Prediction interface used by the agent (contract of docs/ARCHITECTURE.md, section 4).

  from predict import predict
  predict("routing", "photo.jpg")
  -> {"task": "routing", "class": "leaf", "confidence": 0.98,
      "top3": [["leaf", 0.98], ["other", 0.015], ["fruit", 0.005]], "reliable": True}

AGRIA_TTA=1 averages test-time augmentation views (mirror + 3 crops, evaluate.tta_views): 5 passes per photo.
Each model reads the photo at the side it was trained at (model.pt "size", 224 by default).
`reliable` is True when the confidence reaches the threshold of the task: "threshold" in models/<task>/metrics.json
(calibrated in step 2), else DEFAULT_THRESHOLD. Models are loaded once and kept in memory.
Command line: python src/vision/predict.py routing path/to/photo.jpg
"""
import json
import os
import sys

import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from dataset import ROOT, make_transform  # noqa: E402
from evaluate import load_model, tta_views  # noqa: E402

DEFAULT_THRESHOLD = 0.6
# AGRIA_DEVICE=cpu forces the CPU (tests while a training uses the GPU, or a server without GPU)
_DEVICE = torch.device(os.environ.get("AGRIA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu"))
_CACHE = {}
_TRANSFORMS = {}


def _tensor(net, image_path):
    size = getattr(net, "input_size", 224)
    if size not in _TRANSFORMS:
        _TRANSFORMS[size] = make_transform(train=False, size=size)
    with Image.open(image_path) as im:
        im = im.convert("RGB")
    if getattr(net, "leaf_crop", False):  # model trained on leaf-cropped field photos (plan step 5)
        im = _leaf_crop(im)
    return _TRANSFORMS[size](im).unsqueeze(0).to(_DEVICE)


_DETECTOR = []


def _leaf_crop(im):
    """The photo cropped on its leaf box (OWL-ViT, src/preparation/leaf_boxes.py), or unchanged when unsure."""
    sys.path.insert(0, str(ROOT / "src" / "preparation"))
    from leaf_boxes import LeafDetector, crop_box
    if not _DETECTOR:
        _DETECTOR.append(LeafDetector(str(_DEVICE)))
    small = im.resize((224, 224))  # boxes were learnt on the 224 x 224 processed photos
    box, score = _DETECTOR[0]([small])[0]
    c = crop_box(box, 224, 224, score)
    if c is None:
        return im
    sx, sy = im.size[0] / 224, im.size[1] / 224
    return im.crop((int(c[0] * sx), int(c[1] * sy), int(c[2] * sx), int(c[3] * sy)))


def _probs(net, image_path):
    x = _tensor(net, image_path)
    views = tta_views(x) if os.environ.get("AGRIA_TTA") == "1" else [x]
    return torch.stack([torch.softmax(net(v).float(), 1)[0] for v in views]).mean(0).cpu()


def _get(task):
    if task not in _CACHE:
        folder = ROOT / "models" / task
        if not (folder / "model.pt").exists():
            raise FileNotFoundError(f"no trained model for {task!r}: run src/vision/train.py --task {task}")
        net, classes = load_model(str(folder), _DEVICE)
        threshold = DEFAULT_THRESHOLD
        metrics = folder / "metrics.json"
        if metrics.exists():
            with open(metrics, encoding="utf-8") as f:
                threshold = json.load(f).get("threshold", DEFAULT_THRESHOLD)
        _CACHE[task] = (net, classes, threshold)
    return _CACHE[task]


def class_names(task):
    return list(_get(task)[1])


@torch.no_grad()
def predict(task, image_path, allowed=None):
    """allowed: optional list of classes the answer must be among (e.g. the classes of the crop the farmer named).
    Probabilities are then renormalised over these classes, and "mass" tells how much of the model's belief they
    held before (a small mass = the photo does not look like that crop to the model)."""
    net, classes, threshold = _get(task)
    probs = _probs(net, image_path)
    mass = 1.0
    if allowed:
        keep = torch.tensor([c in set(allowed) for c in classes])
        mass = float(probs[keep].sum())
        probs = torch.where(keep, probs, torch.zeros_like(probs)) / max(mass, 1e-9)
    top = probs.topk(min(3, int((probs > 0).sum()) or 1, len(classes)))
    confidence = float(top.values[0])
    return {"task": task, "class": classes[int(top.indices[0])], "confidence": round(confidence, 4),
            "top3": [[classes[int(i)], round(float(p), 4)] for p, i in zip(top.values, top.indices)],
            "reliable": confidence >= threshold, "mass": round(mass, 4)}


@torch.no_grad()
def probabilities(task, image_path):
    """Full probability vector of a model as {class: probability} (task = folder under models/, e.g. "crop_v3a").
    Used by the model combinations of the agents (src/agent/ensemble.py)."""
    net, classes, _ = _get(task)
    probs = _probs(net, image_path).tolist()
    return dict(zip(classes, probs))


if __name__ == "__main__":
    print(json.dumps(predict(sys.argv[1], sys.argv[2]), indent=1))
