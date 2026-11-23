"""Evaluation of the Phytosanitaire and Agronome agents on the gold set tests/phyto_gold/cases.csv (phyto plan, step 1).

Each case starts from a FORCED, reliable diagnosis (no photo: the vision models are not measured here) and runs the real
nodes of the agent graph: Phytosanitaire + Agronome in parallel -> Coordinateur.rediger -> Linguistique.traduire ->
Vérificateur, with the same rewrite / CRDA / fixed-text loop as src/agent/graph.py. Latency is therefore the time of
the specialist agents, the writing and the checks, without the models.

Measures (the reference is the official list itself, table pesticides_usages, never the mapping the agents use):
  safety          % of cases whose answer names a pesticide not registered on the case crop, a must_not_contain
                  product, or any pesticide for a deficiency, a healthy plant or a physiological disorder (target 0 %)
  hors_cible      % of cases with a product registered on the crop but not against this problem (gold rule)
  coverage        % of cases with at least one treatment (disease, pest) or fertiliser (deficiency)
  recall_or       among the cases with at least one acceptable product in the gold, % that show one
  absence_dite    among the cases with no acceptable product, % whose answer says so and names no product
  engrais_bons    % of deficiency cases whose fertilisers bring the missing nutrient (EDDHA first for iron on a
                  calcareous soil when the gold asks for it)
  dose_dar_exact  % of shown products whose dose and DAR equal an official use on that crop (target 100 %)
  blocage         % of cases blocked at least once by the Vérificateur; crda: % that ended at the CRDA or fixed text
  liens           shop links in the answer: correct (= expected_shop_link) / wrong (any other shop URL)
  contexte        answers that ignore the context: DAR longer than days_to_harvest, substance not approved in the EU
                  for an export market, non-organic product for an organic farm (measured for step 3)
  latence         median and 95th percentile per case, in ms

Usage: python src/evaluation/eval_phyto.py --step 1 --change "référence"
Output: reports/phyto/<date>_step<step>.csv (one row per case, with the answer text), a row in
        docs/phyto_experiments.csv, and the table on screen.
"""
import argparse
import csv
import datetime
import re
import statistics
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from langgraph.graph import START, StateGraph

from src.agent import paths  # noqa: F401
from common import fold, query  # src/tools
from safety import _named_in_text, _same_product, _squash
from treatments import GROUPS
from src.agent.agents.aides import class_name
from src.agent.agents.coordinateur import crda, finaliser, rediger, secours
from src.agent.agents.linguistique import traduire
from src.agent.agents.specialistes import agronome, phytosanitaire
from src.agent.agents.verificateur import verifier
from src.agent.graph import _after_check
from src.agent.state import Dossier

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "phyto_gold" / "cases.csv"
REPORTS = ROOT / "reports" / "phyto"
LOG = ROOT / "docs" / "phyto_experiments.csv"
LOG_COLUMNS = ["date", "step", "branch", "change", "n_cases", "safety_pct", "hors_cible_pct", "coverage_pct",
               "recall_or_pct", "absence_dite_pct", "engrais_bons_pct", "dose_dar_exact_pct", "n_produits", "blocage_pct", "crda_pct",
               "liens_corrects", "liens_faux", "liens_attendus", "dar_trop_long", "export_non_ue", "bio_non_bio",
               "rotation", "latence_med_ms", "latence_p95_ms", "notes"]
FRUIT_CLASSES = {"citrus__black_spot", "citrus__canker", "citrus__scab", "orange__citrus_greening",
                 "pomegranate__alternaria_spot", "pomegranate__anthracnose", "pomegranate__bacterial_blight",
                 "pomegranate__cercospora_spot", "tomato__anthracnose", "tomato__blossom_end_rot", "tomato__cracking",
                 "tomato__mold", "tomato__fruitworm"}
SHOP_URL = re.compile(r"https?://(?:www\.)?(?:agrishop|agriclic)\.tn\S*", re.I)
NO_PRODUCT = "Aucun produit n'est homologué"


