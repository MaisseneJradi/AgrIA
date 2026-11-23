"""Filter and rank the registered treatments for the farmer's situation, with a transparent score written in code.

  rank(usages, ctx, n=3) -> {"retenus": [usage + "raisons"], "ecartes": [{"produit", "raisons"}], "n_candidats"}
  decisive_fields(usages, ctx, n=3) -> context fields still unknown whose answer would change the top n

usages: get_treatments() of the class and crop (already restricted to registered uses: the ranking never adds one).
ctx (every key optional): days_to_harvest (int), market (local | export), organic (y | n), stage (early | spread),
last_treatment_group ("FRAC 3"...), greenhouse (y | n), area (ha).

Filters (a filtered product is never shown; the farmer is told how many were set aside and why):
  - known DAR longer than days_to_harvest;
  - market export: a substance not approved in the EU, or of unknown EU status;
  - organic farm: a substance not allowed in organic farming (bio_ue).
Ranking, in this order (one key after the other, never a weighted sum):
  1. relation: direct or vecteur, then groupe, then proche (unchanged safety order of get_treatments);
  2. early stage: organic-allowed / biocontrol substances first;
  3. lower toxicity class (validated rows of docs/substance_hazard.csv; neutral until that table exists);
  4. shorter known DAR (an unknown DAR comes after every known one);
  5. a FRAC / IRAC group different from the last treatment (validated rows of docs/moa_groups.csv; neutral until then);
  6. product name (stable order).
One product appears once (its best use). Availability and price never enter the ranking.
Reasons and set-aside causes are codes: src/agent/redaction.py writes them in French or Arabic.
"""
import csv
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HAZARD = ROOT / "docs" / "substance_hazard.csv"
MOA = ROOT / "docs" / "moa_groups.csv"
FIELDS = ("days_to_harvest", "market", "organic", "stage", "last_treatment_group")  # order of the questions
TIER = {"direct": 0, "vecteur": 0, "groupe": 1, "proche": 2}
HAZARD_ORDER = {"U": 0, "III": 1, "II": 2, "Ib": 3, "Ia": 4}
ALTERNATIVES = {"days_to_harvest": [1, 7, 14, 30], "market": ["local", "export"], "organic": ["n", "y"],
                "stage": ["early", "spread"]}


def _validated(path, key, value):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r[key].strip().lower(): r[value].strip() for r in csv.DictReader(f)
                if r.get("status") == "validated" and r.get(value)}


@lru_cache(maxsize=1)
def _hazard():
    return _validated(HAZARD, "substance", "classe_oms")


@lru_cache(maxsize=1)
def _moa():
    return _validated(MOA, "substance", "groupe")


def _substances(u):
    return [s.strip().lower() for s in str(u.get("substances") or "").split("+") if s.strip()]


def hazard_rank(u):
    """Worst WHO class of the substances (0 = U ... 4 = Ia), None when one is unknown."""
    ranks = [HAZARD_ORDER.get(_hazard().get(s)) for s in _substances(u)]
    return None if not ranks or None in ranks else max(ranks)


def moa_groups(u):
    return {_moa()[s] for s in _substances(u) if s in _moa()}


def set_aside(u, ctx, known_dars=()):
    """Causes that exclude this use for the farmer's situation (codes), empty when it fits. known_dars: the known
    DARs of the other uses of the same product (a use without DAR is set aside when every known one is too long)."""
    out = []
    dth = ctx.get("days_to_harvest")
    if dth is not None and ((u["dar_jours"] is not None and u["dar_jours"] > dth)
                            or (u["dar_jours"] is None and known_dars and min(known_dars) > dth)):
        out.append("dar_long")
    if ctx.get("market") == "export":
        if u.get("ue_approuve") is False:
            out.append("non_ue")
        elif u.get("ue_approuve") is None:
            out.append("ue_inconnu")
    if ctx.get("organic") == "y" and not u.get("bio_ue"):
        out.append("non_bio")
    return out


def _key(u, ctx):
    early_bio = 0 if ctx.get("stage") == "early" and u.get("bio_ue") else 1
    h = hazard_rank(u)
    last = ctx.get("last_treatment_group")
    groups = moa_groups(u)
    rotation = 1 if not last or not groups else (2 if last in groups else 0)
    return (TIER.get(u["relation"], 3), early_bio, 2.5 if h is None else h,
            u["dar_jours"] if u["dar_jours"] is not None else 10**6, rotation, u["produit"])


def reasons(u, ctx):
    """Why this product is in the top: codes with their values, in the order of the ranking."""
    out = [("relation", u["relation"])]
    if u.get("bio_ue"):
        out.append(("bio_debut",) if ctx.get("stage") == "early" else ("bio",))
    h = hazard_rank(u)
    if h is not None:
        out.append(("toxicite", max((_hazard().get(s) for s in _substances(u)), key=HAZARD_ORDER.get)))
    if u["dar_jours"] is not None:
        out.append(("dar", u["dar_jours"], ctx.get("days_to_harvest")))
    if ctx.get("market") == "export" and u.get("ue_approuve"):
        out.append(("ue",))
    last, groups = ctx.get("last_treatment_group"), moa_groups(u)
    if last and groups and last not in groups:
        out.append(("rotation", " + ".join(sorted(groups)), last))
    return out


def rank(usages, ctx=None, n=3):
    ctx = ctx or {}
    kept, aside, seen = [], {}, set()
    dars = {}
    for u in usages:
        if u["dar_jours"] is not None:
            dars.setdefault(u["produit"], []).append(u["dar_jours"])
    for u in sorted(usages, key=lambda u: _key(u, ctx)):
        causes = set_aside(u, ctx, dars.get(u["produit"], ()))
        if causes:
            aside.setdefault(u["produit"], causes)
            continue
        if u["produit"] in seen:
            continue
        seen.add(u["produit"])
        kept.append(dict(u, raisons=reasons(u, ctx)))
    # a product set aside for one use but kept through another use is not "set aside"
    ecartes = [{"produit": p, "raisons": c} for p, c in aside.items() if p not in seen]
    return {"retenus": kept[:n], "ecartes": ecartes, "n_candidats": len({u["produit"] for u in usages})}


def decisive_fields(usages, ctx=None, n=3):
    """Unknown context fields whose answer would change the products shown (at most 3, in the order of FIELDS)."""
    ctx = ctx or {}
    out = []
    for f in FIELDS:
        if ctx.get(f) is not None:
            continue
        if f == "last_treatment_group":
            values = sorted({g for u in usages for g in moa_groups(u)})  # nothing to compare without groups
        else:
            values = ALTERNATIVES[f]
        tops = {tuple(u["produit"] for u in rank(usages, dict(ctx, **{f: v}), n)["retenus"]) for v in values}
        tops.add(tuple(u["produit"] for u in rank(usages, ctx, n)["retenus"]))
        if len(tops) > 1:
            out.append(f)
    return out[:3]
