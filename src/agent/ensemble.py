"""Combination of opinions used by the two agents that read the photo.

Opinions gathered once per photo (opinions()):
  crop       crop model (models/<AGRIA_CROP_MODEL>, default "crop"): 14 crops + autre_plante
  leaf       leaf model (models/leaf): 51 disease classes + 9 deficiencies
  diseases   disease model (models/diseases): 51 disease classes
  deficiency deficiency model (models/deficiency): 9 deficiencies + healthy
  vlm        NVIDIA VLM observer (src/agent/vlm.py), when AGRIA_VLM=nvidia and a key is set: crop + kind of problem

Agent Identification de la culture -> crop_vote(): weighted average of four crop distributions:
  the crop model; the leaf and disease models summed per crop (their classes are "<crop>__<disease>");
  the VLM (its crop with its confidence, the rest spread evenly). Agreement = how many opinions put the same crop first.
Agent Diagnostic -> kind_share() (deficiency or disease: share of deficiency of the leaf model and the VLM's kind of
  problem), then disease_probs() (disease and leaf models, restricted to the crop) or deficiency_probs() (leaf and
  deficiency models).
The weights are learnt on the VALIDATION sets by src/agent/eval_ensemble.py --tune and saved in
models/ensemble_weights.json; DEFAULT_WEIGHTS are used until then. Test sets never choose a weight.
"""
import json
import os

from src.agent import paths  # noqa: F401
from src.agent import vlm
from src.agent.paths import ROOT
from predict import probabilities  # src/vision

CROPS = ("apple", "cherry", "citrus", "corn", "datepalm", "grape", "olive", "peach", "pepper", "potato", "squash",
         "strawberry", "tomato", "wheat", "autre_plante")
ALIASES = {"orange": "citrus"}
DEFAULT_WEIGHTS = {"crop": {"crop": 1.0, "leaf": 0.5, "diseases": 0.5, "vlm": 1.0},
                   "kind": {"leaf": 1.0, "vlm": 1.0},
                   "disease": {"diseases": 1.0, "leaf": 1.0},
                   "deficiency": {"leaf": 1.0, "deficiency": 0.5}}
WEIGHTS_FILE = ROOT / "models" / "ensemble_weights.json"


def weights():
    if WEIGHTS_FILE.exists():
        with open(WEIGHTS_FILE, encoding="utf-8") as f:
            return json.load(f)["weights"]
    return DEFAULT_WEIGHTS


def crop_of(cls):
    if "__" not in cls:
        return None
    c = cls.split("__")[0]
    return ALIASES.get(c, c)


def _available(name):
    return (ROOT / "models" / name / "model.pt").exists()


def opinions(photo, use_vlm=None):
    """Every opinion on one photo (computed once, reused by both agents and by the evaluation)."""
    crop_model = os.environ.get("AGRIA_CROP_MODEL", "crop")
    op = {}
    for key, name in (("crop", crop_model), ("leaf", "leaf"), ("diseases", "diseases"), ("deficiency", "deficiency")):
        if _available(name):
            op[key] = probabilities(name, photo)
    use_vlm = vlm.enabled() if use_vlm is None else use_vlm
    op["vlm"] = vlm.observe(photo) if use_vlm else None
    return op


def _per_crop(probs):
    out = dict.fromkeys(CROPS, 0.0)
    for cls, p in probs.items():
        c = crop_of(cls)
        if c in out:
            out[c] += p
    s = sum(out.values())
    return {c: p / s for c, p in out.items()} if s > 0 else None


def _vlm_crop(v):
    if not v or not v.get("culture"):
        return None
    c, conf = v["culture"], v.get("conf_culture") or 0.5
    rest = (1 - conf) / (len(CROPS) - 1)
    return {k: (conf if k == c else rest) for k in CROPS}


def crop_distributions(op):
    d = {}
    if "crop" in op:
        d["crop"] = {c: op["crop"].get(c, 0.0) for c in CROPS}
    for key in ("leaf", "diseases"):
        if key in op:
            v = _per_crop(op[key])
            if v:
                d[key] = v
    v = _vlm_crop(op.get("vlm"))
    if v:
        d["vlm"] = v
    return d


def crop_vote(op, w=None):
    """{"probs", "top3", "culture", "confiance", "avis" (top crop of each opinion), "accord"}."""
    w = (w or weights())["crop"]
    dists = crop_distributions(op)
    total = sum(w.get(k, 0) for k in dists) or 1.0
    probs = {c: sum(w.get(k, 0) * d[c] for k, d in dists.items()) / total for c in CROPS}
    ranked = sorted(probs.items(), key=lambda kv: -kv[1])
    tops = {k: max(d, key=d.get) for k, d in dists.items()}
    return {"probs": probs, "top3": [[c, round(p, 4)] for c, p in ranked[:3]], "culture": ranked[0][0],
            "confiance": round(ranked[0][1], 4), "avis": tops,
            "accord": sum(t == ranked[0][0] for t in tops.values()), "n_avis": len(tops)}


