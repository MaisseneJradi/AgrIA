"""Classify every shop product (phyto plan, step 8) and list the products that claim a plant-protection effect without a
match in the official list.

Input: data/processed/shop/shop_products.csv (build_shop_products.py).
Output: docs/shop_product_classes.csv  one row per product: category_agria (pesticide | engrais_amendement |
                                        biostimulant | semence | equipement | autre), the evidence, the product of the
                                        official list found by trade name (when any), status = proposed
        docs/shop_unapproved_claims.csv products whose name, description or technical sheet claims to protect against
                                        or cure a disease or a pest, with NO trade-name match in the official list:
                                        never to be advised as a treatment (rule 4 of the plan), for review
Rules, in this order (the first that applies decides; every reason is kept in "preuves"):
  1. equipement: shop category machinery / irrigation / germination kits, or a tool word in the name;
  2. semence: shop category of seeds;
  3. pesticide: trade name found in the official list (exact, prefix or close name, build_agrishop.link_registered),
     or shop category "pesticides";
  4. growth regulators and adjuvants not found in the list: autre (a plant protection product needs a registration);
  5. biostimulant: shop category or words (algues, acides aminés, biostimulant...);
  6. engrais_amendement: shop category of fertilisers / amendments, an NPK grade or a nutrient content;
  7. autre.
The trade-name match only classifies: a shop product is LINKED to an advised product at step 9 only with the same
active substance(s) and concentration, in a validated mapping.
Usage: python src/preparation/classify_shop_products.py
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "preparation"))
import build_agrishop as A  # noqa: E402

SHOP = ROOT / "data" / "processed" / "shop" / "shop_products.csv"
CLASSES = ROOT / "docs" / "shop_product_classes.csv"
CLAIMS = ROOT / "docs" / "shop_unapproved_claims.csv"
EQUIPMENT_CAT = r"^materiel|^irrigation|germination"  # not "engrais > engrais_npk_fertirrigation"
EQUIPMENT_NAME = (r"pulverisateur|motoculteur|debroussailleuse|tronconneuse|recolteuse|souffleur|tuyau|raccord|manchon|"
                  r"coude|vanne|goutteur|secateur|mini serre|\bserre de\b|\bpots?\b|\bkit\b|\bbac\b|tondeuse|bache")
REGULATOR = r"regulateur|gibberell|\bga3\b|cytokinin|cytoquinin|auxin|\bana\b|adjuvant|mouillant"
BIOSTIM = r"biostimul|algue|ascophyllum|ecklonia|acides? amine|amino|extrait d|floraison|nouaison|enracinement"
FERTILISER_CAT = r"engrais|fertilis|correcteur|amendement|npk|oligo|chelate"
NUTRIENT = (r"\b\d{1,2}[-.]\d{1,2}[-.]\d{1,2}\b|\bazote\b|\bpotass|\bphosph|\bmagnesi|\bcalci|\bfer\b|\bzinc\b|\bbore\b|"
            r"\bmangan|eddha|edta|dtpa|humique|fulvique|matiere organique|engrais|dunger")
# a protection or curative claim: kind of product, "contre / anti" a pest or disease, "protège", "élimine"...
PEST = (r"maladies?|champignons?|fongiques?|insectes?|ravageurs?|mildiou|oidium|pucerons?|acariens?|botrytis|nematodes?|"
        r"thrips|mouches?|chenilles?|tuta|cochenilles?|aleurodes?|bacteri\w*|virus|pourritures?|tavelure|rouille|"
        r"mineuses?|noctuelles?|limaces?|escargots?|vers?\b|parasites?")
CLAIM = re.compile(
    r"(?<![a-z])(?:fongicid\w*|insecticid\w*|acaricid\w*|nematicid\w*|bactericid\w*|herbicid\w*|pesticid\w*|"
    rf"antifongi\w*|anti[- ]?(?:{PEST})|(?:contre|lutte contre|lutter contre|protege\w*\s+(?:contre|des|de la|du)|"
    rf"elimine\w*|tue\w*|repousse\w*|eloigne\w*|combat\w*|guerit|guerir|traite\w*)\s+(?:\w+\s+){{0,3}}(?:{PEST})|"
    r"repulsif|biopesticide|defenses? naturelles?|stimul\w* (?:les|des) defenses|eliciteur|"
    r"resistance (?:aux|contre les) maladies|resistance des plantes (?:aux|contre les) maladies)")
# words just before the claim that make it a denial or a compatibility note, not a claim
DENIAL = re.compile(r"ne possede (?:pas|aucune)|n'?est (?:ni|pas)|\bni (?:un|une)\b|sans (?:action|se substituer)|"
                    r"ne doit (?:toutefois )?pas etre presente|ne remplace|ne supprime|ne detruit|ne guerit|"
                    r"aucune action|pas d'?action|compatible|melange|associ|ni la protection|avec (?:la plupart|de nombreux|"
                    r"les|des|un|une)|potentialis|penetration|phytotoxicite des|reduction de leurs doses")
NOT_A_PEST = re.compile(r"pourriture apicale|cul noir|stress")


def plain(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def classify(r):
    cat, name = plain(r["shop_category"]), plain(r["name"])
    text = f"{name} {plain(r['description'])} {plain(r['technical_sheet'])}"
    reasons = [f"catégorie boutique : {r['shop_category']}"]
    if r["liste_fort"]:
        reasons.append(f"nom trouvé dans la liste DGSVCIA ({r['liste_how']}) : {r['liste_nom']} [{r['liste_id']}]"
                       + (" et sa substance est écrite dans la description" if r["liste_substance"] else ""))
    elif r["liste_how"]:
        reasons.append(f"nom proche d'un produit de la liste ({r['liste_nom']}, {r['liste_how']}) mais ni vendu comme "
                       "pesticide ni de substance commune : rapprochement écarté, à vérifier")
    if re.search(EQUIPMENT_CAT, cat) or re.search(EQUIPMENT_NAME, name):
        return "equipement", reasons
    if "semence" in cat:
        return "semence", reasons
    if r["liste_fort"]:
        return "pesticide", reasons
    if cat.startswith("pesticides"):
        return "pesticide", reasons + ["vendu comme pesticide, nom absent de la liste"]
    if re.search(REGULATOR, cat + " " + name):
        return "autre", reasons + ["régulateur ou adjuvant absent de la liste (un produit phytopharmaceutique "
                                   "doit être homologué)"]
    if re.search(BIOSTIM, cat) or re.search(BIOSTIM, name):
        return "biostimulant", reasons
    if re.search(FERTILISER_CAT, cat) or re.search(NUTRIENT, text):
        found = sorted(set(m.group(0) for m in re.finditer(NUTRIENT, text)))[:5]
        return "engrais_amendement", reasons + ([f"composition : {', '.join(found)}"] if found else [])
    if re.search(BIOSTIM, text):
        return "biostimulant", reasons + ["mots de biostimulant dans la description"]
    return "autre", reasons


def substance_written(substance, r):
    """True when a word (5 letters or more) of a substance of the registered product is in the shop text."""
    words = [w for part in re.split(r"[+&,/]", plain(substance)) for w in re.findall(r"[a-z]{5,}", part)
             if w not in ("acide", "acetate", "sodium", "potassium", "huile", "extrait")]
    text = " ".join(plain(r[c]) for c in ("name", "description", "technical_sheet"))
    return bool(words) and any(re.search(r"(?<![a-z])" + re.escape(w[:-1] if w.endswith("e") else w), text)
                               for w in words)


def sentence_before(text, i):
    """The words of the same sentence before position i (a denial or a compatibility note there cancels the claim)."""
    start = max(text.rfind(".", 0, i), text.rfind(chr(10), 0, i), text.rfind(";", 0, i), i - 200)
    return text[start + 1:i]


def claims(r):
    text = " ".join(plain(r[c]) for c in ("name", "description", "technical_sheet"))
    found = [m for m in CLAIM.finditer(text)
             if not DENIAL.search(sentence_before(text, m.start())) and not NOT_A_PEST.search(
                 text[m.start():m.end() + 25])]
    if not found:
        return [], ""
    m = found[0]
    return sorted(set(x.group(0) for x in found))[:6], text[max(0, m.start() - 90):m.end() + 90].strip()


def main():
    os.chdir(ROOT)  # build_agrishop reads the official list by a path relative to the repository
    shop = pd.read_csv(SHOP, keep_default_na=False)
    linked = A.link_registered(shop.rename(columns={"name": "nom"}))
    shop["liste_how"], shop["liste_id"] = linked["homologation_match"], linked["tn_product_id"]
    shop["liste_nom"] = linked["tn_nom_commercial"]
    # a trade name alone can collide (ATLANTIS biostimulant / Atlantis herbicide): the match counts as a registered
    # pesticide only when the shop sells it as a pesticide, or when a substance of that registered product is written
    # in the shop text
    shop["liste_substance"] = [substance_written(s, r) for s, r in zip(linked["tn_substance"], shop.to_dict("records"))]
    # growth regulators are registered products ("Divers"): the same exact name in that shelf counts too
    shop["liste_fort"] = [bool(h) and (plain(c).startswith("pesticides") or bool(s) or
                                       (h == "exact" and re.search(REGULATOR, plain(c)) is not None))
                          for h, c, s in zip(shop["liste_how"], shop["shop_category"], shop["liste_substance"])]
    rows, claim_rows = [], []
    for r in shop.to_dict("records"):
        cat, reasons = classify(r)
        rows.append({"shop_product_id": r["id"], "name": r["name"], "shop": r["id"].split(":")[0],
                     "shop_category": r["shop_category"], "category_agria": cat, "preuves": " ; ".join(reasons),
                     "liste_product_id": r["liste_id"], "liste_nom": r["liste_nom"],
                     "liste_correspondance": r["liste_how"] if r["liste_fort"] else
                     (f"écarté ({r['liste_how']})" if r["liste_how"] else ""), "status": "proposed", "note": ""})
        words, excerpt = claims(r)
        if words and not r["liste_fort"] and cat != "equipement":
            claim_rows.append({"shop_product_id": r["id"], "name": r["name"], "shop": r["id"].split(":")[0],
                               "shop_category": r["shop_category"], "category_agria": cat,
                               "allegation": " | ".join(words), "extrait": excerpt, "product_url": r["product_url"],
                               "status": "proposed", "note": "allégation de protection sans produit de la liste "
                                                             "DGSVCIA du même nom : jamais conseillé comme traitement"})
    classes = pd.DataFrame(rows)
    classes.to_csv(CLASSES, index=False, encoding="utf-8")
    pd.DataFrame(claim_rows).to_csv(CLAIMS, index=False, encoding="utf-8")
    print(f"{CLASSES.relative_to(ROOT)}: {len(classes)} products")
    print(pd.crosstab(classes["category_agria"], classes["shop"]).to_string())
    print(f"registry trade-name match: {classes['liste_correspondance'].ne('').sum()} "
          f"{classes['liste_correspondance'].value_counts().to_dict()}")
    c = pd.DataFrame(claim_rows)
    print(f"{CLAIMS.relative_to(ROOT)}: {len(c)} products claim a protection effect without a registry match "
          f"{c['category_agria'].value_counts().to_dict() if len(c) else {}}")


if __name__ == "__main__":
    main()
