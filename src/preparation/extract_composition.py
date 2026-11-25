"""Composition of every shop product, read by rules and regular expressions (phyto plan, step 9). No language model is
used. Output: docs/shop_composition.csv, status = proposed (the review validates each row).

  pesticides  active substance(s) found with the vocabulary of the official list (data/processed/clean/substances.csv:
              Tunisian spelling and EU name, with or without the final "e", spaces and hyphens free), each with the
              nearest concentration written within CONC_WINDOW characters ("480 g/L Chlorpyriphos-éthyl",
              "Bifenazate 300 g/l + Etoxazole 150 g/l", "80% Captane"); the formulation (EC, SC, WG...); a registration
              number when one is written.
  fertilisers N, P2O5, K2O, CaO, MgO, SO3, Fe, Zn, Mn, B, Cu, Mo in % (an NPK grade "20-20-20" gives N, P2O5, K2O);
  (and        for agriclic, the composition already read from its technical sheet (clean/engrais_catalogue.csv) comes
  biostim.)   first; the chelating agent (EDDHA, EDDHSA, HBED, EDTA, DTPA, IGSA, lignosulfonate, gluconate); the form
              (liquide | solide); the label doses ("2 à 3 kg/ha", "10 à 20 g par arbre"; agriclic: clean/engrais_usages).
  seeds       nothing to read here (the variety is matched from the name, match_shop_products.py).
Usage: python src/preparation/extract_composition.py
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "data" / "processed" / "shop" / "shop_products.csv"
CLASSES = ROOT / "docs" / "shop_product_classes.csv"
OUT = ROOT / "docs" / "shop_composition.csv"
CLEAN = ROOT / "data" / "processed" / "clean"
NUTRIENTS = ["N", "P2O5", "K2O", "CaO", "MgO", "SO3", "Fe", "Zn", "Mn", "B", "Cu", "Mo"]
NUTRIENT_WORDS = {"N": r"azote(?: total)?|\(n\)|\bn\b", "P2O5": r"p2o5|anhydride phosphorique|phosphore",
                  "K2O": r"k2o|oxyde de potassium|potassium|potasse", "CaO": r"\bcao\b|calcium",
                  "MgO": r"\bmgo\b|magnesium|magnesie", "SO3": r"\bso3\b|soufre|trioxyde de soufre",
                  "Fe": r"\bfer\b|\bfe\b", "Zn": r"\bzinc\b|\bzn\b", "Mn": r"manganese|\bmn\b",
                  "B": r"\bbore\b|\(b\)|\bb\b", "Cu": r"cuivre|\bcu\b", "Mo": r"molybdene|\bmo\b"}
NUM = r"\d+(?:[.,]\d+)?"
CONC = re.compile(rf"({NUM})\s*(g\s*/\s*l(?:itre)?|gr?\s*/\s*l|g\s*/\s*kg|%)(?![a-z])")
CONC_WINDOW = 35
FORMULATIONS = r"SC|EC|WG|WDG|WP|SL|EW|OD|SE|CS|FS|SG|SP|GR|ME|ZC|DC|ULV|EO|DP|VP|WS|TB|CB|RB|SU"
CHELATES = r"eddhsa|eddha|hbed|edta|dtpa|igsa|lignosulfon\w*|heptaglucon\w*|glucon\w*"
DOSE = re.compile(rf"({NUM})(?:\s*(?:-|a|à)\s*({NUM}))?\s*(kg|g|l|ml|cc)\s*(?:/|par|pour)\s*"
                  r"(ha|hectare|hl|100\s*l(?:itres?)?|arbre|pied|plant)", re.I)


def plain(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def substance_patterns():
    """[(regex, EU name)] from the official list's substances, longest names first."""
    s = pd.read_csv(CLEAN / "substances.csv").dropna(subset=["eu_name"])
    names = {}
    for r in s.itertuples():
        for n in (r.substance_tn, r.eu_name):
            n = plain(re.sub(r"\(.*?\)", "", str(n))).strip(" -")
            if len(n) >= 5:
                names.setdefault(n, r.eu_name)
                names.setdefault(n.rstrip("e"), r.eu_name)
    out = []
    for n, eu in sorted(names.items(), key=lambda x: -len(x[0])):
        pat = re.escape(n).replace(r"\-", r"[\s-]?").replace(r"\ ", r"[\s-]?")
        # "chlorpyriphos" / "chlorpyrifos": ph and f written for one another
        pat = pat.replace("ph", "§").replace("f", "(?:f|ph)").replace("§", "(?:ph|f)")
        out.append((re.compile(r"(?<![a-z])" + pat + r"e?s?(?![a-z])"), eu))
    return out


def norm_conc(value, unit):
    unit = re.sub(r"\s+", "", unit).replace("gr", "g").replace("litre", "l")
    return float(value.replace(",", ".")), {"g/l": "g/l", "g/kg": "g/kg", "%": "%"}.get(unit, unit)


def pesticide(text, name, patterns):
    t = plain(text)
    hits, taken = [], []
    for pat, eu in patterns:
        for m in pat.finditer(t):
            if any(a <= m.start() < b for a, b in taken) or any(h[0] == eu for h in hits):
                continue
            taken.append((m.start(), m.end()))
            near = [c for c in CONC.finditer(t) if abs(c.start() - m.end()) <= CONC_WINDOW
                    or abs(m.start() - c.end()) <= CONC_WINDOW]
            conc = min(near, key=lambda c: min(abs(c.start() - m.end()), abs(m.start() - c.end()))) if near else None
            hits.append((eu, norm_conc(conc.group(1), conc.group(2)) if conc else None, m.start()))
    hits.sort(key=lambda h: h[2])
    form = re.search(rf"\b({FORMULATIONS})\b", str(name)) or re.search(rf"\b({FORMULATIONS})\b", str(text))
    reg = re.search(r"homolog\w*\W{0,20}((?:[A-Z]\.\s?){1,3}\d{1,3}-\d{2}(?:/\d{2})?)", str(text))
    return {"substances": " + ".join(f"{eu} {v:g} {u}" if c else eu for eu, c, _ in hits
                                     for v, u in [c or (0, "")]),
            "n_substances": len(hits), "concentrations_lues": sum(c is not None for _, c, _ in hits),
            "formulation": form.group(1) if form else "", "n_homologation": reg.group(1) if reg else ""}