SURE = 0.85          # vote confidence for a "sure" crop (same as ACCEPT of the Identification agent)
VLM_FALLBACK = 0.95  # VLM confidence needed to replace a vote that hesitates (0.9: 12 citrus leaves taken for olive)


def crop_decision(op, w=None):
    """Crop vote, then the VLM as a CHECK and as a FALLBACK (docs/eval_ensemble_vlm.md):
      - vote sure (>= SURE) but the VLM sees another crop -> the vote stays, but is no longer "sure"
        (confident wrong crops: field photos 2.0 % -> 1.0 %, Internet photos 26.7 % -> 0 %, nothing lost elsewhere);
      - vote unsure and the VLM sure (>= VLM_FALLBACK) of another crop -> the VLM's crop is proposed first, never "sure"
        (Internet photos 26.7 % -> 66.7 % right; cost: field 86.9 -> 85.4 %, lab 99.2 -> 98.6 %, new sources
        99.5 -> 96.8 %; the VLM's answers are coarse, 0.9 or 0.95, and at 0.9 it took 12 citrus leaves for olive);
      - the VLM's crop is always among the 3 proposals shown to the farmer.
    A fixed VLM weight in the vote was rejected by the validation (weight 0): the VLM is often sure and wrong on the
    lab photos (apple, cherry, peach, potato...), right on the olive and citrus photos of the Internet."""
    v = crop_vote(op, w)
    v.update(sure=v["confiance"] >= SURE, source="vote")
    vl = op.get("vlm") or {}
    vc = vl.get("culture")
    if vc not in CROPS or vc == "autre_plante":
        return v
    v["vlm_culture"] = vc
    if vc == v["culture"]:
        return v
    if v["sure"]:
        v.update(sure=False, desaccord_vlm=True)
    elif vl.get("conf_culture", 0) >= VLM_FALLBACK:
        v.update(culture=vc, confiance=vl["conf_culture"], source="vlm")
    if vc not in [c for c, _ in v["top3"][:1 if v["source"] == "vlm" else 3]]:
        rest = [t for t in v["top3"] if t[0] != vc]
        v["top3"] = [[vc, vl["conf_culture"]]] + rest[:2] if v["source"] == "vlm" else rest[:2] + [[vc, vl["conf_culture"]]]
    v["accord"] = sum(t == v["culture"] for t in v["avis"].values())
    return v


def kind_share(op, w=None, crop=None):
    """Probability that the problem is a deficiency (not a disease, a pest or a healthy leaf). With a crop, the leaf
    model's deficiencies are weighed against the disease classes of that crop only."""
    w = (w or weights())["kind"]
    parts = []
    if "leaf" in op:
        defi = sum(p for c, p in op["leaf"].items() if c.endswith("_deficiency"))
        other = sum(p for c, p in op["leaf"].items() if "__" in c and (crop is None or crop_of(c) == crop))
        if crop is None or other == 0:
            other = 1 - defi
        parts.append((w.get("leaf", 0), defi / max(defi + other, 1e-9)))
    v = op.get("vlm")
    if v and v.get("probleme"):
        conf = v.get("conf_probleme") or 0.5
        parts.append((w.get("vlm", 0), conf + (1 - conf) / 2 if v["probleme"] == "deficiency" else (1 - conf) / 2))
    total = sum(x for x, _ in parts)
    return sum(x * s for x, s in parts) / total if total else 0.0


def _restricted(probs, keep):
    sub = {c: p for c, p in probs.items() if keep(c)}
    s = sum(sub.values())
    return ({c: p / s for c, p in sub.items()}, s) if s > 0 else ({}, 0.0)


def disease_probs(op, crop=None, w=None):
    """Disease classes of the crop (all crops if None), leaf and disease models averaged; also the crop mass the disease
    model gives the photo (small = the photo hardly looks like that crop)."""
    w = (w or weights())["disease"]
    keep = (lambda c: "__" in c and crop_of(c) == crop) if crop else (lambda c: "__" in c)
    parts, mass = [], None
    for key in ("diseases", "leaf"):
        if key in op:
            sub, m = _restricted(op[key], keep)
            if sub:
                parts.append((w.get(key, 0), sub))
                if key == "diseases":
                    mass = m
    return _average(parts), mass


def deficiency_probs(op, w=None):
    w = (w or weights())["deficiency"]
    parts = []
    for key in ("leaf", "deficiency"):
        if key in op:
            sub, _ = _restricted(op[key], lambda c: c.endswith("_deficiency"))
            if sub:
                parts.append((w.get(key, 0), sub))
    return _average(parts)


def _average(parts):
    total = sum(x for x, _ in parts)
    if not total:
        return {}
    classes = set().union(*(d.keys() for _, d in parts))
    return {c: sum(x * d.get(c, 0.0) for x, d in parts) / total for c in classes}


def top(probs, n=3):
    ranked = sorted(probs.items(), key=lambda kv: -kv[1])[:n]
    return [[c, round(p, 4)] for c, p in ranked]
