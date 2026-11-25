"""Agent Linguistique: understands the farmer's message (French, Arabic, darija, arabizi) and writes the final answer in
French or Arabic (a message in darija or arabizi is answered in Arabic).

comprendre: terms of the lexicon, crop, governorate, language of the answer, and the context of the plot (days to
            harvest, market, organic, greenhouse, stage, last treatment, area): the form first, then a few sure words
            of the message ("bio", "export", "serre", "récolte dans 5 jours"...). The questions on what is still
            unknown are asked only when the answer would change (ranking.decisive_fields), at most 3.
traduire:   the answer written again by code in French or Arabic (src/agent/redaction.py). No LLM: a fact can never
            be mistranslated. The Vérificateur checks the final text.
"""
import re
import time

from src.agent import paths  # noqa: F401
from common import fold, governorate  # src/tools
from lexicon import crop_code, normalize_terms
from src.agent.agents.aides import step
from src.agent.redaction import LANGS, compose

LANGUAGES = {"fr": "fr", "ar": "ar", "arabizi": "ar", "darija": "ar"}  # answers in French or Arabic only
CONTEXT_FIELDS = ("days_to_harvest", "market", "organic", "greenhouse", "stage", "last_treatment_group", "area")
YES, NO = {"y", "o", "oui", "yes", "true", "1", "نعم"}, {"n", "non", "no", "false", "0", "لا"}
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# a few words of the message that settle a context field (French, Arabic, darija, arabizi); the form always wins
HARVEST = r"r[ée]colt|cueill|ramass|جني|نجني|الجني|حصاد|n7ass?ad|nhass?ad|nejni|njni"
DAYS = r"(\d{1,3})\s*(jours?|j\b|semaines?|يوم|أيام|ايام|اسابيع|أسابيع|nhar|jmo3a|jom3a)"


def normalize_context(raw):
    """Values of the form -> the codes of ranking.py; an unreadable value is left out (asked again if it matters)."""
    out = {}
    for k in CONTEXT_FIELDS:
        v = raw.get(k)
        if v is None or str(v).strip() == "":
            continue
        s = str(v).strip().lower()
        if k == "days_to_harvest":
            try:
                n = int(float(s.translate(ARABIC_DIGITS)))
            except ValueError:
                continue
            if 0 <= n <= 365:
                out[k] = n
        elif k == "area":
            try:
                a = float(s.replace(",", "."))
            except ValueError:
                continue
            if a > 0:
                out[k] = a
        elif k in ("organic", "greenhouse"):
            if s in YES or s in NO:
                out[k] = "y" if s in YES else "n"
        elif k == "market":
            if s in ("local", "export"):
                out[k] = s
        elif k == "stage":
            s = {"debut": "early", "début": "early", "etendu": "spread", "étendu": "spread"}.get(s, s)
            if s in ("early", "spread"):
                out[k] = s
        else:
            out[k] = str(v).strip()
    return out


def context_from_message(message):
    m = fold(message or "").translate(ARABIC_DIGITS)
    out = {}
    if re.search(r"\b(?:pas|non|mech|mouch|موش|ماهوش)\s+(?:en\s+)?(?:bio|بيولوجي)", m):
        out["organic"] = "n"
    elif re.search(r"\bbio(?:logique)?\b|بيولوجي|عضوي", m):
        out["organic"] = "y"
    if re.search(r"export|تصدير|نصدر|للتصدير|n?sadd?er", m):
        out["market"] = "export"
    if re.search(r"\bserres?\b|sous abri|بيت محمي|بيوت محمي|البيوت المحمي", m):
        out["greenhouse"] = "y"
    if re.search(r"\bdebut\b|premieres? taches|بداية", m):
        out["stage"] = "early"
    elif re.search(r"partout|toute la parcelle|toutes les plantes|منتشر", m):
        out["stage"] = "spread"
    # the number must follow the word of the harvest; a digit glued to letters is an arabizi letter (ba3d, jmo3a)
    d = re.search(rf"(?:{HARVEST})(?:\D|\d(?=[a-z])){{0,30}}?(?<![a-z\d]){DAYS}", m)
    if d:
        n = int(d.group(1))
        out["days_to_harvest"] = n * 7 if re.match(r"sem|اسابيع|أسابيع|jmo3a|jom3a", d.group(2)) else n
    return out


def comprendre(d):
    t0 = time.time()
    terms = normalize_terms(d.get("message") or "")
    lang = LANGUAGES.get(d.get("langue") or "", None) or LANGUAGES.get(terms["langue"] or "", "fr")
    crop, source = None, None
    if d.get("culture"):
        crop, source = crop_code(d["culture"]), "agriculteur"
    elif terms["cultures"]:
        crop = terms["cultures"][0]["lien"][0] if terms["cultures"][0]["lien"] else None
        source = "message" if crop else None
    try:
        gov = governorate(d["gouvernorat"]) if d.get("gouvernorat") else None
    except ValueError:
        gov = None
    found = [e["concept"] for g in ("cultures", "maladies", "ravageurs", "symptomes") for e in terms[g]]
    context = {**context_from_message(d.get("message")), **normalize_context(d)}  # the form wins
    known = ", ".join(f"{k}={v}" for k, v in context.items())
    return {"termes": terms, "langue_reponse": lang, "culture_code": crop, "culture_source": source,
            "gouvernorat_officiel": gov, "contexte": context,
            "trace": step("Linguistique", f"message compris ({terms['langue'] or 'vide'}) : "
                                         f"{', '.join(found) or 'aucun terme agricole'}"
                                         f" ; contexte : {known or 'aucun'}", t0)}


def traduire(d):
    """The answer written again by code in the farmer's language (French or Arabic): no LLM, no translation."""
    t0 = time.time()
    b = d["brouillon"]
    target = d.get("langue_reponse", "fr")
    if target == "fr" or target not in LANGS or not b.get("faits"):
        return {"brouillon": dict(b, langue="fr"), "trace": step("Linguistique", "réponse en français", t0)}
    text = compose(b["faits"], target)
    asked = len(b["faits"].get("questions_contexte") or [])
    return {"brouillon": dict(b, texte=text, langue=target),
            "trace": step("Linguistique", "réponse en arabe, écrite par le code"
                                          + (f" ; {asked} question(s) de contexte" if asked else ""), t0)}
