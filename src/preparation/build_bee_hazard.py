"""docs/bee_hazard.csv: active substances of the Tunisian list that are highly toxic to bees (phyto plan, step 6).

Source (downloaded once into data/raw/pan/): PAN International List of Highly Hazardous Pesticides, December 2024,
https://pan-international.org/wp-content/uploads/PAN_HHP_List.pdf - column "highly toxic bees": "Hazard to ecosystem
services - Highly toxic to bees (<2 µg/bee) according to U.S. EPA as listed by FOOTPRINT data" (legend, table 2).
Only the substances marked 1 in that column are written: a substance absent from the list is NOT shown as safe for bees
(the answer then says nothing about bees, as the data says nothing).
Matching to the Tunisian substances: CAS number first, then the name (keys of build_moa_groups.py).
Every row is written with status = proposed; the agents use validated rows only (bee warning, Vérificateur rule 16).

Usage: python src/preparation/build_bee_hazard.py
"""
import csv
import re
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "preparation"))
from build_moa_groups import key, variants  # noqa: E402

RAW = ROOT / "data" / "raw" / "pan"
PDF = RAW / "PAN_HHP_List.pdf"
URL = "https://pan-international.org/wp-content/uploads/PAN_HHP_List.pdf"
OUT = ROOT / "docs" / "bee_hazard.csv"
COLUMNS = ["substance", "tres_toxique_abeilles", "nom_pan", "cas", "correspondance", "source", "status", "note"]


def download():
    if PDF.exists():
        return
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; AgrIA-research/1.0)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        PDF.write_bytes(r.read())
    time.sleep(1)


def pan_rows():
    """(CAS, name, highly toxic to bees) for every active ingredient of the list (pages 26 and after)."""
    import pdfplumber
    out = []
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages[25:]:
            for table in page.extract_tables():
                header = next((r for r in table if r and len(r) > 2 and r[1] == "CAS number"), None)
                if not header:
                    continue
                heads = [re.sub(r"\s+", "", c or "") for c in header]
                col = heads.index("highlytoxicbees")
                for r in table:
                    if r and re.fullmatch(r"\d+", r[0] or ""):
                        out.append({"cas": (r[1] or "").strip(), "nom_pan": re.sub(r"\s+", " ", r[2] or "").strip(),
                                    "abeilles": (r[col] or "").strip() == "1"})
    return out


def main():
    download()
    pan = [r for r in pan_rows() if r["abeilles"]]
    by_cas = {r["cas"]: r for r in pan if r["cas"]}
    by_key = {}
    for r in pan:
        for name in re.split(r";\s*", r["nom_pan"]):
            by_key.setdefault(key(name), r)
    subs = pd.read_csv(ROOT / "data" / "processed" / "pesticides" / "substances.csv")
    subs = subs.dropna(subset=["eu_name"]).groupby("eu_name")["cas"].first().reset_index()
    rows = []
    for s in subs.itertuples():
        hit, how = None, ""
        for c in re.findall(r"\d{2,7}-\d{2}-\d", str(s.cas or "")):
            if c in by_cas:
                hit, how = by_cas[c], "CAS"
                break
        if not hit:
            for k, h in variants(s.eu_name):
                if k in by_key:
                    hit, how = by_key[k], f"nom ({h})"
                    break
        if hit:
            rows.append({"substance": s.eu_name, "tres_toxique_abeilles": "oui", "nom_pan": hit["nom_pan"],
                         "cas": hit["cas"], "correspondance": how,
                         "source": "PAN International List of HHPs, December 2024 (US EPA, < 2 µg/bee)",
                         "status": "proposed", "note": ""})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["substance"]))
    print(f"PAN list: {len(pan)} active ingredients highly toxic to bees")
    print(f"{OUT.relative_to(ROOT)}: {len(rows)} substances of the Tunisian list "
          f"(how: {pd.Series([r['correspondance'] for r in rows]).value_counts().to_dict()})")
    print([r["substance"] for r in rows])


if __name__ == "__main__":
    main()
