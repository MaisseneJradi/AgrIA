"""Uses of the official list without a DAR (days before harvest), by product, and the DAR completions that the official
list itself gives elsewhere in its text (phyto plan, step 7).

1. reports/phyto/phi_manquants.csv: one row per product with uses without a DAR: number of such uses, crops, whether the
   agents can advise it (it reaches an image class in table traitements), the DAR text of the list when there is one.
   It is the work list for the review: a DAR is taken from the product label, never estimated.
2. docs/phi_completions.csv (product_id, produit, culture, phi_days, phi_texte, source, status, note): the DAR that the
   list writes outside the use column, read by rules, status = proposed:
     - DAR of the product ("DAR:07 jours" before its first use) for its uses without one, when the product gives one
       single DAR (several values, e.g. field / greenhouse, are left for the review);
     - DAR text of the use that the parser did not read as a number: "non requis" / "non applicable" / "N/A"
       (phi_days 0, phi_texte "non requis"), "4 heures" (phi_days 1, rounded up: a harvest can never come earlier),
       "3 jours30 cc/hl" (number glued to the dose).
   Rows already in the file are kept as they are (a validated row is never changed); new proposals are added.
   culture: crop code of the use (docs/culture_mapping.csv), or * for every crop of the product.
get_treatments() uses the validated rows only.

Usage: python src/preparation/phi_report.py
"""
import csv
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "tools"))
from common import query  # noqa: E402

PEST = ROOT / "data" / "processed" / "pesticides"
REPORT = ROOT / "reports" / "phyto" / "phi_manquants.csv"
COMPLETIONS = ROOT / "docs" / "phi_completions.csv"
COLUMNS = ["product_id", "produit", "culture", "phi_days", "phi_texte", "source", "status", "note"]
SOURCE = "liste DGSVCIA du 22/05/2024"
NOT_REQUIRED = re.compile(r"non\s+requis|non\s+applicable|\bn\s*/\s*a\b", re.I)


def read_dar(text):
    """'DAR:07 jours' -> (7, '7 jours'); 'DAR: non requis' -> (0, 'non requis'); 'DAR:4 heures' -> (1, '4 heures');
    several different values -> None (left for the review)."""
    t = str(text or "")
    if NOT_REQUIRED.search(t) and not re.search(r"DAR\s*:?\s*\d", t, re.I):
        return 0, "non requis"
    hours = re.findall(r"DAR\s*:?\s*(\d+)\s*h(?:eures?)?\b", t, re.I)
    days = re.findall(r"DAR\s*:?\s*(\d+)\s*(?:j\b|j\.|jours?)", t, re.I)
    values = {int(d) for d in days} | {math.ceil(int(h) / 24) for h in hours}
    if len(values) != 1:
        return None
    v = values.pop()
    return v, (f"{hours[0]} heures" if hours and not days else f"{v} jour" + ("s" if v > 1 else ""))


def main():
    use = pd.read_csv(PEST / "tn_usages.csv")
    prod = pd.read_csv(PEST / "tn_products.csv")[["product_id", "dar_produit"]]
    use = use.merge(prod, on="product_id", how="left")
    reach = {(r["product_id"], r["usage_idx"]) for r in query("SELECT product_id, usage_idx FROM traitements")}
    use["conseille"] = [(p, u) in reach for p, u in zip(use["product_id"], use["usage_idx"])]
    miss = use[use["dar_jours"].isna()]

    # 1. report by product
    rows = []
    for pid, g in miss.groupby("product_id"):
        rows.append({"product_id": pid, "produit": g["nom_commercial"].iloc[0], "type": g["type"].iloc[0],
                     "usages_sans_dar": len(g), "usages_total": int((use["product_id"] == pid).sum()),
                     "conseillable": bool(g["conseille"].any()),
                     "cultures": " | ".join(sorted({str(c) for c in g["crop"].dropna()})),
                     "texte_dar_liste": " | ".join(sorted({str(x)[:120] for x in pd.concat([g["dar_texte"],
                                                           g["dar_produit"]]).dropna()}))})
    rep = pd.DataFrame(rows).sort_values(["conseillable", "usages_sans_dar"], ascending=[False, False])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    rep.to_csv(REPORT, index=False, encoding="utf-8")

    # 2. completions proposed from the text of the list
    existing = []
    if COMPLETIONS.exists():
        with open(COMPLETIONS, encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    keys = {(r["product_id"], r["culture"]) for r in existing}
    new = []
    for r in miss.itertuples():
        crop = r.crop if isinstance(r.crop, str) else "*"
        for text, where in ((r.dar_texte, "texte de l'usage"), (r.dar_produit, "DAR écrit pour le produit")):
            got = read_dar(text)
            if got is None or (r.product_id, crop) in keys:
                continue
            keys.add((r.product_id, crop))
            new.append({"product_id": r.product_id, "produit": r.nom_commercial, "culture": crop, "phi_days": got[0],
                        "phi_texte": got[1], "source": f"{SOURCE} ({where})", "status": "proposed",
                        "note": str(text)[:160]})
            break
    with open(COMPLETIONS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(existing + new)

    n = len(use)
    print(f"uses: {n}; without DAR: {len(miss)} ({len(miss) / n:.0%}); products concerned: {len(rep)}; "
          f"among them advised by the agents: {int(rep['conseillable'].sum())} "
          f"({int(miss['conseille'].sum())} uses)")
    print(f"{REPORT.relative_to(ROOT)} written; {COMPLETIONS.relative_to(ROOT)}: {len(existing)} rows kept, "
          f"{len(new)} proposed from the text of the list")


if __name__ == "__main__":
    main()
