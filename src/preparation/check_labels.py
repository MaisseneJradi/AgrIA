"""Crop-level label audit with zero-shot CLIP (open_clip, CPU). Reports only: nothing is deleted.

Checks that every image shows a leaf/plant of the crop its class says, and flags non-photos
(stock photos with watermarks, illustrations, text, fruits instead of leaves, empty images).
The exact disease is NOT checked. CLIP is not a botanist: crops with similar leaves
(apple/cherry/peach, pepper/tomato...) give false alarms, so always look at the contact sheets.

Usage:
  python src/preparation/check_labels.py --limit 200                  # quick test
  python src/preparation/check_labels.py                              # default sources
  python src/preparation/check_labels.py --sources plantdoc --task diseases --threshold 0.7

Outputs: docs/label_check.csv, docs/label_check_summary.csv, docs/figures/label_check/<class>.png
Remove confirmed bad images with remove_images.py only.
"""
import argparse
import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import open_clip
import pandas as pd
import torch
from PIL import Image
from tqdm import tqdm

PROC = os.path.join("data", "processed")
DOCS = "docs"
FIG = os.path.join(DOCS, "figures", "label_check")

# Crop key -> name used in the prompts ("orange" and "citrus" are the same crop)
CROPS = {
    "apple": "apple", "blueberry": "blueberry", "cherry": "cherry", "corn": "corn", "grape": "grape",
    "citrus": "citrus", "peach": "peach", "pepper": "bell pepper", "potato": "potato",
    "raspberry": "raspberry", "soybean": "soybean", "squash": "squash", "strawberry": "strawberry",
    "tomato": "tomato", "olive": "olive", "datepalm": "date palm", "rice": "rice", "coffee": "coffee",
}
ALIAS = {"orange": "citrus"}
CROP_TEMPLATES = [
    "a photo of a {} leaf",
    "a close-up photo of a {} leaf",
    "a close-up photo of a {} plant in a field",
    "a photo of {} leaves",
]
# Junk categories competing with the crops in one softmax
JUNK = {
    "fruit": ["a photo of fruits without leaves", "a photo of a fruit on a white background"],
    "illustration": ["a stock illustration", "a vector illustration of a leaf", "a drawing or clip art",
                     "a cartoon of a plant"],
    "text": ["a screenshot of a web page", "a diagram with text labels", "a slide with text"],
    "collage": ["a collage of several photos"],
    "empty": ["a completely blurry photo", "an empty image of a single solid color"],
}
# Stock-photo test: these prompts vs generic "real leaf photo" prompts (in the crop softmax the crop wins)
REAL = ["a photo of a plant leaf", "a photo of leaves on a plant", "a close-up photo of a leaf",
        "a photo of a plant in a field"]
STOCK = ["a stock photo with a watermark", "a shutterstock photo with a watermark",
         "an image with a watermark or text"]
STOCK_MIN = 0.9   # stock-photo prob above which an image is flagged
# "empty" needs one non-light colour to cover much of the image (padding/fill). White/grey lab backgrounds
# don't count, and CLIP alone calls dark palm close-ups "blurry".
EMPTY_FLAT = 0.4  # with CLIP "empty" on top
PAD_FLAT = 0.7    # whatever CLIP says
PAD_LIGHT = 150   # dominant colour with all channels >= this is a light background, not padding


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sources", nargs="+", default=["plantdoc", "olive", "citrus", "datepalm"])
    p.add_argument("--task", choices=["diseases", "deficiency", "both"], default="both")
    p.add_argument("--limit", type=int, default=None, help="check only the first N images (quick test)")
    p.add_argument("--threshold", type=float, default=0.9,
                   help="flag when another crop is predicted with top-1 prob above this")
    p.add_argument("--low", type=float, default=0.002, help="flag when the expected-crop prob is below this")
    p.add_argument("--model", default="ViT-B-32:laion2b_s34b_b79k",
                   help="open_clip arch:pretrained (ViT-B-16:laion2b_s34b_b88k is better but ~4x slower)")
    p.add_argument("--batch-size", type=int, default=64)
    return p.parse_args()


