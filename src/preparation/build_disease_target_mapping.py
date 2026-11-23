"""Build docs/disease_target_mapping.csv: the 48 disease and pest classes -> target names of the Tunisian list
(phyto plan, step 2), and the coverage report docs/disease_target_coverage.csv.

Rows, one per name (src/tools/target_mapping.py reads them):
  1. existant  the target rules used until now (TARGETS of src/preparation/build_pesticide_refs.py, reviewed on
               22/10/2026), one row per alternative of each rule; status validated: they are what the agents use today.
               The script checks that these rows give back exactly the links of clean/classe_traitements.csv.
  2. lexique / fiche  French and scientific names of the class (knowledge/lexique.csv, fiches.jsonl whose scientific
               names come from Wikidata) that no existing rule covers; status proposed.
  3. registre  spellings of the list close to a name of the class but missed by its rules ('rouillle'); proposed.
groupe: a name shared by several classes ("oidium", "rouille"...): one registered use can serve each of them, on its
own crops only.

Coverage report, per class: products and uses reached with the validated rows (avant) and if every proposed row were
validated (si_valide), the new products, and the products registered against the same names on OTHER crops only
(ailleurs: never advised, given to help the review).

Usage: python src/preparation/build_disease_target_mapping.py
"""
import ast
import csv
import difflib
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "tools"))
sys.path.insert(0, str(ROOT / "src" / "preparation"))
from build_pesticide_refs import TARGETS  # noqa: E402
from target_mapping import COLUMNS, MAPPING, covered_crops, plain, row_matches, usage_classes  # noqa: E402

PEST = ROOT / "data" / "processed" / "pesticides"
KNOW = ROOT / "data" / "processed" / "knowledge"
COVERAGE = ROOT / "docs" / "disease_target_coverage.csv"
EXISTING = "existant : règle TARGETS de build_pesticide_refs.py (revue le 22/10/2026), en service avant l'étape 2"
LATIN = {"phytophthora infestans", "fulvia", "passalora", "tetranychus", "tetranyque", "helicoverpa", "heliothis",
         "xanthomonas", "pseudomonas", "colletotrichum", "botrytis", "corynespora", "bemisia", "venturia",
         "gymnosporangium", "botryosphaeria", "guignardia", "isariopsis", "pseudocercospora", "cycloconium",
         "spilocaea", "venturia oleaginea", "savastanoi", "aculus", "eriophy", "phyllosticta", "elsinoe", "diaphorina",
         "trioza", "parlatoria", "fusarium", "thielaviopsis", "graphiola", "alternaria", "diplodia", "diplocarpon",
         "puccinia", "exserohilum", "cladospori", "septori", "alternari", "cercospor", "helminthospori"}
CROP_WORDS = (r"tomates?|pommes? de terre|pommiers?|vignes?|oliviers?|agrumes|palmiers? dattiers?|palmiers?|bles?|"
              r"mais|grenadiers?|fraisiers?|cerisiers?|pechers?|poivrons?|cucurbitacees|solanacees|tabac")
GENERIC = {"pourriture", "maladie", "maladies", "taches", "tache", "brulure", "virus", "gale", "galle", "chancre",
           "feuilles", "charbon", "noire", "noires", "bacterienne", "foliaires", "insecte", "cochenille", "acarien",
           "mouche", "ver", "fruits"}
CLASS_CROP = {"orange": "citrus"}


def readable(alt):
    return re.sub(r"\s+", " ", alt.replace(".?", " ").replace("?", "").replace("\\b", "")).strip()


def existing_rows():
    rows = []
    for crops, rx, cls, rel, excl in TARGETS:
        for alt in rx.split("|"):
            nom = readable(alt)
            rows.append({"unified_class": cls, "crops": "|".join(crops), "nom": nom,
                         "type_nom": "scientifique" if alt in LATIN or nom in LATIN else "francais", "motif": alt,
                         "exclure": excl or "", "relation": rel, "source": EXISTING, "status": "validated"})
    return rows


