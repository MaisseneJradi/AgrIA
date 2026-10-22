"""Fertilizers and seeds sold on agriclic.tn (PrestaShop shop), with their technical sheets.

Crawl: the category pages of "Engrais & Fertilisants" (6), "Semences" (39) and their sub-categories, page after page (?page=N, allowed by
robots.txt), then every product page found. One request per second; every page is cached in data/raw/agriclic/html/,
so a rerun downloads nothing that is already there (delete the folder to refresh prices).
Per product: the JSON in data-product (id, name, price, reference, descriptions, update date), the breadcrumb
(category path) and the "Fiche technique" (dt/dd pairs: Nature, Composition, Usages, Formulation, Biologique,
Emballage, Distributeur, Fabricant...).

Fertilizers: the composition is parsed into one column per nutrient, in % (N, P2O5, K2O, CaO, MgO, SO3, Fe, Zn, Mn,
B, Cu, Mo, SiO2, organic matter, humic/fulvic acids, amino acids, seaweed), and the usages into one row per
crop : dose. Deficiency classes of the image model -> fertilizers ranked by their content of the missing nutrient.

Usage: python src/preparation/scrape_agriclic.py
Output: data/raw/agriclic/products.jsonl                     raw record per product
        data/processed/fertilizers/agriclic_fertilizers.csv  one row per fertilizer, nutrients in %
        data/processed/fertilizers/agriclic_usages.csv       one row per fertilizer x crop/stage : dose
        data/processed/fertilizers/agriclic_seeds.csv        one row per seed product
        data/processed/fertilizers/agriclic_class_fertilizers.csv  deficiency class -> fertilizers
"""
import html
import json
import os
import re
import time
import unicodedata
import urllib.request

import pandas as pd
from tqdm import tqdm

BASE = "https://www.agriclic.tn/"
# the parent categories do not list every product of their sub-categories: each one is crawled too
ROOTS = ["6-engrais-fertilisants", "25-correcteur-de-carence", "26-biostimulant", "27-amendement-organique",
         "28-npk-soluble", "29-regulateur-de-croissance", "211-npk-granule", "59-fertilisant-hydroponique",
         "217-enracinement", "218-floraison-nouaison", "39-semences", "178-potager", "179-fleuris"]
RAW = os.path.join("data", "raw", "agriclic")
OUT = os.path.join("data", "processed", "fertilizers")
UA = "Mozilla/5.0 (compatible; AgrIA-research/1.0; student project, polite crawl 1 req/s)"
DELAY = 1.0
# nutrient column -> regex on one composition item (lower case, no accent)
NUTRIENTS = {
    "N": r"azote|\(n\)", "P2O5": r"p2o5|phosphor", "K2O": r"k2o|potass", "CaO": r"\bcao\b|calcium",
    "MgO": r"\bmgo\b|magnesi", "SO3": r"\bso3\b|soufre|\(s\)", "Fe": r"\bfer\b|\(fe\)", "Zn": r"zinc|\(zn\)",
    "Mn": r"mangan|\(mn\)", "B": r"\bbore\b|\(b\)", "Cu": r"cuivre|\(cu\)", "Mo": r"molybd|\(mo\)",
    "SiO2": r"silic|sio2", "matiere_organique": r"matiere organique|carbone organique", "acides_humiques": r"humique",
    "acides_fulviques": r"fulvique", "acides_amines": r"amine|amino", "algues": r"algue|ascophyllum|ecklonia",
}
DEFICIENCY = {"N_deficiency": "N", "P_deficiency": "P2O5", "K_deficiency": "K2O", "Ca_deficiency": "CaO",
              "Mg_deficiency": "MgO", "Fe_deficiency": "Fe", "Zn_deficiency": "Zn", "Mn_deficiency": "Mn",
              "B_deficiency": "B"}
_last = [0.0]


