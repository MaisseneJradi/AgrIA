"""Is there a newer official list of registered pesticides than the one AgrIA uses? Report what it adds and withdraws,
WITHOUT updating anything (phyto plan, step 7): loading a new list is a decision of the project owner.

Source: the open-data catalogue agridata.tn, dataset "Liste des pesticides homologués en Tunisie"
(https://catalog.agridata.tn/dataset/583ceab9-fba3-481c-bf9d-0d12edcec48d). robots.txt of the site is read and obeyed:
no /api/ (disallowed), one request every CRAWL_DELAY seconds (Crawl-Delay: 10).
Steps: the dataset page -> the PDF links -> the date of each version, read in its file name ("22-mai-2024",
"16-juillet-2025", "13-02-2020") -> if the newest is after treatments.LIST_DATE: download it into
data/raw/pesticides/candidates/ (once), read it with parse_pesticides_tn.py into a temporary folder, compare its products
with data/processed/pesticides/tn_products.csv by registration number (else by trade name + substance).

Usage: python src/preparation/check_dgsvcia_list.py [--offline new.pdf]
Output: reports/phyto/dgsvcia_diff_<date>.csv (changement: ajouté | retiré | modifié, with the fields) and a summary.
Nothing in data/processed, docs/ or the base is changed.
"""
import argparse
import datetime
import re
import sys
import tempfile
import time
import unicodedata
import urllib.request
import urllib.robotparser
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "tools"))
sys.path.insert(0, str(ROOT / "src" / "preparation"))
from treatments import LIST_DATE  # noqa: E402

SITE = "https://catalog.agridata.tn"
DATASET = f"{SITE}/dataset/583ceab9-fba3-481c-bf9d-0d12edcec48d"
UA = "Mozilla/5.0 (compatible; AgrIA-research/1.0; student project)"
CRAWL_DELAY = 10
CANDIDATES = ROOT / "data" / "raw" / "pesticides" / "candidates"
REPORTS = ROOT / "reports" / "phyto"
MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
          "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "jan": 1, "fev": 2, "avr": 4, "juil": 7,
          "sept": 9, "oct": 10, "nov": 11, "dec": 12}
FIELDS = ["nom_commercial", "substance", "conc", "formulation", "type", "statut", "societe", "n_usages"]
_last = [0.0]


