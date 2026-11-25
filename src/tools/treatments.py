"""Registered treatments (Tunisian list of 22/05/2024) for an image class, optionally on one crop.

  get_treatments("tomato__late_blight", "tomate") -> list of usages, best link first
  get_treatments("tomato__healthy") -> []             nothing to treat
  get_treatments("tomato__mosaic_virus") -> []        no registered product: an empty list is an answer, not an error

Each usage: produit, product_id, type, substances, culture, cible, dose, unite, dar_jours (None when the list gives
no DAR and no validated completion of docs/phi_completions.csv does) and dar_message ("DAR non indiqué : vérifiez
l'étiquette" when unknown), dar_source (liste | complement), dar_texte ("non requis", "4 heures"), lmr (EU maximum residue limits of its substances on the crop), relation and its meaning,
restriction, autorisation_provisoire, statut, bio_ue, n_homologation, ue_approuve (every substance approved in the
EU: True / False, None when unknown; used for an export market).
Order: relation direct, then vecteur, groupe, proche (see RELATIONS), then products with a known DAR.
With a crop, only the usages registered for that crop (or for a group that contains it) are kept: a product is never
advised on a crop it is not registered for. A product whose trade name was misread in the list ("50", "SC") is never
returned (UNREADABLE).
"""
import csv
import re
from functools import lru_cache

from common import ROOT, query
from lexicon import crop_code

RELATIONS = {
    "direct": "homologué contre cette maladie ou ce ravageur, sur cette culture",
    "vecteur": "vise l'insecte qui transmet le virus, pas le virus lui-même (aucun produit ne guérit une plante virosée)",
    "groupe": "homologué pour un groupe de cultures qui contient cette culture (par exemple « arboriculture »)",
    "proche": "cible proche (mêmes symptômes, autre agent) : seulement après confirmation du diagnostic",
}
ORDER = {r: i for i, r in enumerate(RELATIONS)}
NO_DAR = "DAR non indiqué : vérifiez l'étiquette"
# the version of the official list loaded in the base (data/raw/pesticides/); written in every answer that speaks of
# registered products. A newer version is reported by src/preparation/check_dgsvcia_list.py, never loaded alone.
LIST_DATE = "22/05/2024"
LIST_URL = ("https://catalog.agridata.tn/dataset/583ceab9-fba3-481c-bf9d-0d12edcec48d/resource/"
            "6978f782-eb4a-491c-bab3-1d16ac72af2f/download/liste-des-produits-homologues-22-mai-2024.pdf")
COMPLETIONS = ROOT / "docs" / "phi_completions.csv"
GROUPS = {"vegetables": ["tomato", "pepper", "potato", "squash", "cucumber", "melon", "eggplant"],
          "cucurbits": ["squash", "cucumber", "melon", "watermelon"],
          "fruit_trees": ["apple", "pear", "peach", "cherry", "apricot", "plum", "almond"],
          "cereals": ["wheat", "barley", "oat"]}


# trade names misread in the PDF of the list ("50", "y", "DP", "SC"...): a farmer cannot ask a shop for them, so their
# uses are never advised (listed for the regulatory data review, phyto plan step 7)
UNREADABLE = re.compile(r"^\s*(?:\d+|[A-Za-z]{1,2}|SC|EC|WG|WP|DP|SL|EW|OD|SE|CS|FS|WDG|SG|SP|GR|ME|UL|DC)\s*$")


def readable_name(name):
    return bool(name) and str(name) != "nan" and not UNREADABLE.match(str(name))


def _crops_of_culture():
    """culture as written in the list -> set of crop codes it covers (groups expanded)."""
    out = {}
    for r in query("SELECT culture, crop FROM culture_mapping WHERE crop IS NOT NULL"):
        out[r["culture"]] = {c for name in r["crop"].split("|") for c in GROUPS.get(name, [name])}
    return out


def _unit(dose):
    m = re.search(r"(cc|ml|l|g|kg|mg)\s*/\s*(hl|ha|l|qt|q|m2|m²|arbre|pied|plant)", str(dose or "").lower())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _lmr(product_id, usage_idx):
    rows = query("SELECT eu_name, product_fr, mrl_mg_kg, at_lod FROM usage_lmr WHERE product_id = ? AND usage_idx = ?",
                 (product_id, usage_idx))
    seen, out = set(), []
    for r in rows:
        key = (r["eu_name"], r["product_fr"])
        if key not in seen and r["mrl_mg_kg"] is not None:
            seen.add(key)
            out.append({"substance": r["eu_name"], "denree": r["product_fr"], "lmr_ue_mg_kg": r["mrl_mg_kg"],
                        "limite_de_detection": bool(r["at_lod"])})
    return out


