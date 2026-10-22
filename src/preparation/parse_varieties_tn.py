"""Official Tunisian catalogue of plant varieties (DGSVCIA, 2025 edition, agridata.tn, Licence Nationale de
Données Publiques Ouvertes): cereals, vegetables, fruit trees and fodder crops.

Download: the four PDFs of the agridata.tn CKAN datasets below go to data/raw/knowledge/agridata/ (skipped when
already there). Parse: pdfplumber tables. Cereals, vegetables and fodder share one layout (species, year of
registration, variety, hybrid or not, growing season, breeder, distributor, list); the fruit-tree catalogue nests
species headings ("Vignes de cuves noires") above its variety rows (variety, type, cultural traits, breeder or
country of origin, year of registration, re-registration date).

Usage: python src/preparation/parse_varieties_tn.py
Output: data/processed/knowledge/varietes_tn.csv (one row per registered variety)
"""
import json
import os
import re
import urllib.request

import pandas as pd
import pdfplumber

RAW = os.path.join("data", "raw", "knowledge", "agridata")
OUT = os.path.join("data", "processed", "knowledge")
DATASETS = {"cereales": "liste-des-varietes-de-cereales-inscrites-au-catalogue-officiel-2020",
            "maraicheres": "liste-des-varietes-maraicheres-inscrites-au-catalogue-officiel-2020",
            "arboricoles": "liste-des-varietes-des-especes-arboricoles-inscrites-aux-catalogue-officiel-2020",
            "fourrageres": "liste-des-varietes-fourrageres-inscrites-au-catalogue-officielle-2020"}
FLAT = ["espece", "annee_inscription", "variete", "type", "saison", "obtenteur", "responsable", "liste"]


def download(group, dataset):
    url = f"https://catalog.agridata.tn/api/3/action/package_show?id={dataset}"
    meta = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                            timeout=60))["result"]
    res = next(r for r in meta["resources"] if (r.get("format") or "").upper() == "PDF")
    path = os.path.join(RAW, f"catalogue_{group}.pdf")
    if not os.path.exists(path):
        os.makedirs(RAW, exist_ok=True)
        data = urllib.request.urlopen(urllib.request.Request(res["url"], headers={"User-Agent": "Mozilla/5.0"}),
                                      timeout=120).read()
        open(path, "wb").write(data)
    return path, meta["title"]


def cell(x):
    return re.sub(r"\s+", " ", x or "").strip()


def flat_rows(path, group):
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    r = [cell(x) for x in r]
                    # data rows start with the species and a year ("2005 (réinscrit)", "2018")
                    if len(r) >= 6 and r[0] and re.match(r"(19|20)\d\d|avant", r[1], re.I):
                        rows.append({"groupe": group, **dict(zip(FLAT, r + [""] * (len(FLAT) - len(r))))})
    return rows


# fruit-tree headings that name a sub-group inside a species, not a species
SUBGROUP = re.compile(r"vari[ée]t|porte|greffe|c[ée]page|cuves?\b|tables?\b|chairs?|sanguin|blonde|dattes|nectarin|"
                      r"pruniers? (japonais|domestiques)|olivier de table|olivier [àa] huile|arbre fruitier", re.I)


def tree_rows(path):
    """Fruit-tree catalogue: in each table, a row whose first filled cell sits LEFT of the variety column is a
    heading. Headings are a species ("Poirier", "Amandier :") or a sub-group ("Variétés locales", "Porte greffe");
    a new species resets the sub-group."""
    rows, species, sub = [], "", ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                cells = [[(j, cell(x)) for j, x in enumerate(r) if cell(x)] for r in table]
                year_rows = [c for c in cells if any(re.search(r"(19|20)\d\d|avant", v, re.I) for _, v in c)]
                if not year_rows:
                    continue
                var_col = pd.Series([c[0][0] for c in year_rows]).mode()[0]
                for c in cells:
                    if not c or re.search(r"Identification|Nomination|Obtenteur", " ".join(v for _, v in c)):
                        continue
                    if c[0][0] < var_col:
                        name = c[0][1].rstrip(" :")
                        if SUBGROUP.search(name):
                            sub = name
                        else:
                            species, sub = name, ""
                        continue
                    vals = [v for _, v in c]
                    years = [v for v in vals if re.search(r"(19|20)\d\d|avant", v, re.I)]
                    rest = [v for v in vals if v not in years]
                    if not rest:
                        continue
                    rows.append({"groupe": "arboricoles", "espece": species, "sous_groupe": sub, "variete": rest[0],
                                 "details": " ; ".join(rest[1:]), "annee_inscription": years[0] if years else "",
                                 "reinscription": years[1] if len(years) > 1 else ""})
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for group, dataset in DATASETS.items():
        path, title = download(group, dataset)
        got = tree_rows(path) if group == "arboricoles" else flat_rows(path, group)
        print(f"{title}: {len(got)} varieties")
        rows += got
    df = pd.DataFrame(rows)
    df["reinscrite"] = df["annee_inscription"].str.contains("réinscrit", case=False, na=False)
    df["annee_inscription"] = df["annee_inscription"].str.extract(r"((?:19|20)\d\d|[Aa]vant \d{4})", expand=False)
    df["espece"] = df["espece"].str.replace(r"\s+", " ", regex=True).str.strip()
    df = df[df["variete"].fillna("") != ""].drop_duplicates()
    df["source"] = "DGSVCIA, catalogue officiel des variétés (agridata.tn)"
    df.to_csv(os.path.join(OUT, "varietes_tn.csv"), index=False, encoding="utf-8")
    print(f"\n{len(df)} varieties, {df['espece'].nunique()} species")
    print(df.groupby("groupe")["espece"].agg(lambda s: s.value_counts().head(8).to_dict()).to_string())


if __name__ == "__main__":
    main()
