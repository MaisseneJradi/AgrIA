"""Search the knowledge sheets (data/processed/knowledge/fiches.jsonl: 76 diseases, pests, deficiencies) for the
passages that answer a question. Every passage keeps the link of its source.

  search_knowledge("comment lutter contre le mildiou de la tomate", k=3)
  -> [{"extrait": "...", "fiche": "mildiou_tomate_pdt", "nom": "...", "section": "lutte", "source": "https://...",
       "licence": "CC BY-SA 4.0 (Wikipédia)", "score": 0.41}, ...]
  search_knowledge("...", classe="tomato__late_blight")   only the sheets of that model class

Index: each section of a sheet (description, symptomes, biologie, lutte, repartition) is cut into passages of about
700 characters. Scoring: TF-IDF on words plus TF-IDF on 3-5 letter pieces (robust to spelling and plurals), on folded
text, averaged; a passage counts 60 % the best passage of its sheet (the topic) and 40 % itself, x1.25 on the
section the question asks for (lutte, symptomes, biologie: INTENT); no passage
under MIN_SCORE (the sheets do not answer), except when a class is given. The question is first expanded with the lexicon: darija or arabizi words ("mildiou", "tmatem",
"الصدى") add the French names of the concepts they name. Small corpus: the index is built in memory at the first
call (under a second), offline, no model to download. A vector database (Chroma) can replace it later behind the
same function if the corpus grows.
"""
import ast
import re
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from common import fold, query
from lexicon import normalize_terms

SECTIONS = ("description", "symptomes", "biologie", "lutte", "repartition")
SIZE = 700
MIN_SCORE = 0.12  # below: nothing in the sheets answers the question (measured: off-topic questions score ~0.10)
# words of the question -> section it asks for (x1.25 on that section)
INTENT = {"lutte": r"lutt|trait|soign|combat|proteg|preven|elimin|dwa|mdew|dawa|na3mel|n3mel|دوا|مداوا|علاج|رش",
          "symptomes": r"sympt|reconna|signe|aspect|ressembl|ki?fech|علام|اعراض",
          "biologie": r"cycle|biolog|propag|transmi|conserv|hiver|contamin"}


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


@lru_cache(maxsize=1)
def _index():
    docs = []
    for f in query("SELECT * FROM fiches"):
        try:
            classes = ast.literal_eval(f["classes_modele"]) if f["classes_modele"] else []
        except (ValueError, SyntaxError):
            classes = []
        for sec in SECTIONS:
            for p in _passages(f.get(sec)):
                docs.append({"extrait": p, "fiche": f["id"], "nom": f["nom"], "section": sec,
                             "classes": classes, "langue": f["langue_texte"], "source": f["source_texte"],
                             "licence": f["licence_texte"],
                             "_text": f"{f['nom']} {f['nom_scientifique'] or ''} {f['cultures'] or ''} {sec}. {p}"})
    words = TfidfVectorizer(preprocessor=fold, sublinear_tf=True)
    chars = TfidfVectorizer(preprocessor=fold, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    texts = [d["_text"] for d in docs]
    return docs, words, words.fit_transform(texts), chars, chars.fit_transform(texts)


@lru_cache(maxsize=1)
def _french_names():
    return {r["concept"]: r["fr"] for r in query("SELECT concept, fr FROM lexique") if r["fr"]}


def _expand(q):
    terms = normalize_terms(q)
    names = _french_names()
    extra = [names.get(e["concept"], "") for g in ("cultures", "maladies", "ravageurs", "symptomes", "organes")
             for e in terms[g]]
    return " ".join([q] + extra)


def search_knowledge(query_text, k=3, classe=None):
    docs, words, wm, chars, cm = _index()
    q = _expand(query_text)
    score = 0.5 * (wm @ words.transform([q]).T).toarray().ravel() + 0.5 * (cm @ chars.transform([q]).T).toarray().ravel()
    # the topic first: a passage is scored with the best passage of its sheet, then its own section
    fiche = np.array([d["fiche"] for d in docs])
    best = {f: score[fiche == f].max() for f in set(fiche)}
    score = 0.6 * np.array([best[f] for f in fiche]) + 0.4 * score
    for sec, rx in INTENT.items():
        if re.search(rx, fold(query_text)):
            score = np.where([d["section"] == sec for d in docs], score * 1.25, score)
    if classe:
        score = np.where([classe in d["classes"] for d in docs], score, -1)
    floor = 0 if classe else MIN_SCORE
    out, seen = [], set()
    for i in np.argsort(-score):
        if score[i] <= floor or len(out) >= k:
            break
        d = docs[i]
        if (d["fiche"], d["section"]) in seen:  # one passage per sheet section: more variety
            continue
        seen.add((d["fiche"], d["section"]))
        out.append({key: v for key, v in d.items() if not key.startswith("_")} | {"score": round(float(score[i]), 3)})
    return out


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(search_knowledge(" ".join(sys.argv[1:])), ensure_ascii=False, indent=1))
