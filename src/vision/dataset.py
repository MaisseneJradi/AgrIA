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
import sys
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


def load_split(task, split, balanced=True, field_holdout=False, exclude_sources=()):
    """Rows (path, class, crop, source) of one split. split: train, val, val_field, test, test_field or field_tn
    (the frozen Tunisian test set, data/field_tn/manifest.csv, written only by src/preparation/field_tn.py).
    balanced=False gives the raw train split of the manifest (no balancing, no augmented copies: hypothesis H3).
    field_holdout=True removes the val_field photos from train (always do it when val_field is used).
    exclude_sources: sources left out of the split (leave-one-source-out runs, src/evaluation/loso.py); the val_field
    draw is unchanged, only the rows of the excluded sources are dropped."""
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}, expected one of {TASKS}")
    if split == "field_tn":
        return field_tn(task)
    if exclude_sources:
        df = load_split(task, split, balanced, field_holdout)
        return df[~df["source"].isin(set(exclude_sources))].reset_index(drop=True)
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


FIELD_TN = ROOT / "data" / "field_tn"


def field_tn(task):
    """Frozen Tunisian field photos of a task (test only: never trained on). Empty when none were frozen yet."""
    f = FIELD_TN / "manifest.csv"
    cols = ["path", "class", "crop", "source", "split"]
    if not f.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(f)
    df = df[df["task"] == task].copy()
    df["path"] = [str(FIELD_TN / p) for p in df["file"]]
    return df.assign(source="field_tn", split="field_tn")[cols].reset_index(drop=True)


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


