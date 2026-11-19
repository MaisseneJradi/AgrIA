"""Evaluation of the combinations used by the agents, on every test set, against each model alone.

Usage:
  python src/agent/eval_ensemble.py --tune         learn the weights on the VALIDATION sets, save
                                                   models/ensemble_weights.json, then evaluate on the test sets
  python src/agent/eval_ensemble.py                evaluate with the saved weights
Options: --per-class N (images per class in the lab sets, default 6), --refresh (recompute the opinions),
         --vlm (ask the NVIDIA VLM too: needs NVIDIA_API_KEY; answers cached, a photo is never sent twice)

Sets (truth: crop, kind = deficiency or not, class when known):
  validation   lab val (N per class of the leaf task) + field val (287 PlantDoc photos held out of train)
  test         lab test (N per class) ; field test (199 PlantDoc) ; test images of the sources added for the crop
               model (olive Turkey and webcam, lemon, CitrusUAT, tomato sets) ; the app journal (Internet photos)
Measures, for each opinion alone and for the combination:
  crop    right crop, and crops wrong with confidence >= 0.85 (the dangerous errors)
  kind    deficiency vs disease/healthy right
  class   right deficiency (deficiency photos), right disease given the true crop (disease photos), and the full chain
          (crop chosen by the vote -> kind -> class)
Output: printed tables and docs/eval_ensemble.md. Opinions are cached in data/processed/eval_opinions/.
"""
import argparse
import itertools
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("AGRIA_DEVICE", "cpu")
from src.agent import ensemble as E  # noqa: E402
from src.agent import vlm  # noqa: E402
from src.agent.paths import ROOT  # noqa: E402
from dataset import load_split, local_path  # noqa: E402  (src/vision)

CACHE = ROOT / "data" / "processed" / "eval_opinions"
SURE = 0.85
JOURNAL_TRUTH = {  # file name prefix -> (crop, deficiency?)
    "tomato-septoria": ("tomato", False), "Citrus_canker_X": ("citrus", False), "citrus-scab": ("citrus", False),
    "Cercospora leaf": ("olive", False), "olive-leaf-spot": ("olive", False), "hojas-amarillas": ("olive", True),
    "images (3)": ("tomato", True), "images (4)": ("tomato", True), "bacterial-spot-a": ("tomato", False),
    "Citrus-Canker-S": ("citrus", False), "images (5)": ("citrus", True), "la-carence-en-fe": ("citrus", True),
    "téléchargement": ("pepper", True), "images (6)": ("citrus", True), "images (7)": ("olive", False)}


def _rows(df, origin):
    out = []
    for r in df.to_dict("records"):  # not itertuples: it renames the column "class" (a Python keyword)
        crop = E.ALIASES.get(r["crop"], r["crop"])
        crop = crop if crop in E.CROPS else "autre_plante"
        cls = r.get("class")
        cls = cls if isinstance(cls, str) else None
        out.append({"path": r["path"], "set": origin, "crop": crop, "deficiency": bool(cls) and cls.endswith("_deficiency"),
                    "cls": cls if cls and ("__" in cls or cls.endswith("_deficiency")) else None})
    return out


def _sample(df, n, seed=42):
    return df.groupby("class", group_keys=False).apply(lambda g: g.sample(min(n, len(g)), random_state=seed))


def build_sets(per_class):
    sets = {
        "val_labo": _rows(_sample(load_split("leaf", "val"), per_class), "val_labo"),
        "val_terrain": _rows(load_split("leaf", "val_field"), "val_terrain"),
        "test_labo": _rows(_sample(load_split("leaf", "test"), per_class), "test_labo"),
        "test_terrain": _rows(load_split("leaf", "test_field"), "test_terrain"),
    }
    extra = ROOT / "data" / "processed" / "crop_manifest.csv"
    if extra.exists():
        x = pd.read_csv(extra)
        x = x[x["split"] == "test"].copy()
        x["path"] = x["path"].map(local_path)
        x["class"] = None
        sets["test_nouvelles_sources"] = [dict(r, cls=None, deficiency=False) for r in
                                          _rows(x.groupby("source", group_keys=False).apply(
                                              lambda g: g.sample(min(len(g), 6 * per_class), random_state=42)),
                                              "test_nouvelles_sources")]
    journal, seen = [], set()
    for f in sorted((ROOT / "data" / "journal").glob("*.json")):
        name = json.load(open(f, encoding="utf-8"))["entree"].get("fichier") or ""
        truth = next((v for k, v in JOURNAL_TRUTH.items() if name.startswith(k)), None)
        if truth and name not in seen:
            seen.add(name)
            journal.append({"path": str(f).replace(".json", ".jpg"), "set": "journal", "crop": truth[0],
                            "deficiency": truth[1], "cls": None})
    sets["journal"] = journal
    return sets


