"""Build the gold set of the Phytosanitaire / Agronome evaluation: tests/phyto_gold/cases.csv (step 1 of the phyto plan).

Every case is a farmer situation: crop, disease or deficiency, governorate, stage, market, days to harvest, organic,
greenhouse, last treatment group. All cases are marked status = to_validate: an agronomist must check them.

acceptable_products is computed HERE from the official list alone (table pesticides_usages: crop and target text of each
registered use), with a target rule written by hand per class (GOLD below). It never uses classe_traitements, the
mapping the agents use, so the evaluation does not grade the system with its own answers.
  - a use counts when its crop is the case crop or a group that contains it (vegetables, fruit_trees...) and its target
    text matches the rule of the class;
  - must_not_contain: products registered against the same target on other crops only (crop trap);
  - deficiencies: "nutriment:<X>" (any fertiliser bringing X), plus "chelate:EDDHA" for iron on a calcareous soil
    (pH >= 7.8), the only chelate that stays available there;
  - healthy plants and physiological disorders: no product at all.

Usage: python src/evaluation/make_phyto_gold.py   (deterministic: seed 42)
A file with reviewed cases (status other than to_validate) is never overwritten, unless --force is given.
"""
import csv
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "tools"))
from common import fold, query  # noqa: E402
from treatments import GROUPS  # noqa: E402

OUT = ROOT / "tests" / "phyto_gold" / "cases.csv"
COLUMNS = ["case_id", "crop", "disease_or_deficiency", "governorate", "stage", "market", "days_to_harvest", "organic",
           "greenhouse", "last_treatment_group", "acceptable_products", "must_not_contain", "expected_shop_link",
           "kind", "gold_target_rule", "status", "note"]

# class -> (kind, regex on the folded target text of the official list, or None when nothing is registered against it)
# kind: disease | pest | virus_vector | virus | physiological
GOLD = {
    "apple__black_rot": ("disease", r"black.?rot|botryosphaeria"),
    "apple__rust": ("disease", r"rouille|gymnosporangium"),
    "apple__scab": ("disease", r"tavelure|venturia"),
    "cherry__powdery_mildew": ("disease", r"oidium|podosphaera"),
    "citrus__black_spot": ("disease", r"black spot|taches noires|phyllosticta"),
    "citrus__canker": ("disease", r"chancre citrique|xanthomonas"),
    "citrus__scab": ("disease", r"tavelure|elsinoe"),
    "corn__common_rust": ("disease", r"rouille|puccinia"),
    "corn__gray_leaf_spot": ("disease", r"cercospor"),
    "corn__northern_leaf_blight": ("disease", r"helminthospor|exserohilum"),
    "datepalm__black_scorch": ("disease", r"thielaviopsis|black scorch"),
    "datepalm__fusarium_wilt": ("disease", r"bayoud|fusari"),
    "datepalm__leaf_spots": ("disease", r"dessechement foliaire|alternaria|taches foliaires"),
    "datepalm__parlatoria_scale": ("pest", r"cochenille|parlatoria"),
    "datepalm__rachis_blight": ("disease", r"rachis"),
    "grape__black_rot": ("disease", r"black.?rot|guignardia"),
    "grape__esca": ("disease", r"\besca\b"),
    "grape__leaf_blight": ("disease", r"isariopsis|pseudocercospora"),
    "olive__aculus_olearius": ("pest", r"acarien|eriophy|aculus"),
    "olive__knot_disease": ("disease", r"tuberculose|pseudomonas savastanoi"),
    "olive__peacock_spot": ("disease", r"(?:oe|œ)il de paon|spilocaea|cycloconium"),  # fold() keeps the ligature
    "orange__citrus_greening": ("virus_vector", r"diaphorina|psylle asiatique|greening"),
    "peach__bacterial_spot": ("disease", r"bacteriose|xanthomonas"),
    "pepper__bacterial_spot": ("disease", r"bacteriose|xanthomonas"),
    "pomegranate__alternaria_spot": ("disease", r"alternari"),
    "pomegranate__anthracnose": ("disease", r"anthracnose|colletotrichum"),
    "pomegranate__bacterial_blight": ("disease", r"bacteriose|xanthomonas"),
    "pomegranate__cercospora_spot": ("disease", r"cercospor"),
    "potato__early_blight": ("disease", r"alternari"),
    "potato__late_blight": ("disease", r"mildiou|phytophthora infestans"),
    "squash__powdery_mildew": ("disease", r"oidium|sphaerotheca|podosphaera|erysiphe"),
    "strawberry__leaf_scorch": ("disease", r"taches pourpres|diplocarpon"),
    "tomato__anthracnose": ("disease", r"anthracnose|colletotrichum"),
    "tomato__bacterial_spot": ("disease", r"bacteriose|xanthomonas"),
    "tomato__blossom_end_rot": ("physiological", None),
    "tomato__cracking": ("physiological", None),
    "tomato__early_blight": ("disease", r"alternari"),
    "tomato__fruitworm": ("pest", r"noctuelle|helicoverpa|heliothis|chenille"),
    "tomato__late_blight": ("disease", r"mildiou|phytophthora infestans"),
    "tomato__leaf_miner": ("pest", r"tuta|mineuse"),
    "tomato__leaf_mold": ("disease", r"cladospori|passalora|fulvia"),
    "tomato__mold": ("disease", r"botrytis|pourriture grise"),
    "tomato__mosaic_virus": ("virus", None),
    "tomato__septoria_leaf_spot": ("disease", r"septori"),
    "tomato__spider_mites": ("pest", r"acarien|tetranychus"),
    "tomato__target_spot": ("disease", r"corynespora"),
    "tomato__yellow_leaf_curl_virus": ("virus_vector", r"mouches? blanches?|aleurode|bemisia"),
    "wheat__leaf_rust": ("disease", r"rouille|puccinia"),
}
CLASS_CROP = {"orange": "citrus"}
# plausible governorates per crop (main production areas)
GOVS = {"apple": ["Kasserine", "Sidi Bouzid", "Siliana"], "cherry": ["Le Kef", "Siliana"],
        "citrus": ["Nabeul", "Ben Arous", "Bizerte"], "corn": ["Jendouba", "Béja"], "datepalm": ["Tozeur", "Kébili"],
        "grape": ["Nabeul", "Ben Arous", "Manouba"], "olive": ["Sfax", "Sousse", "Mahdia"],
        "peach": ["Sidi Bouzid", "Kairouan"], "pepper": ["Kairouan", "Monastir", "Nabeul"],
        "pomegranate": ["Gabès", "Kairouan"], "potato": ["Jendouba", "Nabeul", "Béja"],
        "squash": ["Kairouan", "Monastir"], "strawberry": ["Nabeul", "Béja"],
        "tomato": ["Nabeul", "Kairouan", "Sidi Bouzid", "Monastir"], "wheat": ["Béja", "Jendouba", "Siliana"]}