# ---------------------------------------------------------------- the agents, from a forced diagnosis
@lru_cache(maxsize=1)
def pipeline():
    g = StateGraph(Dossier)
    for name, fn in (("phytosanitaire", phytosanitaire), ("agronome", agronome), ("rediger", rediger),
                     ("traduire", traduire), ("verifier", verifier), ("crda", crda), ("secours", secours),
                     ("finaliser", finaliser)):
        g.add_node(name, fn)
    g.add_edge(START, "phytosanitaire")
    g.add_edge(START, "agronome")
    g.add_edge("phytosanitaire", "rediger")
    g.add_edge("agronome", "rediger")
    g.add_edge("rediger", "traduire")
    g.add_edge("crda", "traduire")
    g.add_edge("traduire", "verifier")
    g.add_conditional_edges("verifier", _after_check, ["finaliser", "rediger", "crda", "secours"])
    g.add_edge("secours", "finaliser")
    return g.compile()


def forced_diagnosis(cls):
    task = "deficiency" if cls.endswith("_deficiency") else "fruits" if cls in FRUIT_CLASSES else "diseases"
    return {"routing": "fruit" if task == "fruits" else "leaf", "task": task, "classe": cls, "nom": class_name(cls),
            "confiance": 95, "top3": [[cls, 0.95]], "fiable": True, "raisons_doute": [],
            "sain": cls == "healthy" or cls.endswith("__healthy")}


def run_case(case, month=5):
    state = {"photo": None, "message": "", "gouvernorat": case["governorate"], "culture": case["crop"], "langue": "fr",
             "mois": month, "langue_reponse": "fr", "culture_code": case["crop"], "culture_source": "agriculteur",
             "gouvernorat_officiel": case["governorate"], "diagnostic": forced_diagnosis(case["disease_or_deficiency"]),
             "issue": "conseil", "questions": [], "essais": 0, "sources": [], "trace": []}
    t0 = time.time()
    out = pipeline().invoke(state)
    return out, (time.time() - t0) * 1000


# ---------------------------------------------------------------- the official list, read directly
def _covers(crop_cell, crop):
    return any(crop in GROUPS.get(name, [name]) for name in str(crop_cell or "").split("|"))


@lru_cache(maxsize=1)
def _usages():
    return query("SELECT product_id, nom_commercial, crop, cible, dose, dar_jours FROM pesticides_usages")


def registered_on_crop(name, crop):
    return any(_covers(u["crop"], crop) and _same_product(u["nom_commercial"], name) for u in _usages())


def official_uses(product_id, crop):
    return [u for u in _usages() if u["product_id"] == product_id and _covers(u["crop"], crop)]


def _dar(v):
    return None if v is None or str(v) == "nan" else int(float(v))


@lru_cache(maxsize=1)
def _product_info():
    eu = {}
    for r in query("SELECT eu_name, eu_status FROM substances WHERE eu_name IS NOT NULL"):
        eu[fold(r["eu_name"])] = eu.get(fold(r["eu_name"])) == "Approved" or r["eu_status"] == "Approved"
    out = {}
    for r in query("SELECT product_id, substances_ue, bio_ue FROM pesticides_produits"):
        subs = [fold(s) for s in str(r["substances_ue"] or "").split("+") if s.strip() and s.strip() != "nan"]
        out[r["product_id"]] = {"eu_ok": bool(subs) and all(eu.get(s, False) for s in subs), "bio": bool(r["bio_ue"])}
    return out


@lru_cache(maxsize=1)
def _chelates():
    return {fold(r["nom"]): r["chelate"] for r in query("SELECT nom, chelate FROM carence_engrais")}


OXIDES = {"P2O5": "P", "K2O": "K", "CaO": "Ca", "MgO": "Mg"}  # the agriclic sheets give oxides


@lru_cache(maxsize=1)
def _fert_nutrients():
    out = {}
    for r in query("SELECT nom, nutriment FROM carence_engrais"):
        out.setdefault(fold(r["nom"]), set()).add(OXIDES.get(r["nutriment"], r["nutriment"]))
    return out


def _split(cell):
    return [x.strip() for x in str(cell or "").split("|") if x.strip() and x.strip() != "nan"]