def make_transform(train, aug="standard", size=SIZE):
    """aug="field": stronger changes of framing and sharpness that field photos show (closer or farther leaf,
    tilted phone, slight blur), still never a colour change.
    aug="crop" (crop model only): the field changes plus brightness and contrast, and a part of the photo erased, so
    that the model cannot recognise a source by its light or background. Hue and saturation are never changed (rule 4
    of the improvement plan, 21/11/2026: crop_v4 was trained with saturation +-30 %, removed since).
    aug="field2" (improvement plan, step 3): field_transform() below."""
    if train and aug == "field2":
        return field_transform(size)
    SIZE = size  # noqa: N806  (input side in pixels: 224 by default, 300 or 384 in the plan's step 4)
    steps = [transforms.Resize((SIZE, SIZE))]
    if train and aug == "crop":
        steps += [transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(0.2), transforms.RandomRotation(25),
                  transforms.RandomPerspective(0.25, p=0.3),
                  transforms.RandomResizedCrop(SIZE, scale=(0.35, 1.0), ratio=(0.75, 1.33)),
                  transforms.ColorJitter(brightness=0.35, contrast=0.35, saturation=0, hue=0),
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


class RandomShadow(torch.nn.Module):
    """A shadow across the photo (a leaf, a hand, the farmer): one random ellipse darkened by the SAME factor on the
    three channels, so hue and saturation are kept, only the brightness drops. Input: uint8 image tensor (C, H, W)."""

    def __init__(self, p=0.3, darkest=0.5, lightest=0.85):
        super().__init__()
        self.p, self.darkest, self.lightest = p, darkest, lightest

    def forward(self, img):
        if torch.rand(1).item() >= self.p:
            return img
        _, h, w = img.shape
        cy, cx = torch.rand(2).tolist()
        ry, rx = (0.2 + 0.5 * torch.rand(2)).tolist()
        yy = torch.linspace(0, 1, h).view(h, 1)
        xx = torch.linspace(0, 1, w).view(1, w)
        inside = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1
        f = self.darkest + (self.lightest - self.darkest) * torch.rand(1).item()
        out = img.float() * torch.where(inside, torch.tensor(f), torch.tensor(1.0))
        return out.clamp(0, 255).to(img.dtype)


class RandomMotionBlur(torch.nn.Module):
    """A moving phone: the image averaged along a short line (length 5 to 11 px, one of 4 directions), the same on
    every channel. Input: uint8 image tensor (C, H, W)."""

    def __init__(self, p=0.15):
        super().__init__()
        self.p = p

    def forward(self, img):
        if torch.rand(1).item() >= self.p:
            return img
        k = int(torch.randint(2, 6, (1,)).item()) * 2 + 1
        kernel = torch.zeros(k, k)
        d = int(torch.randint(0, 4, (1,)).item())
        if d == 0:
            kernel[k // 2, :] = 1
        elif d == 1:
            kernel[:, k // 2] = 1
        elif d == 2:
            kernel = torch.eye(k)
        else:
            kernel = torch.eye(k).flip(1)
        kernel = (kernel / kernel.sum()).view(1, 1, k, k).repeat(img.shape[0], 1, 1, 1)
        out = torch.nn.functional.conv2d(img.float().unsqueeze(0), kernel, padding=k // 2, groups=img.shape[0])[0]
        return out.round().clamp(0, 255).to(img.dtype)


def field_transform(size=SIZE):
    """aug="field2" (improvement plan, step 3): what phone photos in a field do to a leaf, NEVER a hue or saturation
    change (the colour is the symptom): framing (crop scale 0.4-1.0, flips, rotation), a shadow, brightness and
    contrast +-20 %, Gaussian or motion blur, JPEG compression (quality 40-95), a part of the photo erased.
    CutMix / MixUp are applied on the batch by train.py (--mix)."""
    from torchvision.transforms import v2
    return v2.Compose([
        v2.ToImage(), v2.Resize((size, size), antialias=True),
        v2.RandomResizedCrop(size, scale=(0.4, 1.0), ratio=(0.75, 1.33), antialias=True),
        v2.RandomHorizontalFlip(), v2.RandomVerticalFlip(0.2), v2.RandomRotation(20),
        RandomShadow(p=0.3),
        v2.ColorJitter(brightness=0.2, contrast=0.2, saturation=0, hue=0),
        v2.RandomApply([v2.GaussianBlur(5, sigma=(0.1, 1.5))], p=0.25),
        RandomMotionBlur(p=0.15),
        v2.RandomApply([v2.JPEG(quality=(40, 95))], p=0.5),
        v2.ToDtype(torch.float32, scale=True), v2.Normalize(MEAN, STD),
        v2.RandomErasing(p=0.25, scale=(0.02, 0.15)),
    ])


class ManifestDataset(Dataset):
    """(image tensor, class index) pairs of one task and split."""

    def __init__(self, task, split, classes=None, limit=None, seed=42, balanced=True, field_holdout=False,
                 field_weight=1, aug="standard", exclude_sources=(), size=SIZE, leaf_crop=False):
        self.df = load_split(task, split, balanced, field_holdout, exclude_sources)
        self.boxes = leaf_boxes() if leaf_crop else {}  # step 5: field photos cropped on the leaf at read time
        if limit and len(self.df) > limit:  # quick runs: a stratified-looking random sample
            self.df = self.df.sample(limit, random_state=seed).reset_index(drop=True)
        if split == "train" and field_weight > 1:  # field photos seen field_weight times per epoch
            field = self.df[self.df["source"].isin(FIELD_SOURCES)]
            self.df = pd.concat([self.df] + [field] * (field_weight - 1), ignore_index=True)
        self.classes = classes or class_names(task)
        self.index = {c: i for i, c in enumerate(self.classes)}
        self.transform = make_transform(train=(split == "train"), aug=aug, size=size)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        row = self.df.iloc[i]
        with Image.open(row["path"]) as im:
            im = im.convert("RGB")
            b = getattr(self, "boxes", {}).get(row["path"])
            if b is not None:
                im = im.crop(b)
            x = self.transform(im)
        return x, self.index[row["class"]]


def leaf_boxes():
    """{path: crop box} of the field photos whose leaf box passes the rule of src/preparation/leaf_boxes.py."""
    sys.path.insert(0, str(ROOT / "src" / "preparation"))
    from leaf_boxes import crop_box, load_boxes
    out = {}
    for p, (box, w, h, score) in load_boxes().items():
        c = crop_box(box, w, h, score)
        if c is not None:
            out[p] = c
    return out


def save_labels(classes, folder):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "labels.json"), "w", encoding="utf-8") as f:
        json.dump(classes, f, indent=1)
