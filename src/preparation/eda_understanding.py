"""Figures of the data-understanding report that are not image class counts (those come from eda_images.py).

  05_climate_regions.png          monthly rain and reference evapotranspiration (ET0), north / centre / south
  06_governorate_correlations.png Pearson correlations between climate and soil variables of the 24 governorates
  07_pesticides_overview.png      registered products by type, and registered uses per crop (top 10)
  08_class_dependency.png         Cramer's V between the label and the crop or the source of each image task

Usage: python src/preparation/eda_understanding.py   (after fetch_context_tn.py and clean_structured.py)
Output: docs/figures/05_*.png ... 08_*.png
"""
import os

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIG = os.path.join("docs", "figures")
CTX = os.path.join("data", "processed", "context")
CLEAN = os.path.join("data", "processed", "clean")
PROC = os.path.join("data", "processed")
GREEN, DARK, ORANGE, BLUE, SAND = "#2F6B3A", "#12261B", "#E9A23B", "#3D7EB8", "#C9B37E"
plt.rcParams.update({"font.size": 13, "axes.spines.top": False, "axes.spines.right": False})
MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
TYPE_EN = {"Fongicide": "Fungicide", "Insecticide": "Insecticide", "Herbicide": "Herbicide", "Divers": "Other",
           "Nematicide": "Nematicide", "Raticide": "Rodenticide"}
CROP_EN = {"tomato": "Tomato", "grape": "Grapevine", "wheat": "Wheat", "citrus": "Citrus", "potato": "Potato",
           "apple": "Apple", "fruit_trees": "Fruit trees (group)", "strawberry": "Strawberry", "pear": "Pear",
           "pepper": "Pepper", "olive": "Olive", "datepalm": "Date palm", "barley": "Barley", "melon": "Melon",
           "peach": "Peach", "vegetables": "Vegetables (group)", "cereals": "Cereals (group)",
           "all_crops": "All crops", "non_crop": "Non-crop areas"}


def climate_regions():
    norm = pd.read_csv(os.path.join(CTX, "climat_mensuel.csv"))
    regions = [("Bizerte", "North"), ("Kairouan", "Centre"), ("Tozeur", "South")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, (gov, label) in zip(axes, regions):
        g = norm[norm["gouvernorat"] == gov].sort_values("mois")
        ax.bar(range(12), g["pluie_mm"], color=BLUE, label="Rain (mm)")
        ax.plot(range(12), g["et0_mm"], color=ORANGE, lw=3, marker="o", label="ET0 (mm)")
        ax.set_xticks(range(12), MONTHS)
        ax.set_title(f"{label} · {gov}\nrain {g['pluie_mm'].sum():.0f} mm, ET0 {g['et0_mm'].sum():.0f} mm per year",
                     fontsize=13, loc="left")
    axes[0].set_ylabel("mm per month (mean 2015–2024)")
    axes[0].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "05_climate_regions.png"), dpi=110)
    plt.close(fig)


def governorate_correlations():
    norm = pd.read_csv(os.path.join(CTX, "climat_mensuel.csv"))
    year = norm.groupby("gouvernorat").agg(rain=("pluie_mm", "sum"), et0=("et0_mm", "sum"), tmax=("tmax_c", "mean"),
                                           heat_days=("jours_chaleur_35", "sum"))
    year["aridity"] = year["rain"] / year["et0"]
    soil = pd.read_csv(os.path.join(CTX, "sols.csv")).set_index("gouvernorat")
    df = year.join(soil[["phh2o_pH", "sand_%", "clay_%", "soc_g/kg"]]).rename(columns={
        "rain": "Rain", "et0": "ET0", "tmax": "Tmax", "heat_days": "Days ≥35 °C", "aridity": "Rain/ET0",
        "phh2o_pH": "Soil pH", "sand_%": "Sand %", "clay_%": "Clay %", "soc_g/kg": "Organic C"})
    corr = df.corr()
    fig, ax = plt.subplots(figsize=(8.6, 7.4))
    im = ax.imshow(corr, cmap="BrBG", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)), corr.columns)
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=11, color="white" if abs(v) > 0.6 else DARK)
    ax.spines[:].set_visible(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Pearson r (24 governorates)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "06_governorate_correlations.png"), dpi=110)
    plt.close(fig)
    return corr


def pesticides_overview():
    prod = pd.read_csv(os.path.join(CLEAN, "pesticides_produits.csv"))
    use = pd.read_csv(os.path.join(CLEAN, "pesticides_usages.csv"))
    types = prod["type"].map(TYPE_EN).fillna(prod["type"]).value_counts()
    crops = use["crop"].str.split("|").str[0].map(CROP_EN).fillna(use["crop"]).value_counts().head(10)[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [1, 1.3]})
    axes[0].barh(types.index[::-1], types.values[::-1], color=GREEN)
    axes[0].set_title(f"{len(prod)} registered products, by type", loc="left")
    for i, v in enumerate(types.values[::-1]):
        axes[0].text(v + 4, i, str(v), va="center")
    axes[1].barh(crops.index, crops.values, color=ORANGE)
    axes[1].set_title(f"{len(use)} registered uses: top 10 crops", loc="left")
    for i, v in enumerate(crops.values):
        axes[1].text(v + 3, i, str(v), va="center")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "07_pesticides_overview.png"), dpi=110)
    plt.close(fig)


def cramers_v(a, b):
    t = pd.crosstab(a, b).values
    chi2 = chi2_contingency(t)[0]
    return float(np.sqrt(chi2 / (t.sum() * (min(t.shape) - 1))))


def class_dependency():
    rows = []
    for task in ("diseases", "deficiency", "fruits"):
        df = pd.read_csv(os.path.join(PROC, f"{task}_manifest.csv"))
        rows.append((task, "source", cramers_v(df["class"], df["source"])))
        if task == "deficiency":
            rows.append((task, "crop", cramers_v(df["class"], df["crop"])))
    out = pd.DataFrame(rows, columns=["task", "variable", "cramers_v"])
    out.to_csv(os.path.join("docs", "class_dependency.csv"), index=False)
    return out


def main():
    os.makedirs(FIG, exist_ok=True)
    climate_regions()
    corr = governorate_correlations()
    pesticides_overview()
    dep = class_dependency()
    print(corr.round(2).to_string())
    print(dep.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