def class_names():
    """class -> [(name, type_nom, source)] from the lexicon (French) and the sheets (French and scientific)."""
    out = {}
    lex = pd.read_csv(KNOW / "lexique.csv")
    for r in lex[lex["type"].isin(["maladie", "ravageur"])].itertuples():
        for cls in str(r.lien).split() if isinstance(r.lien, str) else []:
            if isinstance(r.fr, str):
                out.setdefault(cls, []).append((r.fr, "francais", f"lexique ({r.source})"))
    for f in pd.read_json(KNOW / "fiches.jsonl", lines=True).itertuples():
        try:
            classes = ast.literal_eval(f.classes_modele) if isinstance(f.classes_modele, str) else f.classes_modele
        except (ValueError, SyntaxError):
            classes = []
        for cls in classes or []:
            out.setdefault(cls, []).append((f.nom, "francais", f"fiche {f.id}"))
            if isinstance(f.nom_scientifique, str) and f.nom_scientifique.strip():
                out.setdefault(cls, []).append((f.nom_scientifique, "scientifique", f"fiche {f.id} (Wikidata)"))
    return out


def terms(name, kind):
    """'Alternariose (brûlure alternarienne) de la tomate' -> ['alternariose', 'brulure alternarienne']."""
    out = []
    if kind == "scientifique" and "virus" in plain(name):
        return [plain(name).strip()]  # a virus name is not a binomial: no genus
    if kind == "scientifique":
        words = re.sub(r"\b(var|f\.? ?sp|pv)\b.*$", "", plain(name)).split()
        if words:
            out.append(" ".join(words[:2]))
            out.append(words[0])
        return [t for t in dict.fromkeys(out) if len(t) >= 5]
    for part in re.split(r"[/(),;]", plain(name)):
        t = re.sub(rf"\s+(?:de la|du|des|de l'|de l|de|sur)\s+(?:{CROP_WORDS})\b.*$", "", part.strip())
        t = re.sub(r"^(?:la|le|les|l')\s*", "", t).strip(" .-'")
        # a piece left by the brackets that only names the crop ('des agrumes', "de l'olivier") is not a name
        if re.match(r"(?:de la|du|des|de l'|de l|de|sur)\b", t):
            continue
        if len(t) >= 4 and not (" " not in t and t in GENERIC):
            out.append(t)
    return list(dict.fromkeys(out))


def proposals(usages, existing):
    by_class = {}
    for r in existing:
        by_class.setdefault(r["unified_class"], []).append(r)
    names = class_names()
    rows = []
    for cls, rules in by_class.items():
        crops = rules[0]["crops"]
        alts = [r["motif"] for r in rules]
        seen = set()
        # 1. names of the lexicon and of the sheets not covered by a rule
        for name, kind, source in names.get(cls, []):
            for t in terms(name, kind):
                if t in seen or any(re.search(a, t) for a in alts):
                    continue
                seen.add(t)
                rows.append({"unified_class": cls, "crops": crops, "nom": t,
                             "type_nom": kind if " " in t or kind == "francais" else "scientifique (genre)",
                             "motif": re.escape(t), "exclure": rules[0]["exclure"], "relation": rules[0]["relation"],
                             "source": source, "status": "proposed",
                             "note": "genre seul : peut viser une autre espèce" if kind == "scientifique"
                             and " " not in t else ""})
        # 2. spellings of the list close to a name of the class, missed by every rule
        words = {w for a in alts + [r["nom"] for r in rows if r["unified_class"] == cls]
                 for w in re.findall(r"[a-z]{5,}", readable(a))}
        targets = {plain(u.cible) for u in usages.itertuples() if isinstance(u.crop, str)
                   and covered_crops(u.crop) & set(crops.split("|"))}
        tokens = {tok for t in targets for tok in re.findall(r"[a-z]{5,}", t)}
        for tok in sorted(tokens):
            if any(re.search(a, tok) for a in alts) or tok in seen:
                continue
            # same first letter and ratio >= 0.85: 'rouillle' and 'phytophtora' yes, 'bouillie' (~ rouille) no
            close = [w for w in words if w != tok and w not in tok and tok not in w and w[0] == tok[0]
                     and difflib.SequenceMatcher(None, w, tok).ratio() >= 0.85]
            if close:
                seen.add(tok)
                rows.append({"unified_class": cls, "crops": crops, "nom": tok, "type_nom": "graphie de la liste",
                             "motif": re.escape(tok), "exclure": rules[0]["exclure"],
                             "relation": rules[0]["relation"], "source": "registre DGSVCIA 22/05/2024",
                             "status": "proposed", "note": f"graphie proche de « {close[0]} »"})
    return rows