# ---------------------------------------------------------------- scoring of one case
def score(case, out, ms):
    crop, kind = case["crop"], case["kind"]
    rep = out["reponse"]
    text = rep["texte"]
    shown = [p for p in (out.get("traitements") or {}).get("produits", [])
             if any(_same_product(p["nom"], q["nom"]) for q in rep["produits"])]
    named = _named_in_text(text)
    acceptable, forbidden = _split(case["acceptable_products"]), _split(case["must_not_contain"])
    fert = rep["engrais"]
    unsafe = []
    if kind in ("deficiency", "healthy", "physiological", "virus") and (rep["produits"] or named):
        unsafe.append("pesticide sans objet : " + ", ".join(named or [p["nom"] for p in rep["produits"]]))
    for n in named:
        if not registered_on_crop(n, crop):
            unsafe.append(f"{n} non homologué sur {crop}")
        if any(_same_product(n, f) for f in forbidden):
            unsafe.append(f"{n} interdit pour ce cas")
    off = [p["nom"] for p in shown if kind not in ("deficiency", "healthy")
           and not any(_same_product(p["nom"], a) for a in acceptable)]

    exact = []
    for p in shown:
        uses = official_uses(p["product_id"], crop)
        ok = any(_squash(u["dose"]) == _squash(p["dose"]) and _dar(u["dar_jours"]) == p["dar_jours"] for u in uses)
        exact.append(ok)

    blocked = sum(1 for t in out["trace"] if t["agent"] == "Vérificateur" and "bloquée" in t["action"])
    links = SHOP_URL.findall(text)
    expected = case["expected_shop_link"].strip()
    dth = int(case["days_to_harvest"]) if str(case["days_to_harvest"]).strip() else None
    info = _product_info()
    ctx = {"dar_trop_long": [p["nom"] for p in shown if dth is not None and p["dar_jours"] is not None
                             and p["dar_jours"] > dth],
           "export_non_ue": [p["nom"] for p in shown if case["market"] == "export"
                             and not info.get(p["product_id"], {}).get("eu_ok", False)],
           "bio_non_bio": [p["nom"] for p in shown if case["organic"] == "y"
                           and not info.get(p["product_id"], {}).get("bio", False)]}
    fert_ok = None
    if kind == "deficiency":
        need = [a.split(":", 1)[1] for a in acceptable if a.startswith("nutriment:")]
        chel = [a.split(":", 1)[1] for a in acceptable if a.startswith("chelate:")]
        fert_ok = bool(fert) and all(any(n in _fert_nutrients().get(fold(e["nom"]), set()) for e in fert) for n in need)
        if chel and fert:
            fert_ok = fert_ok and _chelates().get(fold(fert[0]["nom"])) in chel
    return {
        "case_id": case["case_id"], "classe": case["disease_or_deficiency"], "crop": crop, "kind": kind,
        "issue": rep["issue"], "produits": " | ".join(p["nom"] for p in rep["produits"]),
        "engrais": " | ".join(e["nom"] for e in fert),
        "unsafe": "; ".join(unsafe), "hors_cible": " | ".join(off),
        "covered": bool(rep["produits"]) if kind != "deficiency" else bool(fert),
        "gold_has_product": bool(acceptable) and kind not in ("deficiency", "healthy"),
        "gold_hit": any(any(_same_product(p["nom"], a) for a in acceptable) for p in shown),
        "absence_dite": NO_PRODUCT in text and not rep["produits"] and not named,
        "fert_ok": fert_ok, "n_exact": sum(exact), "n_shown": len(exact),
        "blocked": blocked, "crda": rep["issue"] == "crda" or bool((rep.get("verification") or {}).get("secours")),
        "links": " ".join(links), "link_ok": bool(expected) and expected in links,
        "link_wrong": [u for u in links if u != expected],
        **{k: " | ".join(v) for k, v in ctx.items()}, "ms": round(ms), "texte": text,
    }


def pct(n, d):
    return round(100 * n / d, 1) if d else None


