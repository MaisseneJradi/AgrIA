"""Prediction interface used by the agent (contract of docs/ARCHITECTURE.md, section 4).

  from predict import predict
  predict("routing", "photo.jpg")
  -> {"task": "routing", "class": "leaf", "confidence": 0.98,
      "top3": [["leaf", 0.98], ["other", 0.015], ["fruit", 0.005]], "reliable": True}

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
from evaluate import load_model  # noqa: E402

DEFAULT_THRESHOLD = 0.6
# AGRIA_DEVICE=cpu forces the CPU (tests while a training uses the GPU, or a server without GPU)
_DEVICE = torch.device(os.environ.get("AGRIA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu"))
_CACHE = {}
_TRANSFORM = make_transform(train=False)


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
    with Image.open(image_path) as im:
        x = _TRANSFORM(im.convert("RGB")).unsqueeze(0).to(_DEVICE)
    probs = torch.softmax(net(x).float(), 1)[0].cpu()
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


if __name__ == "__main__":
    print(json.dumps(predict(sys.argv[1], sys.argv[2]), indent=1))
