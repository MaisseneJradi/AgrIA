"""docs/moa_groups.csv: active substance of the Tunisian list -> FRAC group (fungicides) or IRAC group (insecticides,
acaricides), from the public lists (phyto plan, step 4). Every row is written with status = proposed: only the rows the
agronomist sets to validated are used by the agents (ranking.py, safety.py).

Sources (downloaded once into data/raw/moa/, one request per second; delete a file to download it again):
  FRAC Code List 2026 (May 2026), https://www.frac.info/media/s1zfrjqa/frac-code-list-2026.pdf
      tables read with pdfplumber: a group starts on the row that names its group; its FRAC code is the first code
      written in that block (the PDF centres it on the block); the common names are the lines of the "(ISO) COMMON NAME"
      cell, "(=mefenoxam)" being an alias. FRAC allows use for education without permission (page 3 of the list).
  IRAC Mode of Action Classification online, https://irac-online.org/mode-of-action/classification-online/
      one HTML element per active ingredient: data-moa-active (name) and its id (group "3-class-a" -> 3A).
Matching to the Tunisian substances (EU names of data/processed/pesticides/product_substances.csv), in this order:
  exact name, alias in brackets (aka, formerly, =), name without the strain, then genus + species for micro-organisms,
  and "copper" for every copper compound (FRAC M01). How each row was matched is kept in the column `correspondance`.

Usage: python src/preparation/build_moa_groups.py
Output: docs/moa_groups.csv (substance, groupe, liste, nom_liste, groupe_libelle, faible_risque, correspondance,
        source, status, note) and the substances with no group on screen.
"""
import csv
import html
import re
import time
import unicodedata
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "moa"
OUT = ROOT / "docs" / "moa_groups.csv"
FRAC_URL = "https://www.frac.info/media/s1zfrjqa/frac-code-list-2026.pdf"
IRAC_URL = "https://irac-online.org/mode-of-action/classification-online/"
FRAC_PDF, IRAC_HTML = RAW / "frac-code-list-2026.pdf", RAW / "irac-classification-online.html"
UA = "Mozilla/5.0 (compatible; AgrIA-research/1.0; student project)"
COLUMNS = ["substance", "groupe", "liste", "nom_liste", "groupe_libelle", "faible_risque", "correspondance", "source",
           "status", "note"]
# groups with a low or unknown resistance risk: repeating them is not a resistance problem (FRAC: M = multi-site,
# BM = biologicals with multiple modes, P = host plant defence inducers, U = unknown; IRAC UN = unknown or uncertain)
LOW_RISK = re.compile(r"^(FRAC (M\d*|BM\d*|P\d*|U\d*|NC)|IRAC (UN\w*|NC))$")


def download(url, path):
    if path.exists():
        return
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        path.write_bytes(r.read())
    time.sleep(1)


