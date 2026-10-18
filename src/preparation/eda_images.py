"""EDA for the processed image datasets. Saves figures to docs/figures/ and a summary table to docs/.

Run after prepare_images.py:  python src/preparation/eda_images.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

PROC = os.path.join("data", "processed")
FIG = os.path.join("docs", "figures")
os.makedirs(FIG, exist_ok=True)

LAB, FIELD, OTHER = "#2F6B3A", "#E9A23B", "#8A9A90"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})

dis = pd.read_csv(os.path.join(PROC, "diseases_manifest.csv"))
dfc = pd.read_csv(os.path.join(PROC, "deficiency_manifest.csv"))

# Colours per source (distinct in lightness, not only hue)
SRC = {
    "plantvillage": ("#2F6B3A", "Lab - PlantVillage"),
    "plantdoc":     ("#E9A23B", "Field - PlantDoc"),
    "olive":        ("#7A4E9C", "Olive (Roboflow)"),
    "citrus":       ("#F2D16B", "Citrus (Mendeley)"),
    "datepalm":     ("#3D7DB8", "Date palm (Mendeley)"),
    "wheat":        ("#B8862F", "Wheat (Mendeley)"),
    "rice":         ("#1B3A24", "Rice NPK (Kaggle)"),
    "coleaf":       ("#C2622D", "Coffee - CoLeaf"),
}


def stacked_by_source(df, title, out, height):
    counts = df.groupby(["class", "source"]).size().unstack(fill_value=0)
    counts = counts.loc[counts.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(10, height))
    left = pd.Series(0, index=counts.index)
    for src in [s for s in SRC if s in counts.columns] + [s for s in counts.columns if s not in SRC]:
        color, label = SRC.get(src, (OTHER, src))
        ax.barh(counts.index, counts[src], left=left, color=color, label=label)
        left += counts[src]
    for y, total in enumerate(left):
        ax.text(total + left.max() * 0.005, y, str(int(total)), va="center", fontsize=8)
    ax.set_xlabel("Number of images")
    ax.set_title(title, loc="left", fontweight="bold")
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG, out), dpi=150)
    plt.close()
    return counts


# ---------- 1. Diseases: images per class, by source ----------
counts = stacked_by_source(dis, "Diseases and pests: images per class, by source", "01_disease_class_balance.png", 15)
counts["total"] = counts.sum(axis=1)
if "plantdoc" not in counts:
    counts["plantdoc"] = 0

# ---------- 2. Deficiency: images per class, by source ----------
c2 = stacked_by_source(dfc, "Deficiencies: images per class, by source", "02_deficiency_class_balance.png", 5.5)

# ---------- 3. Sample grid: lab vs field for the same disease ----------
both = dis.groupby("class")["source"].nunique()
classes = [c for c in both[both == 2].index if c.startswith("tomato")][:4] or list(both[both == 2].index[:4])
fig, axes = plt.subplots(2, len(classes), figsize=(3.2 * len(classes), 7))
for j, cls in enumerate(classes):
    for i, (src, label) in enumerate([("plantvillage", "Lab"), ("plantdoc", "Field")]):
        ax = axes[i][j] if len(classes) > 1 else axes[i]
        row = dis[(dis["class"] == cls) & (dis["source"] == src)].sample(1, random_state=0).iloc[0]
        ax.imshow(Image.open(row["path"]))
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{label} - {cls.replace('__', ': ').replace('_', ' ')}", fontsize=9)
fig.suptitle("Same disease, two worlds: lab photos vs field photos", fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(FIG, "03_lab_vs_field_samples.png"), dpi=150)
plt.close()

# ---------- 4. Split summary table ----------
summary = pd.concat([
    dis.groupby("split").size().rename("diseases"),
    dfc.groupby("split").size().rename("deficiency"),
], axis=1).fillna(0).astype(int)
summary.loc["total"] = summary.sum()
summary.to_csv(os.path.join("docs", "split_summary.csv"))
print(summary)

# ---------- Key numbers for the report ----------
imb = counts["total"].max() / counts["total"].min()
field_share = (dis["source"] == "plantdoc").mean() * 100
print(f"\nDisease classes: {len(counts)} | crops: {dis['crop'].nunique()} | imbalance max/min: {imb:.0f}x "
      f"({counts['total'].idxmax()} {int(counts['total'].max())} vs {counts['total'].idxmin()} {int(counts['total'].min())})")
print(f"PlantDoc field photos: {field_share:.1f}% of disease images")
tot = c2.sum(axis=1)
print(f"Deficiency classes: {len(c2)} | imbalance max/min: {tot.max() / tot.min():.0f}x")
print("Share of the main source in each deficiency class (crop confounding check):")
share = (c2.max(axis=1) / tot * 100).round(0)
for cls in tot.sort_values(ascending=False).index:
    print(f"  {cls:<15} {int(tot[cls]):>5} images | {c2.loc[cls].idxmax():<12} {int(share[cls])}%")
print(f"Figures saved in {FIG}")
