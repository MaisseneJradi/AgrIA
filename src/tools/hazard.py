"""Applicator and bee safety of a registered product, from the VALIDATED rows of two versioned tables (phyto step 6):
  docs/substance_hazard.csv  WHO acute hazard class (Ia, Ib, II, III, U) of each substance (WHO 2019)
  docs/bee_hazard.csv        substances highly toxic to bees (PAN International HHP list 2024, US EPA < 2 µg/bee)

  who_class({"substances": "Cymoxanil + Copper oxychloride"}) -> "II" (the worst class), None if one is unknown
  bee_toxic({"substances": "Imidacloprid"}) -> ["imidacloprid"] (substances highly toxic to bees), [] when the data
                                             says nothing (never "safe for bees")
"""
from functools import lru_cache
from pathlib import Path

import ranking

ROOT = Path(__file__).resolve().parents[2]
BEES = ROOT / "docs" / "bee_hazard.csv"
LABELS = {"Ia": ("extrêmement dangereux", "شديد الخطورة جدًا"), "Ib": ("très dangereux", "عالي الخطورة"),
          "II": ("modérément dangereux", "متوسط الخطورة"), "III": ("peu dangereux", "قليل الخطورة"),
          "U": ("danger aigu peu probable", "خطر حاد غير مرجّح")}
SEVERE = ("Ia", "Ib")


@lru_cache(maxsize=1)
def _bees():
    return {r["substance"].strip().lower() for r in ranking._rows(BEES) if r.get("tres_toxique_abeilles") == "oui"}


def who_class(u):
    rank = ranking.hazard_rank(u)
    if rank is None:
        return None
    return next(c for c, i in ranking.HAZARD_ORDER.items() if i == rank)


def bee_toxic(u):
    return [s for s in ranking._substances(u) if s in _bees()]