def _text(v):
    return None if v is None or str(v) in ("nan", "") else str(v)


@lru_cache(maxsize=1)
def _eu_status():
    out = {}
    for r in query("SELECT eu_name, eu_status FROM substances WHERE eu_name IS NOT NULL"):
        out.setdefault(r["eu_name"].strip().lower(), set()).add(r["eu_status"])
    return out


def eu_approved(substances):
    """'Cymoxanil + Copper oxychloride' -> True when every substance is approved in the EU, False when one is not
    (or only pending), None when a substance is not found in the EU database (unknown: never taken as approved)."""
    names = [s.strip().lower() for s in str(substances or "").split("+") if s.strip() and s.strip() != "nan"]
    if not names:
        return None
    status = _eu_status()
    if any(n not in status for n in names):
        return None
    return all("Approved" in status[n] for n in names)


@lru_cache(maxsize=1)
def _crop_cell():
    """culture as written in the list -> its crop cell ("tomato", "fruit_trees|grape") of docs/culture_mapping.csv."""
    return {r["culture"]: r["crop"] for r in query("SELECT culture, crop FROM culture_mapping WHERE crop IS NOT NULL")}


@lru_cache(maxsize=1)
def _completions():
    """(product_id, crop cell or *) -> validated DAR completion of docs/phi_completions.csv (phi_report.py)."""
    if not COMPLETIONS.exists():
        return {}
    with open(COMPLETIONS, encoding="utf-8") as f:
        return {(r["product_id"], r["culture"]): r for r in csv.DictReader(f) if r.get("status") == "validated"}


def completion(product_id, culture):
    c = _completions()
    return c.get((product_id, _crop_cell().get(culture, ""))) or c.get((product_id, "*"))


def get_treatments(unified_class, crop=None):
    if unified_class.endswith("__healthy") or unified_class == "healthy":
        return []
    rows = [r for r in query("SELECT * FROM traitements WHERE unified_class = ?", (unified_class,))
            if readable_name(r["nom_commercial"])]
    if crop is not None:
        code = crop_code(crop)
        if code is None:
            raise ValueError(f"culture inconnue : {crop!r}")
        covers = _crops_of_culture()
        rows = [r for r in rows if code in covers.get(r["culture"], set())]
    out = []
    for r in rows:
        dar = r["dar_jours"]
        dar = int(dar) if dar is not None and str(dar) != "nan" else None
        source, dar_text = ("liste", None) if dar is not None else (None, None)
        comp = completion(r["product_id"], r["culture"]) if dar is None else None
        if comp:  # a DAR missing from the use, completed from a validated source (never estimated)
            dar, source, dar_text = int(comp["phi_days"]), "complement", comp["phi_texte"] or None
        restriction = "; ".join(x for x in (_text(r["restriction_usage"]), _text(r["restriction_produit"])) if x)
        out.append({
            "produit": r["nom_commercial"], "product_id": r["product_id"], "usage_idx": int(r["usage_idx"]),
            "type": r["type"], "substances": r["substances_ue"], "culture": r["culture"], "cible": r["cible"],
            "dose": r["dose"], "unite": _unit(r["dose"]),
            "dar_jours": dar, "dar_message": (dar_text or f"{dar} jours") if dar is not None else NO_DAR,
            "dar_source": source, "dar_texte": dar_text,
            "dar_source_detail": comp["source"] if comp else None,
            "lmr": _lmr(r["product_id"], r["usage_idx"]),
            "lmr_tn_texte": _text(r["remarques_lmr"]),  # what the official list writes on MRLs for this use
            "relation": r["relation"], "relation_sens": RELATIONS.get(r["relation"]),
            "restriction": restriction or None, "autorisation_provisoire": bool(r["autorisation_provisoire"]),
            "statut": r["statut"], "bio_ue": bool(r["bio_ue"]), "n_homologation": _text(r["n_homologation"]),
            "ue_approuve": eu_approved(r["substances_ue"]),
        })
    return sorted(out, key=lambda u: (ORDER.get(u["relation"], 9), u["dar_jours"] is None, u["produit"]))


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(get_treatments(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), ensure_ascii=False,
                     indent=1))
