"""Phyto plan, step 11: recall@3 of the retrieval of the knowledge sheets, TF-IDF against BM25, dense and hybrid.

    python -m src.evaluation.eval_rag --step 11 --change "..."      (--no-log: table only)

Gold set: tests/rag_gold/queries.csv, 50 questions in French, Arabic and darija with the expected sheet and section
('a|b' = either), and off-topic questions (kind hors_sujet) that must get no passage.
  recall@3           one of the 3 passages has the expected sheet AND section (floor off: the method alone)
  recall@3 fiche     one of the 3 passages has the expected sheet
  répond / rejet     on-topic questions answered, off-topic questions refused, with the floors of rag.FLOOR
The table also gives, per method, the best raw score of every question (for the floors) and the median latency of one
search. Each run is logged in docs/phyto_experiments.csv (columns rag_*); per-question hits in reports/rag/.
"""
import argparse
import csv
import datetime
import statistics
import sys
import time
from pathlib import Path

from src.agent import paths  # noqa: F401  (src/tools on the path)
import embed  # noqa: E402
import rag  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "tests" / "rag_gold" / "queries.csv"
REPORTS = ROOT / "reports" / "rag"
CONFIGS = [("tfidf", None), ("bm25", None), ("dense", "e5-small"), ("dense", "bge-m3"), ("hybrid", "e5-small"),
           ("hybrid", "bge-m3")]


def read_queries(path=QUERIES):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hit(results, q, k=3, section=True):
    fiches, secs = set(q["expected_fiche"].split("|")), set(q["expected_section"].split("|"))
    return any(r["fiche"] in fiches and (not section or r["section"] in secs) for r in results[:k])


def name(method, model):
    return method if model is None else f"{method}:{model}"


def evaluate(method, model, queries):
    on = [q for q in queries if q["kind"] == "sujet"]
    off = [q for q in queries if q["kind"] == "hors_sujet"]
    rag.search_knowledge("mildiou", method=method, model=model)  # warm-up: index, vectors, model
    if rag.method_used() != method:
        return None  # model or vectors missing
    rag._query_vector.cache_clear()  # each method encodes its questions: a true latency
    rows, times = [], []
    for q in on + off:
        t0 = time.perf_counter()
        free = rag.search_knowledge(q["query"], k=3, method=method, model=model, floor=False)
        times.append((time.perf_counter() - t0) * 1000)
        _, _, ev = rag.raw_scores(q["query"], method, model)
        rows.append({"query_id": q["query_id"], "langue": q["langue"], "kind": q["kind"],
                     "methode": name(method, model), "hit3": q["kind"] == "sujet" and hit(free, q),
                     "hit3_fiche": q["kind"] == "sujet" and hit(free, q, section=False),
                     "hit1": q["kind"] == "sujet" and hit(free, q, k=1), "repond": rag.answers(ev, method, model),
                     "evidence": {k: round(v, 3) for k, v in ev.items()},
                     "top3": " ; ".join(f"{r['fiche']}/{r['section']}" for r in free)})
    pct = lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    s_on = [r for r in rows if r["kind"] == "sujet"]
    s_off = [r for r in rows if r["kind"] == "hors_sujet"]
    summary = {"methode": name(method, model), "n": len(s_on), "recall3": pct([r["hit3"] for r in s_on]),
               "recall1": pct([r["hit1"] for r in s_on]), "recall3_fiche": pct([r["hit3_fiche"] for r in s_on]),
               "repond": pct([r["repond"] for r in s_on]), "rejet": pct([not r["repond"] for r in s_off]),
               "latence_ms": round(statistics.median(times), 1)}
    for lang in ("fr", "ar", "darija"):
        summary["recall3_" + lang] = pct([r["hit3"] for r in s_on if r["langue"] == lang])
    return summary, rows


def floors(rows):
    """Lowest best score of an on-topic question and highest of an off-topic one, per part (for rag.FLOOR)."""
    out = {}
    for part in ("tfidf", "bm25", "dense"):
        on = [r["evidence"][part] for r in rows if r["kind"] == "sujet" and part in r["evidence"]]
        off = [r["evidence"][part] for r in rows if r["kind"] == "hors_sujet" and part in r["evidence"]]
        if on and off:
            out[part] = (round(min(on), 3), round(sorted(on)[len(on) // 10], 3), round(max(off), 3))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="11")
    ap.add_argument("--change", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args(argv)
    queries = read_queries()
    results, all_rows = [], []
    for method, model in CONFIGS:
        if model and not embed.available(model):
            print(f"{name(method, model)} : modèle absent du cache local, ignoré")
            continue
        r = evaluate(method, model, queries)
        if r is None:
            print(f"{name(method, model)} : vecteurs absents (python src/preparation/build_rag_index.py), ignoré")
            continue
        results.append(r[0])
        all_rows += r[1]
    print(f"{sum(q['kind'] == 'sujet' for q in queries)} questions (+ "
          f"{sum(q['kind'] == 'hors_sujet' for q in queries)} hors sujet)")
    cols = ["methode", "recall3", "recall1", "recall3_fiche", "recall3_fr", "recall3_ar", "recall3_darija", "repond",
            "rejet", "latence_ms"]
    print("  ".join(f"{c:>14s}" for c in cols))
    for s in results:
        print("  ".join(f"{str(s[c]):>14s}" for c in cols))
    for r in results:
        rows = [x for x in all_rows if x["methode"] == r["methode"]]
        print(f"  {r['methode']:18s} score max : min sujet / 10e centile sujet / max hors sujet {floors(rows)}")
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{datetime.date.today().isoformat()}_step{args.step}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        w.writeheader()
        w.writerows(all_rows)
    print("->", out.relative_to(ROOT))
    by = {s["methode"]: s for s in results}
    tf = by.get("tfidf")
    hybrids = [s for s in results if s["methode"].startswith("hybrid")]
    best = max(hybrids, key=lambda s: (s["recall3"], -s["latence_ms"])) if hybrids else None
    keep = best if best and tf and best["recall3"] > tf["recall3"] else tf
    print(f"Méthode retenue : {keep['methode']} (rappel@3 {keep['recall3']} % contre TF-IDF {tf['recall3']} %)")
    if not args.no_log:
        from src.evaluation import eval_phyto as E
        summary = {"rag_n_requetes": tf["n"], "rag_recall3_tfidf_pct": tf["recall3"],
                   "rag_recall3_hybride_pct": best["recall3"] if best else "",
                   "rag_methode": keep["methode"], "rag_rejet_hors_sujet_pct": keep["rejet"],
                   "rag_latence_ms": keep["latence_ms"]}
        E.log(summary, args.step, args.change, args.notes)
    return results


if __name__ == "__main__":
    sys.exit(main() and 0)
