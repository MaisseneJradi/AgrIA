"""Temperature scaling and abstention thresholds (step 7 of the improvement plan).

A deployed model is too sure of itself on field photos (ECE 0.14 for diseases and leaf: mean confidence 93 % for
78-80 % right answers). Temperature scaling divides the logits by one number T > 1 fitted on the FIELD validation
photos (val_field, never test): the predicted class does not change, only the confidence. Then, for each threshold,
the share of photos the agent answers (coverage) and the accuracy of those answers, to re-check the agent thresholds
(0.9 diseases, 0.95 deficiency, 0.9 router).

T and the proposed threshold are chosen on the calibration split; the test split only shows what they give.
Logits are cached in reports/temperature/<model>/logits_<split>.npz (recomputed with --refresh).

Usage:
  python src/evaluation/temperature.py --task diseases                      # models/diseases, val_field -> test_field
  python src/evaluation/temperature.py --task deficiency --calib val --test test
  python src/evaluation/temperature.py --task diseases --model-dir models/diseases_v3 --target 0.95
Output: reports/temperature/<model>/summary.json and summary.md (nothing is changed in models/).
"""
import argparse
import json
import os
import sys

import numpy as np
import torch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "vision"))
sys.path.insert(0, os.path.dirname(__file__))

THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98)
AGENT = {"routing": 0.9, "diseases": 0.8, "leaf": 0.9, "deficiency": 0.95, "fruits": 0.65, "crop": 0.9}


def softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def nll(logits, y, t=1.0):
    p = softmax(logits / t)
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-12, None)).mean())


def fit_temperature(logits, y, lo=0.05, hi=20.0):
    """T > 0 minimising the negative log-likelihood of the true classes (LBFGS on log T, started at 1)."""
    z = torch.tensor(logits, dtype=torch.float64)
    t = torch.tensor(y, dtype=torch.long)
    log_t = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200, line_search_fn="strong_wolfe")

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(z / log_t.exp(), t)
        loss.backward()
        return loss

    opt.step(closure)
    return float(np.clip(log_t.exp().item(), lo, hi))


def ece(conf, correct, bins=15):
    from calibrate import ece as _ece
    return _ece(np.asarray(conf), np.asarray(correct, dtype=float), bins)


def coverage(conf, correct, thresholds=THRESHOLDS):
    """For each threshold: share of photos answered and accuracy of the answered ones."""
    rows = []
    for th in thresholds:
        m = conf >= th
        rows.append({"threshold": th, "coverage": round(float(m.mean()), 4),
                     "accuracy_kept": round(float(correct[m].mean()), 4) if m.any() else None,
                     "errors_caught": round(float((~correct & ~m).sum() / max(1, (~correct).sum())), 4)})
    return rows


def propose(conf, correct, target, floor=0.5):
    """Lowest threshold (0.01 steps, >= floor) whose answered photos are right at least `target` of the time."""
    for th in np.round(np.arange(floor, 1.0, 0.01), 2):
        m = conf >= th
        if m.sum() >= 20 and correct[m].mean() >= target:
            return float(th)
    return None


def scores(logits, y, t):
    p = softmax(logits / t)
    conf, correct = p.max(1), p.argmax(1) == y
    return {"n": int(len(y)), "accuracy": round(float(correct.mean()), 4), "mean_conf": round(float(conf.mean()), 4),
            "ece": ece(conf, correct), "nll": round(nll(logits, y, t), 4)}, conf, correct


