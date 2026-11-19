"""Recognise crops, diseases, pests, symptoms and organs in a farmer's message (French, Arabic, Tunisian darija,
arabizi, English), with the lexicon data/processed/knowledge/lexique.csv.

  normalize_terms("el tmatem fiha mildiou")
  -> {"langue": "arabizi", "cultures": [{"concept": "tomate", "lien": ["tomato"], ...}],
      "maladies": [{"concept": "mildiou", "lien": ["tomato__late_blight", "potato__late_blight"], ...}],
      "classes_possibles": ["potato__late_blight", "tomato__late_blight"], "a_valider": True, ...}
  crop_code("طماطم") -> "tomato"

Matching: every spelling of a concept (columns fr, ar_msa, ar_tn, arabizi, en, split on "/", "|", "," and
parentheses) is compared on the folded text (lower case, no accents, unified Arabic letters). The longest spelling
wins and a word is used once. French plurals in -s/-x and Arabic prefixes (و ف ب ل ك + ال) are accepted.
`a_valider`: the darija spellings marked a_valider in the lexicon are still to be checked by a Tunisian speaker:
the agent may use them to understand the message, never to write its answer.
"""
import re
from functools import lru_cache

from common import ARABIC_LETTERS, fold, query

GROUP = {"culture": "cultures", "synonymes_fr": "cultures", "maladie": "maladies", "ravageur": "ravageurs",
         "symptome": "symptomes", "organe": "organes", "general": "general"}
COLUMNS = ("fr", "ar_msa", "ar_tn", "arabizi", "en")


def _spellings(cell, french=False):
    """Spellings of one lexicon cell. In French, "chute des fruits / feuilles" means "chute des feuilles": a shorter
    part after "/" replaces the last words of the first part."""
    if not cell:
        return []
    cell = str(cell)
    inside = re.findall(r"\(([^)]*)\)", cell)
    out = []
    for chunk in re.split(r"[|,]", re.sub(r"\([^)]*\)", " ", cell)) + [p for i in inside for p in re.split(r"[|,]", i)]:
        parts = [p.strip() for p in chunk.split("/") if p.strip()]
        if not parts:
            continue
        first = parts[0].split()
        out.append(parts[0])
        for p in parts[1:]:
            n = len(p.split())
            out.append(" ".join(first[:-n] + [p]) if french and len(first) > n else p)
    return out


@lru_cache(maxsize=1)
def _entries():
    """(compiled pattern, length, entry) sorted longest first."""
    out = []
    rows = query("SELECT * FROM lexique")
    crop_concept = {r["lien"]: r["concept"] for r in rows if r["type"] == "culture" and r["lien"]}
    for r in rows:
        if r["type"] not in GROUP or r["lien"] == "all_crops":
            continue
        lien = str(r["lien"]).split() if r["lien"] else []
        names = [(col, s) for col in COLUMNS for s in _spellings(r.get(col), french=col == "fr")]
        concept = crop_concept.get(r["lien"], r["concept"]) if r["type"] == "synonymes_fr" else r["concept"]
        if r["type"] in ("culture", "synonymes_fr"):
            names += [("en", code.replace("_", " ")) for code in lien]
        if r["type"] == "culture":  # the concept itself ("palmier", "olivier") is how farmers name the crop
            names.append(("fr", r["concept"].replace("_", " ")))
        for col, s in names:
            f = fold(s)
            arabic = bool(ARABIC_LETTERS.search(f))
            if len(f) < (2 if arabic else 3):
                continue
            if arabic:
                pat = r"(?<![؀-ۿ])(?:[وفبلك])?(?:ال)?" + re.escape(f) + r"(?![؀-ۿ])"
            else:
                pat = r"(?<![a-z0-9])" + re.escape(f) + r"(?:s|x)?(?![a-z0-9])"
            out.append((re.compile(pat), len(f), {
                "concept": concept, "type": "culture" if r["type"] == "synonymes_fr" else r["type"], "groupe": GROUP[r["type"]], "lien": lien,
                "forme": s, "colonne": col, "a_valider": bool(r["a_valider"]) and col in ("ar_tn", "arabizi")}))
    return sorted(out, key=lambda e: (-e[1], e[2]["colonne"] != "fr"))


def _language(text, matches):
    if ARABIC_LETTERS.search(text):
        return "ar"
    if any(m["colonne"] == "arabizi" for m in matches) or re.search(r"[a-z][3579]|[3579][a-z]", fold(text)):
        return "arabizi"
    return "fr" if text.strip() else None


def normalize_terms(text):
    folded = fold(text)
    used = [False] * len(folded)
    found, seen = [], set()
    for pat, _, entry in _entries():
        for m in pat.finditer(folded):
            if any(used[m.start():m.end()]):
                continue
            used[m.start():m.end()] = [True] * (m.end() - m.start())
            key = (entry["groupe"], entry["concept"])
            if key in seen:
                continue
            seen.add(key)
            found.append(dict(entry, texte=folded[m.start():m.end()].strip()))
    result = {"texte": text, "langue": _language(text, found)}
    for g in ("cultures", "maladies", "ravageurs", "symptomes", "organes", "general"):
        result[g] = [{k: v for k, v in e.items() if k != "groupe"} for e in found if e["groupe"] == g]
    classes = {c for e in found if e["groupe"] != "cultures" for c in e["lien"] if "__" in c or "_deficiency" in c}
    result["classes_possibles"] = sorted(classes)
    result["a_valider"] = any(e["a_valider"] for e in found)
    return result


@lru_cache(maxsize=512)
def crop_code(name):
    """English crop code used by the models and the tables ("tomato", "datepalm"...), or None if unknown."""
    if not name:
        return None
    key = fold(name).replace(" ", "_")
    codes = {r["crop"] for r in query("SELECT DISTINCT crop FROM culture_mapping WHERE crop IS NOT NULL")}
    codes |= {r["crop"] for r in query("SELECT DISTINCT crop FROM kc")}
    if key in codes:
        return key
    for r in query("SELECT culture, crop FROM culture_mapping WHERE crop IS NOT NULL"):
        if fold(r["culture"]) == fold(name):
            return r["crop"]
    crops = normalize_terms(name)["cultures"]
    return crops[0]["lien"][0] if crops and crops[0]["lien"] else None


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(normalize_terms(" ".join(sys.argv[1:])), ensure_ascii=False, indent=1))
