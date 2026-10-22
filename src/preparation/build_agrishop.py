"""Fertilizers and pesticides sold on agrishop.tn, from the PostgreSQL export of the products table.

The export (data/raw/scrapper/mon_fichier.csv) has no header and its HTML descriptions contain raw line breaks, so
records are rebuilt: a record starts on a line "id,name,slug," and its last physical line ends with the 13 fixed
columns (price, photo, stock, active, created, updated, promo flag, promo price, promo start, promo end,
category_id, -, featured). The export holds no category names: they were read from the products of each id.
No public Tunisian register of fertilizers or seeds with their characteristics was found, and the shop sells no
seeds, so this file is the fertilizer source; machinery (34) and irrigation (18) are left out.

Per product: category / sub-category, plain-text description, price, NPK grade and nutrients found in the name or the
description, chelating agent; pesticides are linked to the Tunisian registration list (tn_products.csv) by trade name.
deficiency classes of the image model -> fertilizers that bring the missing nutrient (class_fertilizers.csv).

Usage: python src/preparation/build_agrishop.py
Output: data/processed/fertilizers/agrishop_products.csv, data/processed/fertilizers/class_fertilizers.csv
"""
import difflib
import html
import os
import re
import unicodedata

import pandas as pd

SRC = os.path.join("data", "raw", "scrapper", "mon_fichier.csv")
OUT = os.path.join("data", "processed", "fertilizers")
TN = os.path.join("data", "processed", "pesticides", "tn_products.csv")
TAIL = ["prix", "photo", "stock", "actif", "cree_le", "maj_le", "promo", "prix_promo", "promo_debut", "promo_fin",
        "category_id", "inconnu", "vedette"]
CATEGORIES = {  # category_id -> (categorie, sous_categorie), read from the products
    4: ("pesticides", "insecticides"), 5: ("pesticides", "acaricides"), 6: ("pesticides", "fongicides"),
    7: ("pesticides", "herbicides"), 8: ("pesticides", "regulateurs_divers"),
    10: ("engrais", "engrais_npk_fertirrigation"), 11: ("engrais", "engrais_foliaires"),
    12: ("engrais", "amendements_organiques_humiques"), 13: ("engrais", "oligo_elements_chelates"),
    14: ("engrais", "regulateurs_de_croissance"), 15: ("engrais", "biostimulants"),
}
# nutrient -> regex on the plain lower-case text (name + description), and the deficiency class it corrects
NUTRIENTS = {
    "N": (r"\bazot|\bnitrat|\bure[ae]?\b|\bammoni|\bn\s*\d+\s*%|\bn27\b|\bcan[- ]?\d", "N_deficiency"),
    "P": (r"phosph|p2o5", "P_deficiency"),
    "K": (r"potass|k2o|\bkelik k|\bpotas", "K_deficiency"),
    "Mg": (r"magn[eé]si|\bmgo\b|\bmg\b", "Mg_deficiency"),
    "Ca": (r"calci|\bcao\b|\bcal\b|\bca\b", "Ca_deficiency"),
    "Fe": (r"\bfer\b|\bfe\b|ferr|eddha|eddhsa|sequestrene", "Fe_deficiency"),
    "Zn": (r"\bzinc|\bzn\b", "Zn_deficiency"),
    "Mn": (r"mangan|\bmn\b", "Mn_deficiency"),
    "B": (r"\bbore\b|\bbor[aoi]|\bb\s*\d+\s*%|\bboro|\bbor\b", "B_deficiency"),
    "Cu": (r"cuivre|\bcu\b|copper", None),
    "S": (r"soufre|\bso3\b|sulfat", None),
    "Si": (r"silic|\bsio2\b|\bsi\b", None),
    "acides_humiques_fulviques": (r"humi|fulvi", None),
    "acides_amines": (r"amin[eéo]|amino", None),
    "algues": (r"algue|\balga|seaweed|ascophyllum|ecklonia", None),
}


def plain(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def key(s):
    return re.sub(r"[^a-z0-9]", "", plain(s))


def read_export(path):
    raw = open(path, encoding="utf-8").read()
    start = re.compile(r'(?m)^(\d+),("[^"]*"|[^\n]*?),([a-z0-9][a-z0-9-]*),')
    starts = [m.start() for m in start.finditer(raw)]
    rows = []
    for a, b in zip(starts, starts[1:] + [len(raw)]):
        rec = raw[a:b].rstrip("\n")
        m = start.match(rec)
        # the 13 last columns never contain a comma; the description is what lies between
        body, *tail = rec[m.end():].rsplit(",", len(TAIL))
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(body.strip().strip('"')))).strip()
        rows.append({"id": int(m.group(1)), "nom": m.group(2).strip('"').strip(), "slug": m.group(3),
                     "description": text, **dict(zip(TAIL, tail))})
    return pd.DataFrame(rows)


def strip_size(name):
    """'LUNA EXPERIENCE SC 400 1L' -> 'LUNA EXPERIENCE SC 400': pack sizes are not part of the registered name."""
    return re.sub(r"\s*\b\d+(?:[.,]\d+)?\s*(?:l|cc|ml|g|gr|kg)\b\.?\s*$", "", name, flags=re.I).strip()


