"""Phyto plan, step 12: refresh the shop catalogue and report what changed; optionally check that every product page
still answers.

    python src/preparation/refresh_shops.py --agrishop-export path/to/new_export.csv     a new PostgreSQL export
    python src/preparation/refresh_shops.py --agriclic                                   collect agriclic.tn again
    python src/preparation/refresh_shops.py --check-links                                HTTP status of every page
    ... add --apply to write the new catalogue (without it: report only, nothing is changed)

Sources (never guessed): agrishop.tn has no page address in its data, so it is refreshed by a NEW EXPORT of its products
table, given as a file; agriclic.tn is collected again page by page with scrape_agriclic.py, into a new dated folder
data/raw/agriclic/refresh_<date>/, robots.txt read first and obeyed (a page it forbids is not requested), one request
per second at most (or the Crawl-delay of robots.txt if longer). Without network the collection or the link check stop
quietly: "réseau indisponible", nothing is changed.

Report reports/shop/refresh_<date>.csv: one row per product new | changed | removed (fields that changed, old and new
values). --apply then:
  - writes data/processed/shop/shop_products.csv: a removed product stays as a row with stock_status "retire" and
    the date in retire_le, so its address is known but never shown (shop.py drops it; Vérificateur rule 28 blocks it);
  - keeps every reviewed row of docs/shop_product_classes.csv, shop_unapproved_claims.csv, shop_composition.csv and
    shop_product_mapping.csv for the products whose text did not change; new products get 'proposed' rows (the
    rules of classify_shop_products.py, extract_composition.py, match_shop_products.py); a product whose name,
    description, technical sheet or category changed gets its rows recomputed and set back to 'proposed' (note:
    "produit modifié le <date> : à relire"): a validated mapping is never kept on a text that changed;
  - rebuilds the SQLite base (build_db.py).
--check-links: a page that answers 404 or 410 is a removed product (stock_status "retire"); other errors (timeout,
5xx, 403) are reported and change nothing. Columns lien_http and lien_verifie_le keep the last answer.
"""
import argparse
import datetime
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "preparation"))
import build_shop_products as B  # noqa: E402

SHOP = B.OUT
REPORTS = ROOT / "reports" / "shop"
REVIEWED = {"classes": ROOT / "docs" / "shop_product_classes.csv",
            "claims": ROOT / "docs" / "shop_unapproved_claims.csv",
            "composition": ROOT / "docs" / "shop_composition.csv",
            "mapping": ROOT / "docs" / "shop_product_mapping.csv"}
OTHER_DOCS = [ROOT / "docs" / "fertiliser_needs.csv"]  # rewritten by match_shop_products.py: kept as reviewed
TEXT_FIELDS = ["name", "description", "technical_sheet", "shop_category"]   # a change -> review again
OTHER_FIELDS = ["price", "stock_status", "stock_quantity", "product_url", "image_url", "fiches_pdf"]
EXTRA = ["retire_le", "lien_http", "lien_verifie_le"]
UA = "Mozilla/5.0 (compatible; AgrIA-research/1.0; student project, polite crawl 1 req/s)"
DELAY = 1.0
SITES = {"agriclic": "https://www.agriclic.tn", "agrishop": "https://www.agrishop.tn"}


class NoNetwork(Exception):
    pass


def today():
    return datetime.date.today().isoformat()


def read_shop(path=None):
    df = pd.read_csv(path or SHOP, keep_default_na=False, dtype=str)
    for c in EXTRA:
        if c not in df:
            df[c] = ""
    return df


def normalise(df):
    """The same text form as a CSV read back (numbers written by pandas)."""
    tmp = ROOT / "data" / "processed" / "shop" / ".refresh_tmp.csv"
    df.to_csv(tmp, index=False, encoding="utf-8")
    try:
        return read_shop(tmp)
    finally:
        tmp.unlink()


# ------------------------------------------------------------------ comparing two catalogues
def compare(old, new, date=None):
    """Rows {id, name, etat (nouveau | modifie | retire), champs, avant, apres, a_relire}."""
    date = date or today()
    o, n = old.set_index("id"), new.set_index("id")
    out = []
    for pid in n.index.difference(o.index):
        out.append({"id": pid, "name": n.at[pid, "name"], "etat": "nouveau", "champs": "", "avant": "", "apres": "",
                    "a_relire": True})
    for pid in o.index.difference(n.index):
        if o.at[pid, "stock_status"] == "retire":  # already removed at an earlier refresh
            continue
        out.append({"id": pid, "name": o.at[pid, "name"], "etat": "retire", "champs": "", "avant": "", "apres": "",
                    "a_relire": False})
    for pid in o.index.intersection(n.index):
        changed = [c for c in TEXT_FIELDS + OTHER_FIELDS if str(o.at[pid, c]) != str(n.at[pid, c])]
        if o.at[pid, "stock_status"] == "retire" and n.at[pid, "stock_status"] != "retire":
            changed = sorted(set(changed) | {"stock_status"})  # back on the site
        if changed:
            out.append({"id": pid, "name": n.at[pid, "name"], "etat": "modifie", "champs": " | ".join(changed),
                        "avant": " | ".join(str(o.at[pid, c])[:80] for c in changed),
                        "apres": " | ".join(str(n.at[pid, c])[:80] for c in changed),
                        "a_relire": any(c in TEXT_FIELDS for c in changed)})
    return pd.DataFrame(out, columns=["id", "name", "etat", "champs", "avant", "apres", "a_relire"])


