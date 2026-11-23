"""New model against the deployed one, on the SAME photos (rule 5 of the improvement plan).

Reads predictions_test.csv (lab) and predictions_test_field.csv (field) of both folders (src/vision/evaluate.py),
and calibration.json when present. The new model is a CANDIDATE to replace the deployed one only if
  (a) its field accuracy is higher, (b) McNemar p < 0.05 on the same field photos, (c) its lab accuracy drops by no
  more than 1 point.
Nothing is replaced here: the switch is asked to the user. One row is added to docs/experiments.csv and a report
written to reports/compare/<new>.md.

Usage:
  python src/evaluation/compare.py --new models/diseases_v3 --current models/diseases --change "aug field2 + mix 0.3"
"""
import argparse
import json
import os
import sys
import time

import pandas as pd
from sklearn.metrics import f1_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "vision"))
sys.path.insert(0, os.path.dirname(__file__))
from calibrate import ece  # noqa: E402
from experiments import log  # noqa: E402
from stats import mcnemar  # noqa: E402

MAX_LAB_DROP, ALPHA = 0.01, 0.05


def scores(folder):
    lab = pd.read_csv(os.path.join(folder, "predictions_test.csv"))
    field = pd.read_csv(os.path.join(folder, "predictions_test_field.csv"))
    ok = field["true"] == field["pred"]
    pdoc = field[field["source"] == "plantdoc"]
    return {"lab_acc": round(float((lab["true"] == lab["pred"]).mean()), 4),
            "field_acc": round(float(ok.mean()), 4),
            "plantdoc_acc": round(float((pdoc["true"] == pdoc["pred"]).mean()), 4) if len(pdoc) else None,
            "field_macro_f1": round(f1_score(field["true"], field["pred"], labels=sorted(set(field["true"])),
                                             average="macro", zero_division=0), 4),
            "field_ece": ece(field["confidence"].to_numpy(), ok.to_numpy())}, field


def decide(cur, new, p):
    reasons = []
    if new["field_acc"] <= cur["field_acc"]:
        reasons.append("pas de gain sur le terrain")
    if p >= ALPHA:
        reasons.append(f"McNemar p = {p:.3g} ≥ {ALPHA}")
    if cur["lab_acc"] - new["lab_acc"] > MAX_LAB_DROP:
        reasons.append(f"labo −{100 * (cur['lab_acc'] - new['lab_acc']):.1f} pts")
    return ("CANDIDAT au remplacement (à demander)" if not reasons else "garder le modèle déployé"), reasons


def compare(new_dir, cur_dir):
    cur, fc = scores(cur_dir)
    new, fn = scores(new_dir)
    a = fc.set_index("path")
    b = fn.set_index("path").reindex(a.index)
    if b["pred"].isna().any():
        raise ValueError("the two models were not scored on the same field photos")
    test = mcnemar(a["true"] == a["pred"], b["true"] == b["pred"])
    pdc = a["source"] == "plantdoc"
    test_pd = mcnemar((a["true"] == a["pred"])[pdc], (b["true"] == b["pred"])[pdc]) if pdc.any() else None
    verdict, reasons = decide(cur, new, test["p"])
    return {"current": cur, "new": new, "mcnemar": test, "mcnemar_plantdoc": test_pd, "verdict": verdict,
            "reasons": reasons}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", required=True)
    ap.add_argument("--current", required=True)
    ap.add_argument("--change", default="")
    a = ap.parse_args()
    r = compare(a.new, a.current)
    cur, new, t = r["current"], r["new"], r["mcnemar"]
    name, cname = os.path.basename(os.path.normpath(a.new)), os.path.basename(os.path.normpath(a.current))
    log({"date": time.strftime("%Y-%m-%d"), "model": name, "change": a.change, **new,
         "mcnemar_p_vs_previous": f"{t['p']:.3g} (vs {cname} déployé : +{t['gains']} / −{t['losses']})",
         "notes": r["verdict"] + (" ; " + ", ".join(r["reasons"]) if r["reasons"] else "")})
    rows = [("Labo", "lab_acc"), ("Terrain", "field_acc"), ("PlantDoc", "plantdoc_acc"),
            ("Macro-F1 terrain", "field_macro_f1"), ("ECE terrain", "field_ece")]
    md = [f"# {name} contre {cname} (déployé)", "", f"Changement : {a.change}", "",
          f"| mesure | {cname} | {name} |", "|---|---|---|"]
    md += [f"| {lbl} | {cur[k]} | {new[k]} |" for lbl, k in rows]
    md += ["", f"McNemar terrain : {t['gains']} photos gagnées, {t['losses']} perdues, p = {t['p']:.3g}"]
    if r["mcnemar_plantdoc"]:
        tp = r["mcnemar_plantdoc"]
        md.append(f"McNemar PlantDoc : +{tp['gains']} / −{tp['losses']}, p = {tp['p']:.3g}")
    md += ["", f"**Verdict : {r['verdict']}**" + (f" ({', '.join(r['reasons'])})" if r["reasons"] else "")]
    os.makedirs(os.path.join(ROOT, "reports", "compare"), exist_ok=True)
    with open(os.path.join(ROOT, "reports", "compare", f"{name}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    print(json.dumps({"verdict": r["verdict"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
