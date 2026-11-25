"""Every product of the two shops in one table (phyto plan, step 8): data/processed/shop/shop_products.csv, loaded by
build_db.py into the SQLite table shop_products. Nothing is downloaded: the data already in the repository is read.

  agrishop.tn  data/raw/scrapper/mon_fichier.csv, PostgreSQL export of the products table (build_agrishop.read_export):
               all 383 rows, machinery (category 34) and irrigation (18) included. The export holds a slug and a relative
               photo path but NO page address and NO image address: product_url and image_url stay empty until the
               pattern is confirmed by the shop owner (never guessed). Technical sheets are PDF links in the description
               (fiches_pdf), their text is not read here.
  agriclic.tn  data/raw/agriclic/products.jsonl (scrape_agriclic.py: fertilisers and seeds, robots.txt obeyed) and the
               cached product pages data/raw/agriclic/html/p_<id>.html for the availability and the cover image.

Columns: id (agrishop:<id> | agriclic:<id>), name, shop_category, description, technical_sheet, price (TND), stock_status
(en_stock | rupture | inactif | inconnu), stock_quantity, image_url, product_url, source, last_updated, slug, fiches_pdf.
Usage: python src/preparation/build_shop_products.py
"""
import html
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "preparation"))
import build_agrishop as A  # noqa: E402

OUT = ROOT / "data" / "processed" / "shop" / "shop_products.csv"
AGRICLIC = ROOT / "data" / "raw" / "agriclic"
# category ids of the agrishop export -> name (4-15 read from the products by build_agrishop.py; 18 and 34 likewise)
CATEGORIES = {**{k: f"{a} > {b}" for k, (a, b) in A.CATEGORIES.items()},
              18: "irrigation > tuyaux_raccords", 34: "materiel > machines_outils"}
COLUMNS = ["id", "name", "shop_category", "description", "technical_sheet", "price", "stock_status", "stock_quantity",
           "image_url", "product_url", "source", "last_updated", "slug", "fiches_pdf"]


def raw_records():
    """id -> raw text of its record in the export, cut exactly as build_agrishop.read_export cuts the records."""
    raw = Path(ROOT / A.SRC).read_text(encoding="utf-8")
    start = re.compile(r'(?m)^(\d+),("[^"]*"|[^\n]*?),([a-z0-9][a-z0-9-]*),')
    starts = [(m.start(), int(m.group(1))) for m in start.finditer(raw)]
    return {pid: raw[a:b] for (a, pid), (b, _) in zip(starts, starts[1:] + [(len(raw), None)])}


def agrishop():
    df = A.read_export(str(ROOT / A.SRC))
    df["category_id"] = pd.to_numeric(df["category_id"], errors="coerce")
    records = raw_records()
    rows = []
    for r in df.itertuples():
        qty = pd.to_numeric(r.stock, errors="coerce")
        status = "inactif" if r.actif != "t" else ("en_stock" if qty and qty > 0 else "rupture" if qty == 0 else "inconnu")
        # PDF links of technical sheets are in the HTML of the description (the plain text lost them)
        pdfs = sorted(set(re.findall(r"https?://[^\s\"'<>]+\.pdf", records.get(r.id, ""))))
        rows.append({"id": f"agrishop:{r.id}", "name": r.nom, "shop_category": CATEGORIES.get(r.category_id, "inconnue"),
                     "description": r.description, "technical_sheet": "", "price": pd.to_numeric(r.prix, errors="coerce"),
                     "stock_status": status, "stock_quantity": qty, "image_url": "", "product_url": "",
                     "source": "agrishop.tn (export PostgreSQL de la table products)", "last_updated": r.maj_le,
                     "slug": r.slug, "fiches_pdf": " | ".join(pdfs)})
    return rows


def page_facts(pid):
    """Availability and cover image of a cached agriclic product page (no request)."""
    path = AGRICLIC / "html" / f"p_{pid}.html"
    if not path.exists():
        return "inconnu", ""
    m = re.search(r'data-product="([^"]+)"', path.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return "inconnu", ""
    d = json.loads(html.unescape(m.group(1)))
    status = {"available": "en_stock", "last_remaining_items": "en_stock", "unavailable": "rupture"}.get(
        d.get("availability"), "inconnu")
    image = ((d.get("cover") or {}).get("large") or {}).get("url", "")
    return status, image


def agriclic():
    rows = []
    for line in open(AGRICLIC / "products.jsonl", encoding="utf-8"):
        r = json.loads(line)
        status, image = page_facts(r["id"])
        sheet = " ; ".join(f"{k} : {', '.join(v)}" for k, v in (r.get("fiche") or {}).items())
        rows.append({"id": f"agriclic:{r['id']}", "name": r["nom"], "shop_category": " > ".join(r["categories"]),
                     "description": " ".join(x for x in (r.get("resume"), r.get("description")) if x),
                     "technical_sheet": sheet, "price": r.get("prix_tnd"), "stock_status": status,
                     "stock_quantity": None, "image_url": image, "product_url": r["url"],
                     "source": "agriclic.tn (pages produits, robots.txt respecté)", "last_updated": r.get("maj_le"),
                     "slug": "", "fiches_pdf": ""})
    return rows


def main():
    df = pd.DataFrame(agrishop() + agriclic(), columns=COLUMNS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(df)} products")
    print(df.groupby(df["id"].str.split(":").str[0]).agg(produits=("id", "size"),
                                                          avec_url=("product_url", lambda s: (s != "").sum()),
                                                          avec_image=("image_url", lambda s: (s != "").sum()),
                                                          avec_fiche=("technical_sheet", lambda s: (s != "").sum()),
                                                          avec_pdf=("fiches_pdf", lambda s: (s != "").sum()))
          .to_string())
    print(df["stock_status"].value_counts().to_dict())


if __name__ == "__main__":
    main()
