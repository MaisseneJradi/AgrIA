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
TASKS = ("routing", "diseases", "deficiency", "fruits", "leaf", "crop")
# crops of the project (task "crop"); any other plant of the data (rice, coffee, gourds...) -> "autre_plante"
PROJECT_CROPS = ("apple", "cherry", "citrus", "corn", "datepalm", "grape", "olive", "peach", "pepper", "potato",
                 "squash", "strawberry", "tomato", "wheat")
CROP_ALIASES = {"orange": "citrus"}
SIZE = 224
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
# real field photos (the other sources are lab or close-up photos); plantwild, gvlid, potato_field added 20/11/2026
FIELD_SOURCES = ("plantdoc", "plantwild", "gvlid", "potato_field")
FIELD_VAL_SHARE = 0.15


def local_path(p):
    """'data\\processed\\x\\y.jpg' -> absolute path on this machine (Windows or Linux)."""
    return str(ROOT.joinpath(*p.replace("\\", "/").split("/")))


def _leaf_manifest():
    """Task "leaf": the 51 disease classes and the 9 deficiencies in one model, so that the model itself tells a
    deficiency (yellowing, discoloration) from a disease (spots, mould, lesions). Built at read time, nothing is
    written: diseases manifest + deficiency manifest, where
      - a healthy leaf of the deficiency set joins the healthy class of its crop (tomato -> tomato__healthy);
        healthy leaves of crops without a disease class (6 coffee photos) are left out;
      - an image already in the diseases set (same md5 or dhash) is left out: no photo in train and test at once.
    No balanced set for this task: train = the raw train split (the retained choice of step 2)."""
    dis = pd.read_csv(PROC / "diseases_manifest.csv")
    dfc = pd.read_csv(PROC / "deficiency_manifest.csv")
    healthy_classes = {c for c in dis["class"].unique() if c.endswith("__healthy")}
    is_healthy = dfc["class"] == "healthy"
    dfc.loc[is_healthy, "class"] = dfc.loc[is_healthy, "crop"] + "__healthy"
    dfc = dfc[~is_healthy | dfc["class"].isin(healthy_classes)]
    h = pd.read_csv(PROC / "hash_cache.csv")
    seen_md5 = set(h.loc[h["path"].isin(dis["path"]), "md5"])
    seen_dh = set(h.loc[h["path"].isin(dis["path"]), "dhash"])
    dup = set(h.loc[h["md5"].isin(seen_md5) | h["dhash"].isin(seen_dh), "path"])
    dfc = dfc[~dfc["path"].isin(dup)]
    return pd.concat([dis, dfc], ignore_index=True)


def _crop_manifest():
    """Task "crop": which plant the leaf belongs to. The leaf manifest (diseases + deficiencies, deduplicated), with
    the crop as class: the 14 crops of the project, "orange" counted as citrus, every other plant "autre_plante";
    plus crop_manifest.csv: leaves used only by this model (added with add_source.py, task "crop": CitrusUAT diseases
    and pests, tomato diseases of the Mendeley and Tomato-Village sets), so that each crop is seen from several
    sources (one source per crop taught the model the style of the photos instead of the plant). An extra image
    already in the leaf manifest (same md5 or dhash) is left out."""
    m = _leaf_manifest()
    extra_path = PROC / "crop_manifest.csv"
    if extra_path.exists():
        extra = pd.read_csv(extra_path)
        h = pd.read_csv(PROC / "hash_cache.csv")
        known = h[h["path"].isin(m["path"])]
        dup = set(h.loc[h["md5"].isin(set(known["md5"])) | h["dhash"].isin(set(known["dhash"])), "path"])
        m = pd.concat([m, extra[~extra["path"].isin(dup)]], ignore_index=True)
    crop = m["crop"].replace(CROP_ALIASES)
    m["class"] = crop.where(crop.isin(PROJECT_CROPS), "autre_plante")
    return m


_MANIFESTS = {}


def manifest(task):
    """Whole manifest of a task (cached)."""
    if task not in _MANIFESTS:
        build = {"leaf": _leaf_manifest, "crop": _crop_manifest}.get(task)
        _MANIFESTS[task] = build() if build else pd.read_csv(PROC / f"{task}_manifest.csv")
    return _MANIFESTS[task].copy()


def field_val_paths(task):
    """Field validation set, built at read time (the manifest is never changed): FIELD_VAL_SHARE of the field photos
    of the train split, drawn per class with seed 42. Used to choose the model and its threshold on real photos
    while test_field stays untouched. Empty for tasks without field photos in train."""
    df = manifest(task)
    df = df[(df["split"] == "train") & df["source"].isin(FIELD_SOURCES)]
    picked = [g.sample(round(FIELD_VAL_SHARE * len(g)), random_state=42) for _, g in df.groupby("class")]
    return set(pd.concat(picked)["path"].map(local_path)) if picked else set()