def nutrients(text, name):
    t = plain(f"{name} {text}")
    out = {}
    npk = re.search(r"(?<![\d.,])(\d{1,2})[-.](\d{1,2})[-.](\d{1,2})(?![\d.,%])", t)
    if npk:
        for col, v in zip(("N", "P2O5", "K2O"), npk.groups()):
            if int(v) > 0:
                out[col] = float(v)
    for col, words in NUTRIENT_WORDS.items():
        if col in out:
            continue
        m = re.search(rf"(?:{words})[^%\d]{{0,25}}({NUM})\s*%", t) or re.search(rf"({NUM})\s*%\s*(?:de\s+|d')?(?:{words})", t)
        if m:
            v = float(m.group(1).replace(",", "."))
            if 0 < v <= 70:
                out[col] = v
    return out


def label_doses(text):
    return " | ".join(dict.fromkeys(f"{m.group(1)}{'-' + m.group(2) if m.group(2) else ''} {m.group(3).lower()}/"
                                    f"{re.sub(r'hectare', 'ha', re.sub(r'100 ?l(itres?)?', 'hl', m.group(4).lower()))}"
                                    for m in DOSE.finditer(plain(text))))


def main():
    shop = pd.read_csv(SHOP, keep_default_na=False)
    classes = pd.read_csv(CLASSES, keep_default_na=False)[["shop_product_id", "category_agria"]]
    shop = shop.merge(classes, left_on="id", right_on="shop_product_id")
    cat = pd.read_csv(CLEAN / "engrais_catalogue.csv")
    agriclic = {f"agriclic:{int(r.id_source)}": r for r in cat[cat["source"] == "agriclic"].itertuples()}
    uses = pd.read_csv(CLEAN / "engrais_usages.csv")
    patterns = substance_patterns()
    rows = []
    for r in shop.itertuples():
        text = f"{r.description} {r.technical_sheet}"
        row = {"shop_product_id": r.id, "name": r.name, "category_agria": r.category_agria, "status": "proposed"}
        if r.category_agria == "pesticide":
            row.update(type_compo="pesticide", methode="règles (vocabulaire de la liste officielle)",
                       **pesticide(f"{r.name} {text}", r.name, patterns))
        elif r.category_agria in ("engrais_amendement", "biostimulant"):
            found = nutrients(text, r.name)
            method = "règles"
            if r.id in agriclic:  # composition already read from the technical sheet of agriclic
                sheet = {c: float(getattr(agriclic[r.id], c)) for c in NUTRIENTS
                         if pd.notna(getattr(agriclic[r.id], c, None)) and float(getattr(agriclic[r.id], c)) > 0}
                if sheet:
                    found, method = sheet, "fiche technique agriclic"
            t = plain(f"{r.name} {text}")
            ch = re.search(CHELATES, t)
            form = "liquide" if re.search(r"liquide|\bsl\b|\bl\b|litre|\bcc\b|suspension|solution", plain(r.name) + " "
                                          + t[:400]) else "solide" if re.search(r"poudre|granul|cristal|\bkg\b|\bwsp\b|\bwg\b",
                                                                                  t[:400] + plain(r.name)) else ""
            doses = label_doses(text)
            if r.id.startswith("agriclic:"):
                u = uses[uses["id"] == int(r.id.split(":")[1])].dropna(subset=["dose_min"])
                doses = " | ".join(f"{a:g}{'-' + format(b, 'g') if b != a else ''} {un}/{ba}" for a, b, un, ba in
                                   zip(u["dose_min"], u["dose_max"], u["dose_unite"], u["dose_base"].fillna("?"))) or doses
            row.update(type_compo="engrais", methode=method, **{c: found.get(c, "") for c in NUTRIENTS},
                       chelate=ch.group(0).upper()[:12] if ch else "", forme=form, doses_etiquette=doses)
        else:
            row.update(type_compo=r.category_agria, methode="")
        rows.append(row)
    cols = ["shop_product_id", "name", "category_agria", "type_compo", "substances", "n_substances",
            "concentrations_lues", "formulation", "n_homologation", *NUTRIENTS, "chelate", "forme", "doses_etiquette",
            "methode", "status", "note"]
    df = pd.DataFrame(rows).reindex(columns=cols)
    df.to_csv(OUT, index=False, encoding="utf-8")
    p = df[df["type_compo"] == "pesticide"]
    f = df[df["type_compo"] == "engrais"]
    print(f"{OUT.relative_to(ROOT)}: {len(df)} products")
    print(f"pesticides {len(p)}: substance found {int((p['n_substances'] > 0).sum())}, every concentration read "
          f"{int(((p['n_substances'] > 0) & (p['concentrations_lues'] == p['n_substances'])).sum())}, formulation "
          f"{int((p['formulation'] != '').sum())}, registration number {int((p['n_homologation'] != '').sum())}")
    has = f[NUTRIENTS].replace("", pd.NA).notna().any(axis=1)
    print(f"fertilisers + biostimulants {len(f)}: a nutrient content {int(has.sum())}, chelate "
          f"{int((f['chelate'] != '').sum())}, label dose {int((f['doses_etiquette'] != '').sum())}")


if __name__ == "__main__":
    main()