def load_rows(args):
    tasks = ["diseases", "deficiency"] if args.task == "both" else [args.task]
    frames = []
    for t in tasks:
        df = pd.read_csv(os.path.join(PROC, f"{t}_manifest.csv"))
        df["task"] = t
        # Diseases: crop = class prefix. Deficiency mixes crops: use the crop column.
        crop = df["class"].str.split("__").str[0] if t == "diseases" else df["crop"]
        df["expected_crop"] = crop.replace(ALIAS)
        frames.append(df[df["source"].isin(args.sources)])
    df = pd.concat(frames, ignore_index=True)
    missing = ~df["path"].map(os.path.exists)
    for p in df.loc[missing, "path"]:
        print("WARNING: in manifest but missing on disk, skipped:", p)
    df = df[~missing]
    unknown = set(df["expected_crop"]) - set(CROPS)
    if unknown:
        raise SystemExit(f"Crops without prompts: {sorted(unknown)}")
    return df.head(args.limit).reset_index(drop=True) if args.limit else df


@torch.no_grad()
def text_embedding(model, tok, prompts):
    """Average of the normalised prompt embeddings, normalised again."""
    e = model.encode_text(tok(prompts))
    e = (e / e.norm(dim=-1, keepdim=True)).mean(0)
    return e / e.norm()


@torch.no_grad()
def image_embeddings(df, model, pre, bs):
    out = []
    for i in tqdm(range(0, len(df), bs), desc="CLIP", unit="batch"):
        x = torch.stack([pre(Image.open(p).convert("RGB")) for p in df["path"].iloc[i:i + bs]])
        e = model.encode_image(x)
        out.append(e / e.norm(dim=-1, keepdim=True))
    return torch.cat(out)


def flatness(path):
    """Share of pixels with the image's most common (coarsely quantised) colour, and whether it is dark/coloured."""
    a = np.asarray(Image.open(path).convert("RGB").resize((64, 64))) // 16
    colours, counts = np.unique(a.reshape(-1, 3), axis=0, return_counts=True)
    return counts.max() / counts.sum(), colours[counts.argmax()].min() * 16 + 8 < PAD_LIGHT


def add_scores(df, img, model, tok, scale, args):
    crops, junk = list(CROPS), list(JUNK)
    crop_emb = torch.stack([text_embedding(model, tok, [t.format(n) for t in CROP_TEMPLATES])
                            for n in CROPS.values()])
    junk_emb = torch.stack([text_embedding(model, tok, v) for v in JUNK.values()])

    # 1) crops + junk in one softmax; crop probs renormalised over crops only
    p = (scale * img @ torch.cat([crop_emb, junk_emb]).T).softmax(-1).numpy()
    pc, pj = p[:, :len(crops)], p[:, len(crops):]
    pc_norm = pc / pc.sum(1, keepdims=True)
    exp_idx = df["expected_crop"].map(crops.index).to_numpy()
    rows = np.arange(len(df))

    # 2) stock-photo test vs generic leaf photo
    real_emb, stock_emb = text_embedding(model, tok, REAL), text_embedding(model, tok, STOCK)
    stock_p = (scale * img @ torch.stack([real_emb, stock_emb]).T).softmax(-1)[:, 1].numpy()

    df["pred_crop"] = [crops[i] for i in pc_norm.argmax(1)]
    df["top1_prob"] = pc_norm.max(1).round(3)
    df["expected_prob"] = pc_norm[rows, exp_idx].round(3)
    df["junk_type"] = [junk[i] for i in pj.argmax(1)]
    df["junk_prob"] = pj.max(1).round(3)
    df["stock_prob"] = stock_p.round(3)
    flat = [flatness(x) for x in tqdm(df["path"], desc="pixels", unit="img")]
    df["flatness"] = [round(f, 3) for f, _ in flat]
    junk_top = pj.max(1) > pc.max(1)

    reasons = []
    for r, jt, (_, not_light) in zip(df.itertuples(), junk_top, flat):
        why = []
        if r.pred_crop != r.expected_crop and r.top1_prob > args.threshold:
            why.append(f"looks_like_{r.pred_crop}")
        if r.expected_prob < args.low:
            why.append("low_expected_prob")
        clip_empty = jt and r.junk_type == "empty" and r.flatness > EMPTY_FLAT
        if not_light and (r.flatness > PAD_FLAT or clip_empty):
            why.append("junk_empty")
        elif jt and r.junk_type != "empty":
            why.append(f"junk_{r.junk_type}")
        if r.stock_prob > STOCK_MIN:
            why.append("junk_stock_watermark")
        reasons.append(";".join(why))
    df["flag_reason"] = reasons
    df["flagged"] = df["flag_reason"] != ""
    return df


