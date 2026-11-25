"""Image class -> target of the Tunisian list, from the versioned table docs/disease_target_mapping.csv.

One row = one name of a disease or pest (French, scientific, spelling of the list, synonym, group name) as a regular
expression on the target text of a registered use, for one image class and its crops:
  unified_class, crops ("tomato" or "squash|cucumber|melon|watermelon"), nom, type_nom, motif, exclure, relation
  (direct | vecteur | proche), groupe, source, status (proposed | validated | rejected), note.
Only status = validated rows link a use to a class (rule: proposed rows wait for the agronomist's review).
A use counts when its crop is one of the row crops, or a crop group that contains one (then relation "groupe"), and
its target matches `motif` but not `exclure`.

  usage_classes(usages, rows) -> DataFrame unified_class, relation, product_id, usage_idx, + the columns of the use
Used by build_db.py (table traitements) and by src/preparation/build_disease_target_mapping.py (coverage report).
"""
import csv
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MAPPING = ROOT / "docs" / "disease_target_mapping.csv"
COLUMNS = ["unified_class", "crops", "nom", "type_nom", "motif", "exclure", "relation", "groupe", "source",
           "n_usages", "n_produits", "exemples_cibles", "status", "note"]
STATUSES = ("proposed", "validated", "rejected")  # rejected: never used, like proposed (review_workbook.py)
# crop groups of the list: same as src/preparation/build_pesticide_refs.py ("Cereales" = small-grain cereals, no maize)
GROUPS = {"vegetables": ["tomato", "pepper", "potato", "squash", "cucumber", "melon", "eggplant"],
          "cucurbits": ["squash", "cucumber", "melon", "watermelon"],
          "fruit_trees": ["apple", "pear", "peach", "cherry", "apricot", "plum", "almond"],
          "cereals": ["wheat", "barley", "oat"]}
USE_COLUMNS = ["nom_commercial", "type", "substances_ue", "culture", "cible", "dose", "dar_jours", "statut",
               "restriction", "autorisation_provisoire", "bio_ue"]


def plain(s):
    """Lower case ASCII, 'œ' -> 'oe' (the form the patterns are written for)."""
    s = str(s).replace("œ", "oe").replace("Œ", "OE")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def load(path=MAPPING, statuses=("validated",)):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    bad = {r["status"] for r in rows} - set(STATUSES)
    if bad:
        raise ValueError(f"{path}: unknown status {sorted(bad)} (expected {STATUSES})")
    return [r for r in rows if r["status"] in statuses]


def covered_crops(crop_cell):
    """'fruit_trees|grape' -> {'apple', 'pear', ..., 'grape'}"""
    return {c for n in str(crop_cell or "").split("|") if n and n != "nan" for c in GROUPS.get(n, [n])}


def row_matches(row, crop_cell, target):
    """Relation of the use for this mapping row (direct, vecteur, proche, groupe) or None."""
    crops = set(row["crops"].split("|"))
    if not covered_crops(crop_cell) & crops:
        return None
    t = plain(target)
    if not re.search(row["motif"], t) or (row["exclure"] and re.search(row["exclure"], t)):
        return None
    named = set(str(crop_cell).split("|"))
    return "groupe" if row["relation"] == "direct" and not named & crops else row["relation"]


def usage_classes(usages, rows):
    """Every (class, use) link of the rows, one per class x product x use (strongest relation kept)."""
    order = {"direct": 0, "vecteur": 1, "groupe": 2, "proche": 3}
    out = []
    for u in usages.itertuples(index=False):
        if not isinstance(u.crop, str):
            continue
        for row in rows:
            rel = row_matches(row, u.crop, u.cible)
            if rel:
                out.append({"unified_class": row["unified_class"], "relation": rel, "product_id": u.product_id,
                            "usage_idx": u.usage_idx, **{c: getattr(u, c, None) for c in USE_COLUMNS}})
    if not out:
        return pd.DataFrame(columns=["unified_class", "relation", "product_id", "usage_idx", *USE_COLUMNS])
    df = pd.DataFrame(out)
    df["_o"] = df["relation"].map(order)
    return df.sort_values("_o").drop_duplicates(["unified_class", "product_id", "usage_idx"]).drop(columns="_o") \
             .sort_values(["unified_class", "product_id", "usage_idx"]).reset_index(drop=True)
