"""Match the shop products to what AgrIA advises (phyto plan, step 9). Output docs/shop_product_mapping.csv
(shop_product_id, name, kind, target_id, target_label, match_score, verdict, reasons, status = proposed). Only rows the
reviewer validates are used to show a shop link (step 10).

  pesticide  -> product of the official list with the SAME active substance(s) AND the SAME concentration(s)
               (docs/shop_composition.csv vs clean/pesticides_produits.csv). A trade name alone is never enough.
               score 1.0 apparié: every substance and concentration equal (g/kg and % compared x10, 2 % tolerance);
                     0.8 incertain: same, but another formulation written (EC / SC...);
                     0.6 incertain: same substances, a concentration not written in the shop text;
                     below: no row (substances or a concentration differ).
               target_id = product_id of the list (one row per registered product of that composition).
  engrais    -> need of the Agronome (docs/fertiliser_needs.csv, proposed): target_id besoin:<deficiency>[:calcaire];
               score 1.0 when the content reaches the minimum of the need (and, for iron on a calcareous soil, the
               chelate is EDDHA / EDDHSA / HBED), 0.5 incertain when the nutrient is there under the minimum.
  semence    -> official variety catalogue (table varietes, agridata.tn): target_id variete:<espece>|<variete> when a
               variety name of the catalogue (4 letters or more) is in the product name and its species too.
Usage: python src/preparation/match_shop_products.py
"""
import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
COMPO = ROOT / "docs" / "shop_composition.csv"
OUT = ROOT / "docs" / "shop_product_mapping.csv"
NEEDS = ROOT / "docs" / "fertiliser_needs.csv"
CLEAN = ROOT / "data" / "processed" / "clean"
DB = ROOT / "data" / "processed" / "agria.db"
COLUMNS = ["shop_product_id", "name", "kind", "target_id", "target_label", "match_score", "verdict", "reasons",
           "status", "note"]
# proposed needs of the Agronome: minimum content of the shop product (% of the nutrient as the label writes it)
NEEDS_ROWS = [
    ("N_deficiency", "N", 10, "", "engrais azoté ; teneur minimale proposée"),
    ("P_deficiency", "P2O5", 10, "", "engrais phosphaté"),
    ("K_deficiency", "K2O", 10, "", "engrais potassique"),
    ("Ca_deficiency", "CaO", 8, "", "correcteur de calcium"),
    ("Mg_deficiency", "MgO", 5, "", "correcteur de magnésium"),
    ("Fe_deficiency", "Fe", 3, "EDDHA|EDDHSA|HBED", "sol calcaire (pH >= 7,8) : seuls ces chélates restent disponibles"),
    ("Zn_deficiency", "Zn", 3, "", "correcteur de zinc"),
    ("Mn_deficiency", "Mn", 3, "", "correcteur de manganèse"),
    ("B_deficiency", "B", 5, "", "correcteur de bore"),
]


