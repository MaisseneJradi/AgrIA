"""Grad-CAM of the deployed models on FIELD photos: does the model look at the lesion or at the background?
(improvement plan, step 1; no training, nothing in data/ or models/ is changed).

1. Overlays: for each weak class of a model (reports/error_analysis/<model>/summary.json; for a model without weak
   class, its --weakest classes), 5 WRONG and 5 RIGHT field test photos (drawn with seed 42) are saved in
   reports/gradcam/<model>/<class>/: photo | Grad-CAM of the predicted class | Grad-CAM of the true class (errors).
2. Lesion focus, measured: the PlantWild photos of the field test are the same pictures as PlantSeg, whose lesion
   masks are in data/raw/plantseg/masks. Each test photo is matched to its PlantSeg original (16x16 thumbnail, then
   64x64 colour check), the mask is brought to 224x224 like the photo, and for the predicted class:
     cam_in_lesion  share of the Grad-CAM mass that falls on the lesion pixels
     lesion_area    share of the photo that is lesion (what a map spread at random would get)
     focus_ratio    cam_in_lesion / lesion_area (1 = no better than chance, > 1 = the model looks at the lesions)
     pointing_hit   the hottest Grad-CAM pixel is on a lesion
   Written to reports/gradcam/<model>/lesion_focus.csv and lesion_focus_summary.json (by class, right vs wrong).

Grad-CAM (Selvaraju et al., 2017) is computed here with hooks on the last convolution block of EfficientNet-B0
(features[-1], 7x7x1280 at 224 px): weights = mean gradient of the class score per channel, map = ReLU of the
weighted sum, upsampled to 224 px. No extra library.

Usage:
  python src/evaluation/gradcam.py                          diseases and leaf (overlays + lesion focus), crop
  python src/evaluation/gradcam.py --models diseases --per-class 5 --weakest 3
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from matplotlib import colormaps
from PIL import Image, ImageDraw, ImageOps

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "vision"))
from dataset import SIZE, local_path, make_transform  # noqa: E402
from evaluate import load_model  # noqa: E402

OUT = os.path.join(ROOT, "reports", "gradcam")
PLANTSEG = os.path.join(ROOT, "data", "raw", "plantseg")
SEED = 42
THUMB_MAE, CHECK_MAE = 10.0, 12.0  # matching thresholds (0-255 scale)
EXIF_OPS = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180, 4: Image.Transpose.FLIP_TOP_BOTTOM,
            5: Image.Transpose.TRANSPOSE, 6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
            8: Image.Transpose.ROTATE_90}


class GradCAM:
    """Grad-CAM on one layer of a network (default: the last feature block of torchvision's EfficientNet)."""

    def __init__(self, net, layer=None):
        self.net = net.eval()
        self.layer = layer if layer is not None else net.features[-1]
        self._act = None
        self.layer.register_forward_hook(self._keep)

    def _keep(self, _module, _inp, out):
        self._act = out
        out.register_hook(lambda g: setattr(self, "_grad", g))

    def __call__(self, x, class_idx=None):
        """x: (1, 3, H, W). Returns (map HxW in [0, 1] as numpy, probabilities, class index used)."""
        x = x.requires_grad_(True)
        logits = self.net(x)
        probs = torch.softmax(logits.float(), 1)[0].detach().cpu().numpy()
        idx = int(probs.argmax()) if class_idx is None else int(class_idx)
        self.net.zero_grad(set_to_none=True)
        logits[0, idx].backward()
        w = self._grad.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((w * self._act).sum(1, keepdim=True))
        cam = torch.nn.functional.interpolate(cam, size=x.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
        cam = cam.detach().float().cpu().numpy()
        cam = cam / cam.max() if cam.max() > 0 else cam
        return cam, probs, idx


def overlay(img, cam, alpha=0.45):
    """img: PIL RGB of the map size; cam: HxW in [0, 1] -> PIL RGB, jet colours over the photo."""
    heat = (colormaps["jet"](cam)[..., :3] * 255).astype(np.uint8)
    return Image.fromarray((np.asarray(img, dtype=np.float32) * (1 - alpha) + heat * alpha).astype(np.uint8))


def img_path(p):
    """Paths in predictions files are absolute (evaluate.py), those of the manifests relative."""
    return p if os.path.isabs(p) else local_path(p)


def load_input(path, device):
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        x = make_transform(train=False)(rgb).unsqueeze(0).to(device)
        return x, rgb.resize((SIZE, SIZE))


def panel(path, cam_tool, classes, true, device):
    """Photo | Grad-CAM of the predicted class | Grad-CAM of the true class (when wrong), with a header line."""
    x, img = load_input(path, device)
    cam_p, probs, ip = cam_tool(x)
    tiles = [img, overlay(img, cam_p)]
    pred = classes[ip]
    if pred != true and true in classes:
        x, _ = load_input(path, device)
        tiles.append(overlay(img, cam_tool(x, classes.index(true))[0]))
    W = SIZE * len(tiles)
    canvas = Image.new("RGB", (W, SIZE + 44), (255, 255, 255))
    for i, t in enumerate(tiles):
        canvas.paste(t, (i * SIZE, 44))
    d = ImageDraw.Draw(canvas)
    d.text((6, 4), f"vrai : {true}", fill=(0, 0, 0))
    d.text((6, 22), f"prédit : {pred} ({probs[ip]:.0%})" + ("   | carte 2 : prédit, carte 3 : vrai" if len(tiles) == 3
                                                         else "   | carte 2 : prédit"), fill=(0, 0, 0))
    return canvas, pred, float(probs[ip])


def thumb(img, side=16):
    return np.asarray(img.convert("L").resize((side, side), Image.BILINEAR), dtype=np.float32).ravel()


def small_rgb(img):
    return np.asarray(img.convert("RGB").resize((64, 64), Image.BILINEAR), dtype=np.float32)


def plantseg_index(cache=os.path.join(OUT, "_plantseg_index.npz")):
    """16x16 thumbnails of every PlantSeg image as the AgrIA pipeline saw it (EXIF applied, 224x224)."""
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return list(z["paths"]), z["thumbs"]
    paths, thumbs = [], []
    img_dir = os.path.join(PLANTSEG, "images")
    for folder in sorted(os.listdir(img_dir)):
        for f in sorted(os.listdir(os.path.join(img_dir, folder))):
            p = os.path.join(img_dir, folder, f)
            try:
                with Image.open(p) as im:
                    thumbs.append(thumb(ImageOps.exif_transpose(im).convert("RGB").resize((SIZE, SIZE))))
                paths.append(p)
            except OSError:
                continue
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.savez_compressed(cache, paths=np.array(paths, dtype=object), thumbs=np.stack(thumbs))
    return paths, np.stack(thumbs)


def mask_for(seg_path):
    """Lesion mask of a PlantSeg image, turned like the image (EXIF) and resized to 224x224, as 0/1 floats."""
    rel = os.path.relpath(seg_path, os.path.join(PLANTSEG, "images"))
    mpath = os.path.join(PLANTSEG, "masks", os.path.splitext(rel)[0] + ".png")
    if not os.path.exists(mpath):
        return None
    with Image.open(seg_path) as im:
        orient = im.getexif().get(0x0112, 1)
    with Image.open(mpath) as m:
        m = m.convert("L")
        if orient in EXIF_OPS:
            m = m.transpose(EXIF_OPS[orient])
        return (np.asarray(m.resize((SIZE, SIZE), Image.NEAREST)) > 0).astype(np.float32)


def match(path, seg_paths, seg_thumbs):
    """PlantSeg original of a processed PlantWild photo, or None."""
    with Image.open(path) as im:
        t, s = thumb(im), small_rgb(im)
    d = np.abs(seg_thumbs - t).mean(1)
    for i in np.argsort(d)[:3]:
        if d[i] > THUMB_MAE:
            break
        with Image.open(seg_paths[i]) as im:
            cand = ImageOps.exif_transpose(im).convert("RGB").resize((SIZE, SIZE))
        if np.abs(small_rgb(cand) - s).mean() < CHECK_MAE:
            return seg_paths[i]
    return None


def focus(cam, mask):
    area = float(mask.mean())
    inside = float((cam * mask).sum() / cam.sum()) if cam.sum() > 0 else 0.0
    hot = np.unravel_index(int(cam.argmax()), cam.shape)
    return {"lesion_area": round(area, 4), "cam_in_lesion": round(inside, 4),
            "focus_ratio": round(inside / area, 3) if area > 0 else None, "pointing_hit": bool(mask[hot] > 0)}


def lesion_focus(model, cam_tool, classes, preds, device, out_dir):
    seg_paths, seg_thumbs = plantseg_index()
    rows = []
    for r in preds[preds["source"] == "plantwild"].to_dict("records"):
        p = img_path(r["path"])
        seg = match(p, seg_paths, seg_thumbs)
        mask = mask_for(seg) if seg else None
        if mask is None or mask.sum() == 0:
            rows.append({"path": r["path"], "class": r["true"], "matched": False})
            continue
        x, _ = load_input(p, device)
        cam, _, _ = cam_tool(x)
        rows.append({"path": r["path"], "class": r["true"], "pred": r["pred"], "right": r["true"] == r["pred"],
                     "matched": True, "plantseg": os.path.relpath(seg, ROOT)} | focus(cam, mask))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "lesion_focus.csv"), index=False)
    m = df[df["matched"]].copy()
    if m.empty:
        return {"model": model, "plantwild_photos": len(df), "matched": 0}
    m["right"] = m["right"].astype(bool)  # NaN on unmatched rows made the column "object"

    def stats(g):
        return {"n": int(len(g)), "cam_in_lesion": round(float(g["cam_in_lesion"].mean()), 4),
                "lesion_area": round(float(g["lesion_area"].mean()), 4),
                "focus_ratio_median": round(float(g["focus_ratio"].median()), 3),
                "pointing_hit": round(float(g["pointing_hit"].mean()), 4)}
    summary = {"model": model, "plantwild_photos": int(len(df)), "matched": int(len(m)), "all": stats(m),
               "right": stats(m[m["right"]]), "wrong": stats(m[~m["right"]]) if (~m["right"]).any() else None,
               "by_class": {c: stats(g) for c, g in m.groupby("class")}}
    with open(os.path.join(out_dir, "lesion_focus_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    return summary


def overlays(model, cam_tool, classes, preds, targets, per_class, device, out_dir):
    index = []
    for c in targets:
        g = preds[preds["true"] == c]
        for kind, sel in (("wrong", g[g["true"] != g["pred"]]), ("right", g[g["true"] == g["pred"]])):
            pick = sel.sample(min(per_class, len(sel)), random_state=SEED) if len(sel) else sel
            for i, r in enumerate(pick.to_dict("records")):
                img, pred, conf = panel(img_path(r["path"]), cam_tool, classes, c, device)
                d = os.path.join(out_dir, c)
                os.makedirs(d, exist_ok=True)
                name = f"{kind}_{i + 1}_{os.path.basename(r['path'])}"
                img.save(os.path.join(d, name), quality=90)
                index.append({"class": c, "kind": kind, "file": f"{c}/{name}", "pred": pred,
                              "confidence": round(conf, 4), "source": r["source"], "path": r["path"]})
    pd.DataFrame(index).to_csv(os.path.join(out_dir, "index.csv"), index=False)
    return len(index)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=["diseases", "leaf", "crop"])
    ap.add_argument("--split", default="test_field")
    ap.add_argument("--per-class", type=int, default=5)
    ap.add_argument("--weakest", type=int, default=3, help="classes shown for a model with no weak class")
    ap.add_argument("--no-lesion", action="store_true")
    a = ap.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(SEED)
    for m in a.models:
        folder = os.path.join(ROOT, "models", m)
        preds = pd.read_csv(os.path.join(folder, f"predictions_{a.split}.csv"))
        ea = os.path.join(ROOT, "reports", "error_analysis", m)
        weak = json.load(open(os.path.join(ea, "summary.json"), encoding="utf-8"))["weak_classes"]
        if not weak:
            weak = pd.read_csv(os.path.join(ea, "per_class.csv")).query("support >= 5")["class"].head(a.weakest).tolist()
        net, classes = load_model(folder, device)
        tool = GradCAM(net)
        out_dir = os.path.join(OUT, m)
        os.makedirs(out_dir, exist_ok=True)
        n = overlays(m, tool, classes, preds, weak, a.per_class, device, out_dir)
        print(f"{m}: {n} images Grad-CAM ({len(weak)} classes) -> {out_dir}", flush=True)
        if not a.no_lesion and m != "crop":  # the crop model must look at the leaf, not at the lesion
            s = lesion_focus(m, tool, classes, preds, device, out_dir)
            if s.get("matched"):
                print(f"   lésions : {s['matched']}/{s['plantwild_photos']} photos PlantWild retrouvées dans PlantSeg | "
                      f"part de la carte sur la lésion {s['all']['cam_in_lesion']:.0%} pour {s['all']['lesion_area']:.0%} "
                      f"de surface (ratio médian {s['all']['focus_ratio_median']}) | point chaud sur la lésion "
                      f"{s['all']['pointing_hit']:.0%} ; justes {s['right']['cam_in_lesion']:.0%}, fausses "
                      f"{(s['wrong'] or {}).get('cam_in_lesion', 0):.0%}", flush=True)
            else:
                print("   lésions : aucune photo PlantWild retrouvée dans PlantSeg", flush=True)


if __name__ == "__main__":
    main()
