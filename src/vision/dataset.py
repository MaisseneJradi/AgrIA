"""Image datasets of the four vision tasks, read from the manifests built in src/preparation.

  routing     leaf / fruit / other         train, val, test, test_field: routing_manifest.csv
  diseases    51 leaf disease / pest classes
  deficiency  9 deficiencies + healthy
  fruits      18 fruit disease classes
For diseases, deficiency and fruits, train = the balanced set (data/processed/balanced/<task>_train.csv, augmented
copies included), val / test / test_field = the manifest (real distribution, never balanced).
Manifest paths are written with Windows separators ("data\\processed\\..."): they are rebuilt here for the machine
that runs the code, the files themselves are never changed.

Same preprocessing everywhere: images are already 224x224 RGB; training adds a flip and a light crop-zoom, never a
colour change (yellowing and spots are the symptoms); every image is normalised with the ImageNet mean and std.
"""
import json
import os
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
TASKS = ("routing", "diseases", "deficiency", "fruits")
SIZE = 224
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)


def local_path(p):
    """'data\\processed\\x\\y.jpg' -> absolute path on this machine (Windows or Linux)."""
    return str(ROOT.joinpath(*p.replace("\\", "/").split("/")))


def load_split(task, split):
    """Rows (path, class, crop, source) of one split. split: train, val, test or test_field."""
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}, expected one of {TASKS}")
    if split == "train" and task != "routing":
        df = pd.read_csv(PROC / "balanced" / f"{task}_train.csv")
    else:
        df = pd.read_csv(PROC / f"{task}_manifest.csv")
        df = df[df["split"] == split]
    df = df.reset_index(drop=True)
    df["path"] = df["path"].map(local_path)
    return df


def class_names(task):
    """Sorted class names of a task, read from the whole manifest (the order of the model outputs)."""
    return sorted(pd.read_csv(PROC / f"{task}_manifest.csv")["class"].unique())


def class_weights(task, classes):
    """Loss weights in the order of `classes`: the balanced-set weights, or inverse frequency for routing."""
    path = PROC / "balanced" / f"{task}_class_weights.csv"
    if path.exists():
        w = pd.read_csv(path).set_index("class")["weight"]
    else:
        counts = load_split(task, "train")["class"].value_counts()
        w = (1 / counts) / (1 / counts).mean()
    return torch.tensor([float(w[c]) for c in classes], dtype=torch.float32)


def make_transform(train):
    steps = [transforms.Resize((SIZE, SIZE))]
    if train:
        steps += [transforms.RandomHorizontalFlip(), transforms.RandomResizedCrop(SIZE, scale=(0.85, 1.0), ratio=(0.95, 1.05))]
    steps += [transforms.ToTensor(), transforms.Normalize(MEAN, STD)]
    return transforms.Compose(steps)


class ManifestDataset(Dataset):
    """(image tensor, class index) pairs of one task and split."""

    def __init__(self, task, split, classes=None, limit=None, seed=42):
        self.df = load_split(task, split)
        if limit and len(self.df) > limit:  # quick runs: a stratified-looking random sample
            self.df = self.df.sample(limit, random_state=seed).reset_index(drop=True)
        self.classes = classes or class_names(task)
        self.index = {c: i for i, c in enumerate(self.classes)}
        self.transform = make_transform(train=(split == "train"))

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        row = self.df.iloc[i]
        with Image.open(row["path"]) as im:
            x = self.transform(im.convert("RGB"))
        return x, self.index[row["class"]]


def save_labels(classes, folder):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "labels.json"), "w", encoding="utf-8") as f:
        json.dump(classes, f, indent=1)