def gather(rows, name, use_vlm, refresh):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{name}__{os.environ.get('AGRIA_CROP_MODEL', 'crop')}.json"  # one cache per crop model
    cache = {} if refresh or not f.exists() else json.load(open(f, encoding="utf-8"))
    if use_vlm:  # ask the VLM first, 4 photos at a time (its answers are cached, then read back by E.opinions)
        todo = [r["path"] for r in rows if (cache.get(r["path"]) or {}).get("vlm") is None]
        with ThreadPoolExecutor(int(os.environ.get("AGRIA_VLM_WORKERS", "4"))) as pool:
            for i, _ in enumerate(pool.map(vlm.observe, todo)):
                if (i + 1) % 25 == 0:
                    print(f"   {name} VLM: {i + 1}/{len(todo)}", flush=True)
    for i, r in enumerate(rows):
        op = cache.get(r["path"])
        if op is None or (use_vlm and op.get("vlm") is None):
            op = E.opinions(r["path"], use_vlm=use_vlm)
            if use_vlm and op.get("vlm") is None:
                print("   VLM :", vlm.observe.last_error)
            cache[r["path"]] = op
            if use_vlm:
                time.sleep(0.3)
        r["op"] = op
        if (i + 1) % 100 == 0:
            print(f"   {name}: {i + 1}/{len(rows)}")
    json.dump(cache, open(f, "w", encoding="utf-8"))
    return rows


def crop_scores(rows, w):
    res = {}
    for key in ("crop", "leaf", "diseases", "vlm"):
        right, sure_wrong, n = 0, 0, 0
        for r in rows:
            d = E.crop_distributions(r["op"]).get(key)
            if d is None:
                continue
            c = max(d, key=d.get)
            n += 1
            right += c == r["crop"]
            sure_wrong += c != r["crop"] and d[c] >= SURE
        if n:
            res[key] = (right / n, sure_wrong / n, n)
    right = sure_wrong = 0
    for r in rows:
        v = E.crop_vote(r["op"], w)
        right += v["culture"] == r["crop"]
        sure_wrong += v["culture"] != r["crop"] and v["confiance"] >= SURE
    res["combinaison"] = (right / len(rows), sure_wrong / len(rows), len(rows))
    if any(r["op"].get("vlm") for r in rows):  # rule used by the agent: vote + VLM as check and fallback
        dec = [(E.crop_decision(r["op"], w), r["crop"]) for r in rows]
        res["décision (vote + contrôle VLM)"] = (sum(v["culture"] == c for v, c in dec) / len(rows),
                                                 sum(v["culture"] != c and v["sure"] for v, c in dec) / len(rows),
                                                 len(rows))
    return res


def kind_scores(rows, w):
    res = {}
    for name, ww in (("leaf seul", {**w, "kind": {"leaf": 1.0, "vlm": 0.0}}),
                     ("vlm seul", {**w, "kind": {"leaf": 0.0, "vlm": 1.0}}), ("combinaison", w)):
        ok = [(E.kind_share(r["op"], ww) >= 0.5) == r["deficiency"] for r in rows
              if not (name == "vlm seul" and not (r["op"].get("vlm") or {}).get("probleme"))]
        if ok:
            res[name] = (sum(ok) / len(ok), len(ok))
    return res


def class_scores(rows, w):
    res = {}
    defi = [r for r in rows if r["cls"] and r["deficiency"]]
    dis = [r for r in rows if r["cls"] and not r["deficiency"]]
    for name, ww in (("leaf seul", {"leaf": 1.0, "deficiency": 0.0}), ("deficiency seul", {"leaf": 0.0, "deficiency": 1.0}),
                     ("combinaison", w["deficiency"])):
        ok = [max(p, key=p.get) == r["cls"] for r in defi if (p := E.deficiency_probs(r["op"], {**w, "deficiency": ww}))]
        if ok:
            res[f"carence / {name}"] = (sum(ok) / len(ok), len(ok))
    for name, ww in (("diseases seul", {"diseases": 1.0, "leaf": 0.0}), ("leaf seul", {"diseases": 0.0, "leaf": 1.0}),
                     ("combinaison", w["disease"])):
        ok = [max(p, key=p.get) == r["cls"] for r in dis if (p := E.disease_probs(r["op"], r["crop"], {**w, "disease": ww})[0])]
        if ok:
            res[f"maladie (vraie culture) / {name}"] = (sum(ok) / len(ok), len(ok))
    chain = []
    for r in [x for x in rows if x["cls"]]:
        crop = E.crop_vote(r["op"], w)["culture"]
        if E.kind_share(r["op"], w) >= 0.5:
            p = E.deficiency_probs(r["op"], w)
        else:
            p, _ = E.disease_probs(r["op"], crop, w)
        chain.append(bool(p) and max(p, key=p.get) == r["cls"])
    if chain:
        res["chaîne complète (culture votée -> type -> classe)"] = (sum(chain) / len(chain), len(chain))
    return res