def key(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def frac_rows():
    import pdfplumber
    rows, code, label, block = [], None, None, []

    def close():
        for name, alias in block:
            rows.append({"nom_liste": name, "alias": alias, "groupe": f"FRAC {code}" if code else "",
                         "groupe_libelle": label})

    with pdfplumber.open(FRAC_PDF) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if len(r) < 7 or (r[4] or "").startswith("(ISO)"):
                        continue
                    group_name, names, frac = (r[2] or "").strip(), (r[4] or "").strip(), (r[6] or "").strip()
                    if group_name.startswith("formerly"):  # a note written in the group column, not a group
                        group_name = ""
                    if group_name:  # a new group starts: the previous one is complete
                        close()
                        block, code, label = [], None, re.sub(r"\s+", " ", group_name)
                    frac = re.sub(r"^([A-Z]{1,2})\s+(\d)", r"\1\2", frac)  # "M 01", "BM 02" -> "M01", "BM02"
                    if frac and not code and re.fullmatch(r"[A-Z]{0,2}\d{1,3}[A-Z]?|NC", frac.split()[0]):
                        code = frac.split()[0]
                    genus = re.search(r"([A-Z][a-z]+) spp\.", r[3] or "")  # "T. atroviride" -> "Trichoderma atroviride"
                    lines, merged = [x.strip() for x in names.split("\n") if x.strip()], []
                    for x in lines:  # a name cut at its hyphen goes on with the next line
                        if merged and merged[-1].endswith("-") and not x.startswith("("):
                            merged[-1] += x
                        else:
                            merged.append(x)
                    for x in merged:
                        if re.match(r"(strain|isolate|str\.)\b", x, re.I):  # strains of the name above
                            continue
                        if genus:
                            x = re.sub(r"^([A-Z])\.\s*", lambda m: genus.group(1) + " "
                                       if genus.group(1)[0] == m.group(1) else m.group(0), x)
                        alias = re.findall(r"\(=\s*([^)]+)\)", x)
                        name = re.sub(r"\(.*?\)", "", x).strip(" ,;")
                        if alias and not name and block:  # "(=mefenoxam)" on its own line: alias of the name above
                            block[-1] = (block[-1][0], alias[0].strip())
                        elif name and len(name) > 2:
                            block.append((name, alias[0].strip() if alias else ""))
    close()
    return rows


def irac_rows():
    h = IRAC_HTML.read_text(encoding="utf-8", errors="replace")
    out = []
    pat = re.compile(r'id="irac-moa-group-[a-z]+-([^"]*?)-active-[^"]*" data-moa-active="([^"]+)" '
                     r'data-search="([^"]*)"')
    for gid, slug, search in pat.findall(h):
        m = re.match(r"([0-9a-z]+)-class-([a-z])$", gid)
        group = (m.group(1) + m.group(2)).upper() if m else gid.split("-class-")[0].upper()
        name = html.unescape(search).split(f" {slug} ")[0].strip()
        name = re.sub(r"^B\.t\. var\.", "Bacillus thuringiensis subsp.", name)  # "B.t. var. kurstaki"
        label = html.unescape(search).split(f" {slug} ")[-1]
        out.append({"nom_liste": name, "alias": "", "groupe": f"IRAC {group}",
                    "groupe_libelle": re.sub(r"^\S+\s+(\S+\s+)?", "", label).strip()})
    return out


def variants(eu_name):
    """EU name -> keys to try, with how: exact, alias, sans souche, genre espece."""
    out = [(key(eu_name), "exact"), (key(eu_name).rstrip("e"), "exact")]
    for a in re.findall(r"\((?:aka|formerly|=)?\s*([^)]+)\)", eu_name):
        out.append((key(re.sub(r"^(aka|formerly)\s+", "", a.strip())), "alias"))
    base = re.split(r"\s+(?:strain|str\.|\(|/)", eu_name)[0]
    out.append((key(base), "sans souche"))
    out.append((key(re.split(r"\s+(?:strain|str\.|subsp\.|\(|/)", eu_name)[0]), "sans souche"))
    words = re.findall(r"[A-Za-z]+", eu_name)
    if len(words) >= 2 and words[0][0].isupper() and words[1].islower():
        out.append((key(" ".join(words[:2])), "genre espece"))
    return out


def main():
    download(FRAC_URL, FRAC_PDF)
    download(IRAC_URL, IRAC_HTML)
    lists = [dict(r, liste="FRAC") for r in frac_rows() if r["groupe"]] + [dict(r, liste="IRAC") for r in irac_rows()]
    index = {}
    for r in lists:
        name = re.sub(r"\(.*?\)", "", r["nom_liste"]).strip()  # "Pyrethrins (pyrethrum)"
        bare = re.sub(r"(?:\s+|-)(benzoate|hydrochloride|sodium|potassium|al|ammonium)$", "", name, flags=re.I)
        # "hymexazole" (FRAC) = "Hymexazol" (EU): a final e is not a difference
        for k in {key(name), key(r["alias"]), key(bare), key(bare).rstrip("e")} - {""}:
            index.setdefault(k, []).append(r)
        words = re.findall(r"[A-Za-z]+", r["nom_liste"])
        if len(words) >= 2 and words[0][0].isupper():  # micro-organisms: genus + species
            index.setdefault(key(" ".join(words[:2])) + "#gs", []).append(r)

    subs = sorted(pd.read_csv(ROOT / "data" / "processed" / "pesticides" / "product_substances.csv")["eu_name"]
                  .dropna().unique())
    rows, missing = [], []
    for s in subs:
        hits, how = [], ""
        for k, h in variants(s):
            found = index.get(k) or (index.get(k + "#gs") if h == "genre espece" else None)
            if found:
                hits, how = found, h
                break
        if not hits and "copper" in s.lower():
            hits, how = [r for r in lists if r["liste"] == "FRAC" and key(r["nom_liste"]).startswith("copper")], "cuivre"
        if not hits:
            missing.append(s)
            continue
        for r in {(h["groupe"], h["liste"]): h for h in hits}.values():
            rows.append({"substance": s, "groupe": r["groupe"], "liste": r["liste"], "nom_liste": r["nom_liste"],
                         "groupe_libelle": r["groupe_libelle"],
                         "faible_risque": "oui" if LOW_RISK.match(r["groupe"]) else "non", "correspondance": how,
                         "source": "FRAC Code List 2026" if r["liste"] == "FRAC" else "IRAC MoA Classification online "
                                                                                       f"({time.strftime('%Y-%m-%d')})",
                         "status": "proposed",
                         "note": "genre et espèce seulement : vérifier la souche" if how == "genre espece" else ""})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["substance"], r["liste"])))
    print(f"lists: FRAC {sum(r['liste'] == 'FRAC' for r in lists)} names, IRAC {sum(r['liste'] == 'IRAC' for r in lists)}")
    print(f"{OUT.relative_to(ROOT)}: {len(rows)} rows for {len({r['substance'] for r in rows})}/{len(subs)} substances "
          f"(how: {pd.Series([r['correspondance'] for r in rows]).value_counts().to_dict()})")
    print(f"no FRAC / IRAC group ({len(missing)}): {missing}")


if __name__ == "__main__":
    main()
