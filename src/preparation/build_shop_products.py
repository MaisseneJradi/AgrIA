"""Every product of the two shops in one table (phyto plan, step 8): data/processed/shop/shop_products.csv, loaded by
build_db.py into the SQLite table shop_products. Nothing is downloaded: the data already in the repository is read.

  agrishop.tn  data/raw/scrapper/mon_fichier.csv, PostgreSQL export of the products table (build_agrishop.read_export):
               all 383 rows, machinery (category 34) and irrigation (18) included. The export holds a slug and a relative
               photo path but no page address: product_url comes from the sitemap of the site
               (data/raw/agrishop/sitemap.xml, refresh_shops.py --agrishop-sitemap), matched by the exact slug;
               empty when the slug is not in it (never guessed). No image address. Technical sheets are PDF links in the description
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
# sitemap of agrishop.tn (refresh_shops.py --agrishop-sitemap): the real address of every product page, matched to the
# export by the EXACT slug (/store/category/<category>/<sub-category>/<slug>/); never built from a pattern
SITEMAP = ROOT / "data" / "raw" / "agrishop" / "sitemap.xml"
PRODUCT_PAGE = r"https://www\.agrishop\.tn/store/category/[^/<]+/[^/<]+/([^/<]+)/"
# category ids of the agrishop export -> name (4-15 read from the products by build_agrishop.py; 18 and 34 likewise)
CATEGORIES = {**{k: f"{a} > {b}" for k, (a, b) in A.CATEGORIES.items()},
              18: "irrigation > tuyaux_raccords", 34: "materiel > machines_outils"}
COLUMNS = ["id", "name", "shop_category", "description", "technical_sheet", "price", "stock_status", "stock_quantity",
           "image_url", "product_url", "source", "last_updated", "slug", "fiches_pdf"]


def raw_records(export=None):
    """id -> raw text of its record in the export, cut exactly as build_agrishop.read_export cuts the records."""
    raw = Path(export or ROOT / A.SRC).read_text(encoding="utf-8")
    start = re.compile(r'(?m)^(\d+),("[^"]*"|[^\n]*?),([a-z0-9][a-z0-9-]*),')
    starts = [(m.start(), int(m.group(1))) for m in start.finditer(raw)]
    return {pid: raw[a:b] for (a, pid), (b, _) in zip(starts, starts[1:] + [(len(raw), None)])}


def sitemap_urls(path=SITEMAP):
    """slug -> product page address listed in the sitemap of agrishop.tn ({} when the sitemap was never fetched)."""
    if not Path(path).exists():
        return {}
    locs = re.findall(r"<loc>([^<]+)</loc>", Path(path).read_text(encoding="utf-8"))
    return {m.group(1): loc for loc in locs for m in [re.fullmatch(PRODUCT_PAGE, loc)] if m}


def agrishop(export=None, sitemap=SITEMAP):
    """export: a newer PostgreSQL export of the products table (refresh_shops.py), same format; default the one of
    the repository. sitemap: the sitemap of the site, for the page addresses."""
    pages = sitemap_urls(sitemap)
    df = A.read_export(str(export or ROOT / A.SRC))
    df["category_id"] = pd.to_numeric(df["category_id"], errors="coerce")
    records = raw_records(export)
    rows = []
    for r in df.itertuples():
        qty = pd.to_numeric(r.stock, errors="coerce")
        status = "inactif" if r.actif != "t" else ("en_stock" if qty and qty > 0 else "rupture" if qty == 0 else "inconnu")
        # PDF links of technical sheets are in the HTML of the description (the plain text lost them)
        pdfs = sorted(set(re.findall(r"https?://[^\s\"'<>]+\.pdf", records.get(r.id, ""))))
        rows.append({"id": f"agrishop:{r.id}", "name": r.nom, "shop_category": CATEGORIES.get(r.category_id, "inconnue"),
                     "description": r.description, "technical_sheet": "", "price": pd.to_numeric(r.prix, errors="coerce"),
                     "stock_status": status, "stock_quantity": qty, "image_url": "", "product_url": pages.get(r.slug, ""),
                     "source": "agrishop.tn (export PostgreSQL de la table products)", "last_updated": r.maj_le,
                     "slug": r.slug, "fiches_pdf": " | ".join(pdfs)})
    return rows


def page_facts(pid, raw=AGRICLIC):
    """Availability and cover image of a cached agriclic product page (no request)."""
    path = Path(raw) / "html" / f"p_{pid}.html"
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


def agriclic(raw=AGRICLIC):
    """raw: a folder with products.jsonl and html/ (scrape_agriclic.py, or a fresh collection of refresh_shops.py)."""
    rows = []
    for line in open(Path(raw) / "products.jsonl", encoding="utf-8"):
        r = json.loads(line)
        status, image = page_facts(r["id"], raw)
        sheet = " ; ".join(f"{k} : {', '.join(v)}" for k, v in (r.get("fiche") or {}).items())
        rows.append({"id": f"agriclic:{r['id']}", "name": r["nom"], "shop_category": " > ".join(r["categories"]),
                     "description": " ".join(x for x in (r.get("resume"), r.get("description")) if x),
                     "technical_sheet": sheet, "price": r.get("prix_tnd"), "stock_status": status,
                     "stock_quantity": None, "image_url": image, "product_url": r["url"],
                     "source": "agriclic.tn (pages produits, robots.txt respecté)", "last_updated": r.get("maj_le"),
                     "slug": "", "fiches_pdf": ""})
    return rows


def build(export=None, raw=AGRICLIC, sitemap=SITEMAP):
    return pd.DataFrame(agrishop(export, sitemap) + agriclic(raw), columns=COLUMNS)


def main():
    df = build()
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