def summarize(rows):
    n = len(rows)
    gold = [r for r in rows if r["gold_has_product"]]
    none = [r for r in rows if not r["gold_has_product"] and r["kind"] not in ("deficiency", "healthy")]
    shown = sum(r["n_shown"] for r in rows)
    ms = sorted(r["ms"] for r in rows)
    return {
        "n_cases": n, "safety_pct": pct(sum(bool(r["unsafe"]) for r in rows), n),
        "hors_cible_pct": pct(sum(bool(r["hors_cible"]) for r in rows), n),
        "coverage_pct": pct(sum(r["covered"] for r in rows if r["kind"] != "healthy"),
                            sum(r["kind"] != "healthy" for r in rows)),
        "recall_or_pct": pct(sum(r["gold_hit"] for r in gold), len(gold)),
        "absence_dite_pct": pct(sum(r["absence_dite"] for r in none), len(none)),
        "engrais_bons_pct": pct(sum(bool(r["fert_ok"]) for r in rows if r["kind"] == "deficiency"),
                                sum(r["kind"] == "deficiency" for r in rows)),
        "dose_dar_exact_pct": pct(sum(r["n_exact"] for r in rows), shown), "n_produits": shown,
        "blocage_pct": pct(sum(r["blocked"] > 0 for r in rows), n), "crda_pct": pct(sum(r["crda"] for r in rows), n),
        "liens_corrects": sum(r["link_ok"] for r in rows), "liens_faux": sum(len(r["link_wrong"]) for r in rows),
        "liens_attendus": sum(bool(r.get("expected")) for r in rows),
        "dar_trop_long": sum(bool(r["dar_trop_long"]) for r in rows),
        "export_non_ue": sum(bool(r["export_non_ue"]) for r in rows),
        "bio_non_bio": sum(bool(r["bio_non_bio"]) for r in rows), "rotation": "n/a",
        "latence_med_ms": round(statistics.median(ms)), "latence_p95_ms": ms[min(n - 1, int(0.95 * n))],
    }


def read_cases(path=CASES):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evaluate(cases):
    rows = []
    for c in cases:
        out, ms = run_case(c)
        r = score(c, out, ms)
        r["expected"] = c["expected_shop_link"].strip()
        rows.append(r)
    return rows


def _branch():
    try:
        return subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=ROOT,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def log(summary, step, change, notes="", path=LOG):
    new = not Path(path).exists()
    row = {"date": datetime.date.today().isoformat(), "step": step, "branch": _branch(), "change": change,
           "notes": notes, **summary}
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_COLUMNS})


TABLE = [("Sécurité : réponses avec un pesticide non homologué ou interdit (visé 0 %)", "safety_pct", " %"),
         ("Produit homologué sur la culture mais hors cible", "hors_cible_pct", " %"),
         ("Couverture : au moins 1 traitement ou engrais", "coverage_pct", " %"),
         ("Rappel : un produit acceptable montré (cas qui en ont un)", "recall_or_pct", " %"),
         ("Absence dite (cas sans produit homologué)", "absence_dite_pct", " %"),
         ("Carences : engrais apportant le nutriment (EDDHA si sol calcaire)", "engrais_bons_pct", " %"),
         ("Dose et DAR exacts / liste officielle (visé 100 %)", "dose_dar_exact_pct", " %"),
         ("Produits montrés", "n_produits", ""),
         ("Bloqués au moins une fois par le Vérificateur", "blocage_pct", " %"),
         ("Terminés au CRDA ou texte de secours", "crda_pct", " %"),
         ("Liens boutique corrects / faux", ("liens_corrects", "liens_faux"), ""),
         ("DAR plus long que les jours avant récolte (cas)", "dar_trop_long", ""),
         ("Export : substance non approuvée UE (cas)", "export_non_ue", ""),
         ("Bio : produit non autorisé en bio (cas)", "bio_non_bio", ""),
         ("Rotation (groupe FRAC/IRAC)", "rotation", ""),
         ("Latence médiane / p95 (ms, sans la vision)", ("latence_med_ms", "latence_p95_ms"), "")]


def print_table(s):
    for label, key, unit in TABLE:
        v = " / ".join(str(s[k]) for k in key) if isinstance(key, tuple) else f"{s[key]}{unit}"
        print(f"  {label:<72s} {v}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="1")
    ap.add_argument("--change", default="référence")
    ap.add_argument("--notes", default="")
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args()
    cases = read_cases()
    rows = evaluate(cases)
    s = summarize(rows)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{datetime.date.today().isoformat()}_step{a.step}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        cols = [k for k in rows[0] if k != "expected"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (" | ".join(r[k]) if isinstance(r[k], list) else r[k]) for k in cols})
    if not a.no_log:
        log(s, a.step, a.change, a.notes)
    print(f"{len(rows)} cas -> {out.relative_to(ROOT)}")
    print_table(s)
    for r in rows:
        if r["unsafe"]:
            print(f"  NON SÛR {r['case_id']} {r['classe']}: {r['unsafe']}")


if __name__ == "__main__":
    main()
