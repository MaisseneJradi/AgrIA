"""docs/substance_hazard.csv: active substance of the Tunisian list -> WHO acute hazard class (Ia, Ib, II, III, U) from
"The WHO Recommended Classification of Pesticides by Hazard and guidelines to classification, 2019 edition"
(phyto plan, step 6). Every row is written with status = proposed: only rows the agronomist validates are used
(ranking.py: lower class first; redaction.py: class and protective equipment line; safety.py rule 15).

Source (downloaded once into data/raw/who/): https://iris.who.int/handle/10665/332193 (PDF, CC BY-NC-SA 3.0 IGO).
Tables 1 to 5 of the PDF: Ia extremely hazardous, Ib highly hazardous, II moderately hazardous, III slightly hazardous,
U unlikely to present acute hazard in normal use. One row per line "Common name [ISO] CAS ...": the class is the one of
the table the line is in. Matching to the Tunisian substances: CAS number first (substances.csv of the list), then the
name (same keys as build_moa_groups.py). Tables 6 and 7 (obsolete, fumigants) are not read.

Usage: python src/preparation/build_substance_hazard.py
Output: docs/substance_hazard.csv (substance, classe_oms, nom_oms, cas, correspondance, source, status, note)
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

RAW = ROOT / "data" / "raw" / "who"
PDF = RAW / "who-hazard-classification-2019.pdf"
URL = "https://iris.who.int/bitstreams/36c193cd-2362-46d1-be00-fef570d80037/download"
OUT = ROOT / "docs" / "substance_hazard.csv"
COLUMNS = ["substance", "classe_oms", "nom_oms", "cas", "correspondance", "source", "status", "note"]
TABLES = {"1": "Ia", "2": "Ib", "3": "II", "4": "III", "5": "U"}
CAS = r"\d{2,7}-\d{2}-\d"
ROW = re.compile(rf"^(?P<name>[A-Za-z0-9][^\[]*?)\s*(?:\[(?:ISO|C)\]\s*)?(?P<cas>{CAS})\b")


def download():
    if PDF.exists():
        return
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; AgrIA-research/1.0)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        PDF.write_bytes(r.read())
    time.sleep(1)


def who_rows():
    import pdfplumber
    out, table = [], None
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            m = re.search(r"^Table (\d)\. .*?(?:hazard|Class)", text, re.M)
            if m:
                table = m.group(1)
            if table not in TABLES:
                continue
            if not m and table is not None and not re.search(r"Common name", text):
                continue  # pages of notes between the tables
            for line in text.splitlines():
                r = ROW.match(line.strip())
                if r:
                    out.append({"nom_oms": r.group("name").strip(), "cas": r.group("cas"), "classe_oms": TABLES[table]})
    return out


def main():
    download()
    who = who_rows()
    by_cas, by_key = {}, {}
    for r in who:
        by_cas.setdefault(r["cas"], r)
        by_key.setdefault(key(r["nom_oms"]), r)
        by_key.setdefault(key(r["nom_oms"]).rstrip("e"), r)
    subs = pd.read_csv(ROOT / "data" / "processed" / "pesticides" / "substances.csv")
    subs = subs.dropna(subset=["eu_name"]).groupby("eu_name")["cas"].first().reset_index()
    rows, missing = [], []
    for s in subs.itertuples():
        hit, how = None, ""
        for c in re.findall(CAS, str(s.cas or "")):
            if c in by_cas:
                hit, how = by_cas[c], "CAS"
                break
        if not hit:
            for k, h in variants(s.eu_name):
                if k in by_key:
                    hit, how = by_key[k], f"nom ({h})"
                    break
        if not hit:
            missing.append(s.eu_name)
            continue
        rows.append({"substance": s.eu_name, "classe_oms": hit["classe_oms"], "nom_oms": hit["nom_oms"],
                     "cas": hit["cas"], "correspondance": how,
                     "source": "WHO Recommended Classification of Pesticides by Hazard, 2019",
                     "status": "proposed", "note": ""})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["substance"]))
    print(f"WHO tables 1-5: {len(who)} rows {pd.Series([r['classe_oms'] for r in who]).value_counts().to_dict()}")
    print(f"{OUT.relative_to(ROOT)}: {len(rows)}/{len(subs)} substances "
          f"{pd.Series([r['classe_oms'] for r in rows]).value_counts().to_dict()} "
          f"(how: {pd.Series([r['correspondance'] for r in rows]).value_counts().to_dict()})")
    print(f"no WHO class ({len(missing)}): {missing[:60]}")


if __name__ == "__main__":
    main()