def merge_catalogue(old, new, diff, date=None):
    """The new catalogue + the removed products kept as 'retire' rows (address known, never shown)."""
    date = date or today()
    new = new.copy()
    for c in EXTRA:
        if c not in new:
            new[c] = ""
    # keep the last link check of the products still there
    keep = old.set_index("id")[["lien_http", "lien_verifie_le"]]
    for c in ("lien_http", "lien_verifie_le"):
        new[c] = new["id"].map(keep[c]).fillna("")
    gone = old[old["id"].isin(diff.loc[diff["etat"] == "retire", "id"]) | ((old["stock_status"] == "retire")
                                                                          & ~old["id"].isin(new["id"]))].copy()
    gone.loc[gone["retire_le"] == "", "retire_le"] = date
    gone["stock_status"] = "retire"
    return pd.concat([new, gone], ignore_index=True)[list(new.columns)]


# ------------------------------------------------------------------ keeping the review
def merge_reviewed(before, after, diff, date=None):
    """before/after: {name: DataFrame} of the reviewed CSV files before and after the rules ran again.
    Unchanged products keep their reviewed rows; new ones take the new 'proposed' rows; products whose text changed
    take the new rows, set back to 'proposed' with a note; removed products keep their rows with a note."""
    date = date or today()
    changed = set(diff.loc[(diff["etat"] == "modifie") & diff["a_relire"], "id"])
    new = set(diff.loc[diff["etat"] == "nouveau", "id"])
    removed = set(diff.loc[diff["etat"] == "retire", "id"])
    out = {}
    for name, old in before.items():
        fresh = after[name]
        keep = old[~old["shop_product_id"].isin(changed | new)].copy()
        if "note" in keep:
            mask = keep["shop_product_id"].isin(removed)
            keep.loc[mask, "note"] = (keep.loc[mask, "note"] + f" retiré du site le {date}").str.strip()
        add = fresh[fresh["shop_product_id"].isin(changed | new)].copy()
        if "status" in add:
            add["status"] = "proposed"
        if "note" in add:
            mask = add["shop_product_id"].isin(changed)
            add.loc[mask, "note"] = f"produit modifié le {date} : à relire"
        cols = list(old.columns) + [c for c in fresh.columns if c not in old.columns]
        out[name] = pd.concat([keep.reindex(columns=cols), add.reindex(columns=cols)], ignore_index=True).fillna("")
    return out


def rerun_rules():
    """The rules of steps 8-9 on the new catalogue (they rewrite every row as 'proposed': merge_reviewed repairs)."""
    import classify_shop_products
    import extract_composition
    import match_shop_products
    classify_shop_products.main()
    extract_composition.main()
    match_shop_products.main()


def read_reviewed():
    return {k: pd.read_csv(p, keep_default_na=False, dtype=str) for k, p in REVIEWED.items() if p.exists()}


# ------------------------------------------------------------------ polite network access
class Polite:
    """robots.txt of each site read once and obeyed; at most one request per DELAY (or Crawl-delay) seconds."""

    def __init__(self, delay=DELAY, opener=urllib.request.urlopen):
        self.delay, self.opener, self.robots, self.last = delay, opener, {}, 0.0

    def _robots(self, url):
        site = "/".join(url.split("/")[:3])
        if site not in self.robots:
            rp = urllib.robotparser.RobotFileParser(site + "/robots.txt")
            try:
                with self.opener(urllib.request.Request(site + "/robots.txt", headers={"User-Agent": UA}),
                                 timeout=20) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    rp.disallow_all = True
                else:  # no robots.txt: everything allowed
                    rp.parse([])
            except (urllib.error.URLError, socket.timeout, OSError) as e:
                raise NoNetwork(str(e))
            self.robots[site] = rp
        return self.robots[site]

    def allowed(self, url):
        return self._robots(url).can_fetch(UA, url)

    def wait(self, url):
        delay = max(self.delay, self._robots(url).crawl_delay(UA) or 0)
        time.sleep(max(0.0, self.last + delay - time.time()))
        self.last = time.time()

    def status(self, url):
        """HTTP status of a page (HEAD, then GET when HEAD is refused); None when robots.txt forbids it."""
        if not self.allowed(url):
            return None
        for method in ("HEAD", "GET"):
            self.wait(url)
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
            try:
                with self.opener(req, timeout=30) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                if e.code == 405 and method == "HEAD":
                    continue
                return e.code
            except (urllib.error.URLError, socket.timeout, OSError) as e:
                raise NoNetwork(str(e))
        return None