def contact_sheets(df, per_sheet=48, cols=8):
    shutil.rmtree(FIG, ignore_errors=True)
    os.makedirs(FIG)
    for cls, g in df[df["flagged"]].groupby("class"):
        for k, start in enumerate(range(0, len(g), per_sheet)):
            chunk = g.iloc[start:start + per_sheet]
            rows = int(np.ceil(len(chunk) / cols))
            fig, axes = plt.subplots(rows, cols, figsize=(cols * 2, rows * 2.3), squeeze=False)
            for ax in axes.ravel():
                ax.axis("off")
            for ax, (idx, r) in zip(axes.ravel(), chunk.iterrows()):
                ax.imshow(Image.open(r["path"]))
                if "stock" in r.flag_reason:
                    second = f"stock {r.stock_prob:.2f}"
                elif "junk_empty" in r.flag_reason:
                    second = f"empty flat={r.flatness:.2f}"
                elif "junk" in r.flag_reason:
                    second = f"{r.junk_type} {r.junk_prob:.2f}"
                else:
                    second = f"exp {r.expected_prob:.2f}"
                ax.set_title(f"#{idx} {r.pred_crop} {r.top1_prob:.2f}\n{second}", fontsize=7)
            fig.suptitle(f"{cls} - {len(g)} flagged (sheet {k + 1})", fontsize=11)
            fig.tight_layout()
            name = cls if k == 0 else f"{cls}_{k + 1}"
            fig.savefig(os.path.join(FIG, f"{name}.png"), dpi=90)
            plt.close(fig)


def main():
    args = parse_args()
    df = load_rows(args)
    print(f"Checking {len(df)} images from {args.sources} ({args.task})")
    torch.set_num_threads(os.cpu_count())
    arch, tag = args.model.split(":")
    model, _, pre = open_clip.create_model_and_transforms(arch, pretrained=tag)
    model.eval()
    tok = open_clip.get_tokenizer(arch)
    img = image_embeddings(df, model, pre, args.batch_size)
    with torch.no_grad():
        df = add_scores(df, img, model, tok, model.logit_scale.exp(), args)

    cols = ["path", "task", "split", "class", "source", "expected_crop", "pred_crop", "expected_prob",
            "top1_prob", "junk_type", "junk_prob", "stock_prob", "flatness", "flag_reason"]
    df[cols].to_csv(os.path.join(DOCS, "label_check.csv"), index_label="row")
    summ = df.groupby(["task", "class"]).agg(n_checked=("flagged", "size"), n_flagged=("flagged", "sum"))
    summ["pct_flagged"] = (100 * summ["n_flagged"] / summ["n_checked"]).round(1)
    summ = summ.sort_values("pct_flagged", ascending=False)
    summ.to_csv(os.path.join(DOCS, "label_check_summary.csv"))
    contact_sheets(df)

    n = df["flagged"].sum()
    print(f"\nFlagged {n}/{len(df)} images ({100 * n / max(len(df), 1):.1f}%)")
    kinds = df.loc[df["flagged"], "flag_reason"].str.split(";").explode()
    print(kinds.str.replace(r"^looks_like_.*", "other crop predicted", regex=True).value_counts().to_string())
    print("\nMost flagged classes:")
    print(summ[summ["n_flagged"] > 0].head(15).to_string())
    print(f"\nWrote {DOCS}/label_check.csv, {DOCS}/label_check_summary.csv, contact sheets in {FIG}/")


if __name__ == "__main__":
    main()
