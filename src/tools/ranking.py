"""Filter and rank the registered treatments for the farmer's situation, with a transparent score written in code.

  rank(usages, ctx, n=3) -> {"retenus": [usage + "raisons"], "ecartes": [{"produit", "raisons"}], "n_candidats",
                             "dernier_groupe": groups of the last treatment, "rotation_impossible": bool}
  decisive_fields(usages, ctx, n=3) -> context fields still unknown whose answer would change the top n
  last_groups(text) -> FRAC / IRAC groups of the last treatment written by the farmer ("FRAC 3", "IRAC 4A", a product
                       of the list, an active substance), from the validated rows of docs/moa_groups.csv

usages: get_treatments() of the class and crop (already restricted to registered uses: the ranking never adds one).
ctx (every key optional): days_to_harvest (int), market (local | export), organic (y | n), stage (early | spread),
last_treatment_group (text), greenhouse (y | n), area (ha).

Filters (a filtered product is never shown; the farmer is told how many were set aside and why):
  - known DAR longer than days_to_harvest;
  - market export: a substance not approved in the EU, or of unknown EU status;
  - organic farm: a substance not allowed in organic farming (bio_ue);
  - resistance (phyto step 4): a product sharing a group with the last treatment, when another product of the case
    has known groups and shares none ("an alternative exists"). Groups with a low or unknown resistance risk are never
    a reason (FRAC M multi-site, BM biologicals, P host defence inducers, U unknown; IRAC UN). With no alternative the
    product stays and the answer says so (rotation_impossible).
Ranking, in this order (one key after the other, never a weighted sum):
  1. relation: direct or vecteur, then groupe, then proche (unchanged safety order of get_treatments);
  2. early stage: organic-allowed / biocontrol substances first;
  3. lower toxicity class (validated rows of docs/substance_hazard.csv; neutral until that table exists);
  4. shorter known DAR (an unknown DAR comes after every known one);
  5. groups known and different from the last treatment, then unknown groups;
  6. product name (stable order).
One product appears once (its best use). Availability and price never enter the ranking.
Reasons and set-aside causes are codes: src/agent/redaction.py writes them in French or Arabic.
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

from common import fold, query

ROOT = Path(__file__).resolve().parents[2]
HAZARD = ROOT / "docs" / "substance_hazard.csv"
MOA = ROOT / "docs" / "moa_groups.csv"
FIELDS = ("days_to_harvest", "market", "organic", "stage", "last_treatment_group")  # order of the questions
TIER = {"direct": 0, "vecteur": 0, "groupe": 1, "proche": 2}
HAZARD_ORDER = {"U": 0, "III": 1, "II": 2, "Ib": 3, "Ia": 4}
ALTERNATIVES = {"days_to_harvest": [1, 7, 14, 30], "market": ["local", "export"], "organic": ["n", "y"],
                "stage": ["early", "spread"]}
LOW_RISK = re.compile(r"^(FRAC (M\d*|BM\d*|P\d*|U\d*|NC)|IRAC (UN\w*|NC))$")
CODE = r"(bm\s*\d{1,2}|[mpu]\s*\d{1,2}|\d{1,2}[a-f]?|un|nc)"
# "FRAC 3", "irac 4a", "groupe M1"; a code alone only when it is the whole answer (never "il y a 10 jours")
GROUP_CODE = re.compile(r"\b(frac|irac|groupe?|group)\s*(?:groupe?\s*)?" + CODE + r"(?![a-z0-9])")
CODE_ALONE = re.compile(r"\s*" + CODE + r"\s*")


def _rows(path, statuses=("validated",)):
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") in statuses]


@lru_cache(maxsize=1)
def _hazard():
    return {r["substance"].strip().lower(): r["classe_oms"].strip() for r in _rows(HAZARD) if r.get("classe_oms")}


@lru_cache(maxsize=1)
def _moa():
    """substance (lower case) -> its FRAC / IRAC groups (a substance can have one of each, e.g. sulphur)."""
    out = {}
    for r in _rows(MOA):
        if r.get("groupe"):
            out.setdefault(r["substance"].strip().lower(), set()).add(r["groupe"].strip())
    return out


def _substances(u):
    return [s.strip().lower() for s in str(u.get("substances") or "").split("+") if s.strip()]


def hazard_rank(u):
    """Worst WHO class of the substances (0 = U ... 4 = Ia), None when one is unknown."""
    ranks = [HAZARD_ORDER.get(_hazard().get(s)) for s in _substances(u)]
    return None if not ranks or None in ranks else max(ranks)


def moa_groups(u):
    """Groups of the substances of a use; empty when one substance has no validated group (unknown)."""
    subs = _substances(u)
    if not subs or any(s not in _moa() for s in subs):
        return set()
    return {g for s in subs for g in _moa()[s]}


def low_risk(group):
    return bool(LOW_RISK.match(group))


def _normal_code(prefix, code):
    code = re.sub(r"\s+", "", code).upper()
    code = re.sub(r"^(BM|M|P|U)(\d)$", r"\g<1>0\2", code)  # "M1" -> "M01" as written by FRAC
    return [f"{p} {code}" for p in ([prefix.upper()] if prefix else ["FRAC", "IRAC"])]


@lru_cache(maxsize=1)
def _products():
    """folded trade name -> substances (EU names) of the products of the list."""
    return {fold(r["nom_commercial"]): r["substances_ue"] for r in query(
        "SELECT nom_commercial, substances_ue FROM pesticides_produits WHERE nom_commercial IS NOT NULL")}


def last_groups(text):
    """Groups of the last treatment: {"FRAC 3"} for "FRAC 3", "groupe 3" (FRAC 3 or IRAC 3), a product of the list or an
    active substance. Empty set when nothing is recognised (then nothing is set aside)."""
    return set(_last_groups(str(text or ""), id(_moa)))


@lru_cache(maxsize=512)
def _last_groups(text, _table):  # _table: the group table in use (a simulation swaps it)
    if not text:
        return frozenset()
    return frozenset(_read_last(text))


def _read_last(text):
    t = fold(text)
    name = _products().get(t) or next((s for n, s in _products().items() if len(n) >= 4 and
                                       re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", t)), None)
    if name:
        return moa_groups({"substances": name})
    subs = [s for s in _moa() if len(s) >= 5 and s in t]
    if subs:
        return {g for s in subs for g in _moa()[s]}
    m = GROUP_CODE.search(t)
    if m:
        return set(_normal_code(m.group(1) if m.group(1) in ("frac", "irac") else None, m.group(2)))
    m = CODE_ALONE.fullmatch(t)
    return set(_normal_code(None, m.group(1))) if m else set()


def shared_groups(groups, last):
    """Groups shared with the last treatment, low-risk groups left out; an IRAC '4' written by the farmer covers 4A."""
    out = set()
    for g in groups:
        if low_risk(g):
            continue
        for x in last:
            if g == x or (x.split()[0] == g.split()[0] and re.fullmatch(r"\d+", x.split()[1])
                          and re.fullmatch(x.split()[1] + r"[A-Z]", g.split()[1])):
                out.add(g)
    return out


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


def _key(u, ctx, last):
    early_bio = 0 if ctx.get("stage") == "early" and u.get("bio_ue") else 1
    h = hazard_rank(u)
    groups = moa_groups(u)
    rotation = 0 if not last else (1 if not groups else (2 if shared_groups(groups, last) else 0))
    return (TIER.get(u["relation"], 3), early_bio, 2.5 if h is None else h,
            u["dar_jours"] if u["dar_jours"] is not None else 10**6, rotation, u["produit"])


def reasons(u, ctx, last=frozenset()):
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
    groups = moa_groups(u)
    if groups:
        g, low = " + ".join(sorted(groups)), sorted(groups & last)  # shared groups (only low-risk ones can be kept)
        if last and low and not shared_groups(groups, last):
            out.append(("groupe_faible_risque", g, " + ".join(low)))
        elif last and not shared_groups(groups, last):
            out.append(("rotation", g, " + ".join(sorted(last))))
        else:
            out.append(("groupe", g))
    return out


def rank(usages, ctx=None, n=3):
    ctx = ctx or {}
    last = last_groups(ctx.get("last_treatment_group"))
    kept, aside, seen = [], {}, set()
    dars = {}
    for u in usages:
        if u["dar_jours"] is not None:
            dars.setdefault(u["produit"], []).append(u["dar_jours"])
    fitting = []
    for u in sorted(usages, key=lambda u: _key(u, ctx, last)):
        causes = set_aside(u, ctx, dars.get(u["produit"], ()))
        if causes:
            aside.setdefault(u["produit"], causes)
        else:
            fitting.append(u)
    # resistance: the same group as the last treatment only when no product of another known group fits the case
    repeat = {u["produit"] for u in fitting if shared_groups(moa_groups(u), last)}
    alternative = any(moa_groups(u) and u["produit"] not in repeat for u in fitting)
    for u in fitting:
        if u["produit"] in repeat and alternative:
            aside.setdefault(u["produit"], ["meme_groupe"])
            continue
        if u["produit"] in seen:
            continue
        seen.add(u["produit"])
        kept.append(dict(u, raisons=reasons(u, ctx, last)))
    # a product set aside for one use but kept through another use is not "set aside"
    ecartes = [{"produit": p, "raisons": c} for p, c in aside.items() if p not in seen]
    shown = kept[:n]
    return {"retenus": shown, "ecartes": ecartes, "n_candidats": len({u["produit"] for u in usages}),
            "dernier_groupe": sorted(last),
            "rotation_impossible": bool(last) and any(shared_groups(moa_groups(u), last) for u in shown)}


def decisive_fields(usages, ctx=None, n=3):
    """Unknown context fields whose answer would change the products shown (at most 3, in the order of FIELDS)."""
    ctx = ctx or {}
    out = []
    for f in FIELDS:
        if ctx.get(f) is not None:
            continue
        if f == "last_treatment_group":  # the groups of the products of the case (nothing to compare without groups)
            values = sorted({g for u in usages for g in moa_groups(u) if not low_risk(g)})
        else:
            values = ALTERNATIVES[f]
        tops = {tuple(u["produit"] for u in rank(usages, dict(ctx, **{f: v}), n)["retenus"]) for v in values}
        tops.add(tuple(u["produit"] for u in rank(usages, ctx, n)["retenus"]))
        if len(tops) > 1:
            out.append(f)
    return out[:3]