def check_links(df, polite=None, date=None):
    """Last HTTP answer of every product page; 404/410 -> the product is removed. Raises NoNetwork."""
    polite, date = polite or Polite(), date or today()
    df = df.copy()
    report = []
    for i, r in df[(df["product_url"] != "") & (df["stock_status"] != "retire")].iterrows():
        code = polite.status(r["product_url"])
        df.at[i, "lien_http"] = "" if code is None else str(code)
        df.at[i, "lien_verifie_le"] = date
        if code in (404, 410):
            df.at[i, "stock_status"], df.at[i, "retire_le"] = "retire", date
        report.append({"id": r["id"], "name": r["name"], "url": r["product_url"],
                       "http": "interdit par robots.txt" if code is None else code})
    return df, pd.DataFrame(report, columns=["id", "name", "url", "http"])


def collect_agriclic(date=None, polite=None):
    """scrape_agriclic.py into data/raw/agriclic/refresh_<date>/ (its cache is that empty folder: every page is
    requested again), each request checked against robots.txt. Raises NoNetwork."""
    import scrape_agriclic as S
    polite = polite or Polite()
    folder = B.AGRICLIC / f"refresh_{date or today()}"
    polite._robots(S.BASE)  # no network: stop before anything is written
    original = S.get

    def get(url, cache):
        if not (Path(S.RAW) / "html" / cache).exists():
            if not polite.allowed(url):
                raise PermissionError(f"robots.txt interdit {url}")
            polite.wait(url)
        return original(url, cache)

    S.RAW, S.OUT, S.DELAY, S.get = str(folder), str(folder / "processed"), 0.0, get
    S.main()
    return folder


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--agrishop-export", help="nouvel export PostgreSQL de la table products d'agrishop.tn")
    ap.add_argument("--agriclic", action="store_true", help="collecter de nouveau les pages d'agriclic.tn")
    ap.add_argument("--agriclic-folder", help="dossier déjà collecté (products.jsonl + html/)")
    ap.add_argument("--check-links", action="store_true", help="statut HTTP de chaque page produit")
    ap.add_argument("--apply", action="store_true", help="écrire le nouveau catalogue (sinon : rapport seulement)")
    args = ap.parse_args(argv)
    date = today()
    old = read_shop()
    raw = Path(args.agriclic_folder) if args.agriclic_folder else B.AGRICLIC
    if args.agriclic:
        try:
            raw = collect_agriclic(date)
        except NoNetwork as e:
            print(f"réseau indisponible ({e}) : collecte d'agriclic.tn ignorée, rien n'est changé")
            return 0
    export = Path(args.agrishop_export) if args.agrishop_export else None
    if export and not export.exists():
        print(f"export introuvable : {export}")
        return 1
    new = normalise(B.build(export, raw))
    diff = compare(old, new, date)
    catalogue = merge_catalogue(old, new, diff, date)
    links = None
    if args.check_links:
        try:
            catalogue, links = check_links(catalogue, date=date)
        except NoNetwork as e:
            print(f"réseau indisponible ({e}) : vérification des liens ignorée")
        else:
            dead = links[links["http"].isin([404, 410])]
            for r in dead.itertuples():
                if r.id not in set(diff["id"]):
                    diff.loc[len(diff)] = {"id": r.id, "name": r.name, "etat": "retire", "champs": "lien_http",
                                           "avant": "", "apres": str(r.http), "a_relire": False}
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"refresh_{date}.csv"
    diff.to_csv(out, index=False, encoding="utf-8")
    counts = diff["etat"].value_counts().to_dict()
    print(f"{len(old)} -> {len(catalogue)} lignes ; nouveaux {counts.get('nouveau', 0)}, modifiés "
          f"{counts.get('modifie', 0)} (dont à relire {int(diff['a_relire'].sum())}), retirés {counts.get('retire', 0)}"
          f" -> {out}")
    if links is not None:
        print("liens :", links["http"].astype(str).value_counts().to_dict())
        links.to_csv(REPORTS / f"liens_{date}.csv", index=False, encoding="utf-8")
    if not args.apply:
        print("rapport seulement : ajoutez --apply pour écrire le nouveau catalogue")
        return 0
    before = read_reviewed()
    others = {p: p.read_bytes() for p in OTHER_DOCS if p.exists()}
    catalogue.to_csv(SHOP, index=False, encoding="utf-8")
    if args.agriclic and raw != B.AGRICLIC:  # the new collection becomes the current one
        shutil.copy(raw / "products.jsonl", B.AGRICLIC / "products.jsonl")
        for page in (raw / "html").glob("p_*.html"):
            shutil.copy(page, B.AGRICLIC / "html" / page.name)
    if not diff.empty:
        rerun_rules()
        after = read_reviewed()
        for name, df in merge_reviewed(before, after, diff, date).items():
            df.to_csv(REVIEWED[name], index=False, encoding="utf-8")
        for p, content in others.items():
            p.write_bytes(content)
    subprocess.run([sys.executable, str(ROOT / "src" / "tools" / "build_db.py")], check=True, cwd=ROOT)
    print("catalogue écrit ; lignes à relire :", int(diff["a_relire"].sum()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
