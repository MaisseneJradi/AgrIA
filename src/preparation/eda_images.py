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

# ---------- 1. Diseases: images per class, lab vs field ----------
counts = dis.groupby(["class", "source"]).size().unstack(fill_value=0)
for col in ("plantvillage", "plantdoc"):
    if col not in counts:
        counts[col] = 0
counts = counts.assign(total=counts.sum(axis=1)).sort_values("total")
fig, ax = plt.subplots(figsize=(10, 12))
ax.barh(counts.index, counts["plantvillage"], color=LAB, label="Lab (PlantVillage)")
ax.barh(counts.index, counts["plantdoc"], left=counts["plantvillage"], color=FIELD, label="Field (PlantDoc)")
ax.set_xlabel("Number of images")
ax.set_title("Diseases: images per class (lab vs field)", loc="left", fontweight="bold")
ax.legend(loc="lower right", frameon=False)
plt.tight_layout()
plt.savefig(os.path.join(FIG, "01_disease_class_balance.png"), dpi=150)
plt.close()

# ---------- 2. Deficiency: images per class, by crop ----------
c2 = dfc.groupby(["class", "source"]).size().unstack(fill_value=0)
c2 = c2.loc[c2.sum(axis=1).sort_values().index]
fig, ax = plt.subplots(figsize=(9, 5))
left = pd.Series(0, index=c2.index)
palette = {"rice": LAB, "coleaf": FIELD, "plantvillage": OTHER}
for crop in c2.columns:
    ax.barh(c2.index, c2[crop], left=left, color=palette.get(crop, OTHER), label=crop)
    left += c2[crop]
for y, total in enumerate(left):
    ax.text(total + 5, y, str(int(total)), va="center", fontsize=10)
ax.set_xlabel("Number of images")
ax.set_title("Deficiencies: images per class, by source", loc="left", fontweight="bold")
ax.legend(frameon=False, ncol=2, loc="lower right", fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(FIG, "02_deficiency_class_balance.png"), dpi=150)
plt.close()

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
lab_only = int((counts["plantdoc"] == 0).sum())
print(f"\nDisease classes: {len(counts)} | lab-only classes: {lab_only} | imbalance ratio max/min: {imb:.1f}x")
print(f"Deficiency classes: {dfc['class'].nunique()} | smallest: {c2.sum(axis=1).idxmin()} ({int(c2.sum(axis=1).min())})")
print(f"Figures saved in {FIG}")
