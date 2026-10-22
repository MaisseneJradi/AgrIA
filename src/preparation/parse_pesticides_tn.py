"""Parse the official Tunisian list of registered pesticides (DGSVCIA, version of 22 May 2024, 122 pages) into CSV.

The PDF is a ruled table: N°, SUBSTANCE ACTIVE, CONC., T.F., P.COMM, N°.H., SOCIETE, FABRICANT, USAGE. Cells wrap on
several lines and rows run over page breaks, so the table extractor of pdfplumber splits them; instead:
  - the column edges are read on each page from the header words (cell edge = header x - 4);
  - a row is the band between two horizontal rulings that cross the N° column; a band with a number starts a product,
    a band without one (top of a page) continues the previous product;
  - sections come from the headings (I. INSECTICIDES, II. FONGICIDES...; pages 1-3 = restricted substances);
  - green text marks the products added on 22/05/2024.
USAGE is free text, mostly "Culture : Cible : dose" then lines such as "DAR 14 jours", "LMR ...", "Volume de bouillie",
"AUTORISATION PROVISOIRE DE VENTE", "(COMM 22/02/2024)" or "Restriction d'usage...". Each "x : y : z" line starts a new
usage; other lines extend the current one, except DAR/LMR, which are kept per usage (or for the whole product when they
come before the first usage).

Usage: python src/preparation/parse_pesticides_tn.py [pdf]
Output: data/processed/pesticides/tn_products.csv (one row per product)
        data/processed/pesticides/tn_usages.csv   (one row per product x crop x target)
"""
import os
import re
import sys

import pandas as pd
import pdfplumber

PDF = os.path.join("data", "raw", "pesticides", "liste-des-produits-homologues-22-mai-2024.pdf")
OUT = os.path.join("data", "processed", "pesticides")
COLS = ["num", "substance", "conc", "formulation", "nom_commercial", "n_homologation", "societe", "fabricant", "usage"]
HEADER = {"N°": "num", "SUBSTANCE": "substance", "CONC.": "conc", "T.F.": "formulation", "P.COMM": "nom_commercial",
          "N°.H.": "n_homologation", "SOCIETE": "societe", "FABRICANT": "fabricant", "USAGE": "usage"}
GREEN = (0.0, 0.69, 0.314)
SECTIONS = [  # (regex on a heading line, section, type)
    (r"^1\.\s*INSECTICIDES$", "restriction_campagnes_nationales", "Insecticide"),
    (r"^2\.\s*INSECTICIDES HOMOLOGUES STRICTEMENT", "strictement_reglemente", "Insecticide"),
    (r"^3\.\s*FONGICIDES$", "restriction_campagnes_nationales", "Fongicide"),
    (r"^4\.\s*FONGICIDES HOMOLOGUES STRICTEMENT", "strictement_reglemente", "Fongicide"),
    (r"^I\.\s*INSECTICIDES$", "homologue", "Insecticide"),
    (r"^II\.\s*FONGICIDES$", "homologue", "Fongicide"),
    (r"^III\.\s*HERBICIDES$", "homologue", "Herbicide"),
    (r"^IV\.\s*DIVERS$", "homologue", "Divers"),
    (r"^V\.\s*NEMATICIDES$", "homologue", "Nematicide"),
    (r"^VI\.\s*RATICIDES$", "homologue", "Raticide"),
]
FOOTER = re.compile(r"(L.usage des produits retir|Liste des produits pesticides homologu|Direction G[ée]n[ée]rale|"
                    r"T[ée]l\s*:|ـــ|MINISTERE DE L|DES RESSOURCES HYDRAULIQUES|Et DE LA PECHE)")


def despace(s):
    """'4 0 0 g / L' -> '400g/L': runs of 3+ one-character tokens come from letter-spaced cells."""
    return re.sub(r"(?<!\S)(?:\S ){2,}\S(?!\S)", lambda m: m.group(0).replace(" ", ""), s).strip()