def tune(val_rows, has_vlm):
    """Weights maximising, on the validation sets: crop right - 2 x sure-wrong ; kind ; class."""
    best = json.loads(json.dumps(E.DEFAULT_WEIGHTS))
    grid = [0.0, 0.25, 0.5, 1.0, 2.0]
    vlm_grid = grid if has_vlm else [0.0]

    def crop_obj(w):
        s = crop_scores(val_rows, w)["combinaison"]
        return s[0] - 2 * s[1]
    best["crop"] = max(({"crop": 1.0, "leaf": a, "diseases": b, "vlm": c} for a, b, c in itertools.product(grid, grid, vlm_grid)),
                       key=lambda cw: crop_obj({**best, "crop": cw}))
    best["kind"] = max(({"leaf": 1.0, "vlm": c} for c in vlm_grid),
                       key=lambda kw: kind_scores(val_rows, {**best, "kind": kw})["combinaison"][0])
    best["disease"] = max(({"diseases": 1.0, "leaf": a} for a in grid),
                          key=lambda dw: class_scores(val_rows, {**best, "disease": dw}).get(
                              "maladie (vraie culture) / combinaison", (0,))[0])
    best["deficiency"] = max(({"leaf": 1.0, "deficiency": a} for a in grid),
                             key=lambda fw: class_scores(val_rows, {**best, "deficiency": fw}).get(
                                 "carence / combinaison", (0,))[0])
    return best


def fmt(res):
    lines = []
    for k, v in res.items():
        if len(v) == 3:
            lines.append(f"| {k} | {v[0]:.1%} | {v[1]:.1%} | {v[2]} |")
        else:
            lines.append(f"| {k} | {v[0]:.1%} | — | {v[1]} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--vlm", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--per-class", type=int, default=6)
    a = ap.parse_args()
    if a.vlm and not vlm._key():
        sys.exit("NVIDIA_API_KEY absente : la définir dans D:\\AgrIA\\.env")
    sets = build_sets(a.per_class)
    for name, rows in sets.items():
        print(f"{name}: {len(rows)} photos")
        gather(rows, name, a.vlm, a.refresh)
    w = E.weights()
    if a.tune:
        w = tune(sets["val_labo"] + sets["val_terrain"], a.vlm)
        E.WEIGHTS_FILE.parent.mkdir(exist_ok=True)
        json.dump({"weights": w, "vlm": a.vlm, "per_class": a.per_class,
                   "learnt_on": ["val_labo", "val_terrain"], "date": time.strftime("%Y-%m-%d %H:%M")},
                  open(E.WEIGHTS_FILE, "w", encoding="utf-8"), indent=1)
        print("poids appris sur la validation :", json.dumps(w))
    report = [f"# Évaluation des combinaisons de modèles\n\nModèle de culture : `{os.environ.get('AGRIA_CROP_MODEL', 'crop')}`"
              f" · Poids : `{json.dumps(w)}` · VLM : {'oui' if a.vlm else 'non'}"
              f" · {time.strftime('%Y-%m-%d %H:%M')}\n"]
    for name, rows in sets.items():
        if name.startswith("val"):
            continue
        report.append(f"\n## {name} ({len(rows)} photos)\n\n| Culture | juste | fausse et sûre (≥ 85 %) | n |\n|---|---|---|---|\n"
                      + fmt(crop_scores(rows, w)))
        report.append("\n\n| Carence ou maladie | juste | | n |\n|---|---|---|---|\n" + fmt(kind_scores(rows, w)))
        cs = class_scores(rows, w)
        if cs:
            report.append("\n\n| Classe | juste | | n |\n|---|---|---|---|\n" + fmt(cs))
    text = "\n".join(report) + "\n"
    print(text)
    (ROOT / "docs" / os.environ.get("AGRIA_EVAL_OUT", "eval_ensemble.md")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
