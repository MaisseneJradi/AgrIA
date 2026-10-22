"""Client for the EU Pesticides Database (DG SANTE datalake API v3), with a local JSON cache.

Endpoints used (100 records per page, next page in "nextLink"):
  active-substances            approval status, category, CAS number of each active substance
  pesticide-residues           residue definitions (the MRLs are set per residue), names in every EU language
  pesticide-residues-products  the commodities of Annex I of Reg. (EC) 396/2005 (code, name, parent)
  pesticide-residues-mrls      MRL per residue x commodity, with the regulation and its applicability
Everything is cached in data/raw/eu_pesticides/ (delete a file to download it again).
"""
import json
import os
import time
import urllib.parse
import urllib.request

from tqdm import tqdm

API = "https://api.datalake.sante.service.ec.europa.eu/sante/pesticides/"
CACHE = os.path.join("data", "raw", "eu_pesticides")


def _get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def fetch(endpoint, cache_name, desc=None, keep=None, progress=True, **params):
    """All the records of an endpoint (follows nextLink), cached in CACHE/<cache_name>.json.
    keep: optional filter applied before caching (the API cannot filter on every field)."""
    path = os.path.join(CACHE, cache_name + ".json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = API + endpoint + "?" + urllib.parse.urlencode({"format": "json", **params, "api-version": "v3.0"})
    out, bar = [], tqdm(desc=desc or cache_name, unit="page", leave=False, disable=not progress)
    while url:
        page = _get(url)
        out += [r for r in page.get("value", []) if keep is None or keep(r)]
        url = page.get("nextLink")
        bar.update()
    bar.close()
    tmp = path + ".tmp"  # written then renamed: an interrupted download leaves no truncated cache
    json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, path)
    return out


def active_substances():
    return fetch("active-substances", "active_substances")


def residues(lang):
    return fetch("pesticide-residues", f"residues_{lang}", pesticide_residue_lg=lang)


def products(lang):
    return fetch("pesticide-residues-products", f"products_{lang}", language=lang)


def mrls(residue_id, progress=True):
    """MRLs of one residue. The API returns every past version (up to ~20 per commodity): only the applicable and
    the future ones are kept."""
    return fetch("pesticide-residues-mrls", os.path.join("mrls", str(residue_id)), desc=f"MRL {residue_id}",
                 keep=lambda r: r.get("applicability_text") != "No longer applicable", progress=progress,
                 pesticide_residue_id=residue_id)


def mrls_many(residue_ids, workers=8):
    """Download the MRLs of several residues in parallel (one residue = 15 to 70 pages)."""
    from concurrent.futures import ThreadPoolExecutor
    ids = sorted(set(residue_ids))
    with ThreadPoolExecutor(workers) as pool:
        list(tqdm(pool.map(lambda i: mrls(i, progress=False), ids), total=len(ids), desc="EU MRLs", unit="residue"))
    return {i: mrls(i) for i in ids}