def logits_for(task, split, folder, out_dir, refresh=False, batch=64, workers=0):
    """(logits, true class indices) of every photo of `split`, cached."""
    cache = os.path.join(out_dir, f"logits_{split}.npz")
    if os.path.exists(cache) and not refresh:
        d = np.load(cache)
        return d["logits"], d["y"]
    from torch.utils.data import DataLoader
    from dataset import ManifestDataset
    from evaluate import load_model
    dev = os.environ.get("AGRIA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(dev)
    net, classes = load_model(folder, device)
    ds = ManifestDataset(task, split, classes, size=net.input_size)
    out, ys = [], []
    with torch.no_grad():
        for x, y in DataLoader(ds, batch, num_workers=workers):
            out.append(net(x.to(device)).float().cpu().numpy())
            ys.append(y.numpy())
    logits, y = np.concatenate(out), np.concatenate(ys)
    os.makedirs(out_dir, exist_ok=True)
    np.savez_compressed(cache, logits=logits, y=y)
    return logits, y


def run(task, folder, calib, test, target, refresh=False):
    name = os.path.basename(os.path.normpath(folder))
    out_dir = os.path.join(ROOT, "reports", "temperature", name)
    lc, yc = logits_for(task, calib, folder, out_dir, refresh)
    lt, yt = logits_for(task, test, folder, out_dir, refresh)
    t = fit_temperature(lc, yc)
    res = {"task": task, "model": name, "calib_split": calib, "test_split": test, "temperature": round(t, 4),
           "agent_threshold": AGENT.get(task), "target": target}
    for tag, temp in (("before", 1.0), ("after", t)):
        sc, cc, okc = scores(lc, yc, temp)
        st, ct, okt = scores(lt, yt, temp)
        res[tag] = {"calib": sc, "test": st, "coverage_test": coverage(ct, okt)}
        th = propose(cc, okc, target)
        m = ct >= th if th is not None else np.zeros_like(okt)
        res[tag]["proposed_threshold"] = th
        res[tag]["proposed_on_test"] = {"coverage": round(float(m.mean()), 4),
                                        "accuracy_kept": round(float(okt[m].mean()), 4) if m.any() else None}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(markdown(res))
    return res


def markdown(r):
    b, a = r["before"], r["after"]
    md = [f"# Température : {r['model']} ({r['task']})", "",
          f"T = {r['temperature']} ajustée sur {r['calib_split']}, mesurée sur {r['test_split']}.", "",
          "| | exactitude | confiance moyenne | ECE | NLL |", "|---|---|---|---|---|"]
    for tag, s in (("avant (T = 1)", b), (f"après (T = {r['temperature']})", a)):
        md.append(f"| {tag} | {s['test']['accuracy']:.1%} | {s['test']['mean_conf']:.1%} | {s['test']['ece']} | "
                  f"{s['test']['nll']} |")
    md += ["", f"Couverture et exactitude des réponses données sur {r['test_split']}, selon le seuil :", "",
           "| seuil | couverture avant | exactitude avant | couverture après | exactitude après |",
           "|---|---|---|---|---|"]
    for x, y in zip(b["coverage_test"], a["coverage_test"]):
        mark = " ← seuil actuel" if r["agent_threshold"] == x["threshold"] else ""
        fmt = lambda v: "-" if v is None else f"{v:.1%}"  # noqa: E731
        md.append(f"| {x['threshold']}{mark} | {fmt(x['coverage'])} | {fmt(x['accuracy_kept'])} | "
                  f"{fmt(y['coverage'])} | {fmt(y['accuracy_kept'])} |")
    md += ["", f"Seuil proposé (le plus bas dont les réponses sont justes à ≥ {r['target']:.0%} sur "
               f"{r['calib_split']}) :"]
    for tag, s in (("avant", b), ("après", a)):
        p = s["proposed_on_test"]
        md.append(f"- {tag} : {s['proposed_threshold']} → sur {r['test_split']} couverture "
                  f"{p['coverage']:.1%}, exactitude {'-' if p['accuracy_kept'] is None else format(p['accuracy_kept'], '.1%')}")
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--model-dir", default=None)
    ap.add_argument("--calib", default="val_field")
    ap.add_argument("--test", default="test_field")
    ap.add_argument("--target", type=float, default=0.95)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    r = run(a.task, a.model_dir or os.path.join(ROOT, "models", a.task), a.calib, a.test, a.target, a.refresh)
    print(markdown(r))


if __name__ == "__main__":
    main()