GREENHOUSE_CROPS = {"tomato", "pepper", "squash", "strawberry"}
# last treatment group of a few cases (FRAC / IRAC code of a product often used against that problem)
LAST_GROUP = {"tomato__late_blight": "FRAC 40", "potato__late_blight": "FRAC 11", "tomato__leaf_miner": "IRAC 28",
              "tomato__spider_mites": "IRAC 6", "grape__black_rot": "FRAC 3", "apple__scab": "FRAC 3",
              "squash__powdery_mildew": "FRAC 3", "wheat__leaf_rust": "FRAC 3",
              "tomato__yellow_leaf_curl_virus": "IRAC 4A", "tomato__fruitworm": "IRAC 28"}
# deficiency -> crops, seen in training or not (then the answer must be a hypothesis: regles_carences.json)
DEFICIENCY_CROPS = {"Fe": ["pepper", "citrus", "olive"], "N": ["tomato", "wheat"], "K": ["tomato", "potato"],
                    "Mg": ["grape"], "P": ["tomato"], "Ca": ["tomato"], "Zn": ["pepper"], "Mn": ["datepalm"],
                    "B": ["olive"]}
DEF_GOVS = ["Kairouan", "Nabeul", "Sfax", "Sidi Bouzid", "Jendouba", "Tozeur", "Gabès", "Béja", "Monastir"]


def _covers(crop_cell, crop):
    return any(crop in GROUPS.get(name, [name]) for name in str(crop_cell or "").split("|"))


def gold_products(cls, rx):
    """(acceptable product names on the case crop, crop-trap names) from the official list."""
    if rx is None:
        return [], []
    crop = CLASS_CROP.get(cls.split("__")[0], cls.split("__")[0])
    usages = [u for u in query("SELECT nom_commercial, crop, cible FROM pesticides_usages")
              if re.search(r"[a-zA-Z]{3}", str(u["nom_commercial"] or ""))]  # skip names misread in the list ("50")
    on_crop = {u["nom_commercial"].strip() for u in usages if _covers(u["crop"], crop)}
    ok, other = set(), set()
    for u in usages:
        if re.search(rx, fold(u["cible"])):
            (ok if _covers(u["crop"], crop) else other).add(u["nom_commercial"].strip())
    # crop trap: registered against this target elsewhere, and for nothing at all on this crop
    return sorted(ok), sorted(other - on_crop)[:3]


