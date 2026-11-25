"""Label dose of a shop fertilizer, shown only when it passes the reference range (phyto plan, step 9; shown at step 10).

  label_dose("10-20 kg/ha | 10-20 g/plant", "Fe") -> {"texte": "10-20 kg/ha ; 10-20 g/plant", "montrer": True, ...}
  label_dose("1000 kg/ha", "Fe")                  -> {"montrer": False, "raison": "hors fourchette ..."}

The label doses come from docs/shop_composition.csv (doses_etiquette, read by rules); the ranges from the VALIDATED
rows of docs/fertiliser_dose_ranges.csv (nutrient, crop, application type, min, max, unit per hl | ha | plant).
A dose is shown, as "dose indiquée par le fabricant", only when EVERY dose read on the label parses and falls in a
validated range of its nutrient and basis; otherwise the answer says "suivez l'étiquette / demandez au CRDA" (rule 7:
never fill a gap). g and ml, kg and l are compared together (density close to 1: the range is only a sanity check).
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RANGES = ROOT / "docs" / "fertiliser_dose_ranges.csv"
TO_BASE = {"g": 1, "ml": 1, "cc": 1, "kg": 1000, "l": 1000}
BASES = {"hl": "hl", "ha": "ha", "plant": "plant", "arbre": "plant", "pied": "plant"}
DOSE = re.compile(r"(\d+(?:[.,]\d+)?)(?:\s*-\s*(\d+(?:[.,]\d+)?))?\s*(kg|g|l|ml|cc)/(hl|ha|plant|arbre|pied)\b", re.I)


@lru_cache(maxsize=1)
def _ranges():
    if not RANGES.exists():
        return []
    with open(RANGES, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("status") == "validated"]
    out = []
    for r in rows:
        m = re.fullmatch(r"(kg|g|l|ml)/(hl|ha|plant)", r["unite"].strip())
        if m:
            k = TO_BASE[m.group(1)]
            out.append({"nutriments": set(r["nutriment"].split("|")), "culture": r["culture"],
                        "min": float(r["min"]) * k, "max": float(r["max"]) * k, "base": m.group(2)})
    return out


def parse(doses):
    """'10-20 kg/ha | 150-300 cc/hl' -> [(10000.0, 20000.0, 'ha', '10-20 kg/ha'), ...] in g or ml; None if unread."""
    out = []
    for part in [p.strip() for p in str(doses or "").split("|") if p.strip()]:
        m = DOSE.fullmatch(part.replace(",", "."))
        if not m:
            return None
        k = TO_BASE[m.group(3).lower()]
        lo = float(m.group(1)) * k
        hi = float(m.group(2)) * k if m.group(2) else lo
        out.append((lo, hi, BASES[m.group(4).lower()], part))
    return out


def label_dose(doses, nutrient, crop="*"):
    parsed = parse(doses)
    if not parsed:
        return {"montrer": False, "raison": "dose de l'étiquette absente ou illisible"}
    for lo, hi, base, text in parsed:
        ok = [r for r in _ranges() if (nutrient in r["nutriments"] or "*" in r["nutriments"])
              and r["culture"] in ("*", crop) and r["base"] == base and r["min"] <= lo and hi <= r["max"]]
        if not ok:
            return {"montrer": False, "raison": f"« {text} » hors des fourchettes validées (ou aucune fourchette "
                                                f"validée pour {nutrient} par {base})"}
    return {"montrer": True, "texte": " ; ".join(t for *_, t in parsed), "raison": ""}