def plain(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def concentrations(text):
    """'200 g/l+12 g/l' -> [(200.0, 'g/l'), (12.0, 'g/l')]; '95% 500 g/L' -> [(95.0, '%'), (500.0, 'g/l')]."""
    out = []
    for v, u in re.findall(r"(\d+(?:[.,]\d+)?)\s*(g\s*/\s*l|g\s*/\s*kg|%)", plain(text)):
        out.append((float(v.replace(",", ".")), re.sub(r"\s+", "", u)))
    return out


def same_conc(a, b):
    """(value, unit) equal, within 2 %, g/kg and % being 10 to 1; g/l and % are never compared (density unknown)."""
    (va, ua), (vb, ub) = a, b
    if ua == ub:
        return abs(va - vb) <= 0.02 * max(va, vb)
    if {ua, ub} == {"g/kg", "%"}:
        x, y = (va, vb * 10) if ua == "g/kg" else (va * 10, vb)
        return abs(x - y) <= 0.02 * max(x, y)
    return False


def registry():
    """product_id -> (name, [(EU substance, (value, unit) or None)], formulation)."""
    subs = pd.read_csv(CLEAN / "substances.csv")
    tn_to_eu = {plain(r.substance_tn).strip(): r.eu_name for r in subs.itertuples() if isinstance(r.eu_name, str)}
    out = {}
    for r in pd.read_csv(CLEAN / "pesticides_produits.csv").itertuples():
        names = [plain(x).strip() for x in re.split(r"\s*[+&]\s*", str(r.substance)) if x.strip()]
        eus = [tn_to_eu.get(n) for n in names]
        if not names or None in eus:
            continue
        conc = concentrations(r.conc)
        conc = conc[-len(eus):] if len(conc) >= len(eus) else conc + [None] * (len(eus) - len(conc))
        out[r.product_id] = (r.nom_commercial, list(zip(eus, conc)), str(r.formulation or ""))
    return out


def shop_substances(text):
    """'Bifenazate 300 g/l + Etoxazole 150 g/l' -> [('Bifenazate', (300.0, 'g/l')), ('Etoxazole', (150.0, 'g/l'))]."""
    out = []
    for part in [p.strip() for p in str(text).split(" + ") if p.strip()]:
        m = re.match(r"(.*?)\s+(\d+(?:\.\d+)?)\s+(g/l|g/kg|%)$", part)
        out.append((m.group(1), (float(m.group(2)), m.group(3))) if m else (part, None))
    return out


SAME_FORM = {"WDG": "WG"}  # water dispersible granules: two codes for one formulation


def similar_names(a, b):
    """Trade names that agree once pack sizes and formulation codes are removed (prefix or difflib >= 0.75)."""
    import difflib
    def k(s):
        s = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:l|cc|ml|g|gr|kg)\b", "", plain(s))
        return re.sub(r"[^a-z]", "", re.sub(r"\b(?:sc|ec|wg|wdg|wp|sl|ew|od|se|cs|fs|sg|sp|gr|zc)\b", "", s))
    x, y = k(a), k(b)
    return min(len(x), len(y)) >= 4 and (x.startswith(y) or y.startswith(x)
                                         or difflib.SequenceMatcher(None, x, y).ratio() >= 0.75)


def match_pesticide(row, reg):
    shop = shop_substances(row["substances"])
    if not shop:
        return []
    names = {s.lower() for s, _ in shop}
    rows = []
    for pid, (pname, comp, form) in reg.items():
        if {s.lower() for s, _ in comp} != names:
            continue
        by = {s.lower(): c for s, c in comp}
        missing = [s for s, c in shop if c is None or by[s.lower()] is None]
        differ = [s for s, c in shop if c is not None and by[s.lower()] is not None and not same_conc(c, by[s.lower()])]
        if differ:
            continue
        reasons = [f"mêmes substances ({', '.join(sorted(names))})"]
        if missing:
            # a concentration not written: kept as uncertain only if the trade names agree too (never alone)
            if not similar_names(row["name"], pname):
                continue
            score, verdict = 0.6, "incertain"
            reasons.append(f"concentration non écrite dans la boutique pour : {', '.join(missing)} ; noms proches")
        else:
            score, verdict = 1.0, "apparié"
            reasons.append("mêmes concentrations")
        f_shop, f_reg = SAME_FORM.get(row["formulation"], row["formulation"]),             [SAME_FORM.get(x, x) for x in re.split(r"[/ ]", form.upper())]
        if f_shop and form and f_shop not in f_reg:
            score, verdict = min(score, 0.8), "incertain"
            reasons.append(f"formulation différente ({f_shop} / {form})")
        rows.append({"target_id": pid, "target_label": f"{pname} ({' + '.join(f'{s} {c[0]:g} {c[1]}' if c else s for s, c in comp)})",
                     "match_score": score, "verdict": verdict, "reasons": " ; ".join(reasons)})
    return rows