def _context(rng, crop, variant):
    greenhouse = "y" if crop in GREENHOUSE_CROPS and rng.random() < 0.5 else "n"
    row = {"stage": rng.choice(["early", "spread"]), "market": "local", "days_to_harvest": rng.choice([7, 15, 30, 45, 60]),
           "organic": "n", "greenhouse": greenhouse, "last_treatment_group": ""}
    if variant == "harvest_soon":
        row.update(days_to_harvest=3, note="récolte dans 3 jours : DAR à respecter")
    elif variant == "export":
        row.update(market="export", note="export vers l'UE : substances approuvées dans l'UE seulement")
    elif variant == "organic":
        row.update(organic="y", stage="early", note="agriculture biologique")
    elif variant == "rotation":
        row.update(note="dernier traitement du même groupe : rotation attendue")
    return row


def build(force=False):
    rng = random.Random(42)
    rows = []

    def add(**r):
        r["case_id"] = f"c{len(rows) + 1:03d}"
        r.setdefault("expected_shop_link", "")
        r.setdefault("note", "")
        r["status"] = "to_validate"
        rows.append(r)

    # 1. one case per disease class (48), then variants of the classes that have registered products
    with_products = []
    for cls, (kind, rx) in GOLD.items():
        crop = CLASS_CROP.get(cls.split("__")[0], cls.split("__")[0])
        ok, trap = gold_products(cls, rx)
        base = dict(crop=crop, disease_or_deficiency=cls, governorate=rng.choice(GOVS[crop]), kind=kind,
                    acceptable_products=" | ".join(ok), must_not_contain=" | ".join(trap),
                    gold_target_rule=rx or "")
        add(**base, **_context(rng, crop, None))
        if ok:
            with_products.append((cls, base))
    cycle = iter(["harvest_soon", "export", "organic"] * 20)
    for cls, base in with_products:
        crop = base["crop"]
        # one context variant per class with products, a second one (rotation) for the classes of LAST_GROUP
        variants = [next(cycle)] if len(base["acceptable_products"].split(" | ")) >= 5 else ["harvest_soon"]
        if cls in LAST_GROUP:
            variants.append("rotation")
        for v in variants:
            ctx = _context(rng, crop, v)
            if v == "rotation":
                ctx["last_treatment_group"] = LAST_GROUP[cls]
            add(**dict(base, governorate=rng.choice(GOVS[crop])), **ctx)

    # 2. deficiencies: nutrient needed, EDDHA for iron on a calcareous soil
    ph = {r["gouvernorat"]: r["phh2o_pH"] for r in query("SELECT gouvernorat, phh2o_pH FROM sols")}
    for nut, crops in DEFICIENCY_CROPS.items():
        for crop in crops:
            gov = rng.choice(DEF_GOVS)
            need = [f"nutriment:{nut}"] + (["chelate:EDDHA"] if nut == "Fe" and (ph.get(gov) or 0) >= 7.8 else [])
            add(crop=crop, disease_or_deficiency=f"{nut}_deficiency", governorate=gov, kind="deficiency",
                acceptable_products=" | ".join(need), must_not_contain="", gold_target_rule="",
                **_context(rng, crop, None))

    # 3. healthy plants: nothing to buy
    for crop, gov in (("tomato", "Nabeul"), ("olive", "Sfax"), ("citrus", "Nabeul")):
        add(crop=crop, disease_or_deficiency=f"{crop}__healthy", governorate=gov, kind="healthy",
            acceptable_products="", must_not_contain="", gold_target_rule="", **_context(rng, crop, None))

    if OUT.exists() and not force:
        with open(OUT, encoding="utf-8") as f:
            reviewed = [r["case_id"] for r in csv.DictReader(f) if r.get("status") != "to_validate"]
        if reviewed:
            raise SystemExit(f"{len(reviewed)} cases already reviewed ({reviewed[:5]}...): not overwritten "
                             "(use --force to rebuild from scratch)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"{OUT.relative_to(ROOT)}: {len(rows)} cases {kinds}; "
          f"{sum(1 for r in rows if r['kind'] not in ('deficiency', 'healthy') and r['acceptable_products'])} "
          f"disease/pest cases with at least one acceptable registered product")
    return rows


if __name__ == "__main__":
    build(force="--force" in sys.argv)