def plain(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def get(url, cache):
    """Page from the cache, else downloaded (at most one request per DELAY seconds) and cached."""
    path = os.path.join(RAW, "html", cache)
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    time.sleep(max(0.0, _last[0] + DELAY - time.time()))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    _last[0] = time.time()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(text)
    return text


def product_urls(root):
    """Every product link of a category and its sub-categories, following ?page=N until a page adds nothing."""
    urls, page = [], 1
    while True:
        h = get(f"{BASE}{root}?page={page}", f"cat_{root}_{page}.html")
        found = [u for u in dict.fromkeys(re.findall(r'href="(https://www\.agriclic\.tn/\d+-[^"#?]+\.html)', h))
                 if u not in urls]
        if not found:
            return urls
        urls += found
        page += 1


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_product(h, url):
    d = json.loads(html.unescape(re.search(r'data-product="([^"]+)"', h).group(1)))
    crumbs = re.search(r'"breadcrumb":\{"links":(\[.*?\])', h)
    path = [c["title"] for c in json.loads(crumbs.group(1))][2:-1] if crumbs else []
    sheet = {}
    m = re.search(r'<dl class="data-sheet">(.*?)</dl>', h, re.S)
    for k, v in re.findall(r'<dt class="name">(.*?)</dt>\s*<dd class="value">(.*?)</dd>', m.group(1) if m else "", re.S):
        # multi-valued features come as "\n , value": one item per line
        items = [x.strip(" ,") for x in clean(v).split("\n") if x.strip(" ,")]
        sheet[clean(k)] = items
    return {"id": d["id"], "nom": clean(d["name"]), "url": url, "reference": d.get("reference"),
            "prix_tnd": d.get("price_amount"), "categories": path, "fiche": sheet,
            "resume": clean(d.get("description_short")), "description": clean(d.get("description")),
            "maj_le": d.get("date_upd")}


def percent(item):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", item)
    return float(m.group(1).replace(",", ".")) if m else None


def nutrients(items):
    """['Azote (N) total 10 %', 'Oxyde de potassium (K2O) soluble dans l'eau 40 %'] -> {'N': 10.0, 'K2O': 40.0}.
    Several forms of one nutrient (nitric + ammoniacal N...) are not summed: the 'total' item wins, else the largest.
    'AZOTE: 20% - OXYDE DE POTASSIUM: 20%' is split into items; a lone '21% p/p' item takes the nutrient of the next
    item ('Bore (B) soluble'); phosphites (phosphonates) are not counted as K2O or P2O5."""
    parts = [p.strip() for it in items for p in re.split(r"\s+-\s+|\s*;\s*", it) if p.strip()]
    merged, k = [], 0
    while k < len(parts):
        cur = parts[k]
        if re.fullmatch(r"\d+(?:[.,]\d+)?\s*%.{0,8}", cur) and k + 1 < len(parts) and percent(parts[k + 1]) is None:
            cur, k = parts[k + 1] + " " + cur, k + 1
        merged.append(cur)
        k += 1
    out, total = {}, {}
    for it in merged:
        p, t = percent(it), plain(it)
        if p is None or "phosphite" in t:
            continue
        for col, rx in NUTRIENTS.items():
            if re.search(rx, t):
                if "total" in t:
                    total[col] = p
                out[col] = max(out.get(col, 0.0), p)
                break
    return {**out, **total}


def usages(rec):
    """'Usages' items -> rows (contexte, culture, dose). A line ending with ':' sets the context (e.g. fertigation)."""
    rows, ctx = [], ""
    for it in rec["fiche"].get("Usages", []):
        if it.endswith(":") and not re.search(r"\d", it):
            ctx = it.rstrip(" :")
            continue
        crop, _, dose = it.partition(":")
        rows.append({"id": rec["id"], "nom": rec["nom"], "contexte": ctx,
                     "culture": crop.strip() if dose else "", "dose": (dose or it).strip(" .")})
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    recs, seen = [], set()
    for root in ROOTS:
        urls = product_urls(root)
        for url in tqdm(urls, desc=root, unit="product"):
            pid = re.search(r"/(\d+)-", url).group(1)
            try:
                rec = parse_product(get(url, f"p_{pid}.html"), url)
            except Exception as e:  # a page without product data (removed product...): reported, not fatal
                print(f"skip {url}: {e}")
                continue
            # category pages also link featured products of other shelves: the breadcrumb decides
            crumbs = plain(" ".join(rec["categories"]))
            kind_of = "engrais" if "engrais" in crumbs else "semences" if "semences" in crumbs else None
            if kind_of and rec["id"] not in seen:
                seen.add(rec["id"])
                recs.append({"type": kind_of, **rec})
    with open(os.path.join(RAW, "products.jsonl"), "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def flat(r):
        f = r["fiche"]
        return {"id": r["id"], "nom": r["nom"], "categorie": " > ".join(r["categories"]),
                "sous_categorie": r["categories"][-1] if r["categories"] else "", "prix_tnd": r["prix_tnd"],
                "reference": r["reference"], **{k: " ; ".join(v) for k, v in f.items()},
                "resume": r["resume"], "description": r["description"], "url": r["url"], "maj_le": r["maj_le"]}

    eng = [r for r in recs if r["type"] == "engrais"]
    fert = pd.DataFrame([{**flat(r), **nutrients(r["fiche"].get("Composition", []))} for r in eng])
    text = (fert["nom"] + " " + fert.get("Composition", "").fillna("") + " " + fert["description"]).map(plain)
    fert["chelate"] = text.str.extract(r"\b(eddha|eddhsa|edta|dtpa|hbed|igsa|lignosulfonate|gluconate|heptagluconate)\b",
                                       expand=False).fillna("").str.upper()
    fert.to_csv(os.path.join(OUT, "agriclic_fertilizers.csv"), index=False, encoding="utf-8")
    pd.DataFrame([u for r in eng for u in usages(r)]).to_csv(os.path.join(OUT, "agriclic_usages.csv"), index=False,
                                                             encoding="utf-8")
    seeds = pd.DataFrame([flat(r) for r in recs if r["type"] == "semences"])
    seeds.to_csv(os.path.join(OUT, "agriclic_seeds.csv"), index=False, encoding="utf-8")

    rows = []
    for cls, col in DEFICIENCY.items():
        if col not in fert:
            continue
        hit = fert[fert[col].fillna(0) > 0].sort_values(col, ascending=False)
        for r in hit.itertuples():
            rows.append({"unified_class": cls, "nutriment": col, "teneur_pct": getattr(r, col), "id": r.id, "nom": r.nom,
                         "sous_categorie": r.sous_categorie, "chelate": r.chelate, "prix_tnd": r.prix_tnd, "url": r.url})
    cf = pd.DataFrame(rows)
    cf.to_csv(os.path.join(OUT, "agriclic_class_fertilizers.csv"), index=False, encoding="utf-8")

    print(f"\n{len(eng)} fertilizers, {len(seeds)} seed products")
    print(fert["sous_categorie"].value_counts().to_string())
    print("\nsheet fields (fertilizers):", pd.Series([k for r in eng for k in r["fiche"]]).value_counts().to_dict())
    print("sheet fields (seeds):", pd.Series([k for r in recs if r["type"] == "semences" for k in r["fiche"]])
          .value_counts().to_dict())
    print("seed sub-categories:", seeds["sous_categorie"].value_counts().to_dict() if len(seeds) else {})
    print("\nfertilizers per deficiency class:", cf.groupby("unified_class").size().to_dict() if len(cf) else {})


if __name__ == "__main__":
    main()
