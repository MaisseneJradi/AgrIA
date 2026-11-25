"""Agent thresholds measured on the confidence the Diagnostic agent really uses (step 7 of the improvement plan).

The agent does not read one model's softmax: src/agent/agents/diagnostic.py combines models (src/agent/ensemble.py).
  - disease photos: confidence = top class of E.disease_probs(opinions, crop) (disease and leaf models averaged,
    restricted to the farmer's crop); compared with AGENT_THRESHOLDS["diseases"];
  - deficiency photos: the kind share s = E.kind_share(opinions, crop); if s >= 0.5 the answer is a deficiency with
    confidence = top class of E.deficiency_probs(opinions) x s; compared with AGENT_THRESHOLDS["deficiency"].
For each threshold: coverage (share of photos answered with trust), accuracy of those answers, and share of photos
answered WRONG with trust (the error that matters for a farmer).

Disease photos: the field splits (val_field, test_field) through the opinions cached by src/agent/eval_ensemble.py
(VLM included). Deficiency photos: every lab deficiency photo of the leaf val and test splits, leaf and deficiency models
(no VLM: the VLM was not asked on these 3,700 photos), so a leaf model can be compared with another on the same
photos (--leaf-dirs).

Usage:
  python src/evaluation/agent_thresholds.py deficiency --leaf-dirs models/_replaced_2026-11-22/leaf models/leaf          --weights models/_replaced_2026-11-22/ensemble_weights_apres_diseases_s300.json -
  python src/evaluation/agent_thresholds.py diseases
Output: reports/temperature/agent_threshold_<kind>.json (and the tables printed).
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "src", "vision")]
THS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95)


def deficiency_answer(op, crop, w):
    """(class, confidence) the agent gives a leaf photo when it decides 'deficiency', or (None, 0.0) when it sends
    the photo to the disease branch."""
    from src.agent import ensemble as E
    share = E.kind_share(op, w, crop=crop)
    if share < 0.5:
        return None, 0.0
    probs = E.deficiency_probs(op, w)
    cls, p = max(probs.items(), key=lambda kv: kv[1])
    return cls, p * share


def disease_answer(op, crop, w):
    from src.agent import ensemble as E
    probs, _ = E.disease_probs(op, crop, w)
    if not probs:
        probs, _ = E.disease_probs(op, None, w)
    return max(probs.items(), key=lambda kv: kv[1])


def table(conf, ok, ths=THS):
    """{threshold: (coverage, accuracy of the answered, share answered wrong)} over all photos."""
    conf, ok = np.asarray(conf, dtype=float), np.asarray(ok, dtype=bool)
    out = {}
    for t in ths:
        m = conf >= t
        out[t] = (round(float(m.mean()), 4), round(float(ok[m].mean()), 4) if m.any() else None,
                  round(float((m & ~ok).mean()), 4))
    return out


def _crop(c):
    from src.agent import ensemble as E
    c = E.ALIASES.get(c, c)
    return c if c in E.CROPS else None


def _load_weights(path):
    from src.agent import ensemble as E
    if not path:
        return E.weights()
    with open(path, encoding="utf-8") as f:
        return json.load(f)["weights"]


def deficiency(leaf_dirs, weight_files=None, device="cpu", batch=32):
    """Each leaf model with its weights file (default: the current models/ensemble_weights.json); the deficiency model
    (models/deficiency) is included as in the agent, with the weight the file gives it."""
    import torch
    from dataset import ManifestDataset
    from evaluate import load_model, predict_all
    dev, res = torch.device(device), {}
    weight_files = weight_files or [None] * len(leaf_dirs)
    dnet, dcls = load_model(os.path.join(ROOT, "models", "deficiency"), dev)
    dprobs = {}
    for folder, wf in zip(leaf_dirs, weight_files):
        w = _load_weights(wf)
        net, classes = load_model(folder, dev)
        for split in ("val", "test"):
            ds = ManifestDataset("leaf", split, classes, size=net.input_size)
            ds.df = ds.df[ds.df["class"].str.endswith("_deficiency")].reset_index(drop=True)
            probs = predict_all(net, ds, dev, batch, 0)
            if split not in dprobs:
                dd = ManifestDataset("leaf", split, dcls, size=getattr(dnet, "input_size", 224))
                dd.df = ds.df
                dprobs[split] = predict_all(dnet, dd, dev, batch, 0)
            conf, ok = [], []
            for i, r in ds.df.iterrows():
                op = {"leaf": dict(zip(classes, probs[i].tolist())),
                      "deficiency": dict(zip(dcls, dprobs[split][i].tolist()))}
                cls, c = deficiency_answer(op, _crop(r["crop"]), w)
                conf.append(c)
                ok.append(cls == r["class"])
            res[f"{split}|{folder}|{wf or 'models/ensemble_weights.json'}"] = {"n": len(ds.df), "table": table(conf, ok)}
    return res


def diseases():
    from dataset import load_split
    from src.agent import ensemble as E
    w, res = E.weights(), {}
    for name, split in (("val_terrain", "val_field"), ("test_terrain", "test_field")):
        ops = json.load(open(os.path.join(ROOT, "data", "processed", "eval_opinions", f"{name}__crop.json"),
                             encoding="utf-8"))
        conf, ok = [], []
        for r in load_split("diseases", split).to_dict("records"):
            op = ops.get(r["path"])
            if op is None:
                continue
            cls, c = disease_answer(op, r["class"].split("__")[0], w)
            conf.append(c)
            ok.append(cls == r["class"])
        res[name] = {"n": len(conf), "table": table(conf, ok)}
    return res


def show(res):
    for k, v in res.items():
        print(f"{k} ({v['n']} photos)")
        for t, (cov, acc, wrong) in v["table"].items():
            print(f"   {t}: répondues {cov:.1%}  justes {'-' if acc is None else format(acc, '.1%')}  "
                  f"fausses données {wrong:.1%}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=("deficiency", "diseases"))
    ap.add_argument("--leaf-dirs", nargs="+", default=[os.path.join(ROOT, "models", "leaf")])
    ap.add_argument("--weights", nargs="+", default=None, help="one ensemble weights file per leaf model ('-' = current)")
    ap.add_argument("--device", default=os.environ.get("AGRIA_DEVICE", "cpu"))
    a = ap.parse_args()
    wf = [None if x == "-" else x for x in a.weights] if a.weights else None
    res = deficiency(a.leaf_dirs, wf, a.device) if a.kind == "deficiency" else diseases()
    show(res)
    out = os.path.join(ROOT, "reports", "temperature", f"agent_threshold_{a.kind}_{'leaf_s300' if a.kind else ''}.json")
    out = os.path.join(ROOT, "reports", "temperature", f"agent_threshold_{a.kind}.json") if a.kind == "deficiency" \
        else os.path.join(ROOT, "reports", "temperature", "agent_threshold_diseases_leaf_s300.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
