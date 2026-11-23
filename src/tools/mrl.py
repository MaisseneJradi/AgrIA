"""Maximum residue limit (LMR) of each substance of a registered use on the farmer's crop, chosen by the market
(phyto plan, step 7):
  market export (EU) -> the EU MRL (table usage_lmr, EU Pesticides Database), the limit of the importing market;
  market local       -> the Tunisian MRL when the official list writes one for this use (one value, one substance),
                        else the Codex MRL (table codex_mrl, FAO/WHO Codex Alimentarius) of the crop's commodity;
  market unknown     -> nothing (the limit depends on where the harvest is sold).

  applicable_mrl(usage, "tomato", "local") -> [{"substance": "Azoxystrobin", "valeur": 3.0, "source": "Codex",
                                                "denree": "Tomatoes (subgroup)"}, {"substance": "...", "valeur": None,
                                                "source": "Codex", "denree": None}]   (None: no MRL found: said so)
Codex commodity of a crop: VALIDATED rows of docs/codex_commodity_mapping.csv (build_codex_mrl.py), the most specific
level first (denree, then sous-groupe, then groupe); a group row whose note excludes the crop ("Except ... grapes") is
skipped. When several commodities of the same level give different values, the lowest is kept (the strictest).
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

from common import query

ROOT = Path(__file__).resolve().parents[2]
MAPPING = ROOT / "docs" / "codex_commodity_mapping.csv"
LEVELS = ("denree", "sous-groupe", "groupe")
# English words of each crop in the Codex notes ("Except cranberry, grapes, and strawberry")
CROP_WORDS = {"tomato": "tomato", "pepper": "pepper", "potato": "potato", "squash": "squash", "grape": "grape",
              "citrus": "citrus|orange|mandarin|lemon", "apple": "apple", "peach": "peach", "cherry": "cherr",
              "strawberry": "strawberr", "olive": "olive", "wheat": "wheat", "corn": "maize|corn",
              "datepalm": "date", "pomegranate": "pomegranate"}


@lru_cache(maxsize=1)
def _mapping():
    if not MAPPING.exists():
        return {}
    with open(MAPPING, encoding="utf-8") as f:
        out = {}
        for r in csv.DictReader(f):
            if r.get("status") == "validated":
                out.setdefault(r["culture"], []).append((r["denree_codex"], r["niveau"]))
        return out


@lru_cache(maxsize=1)
def _codex():
    try:
        rows = query("SELECT substance, denree, lmr_mg_kg, notes FROM codex_mrl")
    except Exception:  # base built before step 7: no Codex table
        return {}
    out = {}
    for r in rows:
        out.setdefault(r["substance"].strip().lower(), []).append(r)
    return out


def codex_mrl(substance, crop):
    """(value, commodity) of the Codex MRL of a substance on a crop, (None, None) when none applies."""
    rows = _codex().get(str(substance).strip().lower(), [])
    words = CROP_WORDS.get(crop, crop or "")
    for level in LEVELS:
        names = {n for n, lv in _mapping().get(crop, []) if lv == level}
        hits = [r for r in rows if r["denree"] in names
                and not (re.search(r"\bexcept", str(r["notes"] or ""), re.I)
                         and re.search(words, str(r["notes"]), re.I))]
        if hits:
            best = min(hits, key=lambda r: r["lmr_mg_kg"])
            return best["lmr_mg_kg"], best["denree"]
    return None, None


def _eu_not_required(product_id, usage_idx, substance):
    """True when the EU writes 'No MRL required' for this substance on the commodities of the use."""
    try:
        rows = query("SELECT e.mrl_text FROM usage_lmr u JOIN eu_mrl e ON e.residue_id = u.residue_id "
                     "AND e.product_code = u.product_code WHERE u.product_id = ? AND u.usage_idx = ? "
                     "AND lower(u.eu_name) = lower(?)", (product_id, usage_idx, substance))
    except Exception:  # base built before step 7
        return False
    return bool(rows) and all("no mrl required" in str(r["mrl_text"]).lower() for r in rows)


def tunisian_mrl(usage):
    """One value written by the official list for a use of a one-substance product ('LMR :0.05 mg/kg'), else None."""
    subs = [s for s in str(usage.get("substances") or "").split("+") if s.strip()]
    values = re.findall(r"LMR\s*:?\s*(?:[A-Za-zé]+\s*:\s*)?(\d+(?:[.,]\d+)?)", str(usage.get("lmr_tn_texte") or ""),
                        re.I)
    if len(subs) != 1 or len(set(values)) != 1:
        return None
    return float(values[0].replace(",", "."))


def mrl_number(v):
    """0.01 -> '0,01'; 3.0 -> '3' (an MRL keeps all its decimals)."""
    return f"{v:g}".replace(".", ",")


MARKERS = ("LMR de ", "الحد الأقصى للمتبقيات في ")  # first words of the MRL line of a product (redaction.py)


def check_line(text, name, expected):
    """Errors of the MRL line written for product `name` against the expected MRLs (applicable_mrl)."""
    lines = [x for x in text.splitlines() if any(m + name in x for m in MARKERS)]
    if not lines:
        return []
    if not expected:
        return ["LMR écrite alors que le marché n'est pas connu"]
    written = sorted(re.findall(r"(\d+(?:,\d+)?)\s*mg/kg", lines[0]))
    wanted = sorted(mrl_number(m["valeur"]) for m in expected if m["valeur"] is not None)
    errors = []
    if written != wanted:
        errors.append(f"LMR écrites {written} au lieu de {wanted} ({expected[0]['source']})")
    if f"({expected[0]['source']}," not in lines[0] and f"({expected[0]['source']}،" not in lines[0]:
        errors.append(f"source de la LMR différente de {expected[0]['source']}")
    return errors


def applicable_mrl(usage, crop, market):
    if market not in ("local", "export"):
        return []
    subs = [s.strip() for s in str(usage.get("substances") or "").split("+") if s.strip()]
    out = []
    if market == "export":
        eu = {}
        for x in usage.get("lmr") or []:
            if x.get("lmr_ue_mg_kg") is not None:
                k = x["substance"].strip().lower()
                if k not in eu or x["lmr_ue_mg_kg"] < eu[k][0]:
                    eu[k] = (x["lmr_ue_mg_kg"], x.get("denree"))
        for s in subs:
            v, d = eu.get(s.lower(), (None, None))
            item = {"substance": s, "valeur": v, "source": "UE", "denree": d}
            if v is None and usage.get("product_id") and _eu_not_required(usage["product_id"], usage.get("usage_idx"), s):
                item["non_requise"] = True  # Annex IV of Reg. (EC) 396/2005: no MRL is required (sulphur...)
            out.append(item)
        return out
    tn = tunisian_mrl(usage)
    if tn is not None:
        return [{"substance": subs[0], "valeur": tn, "source": "liste DGSVCIA", "denree": None}]
    if crop not in _mapping():  # no validated Codex commodity for this crop yet: nothing said (not "not found")
        return []
    for s in subs:
        v, d = codex_mrl(s, crop)
        out.append({"substance": s, "valeur": v, "source": "Codex", "denree": d})
    return out
