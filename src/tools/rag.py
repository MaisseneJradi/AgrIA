"""Search the knowledge sheets for the passages that answer a question. Every passage keeps its sheet, its section and
the link of its source, so that the answer can cite them.

  search_knowledge("comment lutter contre le mildiou de la tomate", k=3)
  -> [{"extrait": "...", "fiche": "mildiou_tomate_pdt", "nom": "...", "section": "lutte", "source": "https://...",
       "licence": "CC BY-SA 4.0 (Wikipédia)", "score": 0.41}, ...]
  search_knowledge("...", classe="tomato__late_blight")   only the sheets of that model class
  search_knowledge("...", method="tfidf")                 one method; default METHOD (env AGRIA_RAG)

Index (phyto plan, step 11): the sections of the 76 sheets (table fiche_sections, src/preparation/build_sections.py:
description, symptomes, biologie, lutte, prevention, repartition), cut into passages of about 700 characters.
Methods, all on the same passages, the question first expanded with the lexicon (darija, arabizi and Arabic words add
the French names of the concepts they name):
  tfidf   TF-IDF on words + TF-IDF on 3-5 letter pieces (the method before step 11);
  bm25    BM25 on folded words cut to 7 letters (a light stemming: plurals, genders);
  dense   cosine of local multilingual vectors (embed.py, model MODEL; vectors stored in data/processed/knowledge);
  hybrid  0.5 BM25 (divided by its best score) + 0.5 dense (cosine rescaled between its worst and best passage);
          it answers when the cosine of its best passage passes the floor of the model.
Then, for every method: a passage counts 60 % the best passage of its sheet (the topic) and 40 % itself, x1.25 on the
section the question asks for (INTENT); nothing is returned when the sheets do not answer (FLOOR: measured on the
off-topic questions of tests/rag_gold/queries.csv), except when a class is given. When the vectors or the model are
missing, dense and hybrid fall back to bm25 (method_used() says which one ran).
"""
import ast
import hashlib
import json
import math
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from common import PROC, fold, query
from lexicon import normalize_terms

SECTIONS = ("description", "symptomes", "biologie", "lutte", "prevention", "repartition")
# how an answer names a section (redaction.py writes it, the Vérificateur reads it back: rule 27)
SECTION_LABELS = {"fr": {"description": "description", "symptomes": "symptômes", "biologie": "biologie",
                         "lutte": "lutte", "prevention": "prévention", "repartition": "répartition"},
                  "ar": {"description": "الوصف", "symptomes": "الأعراض", "biologie": "دورة الحياة",
                         "lutte": "المكافحة", "prevention": "الوقاية", "repartition": "الانتشار"}}
SIZE = 700
METHOD = os.environ.get("AGRIA_RAG", "hybrid")
MODEL = os.environ.get("AGRIA_RAG_MODEL", "bge-m3")  # eval_rag.py, step 11: e5-small = lighter, 4 points lower
VECTORS = PROC / "knowledge"
# best score of a question that the sheets answer, per method (below: nothing). Measured by
# src/evaluation/eval_rag.py on the on-topic and off-topic questions of tests/rag_gold/queries.csv.
FLOOR = {"tfidf": 0.12, "bm25": 0.30, "dense:e5-small": 0.80, "dense:bge-m3": 0.45}
# words of the question -> section it asks for (x1.25 on that section). The question is FOLDED first (common.fold:
# no accents, أ/إ/آ -> ا, ة -> ه): the Arabic words are written folded here. "kifech" / "كيفاش" (how) asks for no section.
INTENT = {"prevention": r"preven|evite|proteg|wi9aya|wqaya|tfadi|nfadi|n7mi|ne7mi|وقاي|\bاقي\b|\bنقي\b|تجنب|حمي",
          "lutte": r"lutt|trait|soign|combat|elimin|dwa|daw|\bnda\b|mdew|na3mel|n3mel|دوا|داو|علاج|عالج|كافح|رش|نعمل",
          "symptomes": r"sympt|reconna|signe|aspect|ressembl|3alam|علام|اعراض",
          "biologie": r"cycle|biolog|propag|transmi|conserv|hiver|contamin|reprodu|multipli|kather|yetna9al|دوره|"
                      r"ينتقل|نتشر|تكاثر",
          "repartition": r"repartit|distribution|ou trouve|quels pays|regions|مناطق|بلدان"}