def plain(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def date_of(name):
    """'liste-des-produits-pesticides-homologues-16-juillet-2025-vf-1.pdf' -> date(2025, 7, 16); None if not found."""
    n = plain(name)
    m = re.search(r"(\d{1,2})[-_ ]([a-z]+)[-_ ](20\d\d)", n)
    if m and m.group(2) in MONTHS:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    m = re.search(r"(\d{1,2})[-_.](\d{1,2})[-_.](20\d\d)", n)
    return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def polite_get(url, robots):
    if not robots.can_fetch(UA, url):
        raise PermissionError(f"robots.txt forbids {url}")
    time.sleep(max(0.0, _last[0] + CRAWL_DELAY - time.time()))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    _last[0] = time.time()
    return data


def versions(robots):
    page = polite_get(DATASET, robots).decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="(https://catalog\.agridata\.tn/dataset/[^"]+/download/[^"]+\.pdf)"', page)))
    return sorted(((date_of(u.rsplit("/", 1)[1]), u) for u in links if date_of(u.rsplit("/", 1)[1])), reverse=True)


def parse(pdf):
    """Products of a list PDF, read with the parser of the current list, into a temporary folder."""
    import parse_pesticides_tn as P
    with tempfile.TemporaryDirectory() as tmp:
        P.OUT = tmp
        P.main(str(pdf))
        return pd.read_csv(Path(tmp) / "tn_products.csv")


def key(r):
    nh = str(r.get("n_homologation") or "").strip()
    if nh and nh != "nan":
        return "H:" + re.sub(r"\s+", "", nh).upper()
    return "N:" + re.sub(r"[^a-z0-9]", "", plain(r.get("nom_commercial"))) + "|" + re.sub(r"[^a-z0-9]", "",
                                                                                         plain(r.get("substance")))


def diff(old, new):
    o = {key(r): r for r in old.to_dict("records")}
    n = {key(r): r for r in new.to_dict("records")}
    rows = []
    for k in sorted(set(n) - set(o)):
        rows.append({"changement": "ajouté", "cle": k, **{f: n[k].get(f) for f in FIELDS}, "details": ""})
    for k in sorted(set(o) - set(n)):
        rows.append({"changement": "retiré", "cle": k, **{f: o[k].get(f) for f in FIELDS}, "details": ""})
    for k in sorted(set(o) & set(n)):
        changed = [f"{f} : {o[k].get(f)} -> {n[k].get(f)}" for f in FIELDS
                   if str(o[k].get(f)).strip() != str(n[k].get(f)).strip()]
        if changed:
            rows.append({"changement": "modifié", "cle": k, **{f: n[k].get(f) for f in FIELDS},
                         "details": " ; ".join(changed)})
    return pd.DataFrame(rows, columns=["changement", "cle", *FIELDS, "details"])


MIN_SHARE = 0.7  # a new list read with fewer than 70 % of the products in use: the table reader failed on its layout
REG = re.compile(r"(?<![\w/])(?:(?:[A-Z]\s?\.\s?){1,3}\s?\d{1,3}\s?-\s?\d{2}(?:/\d{2})?"
                 r"|\d{1,3}-\d{2}(?:/\d{2})?\s?\.?\s?[A-Z]\.?)(?![\w])")


def reg_key(s):
    """'F.010-11/21', '126-11/21 F.', 'I.A.F.017-16' -> 'F|10-11-21', 'F|126-11-21', 'IAF|17-16' (None if unreadable)."""
    s = str(s).upper()
    letters, nums = "".join(re.findall(r"[A-Z]", s)), [str(int(n)) for n in re.findall(r"\d+", s)]
    return f"{letters}|{'-'.join(nums)}" if letters and len(nums) >= 2 else None


def registrations(pdf):
    """Registration numbers written anywhere in a list PDF, with the page and the line (layout-independent)."""
    import pdfplumber
    out = {}
    with pdfplumber.open(pdf) as doc:
        for i, page in enumerate(doc.pages, 1):
            for line in (page.extract_text() or "").splitlines():
                for m in REG.findall(line):
                    k = reg_key(m)
                    if k:
                        out.setdefault(k, (i, line.strip()[:160]))
    return out


def diff_by_registration(old_pdf, new_pdf):
    """Fallback when the table reader fails: products added / withdrawn by registration number found in the text.
    Measured on the list of 22/05/2024: 91 % of the numbers of the full reading are found this way, so a product
    'withdrawn' here may be a number not read: every row is to check in the PDF (page and line given)."""
    old, new = registrations(old_pdf), registrations(new_pdf)
    rows = [{"changement": "ajouté", "cle": k, "page": new[k][0], "ligne": new[k][1]} for k in sorted(set(new) - set(old))]
    rows += [{"changement": "retiré (à vérifier)", "cle": k, "page": old[k][0], "ligne": old[k][1]}
             for k in sorted(set(old) - set(new))]
    return pd.DataFrame(rows, columns=["changement", "cle", "page", "ligne"]), len(old), len(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", help="compare this PDF instead of looking on agridata.tn")
    a = ap.parse_args()
    current = datetime.datetime.strptime(LIST_DATE, "%d/%m/%Y").date()
    if a.offline:
        newest, pdf = date_of(Path(a.offline).name) or datetime.date.today(), Path(a.offline)
    else:
        robots = urllib.robotparser.RobotFileParser(f"{SITE}/robots.txt")
        robots.read()
        found = versions(robots)
        print("versions on agridata.tn: " + ", ".join(d.strftime("%d/%m/%Y") for d, _ in found))
        if not found or found[0][0] <= current:
            print(f"no list newer than the one in use ({LIST_DATE})")
            return
        newest, url = found[0]
        pdf = CANDIDATES / url.rsplit("/", 1)[1]
        if not pdf.exists():
            CANDIDATES.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(polite_get(url, robots))
    print(f"NEWER LIST: {newest.strftime('%d/%m/%Y')} (in use: {LIST_DATE}) -> {pdf.relative_to(ROOT)}")
    old = pd.read_csv(ROOT / "data" / "processed" / "pesticides" / "tn_products.csv")
    new = parse(pdf)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"dgsvcia_diff_{newest.isoformat()}.csv"
    if len(new) >= MIN_SHARE * len(old):
        d = diff(old, new)
        print(f"{len(old)} products in use, {len(new)} in the new list: {d['changement'].value_counts().to_dict()}")
    else:
        print(f"WARNING: the table reader found {len(new)} products in the new list ({len(old)} in use): its layout "
              f"differs, the full comparison would be false. Comparison by registration numbers in the text instead.")
        current_pdf = ROOT / "data" / "raw" / "pesticides" / "liste-des-produits-homologues-22-mai-2024.pdf"
        d, n_old, n_new = diff_by_registration(current_pdf, pdf)
        print(f"registration numbers: {n_old} in the list in use, {n_new} in the new one: "
              f"{d['changement'].value_counts().to_dict()} (approximate: check each row in the PDF)")
    d.to_csv(out, index=False, encoding="utf-8")
    print(f"{out.relative_to(ROOT)} written. Nothing was updated: to load the new list, the parser, the cleaning and "
          f"the base must be run on purpose, after review.")


if __name__ == "__main__":
    main()
