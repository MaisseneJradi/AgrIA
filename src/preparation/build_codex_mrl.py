"""Codex maximum residue limits (FAO/WHO Codex Alimentarius) of the substances of the Tunisian list (phyto plan, step 7).

Source: Codex "Pesticide Residues in Food and Feed" database, https://codex.fao.org/codex-texts/codex-online-databases/
pesticides-residues: the pesticide index, then one page per pesticide ("pesticide-details?pestId=..."), each with its
table Commodities | MRL | Year | Symbols | Notes. robots.txt of the site allows these pages; one request per second,
every page cached in data/raw/codex/ (delete a page to download it again).
Pesticide names are matched to the EU names of the Tunisian substances with the keys of build_moa_groups.py.

Output: data/processed/pesticides/codex_mrl.csv (substance, codex_nom, codex_id, denree, lmr_mg_kg, annee, symboles,
        notes) and, the first time only, docs/codex_commodity_mapping.csv: AgrIA crop -> Codex commodity names found
        in the data, with their level (denree | sous-groupe | groupe), status = proposed (src/tools/mrl.py uses the
        validated rows only).
Usage: python src/preparation/build_codex_mrl.py
"""
import csv
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "preparation"))
from build_moa_groups import key, variants  # noqa: E402

BASE = "https://codex.fao.org/codex-texts/codex-online-databases/pesticides-residues/pesticide-index"
RAW = ROOT / "data" / "raw" / "codex"
OUT = ROOT / "data" / "processed" / "pesticides" / "codex_mrl.csv"
MAPPING = ROOT / "docs" / "codex_commodity_mapping.csv"
UA = "Mozilla/5.0 (compatible; AgrIA-research/1.0; student project)"
# AgrIA crop -> (regex on the Codex commodity name, level); most specific first. Written from the Codex names of the
# data; every row produced is "proposed" and must be checked against the Codex classification of foods (CXA 4-1989).
CROPS = {
    "tomato": [(r"^Tomato(es)?\b", "denree"), (r"^Fruiting vegetables, other than Cucurbits", "groupe")],
    "pepper": [(r"^Peppers?, (sweet|chili)|^Peppers\b", "denree"),
               (r"^Fruiting vegetables, other than Cucurbits", "groupe")],
    "potato": [(r"^Potato", "denree"), (r"^Tuberous and corm vegetables", "sous-groupe"),
               (r"^Root and tuber vegetables", "groupe")],
    "squash": [(r"^Squash", "denree"), (r"^Fruiting vegetables, [Cc]ucurbits", "groupe")],
    "grape": [(r"^Grapes?\b", "denree"), (r"^Small fruit vine climbing", "sous-groupe"),
              (r"^Berries and other small fruits", "groupe")],
    "citrus": [(r"^Oranges?, [Ss]weet|^Mandarins?|^Lemons? and limes", "sous-groupe"), (r"^Citrus fruits?", "groupe")],
    "apple": [(r"^Apples?\b", "denree"), (r"^Pome fruits?", "groupe")],
    "peach": [(r"^Peach", "denree"), (r"^Peaches", "sous-groupe"), (r"^Stone fruits?", "groupe")],
    "cherry": [(r"^Cherries", "denree"), (r"^Stone fruits?", "groupe")],  # never "Cherry tomato"
    "strawberry": [(r"^Strawberr", "denree"), (r"^Low growing berries", "sous-groupe"),
                   (r"^Berries and other small fruits", "groupe")],
    "olive": [(r"^Table olives|^Olives for oil|^Olives?\b", "denree")],
    "wheat": [(r"^Wheat\b", "denree"), (r"^Cereal grains", "groupe")],
    "corn": [(r"^Maize\b|^Sweet corn", "denree"), (r"^Cereal grains", "groupe")],
    "datepalm": [(r"^Dates?\b", "denree")],
    "pomegranate": [(r"^Pomegranate", "denree")],
}
PROCESSED = re.compile(r"juice|paste|dried|pomace|(?<!for )\boil\b|flour|bran|germ|wholemeal|hay|straw|stover|fodder|"
                       r"gluten|shorts|aspirated|flakes|granules|feed|pulp|refined|crude", re.I)
_last = [0.0]


def get(url, path):
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    time.sleep(max(0.0, _last[0] + 1.0 - time.time()))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    _last[0] = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def index():
    """Codex pesticide name -> (codex number, pestId)."""
    h = get(BASE, RAW / "index.html")
    out = {}
    for pid, name in re.findall(r'pesticide-details\?pestId=([0-9a-f-]+)"[^>]*>\s*([^<]+?)\s*</a>', h):
        m = re.match(r"(.*?)\s*\((\d+)\)$", html.unescape(name).strip())
        if m:
            out[m.group(1)] = (m.group(2), pid)
    return out


def mrls(pid):
    h = get(f"{BASE}/pesticide-details?pestId={pid}", RAW / "details" / f"{pid}.html")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) >= 6 and cells[1] != "Commodities":
            v = re.search(r"([\d.]+)\s*mg/kg", cells[2], re.I)
            if v:
                rows.append({"denree": cells[1], "lmr_mg_kg": float(v.group(1)), "annee": cells[3],
                             "symboles": cells[4], "notes": cells[5]})
    return rows


def main():
    idx = index()
    by_key = {}
    for name, (num, pid) in idx.items():
        by_key.setdefault(key(name), (name, num, pid))
    subs = sorted(pd.read_csv(ROOT / "data" / "processed" / "pesticides" / "product_substances.csv")["eu_name"]
                  .dropna().unique())
    out, missing = [], []
    for s in subs:
        hit = next((by_key[k] for k, _ in variants(s) if k in by_key), None)
        if not hit:
            missing.append(s)
            continue
        for r in mrls(hit[2]):
            out.append({"substance": s, "codex_nom": hit[0], "codex_id": hit[1], **r})
    df = pd.DataFrame(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Codex index: {len(idx)} pesticides; Tunisian substances with Codex MRLs: {df['substance'].nunique()}/"
          f"{len(subs)}; {len(df)} MRL rows -> {OUT.relative_to(ROOT)}")

    if not MAPPING.exists():
        names = sorted(df["denree"].unique())
        rows = []
        for crop, rules in CROPS.items():
            seen = set()
            for rx, rule_level in rules:
                for n in names:
                    # the harvest of the farmer, not a processed food or a feed (juice, dried, oil, straw...)
                    if re.search(rx, n) and not PROCESSED.search(n) and n not in seen:
                        seen.add(n)
                        level = "groupe" if "(group)" in n else "sous-groupe" if "(subgroup)" in n else rule_level
                        rows.append({"culture": crop, "denree_codex": n, "niveau": level, "status": "proposed",
                                     "note": ""})
        with open(MAPPING, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["culture", "denree_codex", "niveau", "status", "note"])
            w.writeheader()
            w.writerows(rows)
        print(f"{MAPPING.relative_to(ROOT)}: {len(rows)} rows proposed "
              f"({', '.join(sorted({r['culture'] for r in rows}))})")
    print(f"no Codex MRL ({len(missing)} substances), e.g. {missing[:15]}")


if __name__ == "__main__":
    main()