_used = {"method": None}


def _passages(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text or text == "None":
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) > SIZE:
            out.append(cur)
            cur = ""
        cur = f"{cur} {s}".strip()
    return out + ([cur] if cur else [])


def _classes(v):
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        try:
            return ast.literal_eval(v) if v else []
        except (ValueError, SyntaxError):
            return []


def _section_rows():
    """The sections of step 11; before build_sections.py ran, the five fields of the sheets."""
    try:
        rows = query("SELECT * FROM fiche_sections")
    except Exception:
        rows = []
    if rows:
        return rows
    out = []
    for f in query("SELECT * FROM fiches"):
        for sec in ("description", "symptomes", "biologie", "lutte", "repartition"):
            out.append({"fiche": f["id"], "nom": f["nom"], "section": sec, "texte": f.get(sec),
                        "classes": f["classes_modele"], "langue": f["langue_texte"], "source": f["source_texte"],
                        "licence": f["licence_texte"], "nom_scientifique": f["nom_scientifique"],
                        "cultures": f["cultures"]})
    return out


def _tokens(text):
    return [w[:7] for w in re.findall(r"\w+", fold(text)) if len(w) > 1]


@lru_cache(maxsize=1)
def _index():
    docs = []
    for r in _section_rows():
        for p in _passages(r.get("texte")):
            docs.append({"extrait": p, "fiche": r["fiche"], "nom": r["nom"], "section": r["section"],
                         "classes": _classes(r.get("classes")), "langue": r.get("langue"), "source": r.get("source"),
                         "licence": r.get("licence"),
                         "_text": f"{r['nom']} {r.get('nom_scientifique') or ''} {r.get('cultures') or ''} "
                                  f"{r['section']}. {p}"})
    texts = [d["_text"] for d in docs]
    words = TfidfVectorizer(preprocessor=fold, sublinear_tf=True)
    chars = TfidfVectorizer(preprocessor=fold, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    # BM25 statistics
    toks = [_tokens(t) for t in texts]
    df = Counter(w for t in toks for w in set(t))
    n = len(toks)
    idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
    return {"docs": docs, "words": words, "wm": words.fit_transform(texts), "chars": chars,
            "cm": chars.fit_transform(texts), "tf": [Counter(t) for t in toks], "len": np.array([len(t) for t in toks]),
            "idf": idf}


def _key(docs):
    return hashlib.sha1("\n".join(d["_text"] for d in docs).encode("utf-8")).hexdigest()[:16]


def vector_path(model=MODEL):
    return VECTORS / f"vectors_{model}.npz"


def build_vectors(model=MODEL):
    """Vectors of every passage, stored locally with the key of the passages they were computed on."""
    from embed import encode
    docs = _index()["docs"]
    v = encode([d["_text"] for d in docs], model, kind="passage")
    np.savez(vector_path(model), vectors=v, key=_key(docs))
    return v


@lru_cache(maxsize=2)
def _vectors(model=MODEL):
    """Stored vectors if they match the passages; None when they are missing or stale (run build_rag_index.py)."""
    p = vector_path(model)
    if not p.exists():
        return None
    z = np.load(p)
    return z["vectors"] if str(z["key"]) == _key(_index()["docs"]) else None


@lru_cache(maxsize=1)
def _names():
    return {r["concept"]: r["fr"] for r in query("SELECT concept, fr FROM lexique") if r["fr"]}


def _expand(q):
    terms = normalize_terms(q)
    names = _names()
    extra = [names.get(e["concept"], "") for g in ("cultures", "maladies", "ravageurs", "symptomes", "organes")
             for e in terms[g]]
    return " ".join([q] + extra)


def _tfidf(ix, q):
    return 0.5 * (ix["wm"] @ ix["words"].transform([q]).T).toarray().ravel() \
        + 0.5 * (ix["cm"] @ ix["chars"].transform([q]).T).toarray().ravel()


def _bm25(ix, q, k1=1.5, b=0.75):
    qt = set(_tokens(q))
    avg = ix["len"].mean() or 1
    out = np.zeros(len(ix["docs"]))
    for i, tf in enumerate(ix["tf"]):
        s = 0.0
        for w in qt:
            f = tf.get(w)
            if f:
                s += ix["idf"][w] * f * (k1 + 1) / (f + k1 * (1 - b + b * ix["len"][i] / avg))
        out[i] = s
    return out


def _dense(q, model=MODEL):
    vec = _vectors(model)
    if vec is None:
        return None
    return vec @ _query_vector(q, model)


@lru_cache(maxsize=512)
def _query_vector(q, model):
    from embed import encode
    return encode([q], model, kind="query")[0]


def raw_scores(query_text, method=None, model=None):
    """(scores of every passage, method that ran, evidence): evidence = best raw score of each method that ran,
    read by answers() against FLOOR."""
    method, model = method or METHOD, model or MODEL
    ix = _index()
    q = _expand(query_text)
    if method == "tfidf":
        s = _tfidf(ix, q)
        return s, "tfidf", {"tfidf": float(s.max(initial=0))}
    bm = _bm25(ix, q)
    # BM25 grows with the length of the question: its floor is read on the best score per question word
    ev = {"bm25": float(bm.max(initial=0)) / max(1, len(set(_tokens(q))))}
    if method == "bm25":
        return bm, "bm25", ev
    dn = _dense(q, model)
    if dn is None:  # no vectors or no model: BM25 alone, said by method_used()
        return bm, "bm25", ev
    ev["dense"] = float(dn.max(initial=0))
    if method == "dense":
        return dn, "dense", ev
    bn = bm / bm.max() if bm.max() > 0 else bm
    dnn = (dn - dn.min()) / (dn.max() - dn.min()) if dn.max() > dn.min() else dn * 0
    return 0.5 * bn + 0.5 * dnn, "hybrid", ev


def answers(ev, ran, model=None):
    """Do the sheets answer? tfidf and bm25 by their own floor; dense and hybrid by the cosine of the best passage
    (BM25 does not separate the off-topic questions: a rare word scores high)."""
    if ran in ("dense", "hybrid"):
        return ev["dense"] >= FLOOR["dense:" + (model or MODEL)]
    return ev[ran] >= FLOOR[ran]


def method_used():
    return _used["method"]


def search_knowledge(query_text, k=3, classe=None, method=None, model=None, floor=True):
    ix = _index()
    docs = ix["docs"]
    score, ran, ev = raw_scores(query_text, method, model)
    _used["method"] = ran
    # the topic first: a passage is scored with the best passage of its sheet, then its own section
    fiche = np.array([d["fiche"] for d in docs])
    best = {f: score[fiche == f].max() for f in set(fiche)}
    score = 0.6 * np.array([best[f] for f in fiche]) + 0.4 * score
    folded = fold(query_text)
    for sec, rx in INTENT.items():
        if re.search(rx, folded):
            score = np.where([d["section"] == sec for d in docs], score * 1.25, score)
    if classe:
        score = np.where([classe in d["classes"] for d in docs], score, -1)
    elif floor and not answers(ev, ran, model):
        return []  # the sheets do not answer this question
    out, seen = [], set()
    for i in np.argsort(-score):
        if score[i] < 0 or (score[i] == 0 and not classe) or len(out) >= k:
            break
        d = docs[i]
        if (d["fiche"], d["section"]) in seen:  # one passage per sheet section: more variety
            continue
        seen.add((d["fiche"], d["section"]))
        out.append({key: v for key, v in d.items() if not key.startswith("_")} | {"score": round(float(score[i]), 3)})
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(search_knowledge(" ".join(sys.argv[1:])), ensure_ascii=False, indent=1))
