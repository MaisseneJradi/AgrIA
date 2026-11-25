"""Shop offers for what AgrIA advises (phyto plan, step 10), added AFTER the ranking: availability and price never
change which product is advised.

  pesticide_offers(usage) -> [{"shop_id", "nom", "resume", "stock", "url", "boutique"}]  shop products of the SAME
        composition as the registered product, through VALIDATED rows of docs/shop_product_mapping.csv
  fertiliser_offers("Fe_deficiency", calcareous=True) -> offers for the need besoin:Fe_deficiency[:calcaire]
  registry_composition(product_id) -> "Azoxystrobine 250 g/l"   (what to ask for when no shop sells it)

An offer is never: a product of docs/shop_unapproved_claims.csv (unless the reviewer marked it 'rejected'), a product
whose shop marks it inactive, a product whose name the official list does not register for the case (caller's check).
"resume" is written from the composition read by rules (docs/shop_composition.csv): substances + concentrations +
formulation, or N-P-K + nutrient + chelate. Never a marketing sentence, never a dose of the shop.
"url": only the product_url of the table shop_products (agriclic pages); agrishop pages have no address in the data.
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

from common import query

ROOT = Path(__file__).resolve().parents[2]
MAPPING = ROOT / "docs" / "shop_product_mapping.csv"
COMPOSITION = ROOT / "docs" / "shop_composition.csv"
CLAIMS = ROOT / "docs" / "shop_unapproved_claims.csv"
MAX_OFFERS = 2
SHOPS = {"agrishop": "agrishop.tn", "agriclic": "agriclic.tn"}
NUTRIENT_COLUMNS = {"N": "N", "P": "P2O5", "K": "K2O", "Ca": "CaO", "Mg": "MgO", "Fe": "Fe", "Zn": "Zn", "Mn": "Mn",
                    "B": "B"}


def _read(path):
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def _mapping():
    """target_id -> validated shop_product_ids (best score first)."""
    out = {}
    rows = [r for r in _read(MAPPING) if r.get("status") == "validated" and r.get("target_id")]
    for r in sorted(rows, key=lambda r: -float(r["match_score"] or 0)):
        out.setdefault(r["target_id"], []).append(r["shop_product_id"])
    return out


@lru_cache(maxsize=1)
def _composition():
    return {r["shop_product_id"]: r for r in _read(COMPOSITION)}


@lru_cache(maxsize=1)
def _claims():
    return {r["shop_product_id"] for r in _read(CLAIMS) if r.get("status") != "rejected"}


@lru_cache(maxsize=1)
def _products():
    try:
        return {r["id"]: r for r in query("SELECT * FROM shop_products")}
    except Exception:  # base built before step 8
        return {}


def validated_targets(shop_id):
    return {t for t, ids in _mapping().items() if shop_id in ids}


def summary(shop_id):
    """Composition written by code: 'Mandipropamid 250 g/l, SC' or 'Fe 6 %, chélate EDDHA' or 'NPK 20-20-20'."""
    c = _composition().get(shop_id) or {}
    if c.get("type_compo") == "pesticide":
        return ", ".join(x for x in (c.get("substances"), c.get("formulation")) if x)
    parts = []
    npk = [c.get(k) for k in ("N", "P2O5", "K2O")]
    if all(npk):
        parts.append("NPK " + "-".join(f"{float(v):g}" for v in npk))
    for k in ("CaO", "MgO", "Fe", "Zn", "Mn", "B"):
        if c.get(k):
            parts.append(f"{k} {float(c[k]):g} %".replace(".", ","))
    if c.get("chelate"):
        parts.append(f"chélate {c['chelate']}")
    return ", ".join(parts)


def _offer(shop_id):
    p = _products().get(shop_id)
    if not p or shop_id in _claims() or p.get("stock_status") == "inactif":
        return None
    return {"shop_id": shop_id, "nom": p["name"], "resume": summary(shop_id), "stock": p.get("stock_status"),
            "url": p.get("product_url") or None, "boutique": SHOPS.get(shop_id.split(":")[0], shop_id)}


def pesticide_offers(usage, registered_name=None):
    """Offers of the registered product of this use. registered_name(name) -> bool: the caller checks that the shop's
    trade name is registered for the case (the Vérificateur blocks any other name, rule 1)."""
    out = []
    for sid in _mapping().get(usage["product_id"], []):
        o = _offer(sid)
        if o and (registered_name is None or registered_name(o["nom"])):
            out.append(o)
    return out[:MAX_OFFERS]


def fertiliser_offers(deficiency, calcareous=False):
    target = f"besoin:{deficiency}" + (":calcaire" if calcareous and deficiency == "Fe_deficiency" else "")
    return [o for o in (_offer(s) for s in _mapping().get(target, [])) if o][:MAX_OFFERS]


@lru_cache(maxsize=None)
def registry_composition(product_id):
    rows = query("SELECT substance, substances_ue, conc FROM pesticides_produits WHERE product_id = ?", (product_id,))
    if not rows:
        return ""
    # the EU names (the spelling of the list has typos: "Fostetyl"), in the order of the list
    eu = [s.strip() for s in str(rows[0]["substances_ue"] or "").split(" + ") if s.strip() and s.strip() != "nan"]
    tn = [s.strip() for s in re.split(r"\s*[+&]\s*", str(rows[0]["substance"])) if s.strip()]
    subs = eu if len(eu) == len(tn) else tn
    conc = [c.strip() for c in re.split(r"\s*\+\s*", str(rows[0]["conc"] or "")) if c.strip() and c.strip() != "nan"]
    if len(conc) == len(subs):
        return " + ".join(f"{s} {c}" for s, c in zip(subs, conc))
    return " + ".join(subs) + (f" ({rows[0]['conc']})" if conc else "")