def link_registered(df):
    """Trade name -> product of the Tunisian list: exact key, prefix covering at least half of the longer name
    ('Corail 250 EW' -> 'Corail', not 'JUDOKA GOLD' -> 'JUDO'), then difflib >= 0.85."""
    if not os.path.exists(TN):
        return df
    tn = pd.read_csv(TN).dropna(subset=["nom_commercial"])
    tn["k"] = tn["nom_commercial"].map(key)
    keys = tn.drop_duplicates("k").set_index("k")
    out = []
    for name in df["nom"]:
        k = key(strip_size(name))
        hit, how = None, ""
        if k in keys.index:
            hit, how = k, "exact"
        else:
            pre = [x for x in keys.index if min(len(x), len(k)) >= max(4, max(len(x), len(k)) / 2)
                   and (k.startswith(x) or x.startswith(k))]
            if pre:
                hit, how = max(pre, key=len), "prefix"
            else:
                close = difflib.get_close_matches(k, list(keys.index), n=1, cutoff=0.85)
                hit, how = (close[0], "fuzzy") if close else (None, "")
        r = keys.loc[hit] if hit else None
        out.append({"homologation_match": how, "tn_product_id": r["product_id"] if hit else "",
                    "tn_nom_commercial": r["nom_commercial"] if hit else "",
                    "tn_substance": r["substance"] if hit else "", "tn_n_homologation": r["n_homologation"] if hit else ""})
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(out)], axis=1)


def main():
    os.makedirs(OUT, exist_ok=True)
    df = read_export(SRC)
    df["category_id"] = pd.to_numeric(df["category_id"], errors="coerce")
    df = df[df["category_id"].isin(CATEGORIES)].copy()
    df["categorie"] = df["category_id"].map(lambda c: CATEGORIES[c][0])
    df["sous_categorie"] = df["category_id"].map(lambda c: CATEGORIES[c][1])
    df["actif"] = df["actif"].eq("t")
    df["prix_dt"] = pd.to_numeric(df["prix"], errors="coerce")
    df["prix_promo_dt"] = pd.to_numeric(df["prix_promo"], errors="coerce")
    text = (df["nom"] + " " + df["description"]).map(plain)
    npk = text.str.extract(r"\b(\d{1,2})[-.](\d{1,2})[-.](\d{1,2})\b")
    df["npk"] = npk.dropna().astype(int).astype(str).agg("-".join, axis=1).reindex(df.index).fillna("")
    for nut, (rx, _) in NUTRIENTS.items():
        df[nut] = text.str.contains(rx, regex=True)
    for nut, i in (("N", 0), ("P", 1), ("K", 2)):  # an NPK grade with a non-zero figure brings the nutrient
        df[nut] |= npk[i].fillna("0").astype(int).gt(0)
    df["chelate"] = text.str.extract(r"\b(eddha|eddhsa|edta|dtpa|hbed|igsa|lignosulfonate|gluconate|heptagluconate)\b",
                                     expand=False).fillna("").str.upper()
    df = link_registered(df)
    cols = ["id", "nom", "slug", "categorie", "sous_categorie", "actif", "prix_dt", "prix_promo_dt", "npk", "chelate",
            *NUTRIENTS, "homologation_match", "tn_product_id", "tn_nom_commercial", "tn_substance", "tn_n_homologation",
            "description", "photo"]
    df[cols].to_csv(os.path.join(OUT, "agrishop_products.csv"), index=False, encoding="utf-8")

    # deficiency class -> fertilizers bringing that nutrient (name hits ranked before description-only hits)
    eng = df[df["categorie"] == "engrais"]
    rows = []
    for nut, (rx, cls) in NUTRIENTS.items():
        if cls is None:
            continue
        for r in eng[eng[nut]].itertuples():
            rows.append({"unified_class": cls, "nutriment": nut, "id": r.id, "nom": r.nom, "sous_categorie": r.sous_categorie,
                         "npk": r.npk, "chelate": r.chelate, "prix_dt": r.prix_dt, "actif": r.actif,
                         "preuve": "nom" if re.search(rx, plain(r.nom)) or (nut in "NPK" and r.npk) else "description"})
    cf = pd.DataFrame(rows).sort_values(["unified_class", "preuve", "nom"], key=lambda s: s.map({"nom": 0, "description": 1})
                                        if s.name == "preuve" else s)
    cf.to_csv(os.path.join(OUT, "class_fertilizers.csv"), index=False, encoding="utf-8")

    print(df.groupby(["categorie", "sous_categorie"]).size().to_string())
    pest = df[df["categorie"] == "pesticides"]
    print(f"\n{len(df)} products ({int(df['actif'].sum())} active); pesticides linked to the Tunisian list: "
          f"{pest['homologation_match'].ne('').sum()}/{len(pest)} {pest['homologation_match'].value_counts().to_dict()}")
    print("fertilizers per deficiency class (name / description evidence):")
    print(cf.groupby(["unified_class", "preuve"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