def needs():
    if not NEEDS.exists():
        with open(NEEDS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["carence", "nutriment", "teneur_min_pct", "chelates_sol_calcaire",
                                              "source", "status", "note"])
            w.writeheader()
            for c, n, mn, ch, note in NEEDS_ROWS:
                w.writerow({"carence": c, "nutriment": n, "teneur_min_pct": mn, "chelates_sol_calcaire": ch,
                            "source": "proposé par AgrIA (à confirmer : INRAT / CRDA)", "status": "proposed",
                            "note": note})
    with open(NEEDS, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def match_fertiliser(row, need_rows):
    out = []
    for n in need_rows:
        v = row.get(n["nutriment"])
        v = float(v) if v not in ("", None) and not pd.isna(v) else None
        if not v:
            continue
        mn = float(n["teneur_min_pct"])
        reasons = [f"{n['nutriment']} {v:g} % (minimum proposé {mn:g} %)"]
        score, verdict = (1.0, "apparié") if v >= mn else (0.5, "incertain")
        out.append({"target_id": f"besoin:{n['carence']}", "target_label": f"besoin : {n['carence']}",
                    "match_score": score, "verdict": verdict, "reasons": " ; ".join(reasons)})
        if n["chelates_sol_calcaire"]:
            ok = bool(row["chelate"]) and re.fullmatch(n["chelates_sol_calcaire"], row["chelate"]) is not None
            out.append({"target_id": f"besoin:{n['carence']}:calcaire",
                        "target_label": f"besoin : {n['carence']} sur sol calcaire",
                        "match_score": score if ok else 0.3, "verdict": verdict if ok else "non_apparié",
                        "reasons": " ; ".join(reasons + [f"chélate {row['chelate'] or 'non indiqué'}"
                                                         + (" adapté au sol calcaire" if ok else
                                                            " : pas EDDHA, EDDHSA ou HBED")])})
    return out


def varieties():
    with sqlite3.connect(DB) as con:
        rows = con.execute("SELECT espece, variete FROM varietes").fetchall()
    return [(plain(e), plain(v).strip(), e, v) for e, v in rows if v and len(plain(v).strip()) >= 4]


def match_seed(name, cat):
    n = plain(name)
    out = []
    for e, v, espece, variete in cat:
        species_word = e.split()[0] if e else ""
        if re.search(r"(?<![a-z])" + re.escape(v) + r"(?![a-z])", n) and species_word[:5] in n:
            out.append({"target_id": f"variete:{espece}|{variete}", "target_label": f"{espece} {variete}",
                        "match_score": 1.0, "verdict": "apparié",
                        "reasons": f"variété « {variete} » et espèce « {espece} » dans le nom"})
    return out


def main():
    compo = pd.read_csv(COMPO, keep_default_na=False)
    reg, need_rows, cat = registry(), needs(), varieties()
    rows = []
    for r in compo.to_dict("records"):
        kind = r["type_compo"]
        if kind == "pesticide":
            found = match_pesticide(r, reg)
        elif kind == "engrais":
            found = match_fertiliser(r, need_rows)
        elif kind == "semence":
            found = match_seed(r["name"], cat)
        else:
            continue
        if not found:
            found = [{"target_id": "", "target_label": "", "match_score": 0.0, "verdict": "non_apparié",
                      "reasons": "aucune substance lue" if kind == "pesticide" and not r["substances"] else
                      "aucun produit de la liste avec les mêmes substances et concentrations" if kind == "pesticide"
                      else "aucune teneur lue" if kind == "engrais" else "aucune variété du catalogue officiel"}]
        for f in found:
            rows.append({"shop_product_id": r["shop_product_id"], "name": r["name"], "kind": kind, **f,
                         "status": "proposed", "note": ""})
    df = pd.DataFrame(rows, columns=COLUMNS)
    df.to_csv(OUT, index=False, encoding="utf-8")
    best = df.sort_values("match_score", ascending=False).drop_duplicates("shop_product_id")
    print(f"{OUT.relative_to(ROOT)}: {len(df)} rows for {best.shape[0]} products")
    print(pd.crosstab(best["kind"], best["verdict"]).to_string())


if __name__ == "__main__":
    main()