def load_split(task, split, balanced=True, field_holdout=False):
    """Rows (path, class, crop, source) of one split. split: train, val, val_field, test or test_field.
    balanced=False gives the raw train split of the manifest (no balancing, no augmented copies: hypothesis H3).
    field_holdout=True removes the val_field photos from train (always do it when val_field is used)."""
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}, expected one of {TASKS}")
    if split == "val_field":
        df = manifest(task)
        df = df[df["split"] == "train"].copy()
        df["path"] = df["path"].map(local_path)
        held = field_val_paths(task)
        return df[df["path"].isin(held)].assign(split="val_field").reset_index(drop=True)
    if split == "train" and task not in ("routing", "leaf", "crop") and balanced:
        df = pd.read_csv(PROC / "balanced" / f"{task}_train.csv")
    else:
        df = manifest(task)
        df = df[df["split"] == split]
    df = df.reset_index(drop=True)
    df["path"] = df["path"].map(local_path)
    if split == "train" and field_holdout:
        df = df[~df["path"].isin(field_val_paths(task))].reset_index(drop=True)
    return df


def class_names(task):
    """Sorted class names of a task, read from the whole manifest (the order of the model outputs)."""
    return sorted(manifest(task)["class"].unique())


def class_weights(task, classes):
    """Loss weights in the order of `classes`: the balanced-set weights, or inverse frequency for routing."""
    path = PROC / "balanced" / f"{task}_class_weights.csv"
    if path.exists():
        w = pd.read_csv(path).set_index("class")["weight"]
    else:
        counts = load_split(task, "train")["class"].value_counts()
        w = (1 / counts) / (1 / counts).mean()
    return torch.tensor([float(w[c]) for c in classes], dtype=torch.float32)


def make_transform(train, aug="standard"):
    """aug="field": stronger changes of framing and sharpness that field photos show (closer or farther leaf,
    tilted phone, slight blur), still never a colour change.
    aug="crop" (crop model only): the field changes plus brightness, contrast and saturation, and a part of the photo
    erased, so that the model cannot recognise a source by its light or background. The hue is never changed, and
    this is not used for the diagnosis models: there a colour is a symptom."""
    steps = [transforms.Resize((SIZE, SIZE))]
    if train and aug == "crop":
        steps += [transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(0.2), transforms.RandomRotation(25),
                  transforms.RandomPerspective(0.25, p=0.3),
                  transforms.RandomResizedCrop(SIZE, scale=(0.35, 1.0), ratio=(0.75, 1.33)),
                  transforms.ColorJitter(brightness=0.35, contrast=0.35, saturation=0.3, hue=0),
                  transforms.RandomApply([transforms.GaussianBlur(5, sigma=(0.1, 1.5))], p=0.3),
                  transforms.ToTensor(), transforms.Normalize(MEAN, STD),
                  transforms.RandomErasing(p=0.3, scale=(0.02, 0.15))]
        return transforms.Compose(steps)
    if train and aug == "field":
        steps += [transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(0.2),
                  transforms.RandomRotation(25),
                  transforms.RandomPerspective(0.25, p=0.3),
                  transforms.RandomResizedCrop(SIZE, scale=(0.45, 1.0), ratio=(0.75, 1.33)),
                  transforms.RandomApply([transforms.GaussianBlur(5, sigma=(0.1, 1.5))], p=0.3)]
    elif train:
        steps += [transforms.RandomHorizontalFlip(), transforms.RandomResizedCrop(SIZE, scale=(0.85, 1.0), ratio=(0.95, 1.05))]
    steps += [transforms.ToTensor(), transforms.Normalize(MEAN, STD)]
    return transforms.Compose(steps)


class ManifestDataset(Dataset):
    """(image tensor, class index) pairs of one task and split."""

    def __init__(self, task, split, classes=None, limit=None, seed=42, balanced=True, field_holdout=False,
                 field_weight=1, aug="standard"):
        self.df = load_split(task, split, balanced, field_holdout)
        if limit and len(self.df) > limit:  # quick runs: a stratified-looking random sample
            self.df = self.df.sample(limit, random_state=seed).reset_index(drop=True)
        if split == "train" and field_weight > 1:  # field photos seen field_weight times per epoch
            field = self.df[self.df["source"].isin(FIELD_SOURCES)]
            self.df = pd.concat([self.df] + [field] * (field_weight - 1), ignore_index=True)
        self.classes = classes or class_names(task)
        self.index = {c: i for i, c in enumerate(self.classes)}
        self.transform = make_transform(train=(split == "train"), aug=aug)

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