def lines_of(words, tol=2.5):
    """Group words into text lines by their top coordinate."""
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(out[-1][0]["top"] - w["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in out]


def page_events(page, pno):
    """Yield, top to bottom, ('section', idx), ('header', edges) and ('band', {col: [lines]}, green) events."""
    words = page.extract_words(extra_attrs=["non_stroking_color"])
    lines = lines_of(words)
    events, headers = [], []
    for l in lines:
        text = " ".join(w["text"] for w in l)
        for i, (rx, _, _) in enumerate(SECTIONS):
            if re.match(rx, text) and (pno <= 3) == (i < 4):
                events.append((l[0]["top"], "section", i))
        if "SUBSTANCE" in text and "USAGE" in text:
            edges = {HEADER[w["text"]]: w["x0"] - 4 for w in l if w["text"] in HEADER}
            headers.append((l[0]["top"], l[0]["bottom"], edges))
            events.append((l[0]["top"], "header", edges))
    if not headers:
        return sorted(events, key=lambda e: e[0])
    footer_top = min([l[0]["top"] for l in lines if FOOTER.search(" ".join(w["text"] for w in l))
                      and l[0]["top"] > headers[0][0]] + [page.height])
    for hi, (htop, hbottom, edges) in enumerate(headers):
        end = headers[hi + 1][0] if hi + 1 < len(headers) else footer_top
        # the section headings between two tables also end the table above
        end = min([e[0] for e in events if e[1] == "section" and htop < e[0] < end] + [end])
        order = sorted(edges, key=edges.get)
        left_num, right_num = edges["num"], edges[order[order.index("num") + 1]]
        rules = sorted({round(e["top"]) for e in page.horizontal_edges
                        if e["x0"] <= left_num + 3 and e["x1"] >= right_num - 3 and hbottom + 1 < e["top"] < end + 2})
        cuts = [hbottom + 1] + [r for r in rules if r > hbottom + 1] + [end]
        mine = [w for w in words if hbottom + 1 < w["top"] < end]
        for a, b in zip(cuts, cuts[1:]):
            band = [w for w in mine if a - 1 <= w["top"] < b - 1]
            if not band:
                continue
            cells = {c: [] for c in COLS}
            for l in lines_of(band):
                per = {}
                for w in l:
                    col = max((c for c in edges if edges[c] <= w["x0"] + 1), key=edges.get, default="num")
                    per.setdefault(col, []).append(w["text"])
                for c, t in per.items():
                    cells[c].append(despace(" ".join(t)))
            green = sum(w["non_stroking_color"] == GREEN for w in band) > len(band) / 2
            events.append((a, "band", (cells, green)))
    return sorted(events, key=lambda e: (e[0], e[1] != "section"))


def read_pdf(path):
    products, cur, sec = [], None, None
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            for _, kind, val in page_events(page, pno):
                if kind == "section":
                    sec, cur = val, None
                elif kind == "band" and sec is not None:
                    cells, green = val
                    num = " ".join(cells["num"])
                    if re.fullmatch(r"\d{1,3}", num):
                        cur = {"section_idx": sec, "page": pno, "nouveau_22_05_2024": green,
                               **{c: list(cells[c]) for c in COLS}}
                        products.append(cur)
                    elif cur is not None:
                        for c in COLS[1:]:
                            cur[c] += cells[c]
    return products


DAR = re.compile(r"(?<![A-Za-z])(?:DAR|D\.A\.R|d[ée]lai avant r[ée]colte)(?![A-Za-z])\s*[:=]?\s*([^;]*)", re.I)
LMR = re.compile(r"(?<![A-Za-z])LMR(?![A-Za-z])", re.I)
# lines that never start or continue a "culture : cible : dose" text: they go to the remarks of the current usage
FLAG = re.compile(r"^\W*(AUTORISATION PROVISOIRE|Restriction d.usage|\(?\s*COMM|Volume de bouillie|Nbre|Nombre|"
                  r"calendrier|DAR|D\.A\.R|LMR|intervalle|Appliquer|Application|Stade|SOIT|-)", re.I)
NUM = r"\d+(?:[.,]\d+)?"
DOSE = re.compile(rf"{NUM}(?:\s*(?:à|-|a)\s*{NUM})?\s*(?:cc|ml|cl|l|litres?|g|gr|kg|t|comprim[ée]s?|plaquettes?|"
                  rf"diffuseurs?|pi[èe]ges?|sachets?|boulettes?|%)\b\.?(?:\s*(?:PC|de produit|p\.c\.?))?"
                  rf"(?:\s*(?:/|par|pour)\s*(?:{NUM}\s*)?[\w².]+)?", re.I)
CROP_START = re.compile(r"^([^:\d]{2,80}?)\s*:\s*(.*)$")
# "X :" lines whose X is an instruction, not a crop
NOT_CROP = re.compile(r"(mode|p[ée]riode|dur[ée]e|effet|trait|applic|cadence|interval|bouillie|dose|stade|date|calendrier|"
                      r"nombre|nbre|max|volume|d[ée]lai|remarque|NB|recommand|pr[ée]cauti|condition|utilis|moment|"
                      r"m[ée]thode|fr[ée]quence|renouvel|\bles\b|\bla\b|\bpour\b)", re.I)


def dar_days(text):
    m = DAR.search(text or "")
    m = re.search(r"(\d+)\s*(?:jours?|j)\b", m.group(1) if m else "", re.I)
    return int(m.group(1)) if m else None


def parse_usage(text):
    """'Tomate : Acariens : 60 cc/hl ...' -> culture, cible, dose, rest. Dose = first quantity with a unit."""
    culture, rest = [s.strip() for s in text.split(":", 1)]
    m = DOSE.search(rest)
    if not m:
        return culture, rest.strip(" :;"), "", ""
    cible = re.sub(r"(à la dose de|dose|soit)\s*$", "", rest[:m.start()].strip(" :;,"), flags=re.I).strip(" :;,")
    tail = rest[m.end():]
    extra = re.match(r"\s*(\([^)]*\)|soit\s+[^;]*)", tail, re.I)  # "(150 g/ha)" or "soit 2 kg/ha"
    dose = m.group(0) + (extra.group(0) if extra else "")
    return culture, cible, dose.strip(), tail[len(extra.group(0)) if extra else 0:].strip(" ;,.")


def split_usages(lines):
    """Usage lines of one product -> list of dicts (culture, cible, dose, remarques, text) + product notes.
    A line 'X : ...' starts a new usage when X has no digit and the current usage already has a dose."""
    uses, notes = [], []
    for line in (l.strip() for l in lines):
        if not line:
            continue
        m = CROP_START.match(line)
        m = m if m and not NOT_CROP.search(m.group(1)) else None
        if FLAG.match(line):
            (uses[-1]["remarques"] if uses else notes).append(line)
        elif m and (not uses or (DOSE.search(uses[-1]["text"]) and not DOSE.match(m.group(2)))):
            uses.append({"text": line, "remarques": []})
        elif uses and not uses[-1]["remarques"]:
            uses[-1]["text"] += " " + line
        elif uses:
            uses[-1]["remarques"].append(line)
        else:
            notes.append(line)
    out = []
    for u in uses:
        culture, cible, dose, rest = parse_usage(u["text"])
        out.append({"culture": culture, "cible": cible, "dose": dose,
                    "remarques": " ".join(([rest] if rest else []) + u["remarques"])})
    return out, notes


def split_cultures(text):
    """'Tomate, Piment (sous serre)' -> ['Tomate', 'Piment (sous serre)']: split outside parentheses only."""
    text = re.sub(r"\bs\s*/\s*s(?:erres?)?\b", "sous serre", text, flags=re.I)  # 'Tomate s/serre', 's/s chauffées'
    text = re.sub(r"\s+et\s+", "|", text)  # ' et ' separates crops, except inside parentheses
    parts, depth, cur = [], 0, ""
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if ch in ",;/|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += " et " if ch == "|" else ch
    parts.append(cur)
    return [p.strip(" .-") for p in parts if p.strip(" .-")]


def main(path):
    os.makedirs(OUT, exist_ok=True)
    prods = read_pdf(path)
    prod_rows, use_rows = [], []
    for p in prods:
        _, statut, typ = SECTIONS[p["section_idx"]]
        j = {c: " ".join(p[c]).strip() for c in COLS}
        pid = f"{statut[:4]}-{typ[:3].lower()}-{int(j['num']):03d}"
        uses, notes = split_usages(p["usage"])
        whole = " ".join(p["usage"])
        restriction = " ".join(re.findall(r"Restriction d.usage[^)]*\)?[^)]*\)?", whole, re.I)) or (
            "" if statut == "homologue" else statut)
        apv = bool(re.search(r"AUTORISATION PROVISOIRE", whole, re.I))
        # DAR given once for the product (before the first usage, or a single DAR for the whole product)
        dars = [m.group(0) for m in DAR.finditer(whole)]
        dar_prod = dars[0] if len(set(dars)) == 1 else (" ".join(n for n in notes if DAR.search(n)) or "")
        prod_rows.append({"product_id": pid, "statut": statut, "type": typ, **{c: j[c] for c in COLS if c != "usage"},
                          "nouveau_22_05_2024": p["nouveau_22_05_2024"], "autorisation_provisoire": apv,
                          "restriction": restriction, "dar_produit": " ".join(dars), "notes": " ".join(notes),
                          "usage_brut": " | ".join(p["usage"]), "n_usages": len(uses), "page": p["page"]})
        for k, u in enumerate(uses):
            dar_text = (DAR.search(u["remarques"]) or DAR.search(u["dose"]) or DAR.search(dar_prod) or [""])[0]
            lmr = " ".join(s for s in re.split(r"(?<=[;.])\s+", u["remarques"]) if LMR.search(s))
            for cult in split_cultures(u["culture"]):
                use_rows.append({"product_id": pid, "usage_idx": k, "nom_commercial": j["nom_commercial"],
                                 "substance": j["substance"], "conc": j["conc"], "formulation": j["formulation"],
                                 "type": typ, "statut": statut, "culture": cult, "culture_brut": u["culture"],
                                 "cible": u["cible"], "dose": u["dose"], "dar_jours": dar_days(dar_text),
                                 "dar_texte": dar_text.strip(), "lmr": lmr, "remarques": u["remarques"],
                                 "nouveau_22_05_2024": p["nouveau_22_05_2024"], "autorisation_provisoire": apv,
                                 "restriction": restriction, "page": p["page"]})
    prod, use = pd.DataFrame(prod_rows), pd.DataFrame(use_rows)
    use["dar_jours"] = use["dar_jours"].astype("Int64")
    prod.to_csv(os.path.join(OUT, "tn_products.csv"), index=False, encoding="utf-8")
    use.to_csv(os.path.join(OUT, "tn_usages.csv"), index=False, encoding="utf-8")
    print(prod.groupby(["statut", "type"]).size().to_string())
    print(f"\n{len(prod)} products ({int(prod['nouveau_22_05_2024'].sum())} new, "
          f"{int(prod['autorisation_provisoire'].sum())} provisional), {len(use)} usage rows "
          f"(product x crop x target), {int((prod['n_usages'] == 0).sum())} products without a parsed usage, "
          f"DAR known on {use['dar_jours'].notna().mean():.0%} of the usage rows")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else PDF)
