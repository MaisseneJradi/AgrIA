"""Prevention advice without any product: what the farmer can do when no product is registered, and the passages of
the sheets cleaned of every chemical control.

  prevention_advice("tomato__septoria_leaf_spot") -> [{"fr": "...", "ar": "...", "origine": "..."}]
      the VALIDATED rows of docs/conseils_prevention.csv (status proposed rows wait for the agronomist's review)
  cultural_sentences(passages) -> ["...", ...]
      sentences of the French passages of search_knowledge that name no substance, no product, no word of chemical
      control and no number (a number in an answer is always written by code): rotation, healthy plants, pruning...

No sentence is ever written by a language model here: the rows are fixed texts to review, the passages are quoted.
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

from safety import _named_in_text, chemical_terms

ROOT = Path(__file__).resolve().parents[2]
ADVICE = ROOT / "docs" / "conseils_prevention.csv"
MIN_LEN, MAX_SENTENCES = 30, 3


@lru_cache(maxsize=1)
def _rows(path=ADVICE):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    bad = {r["status"] for r in rows} - {"proposed", "validated"}
    if bad:
        raise ValueError(f"{path}: unknown status {sorted(bad)}")
    return rows


def prevention_advice(unified_class, path=ADVICE):
    rows = [r for r in _rows(path) if r["unified_class"] == unified_class and r["status"] == "validated"]
    return [{"fr": r["conseil_fr"], "ar": r["conseil_ar"], "origine": r["origine"]}
            for r in sorted(rows, key=lambda r: int(r["ordre"] or 0))]


def clean_sentence(s):
    """The sentence if it can be quoted to a farmer, else None."""
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(?:Lutte et prophylaxie|Moyens de lutte|Prévention|Lutte|Symptômes|Description|Biologie|Répartition)"
               r"\s+(?=[A-ZÀ-Ý])", "", s)  # section titles glued to the first sentence
    if len(s) < MIN_LEN or re.search(r"\d|https?://|www\.", s):
        return None
    if chemical_terms(s) or _named_in_text(s):
        return None
    return s


def cultural_sentences(passages, max_sentences=MAX_SENTENCES):
    out = []
    for p in passages:
        if p.get("langue") != "fr":
            continue
        for s in re.split(r"(?<=[.!?])\s+", p["extrait"]):
            s = clean_sentence(s)
            if s and s not in out:
                out.append(s)
            if len(out) >= max_sentences:
                return out
    return out