def count(rows, usages):
    for r in rows:
        hit = [u for u in usages.itertuples() if isinstance(u.crop, str) and row_matches(r, u.crop, u.cible)]
        r["n_usages"] = len(hit)
        r["n_produits"] = len({u.product_id for u in hit})
        r["exemples_cibles"] = " | ".join(list(dict.fromkeys(plain(u.cible) for u in hit))[:3])
    noms = {}
    for r in rows:
        noms.setdefault(r["nom"], set()).add(r["unified_class"])
    for r in rows:
        r["groupe"] = r["nom"] if len(noms[r["nom"]]) > 1 else ""
    return rows


def elsewhere(cls, rules, usages):
    """Products registered against a name of the class on crops the class does not cover."""
    crops = set(rules[0]["crops"].split("|"))
    out = set()
    for u in usages.itertuples():
        if not isinstance(u.crop, str) or covered_crops(u.crop) & crops:
            continue
        t = plain(u.cible)
        if any(re.search(r["motif"], t) and not (r["exclure"] and re.search(r["exclure"], t)) for r in rules):
            out.add(f"{u.nom_commercial} ({u.culture} : {u.cible})")
    return sorted(out)


def main():
    usages = pd.read_csv(PEST / "tn_usages.csv")
    existing = existing_rows()
    rows = count(existing + proposals(usages, existing), usages)
    rows.sort(key=lambda r: (r["unified_class"], r["status"] != "validated", r["type_nom"], r["nom"]))
    with open(MAPPING, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})

    # the validated rows must give back the links used until now
    old = pd.read_csv(ROOT / "data" / "processed" / "clean" / "classe_traitements.csv")
    new = usage_classes(usages, [r for r in rows if r["status"] == "validated"])
    key = ["unified_class", "relation", "product_id", "usage_idx"]
    a, b = set(map(tuple, old[key].values)), set(map(tuple, new[key].values))
    print(f"{MAPPING.relative_to(ROOT)}: {len(rows)} rows ({sum(r['status'] == 'validated' for r in rows)} validated, "
          f"{sum(r['status'] == 'proposed' for r in rows)} proposed); validated rows = classe_traitements: "
          f"{a == b} (missing {len(a - b)}, extra {len(b - a)})")

    every = usage_classes(usages, rows)
    classes = sorted({r["unified_class"] for r in rows})
    report = []
    for cls in classes:
        before, after = new[new["unified_class"] == cls], every[every["unified_class"] == cls]
        added = sorted(set(after["nom_commercial"]) - set(before["nom_commercial"]))
        other = elsewhere(cls, [r for r in rows if r["unified_class"] == cls], usages)
        report.append({"unified_class": cls, "produits_avant": before["product_id"].nunique(),
                       "usages_avant": len(before), "produits_si_valide": after["product_id"].nunique(),
                       "usages_si_valide": len(after), "nouveaux_produits": " | ".join(added),
                       "n_ailleurs": len(other), "ailleurs_exemples": " | ".join(other[:4])})
    pd.DataFrame(report).to_csv(COVERAGE, index=False, encoding="utf-8")
    rep = pd.DataFrame(report)
    print(f"{COVERAGE.relative_to(ROOT)}: classes with a product {int((rep['produits_avant'] > 0).sum())}/{len(rep)} "
          f"-> {int((rep['produits_si_valide'] > 0).sum())}/{len(rep)} if every proposed row is validated; "
          f"uses {rep['usages_avant'].sum()} -> {rep['usages_si_valide'].sum()}")
    return a == b


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(0 if main() else 1)
