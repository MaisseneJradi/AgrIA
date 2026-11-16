"""Agent Linguistique: understands the farmer's message (French, Arabic, darija, arabizi) and writes the final answer in
French or Arabic (a message in darija or arabizi is answered in Arabic).

comprendre: terms of the lexicon, crop, governorate, language of the answer.
traduire:   the answer written again by code in French or Arabic (src/agent/redaction.py). No LLM: a fact can never
            be mistranslated. The Vérificateur checks the final text.
"""
import time

from src.agent import paths  # noqa: F401
from common import governorate  # src/tools
from lexicon import crop_code, normalize_terms
from src.agent.agents.aides import step
from src.agent.redaction import LANGS, compose

LANGUAGES = {"fr": "fr", "ar": "ar", "arabizi": "ar", "darija": "ar"}  # answers in French or Arabic only


def comprendre(d):
    t0 = time.time()
    terms = normalize_terms(d.get("message") or "")
    lang = LANGUAGES.get(d.get("langue") or "", None) or LANGUAGES.get(terms["langue"] or "", "fr")
    crop = None
    if d.get("culture"):
        crop = crop_code(d["culture"])
    elif terms["cultures"]:
        crop = terms["cultures"][0]["lien"][0] if terms["cultures"][0]["lien"] else None
    try:
        gov = governorate(d["gouvernorat"]) if d.get("gouvernorat") else None
    except ValueError:
        gov = None
    found = [e["concept"] for g in ("cultures", "maladies", "ravageurs", "symptomes") for e in terms[g]]
    return {"termes": terms, "langue_reponse": lang, "culture_code": crop, "gouvernorat_officiel": gov,
            "trace": step("Linguistique", f"message compris ({terms['langue'] or 'vide'}) : "
                                         f"{', '.join(found) or 'aucun terme agricole'}", t0)}


def traduire(d):
    """The answer written again by code in the farmer's language (French or Arabic): no LLM, no translation."""
    t0 = time.time()
    b = d["brouillon"]
    target = d.get("langue_reponse", "fr")
    if target == "fr" or target not in LANGS or not b.get("faits"):
        return {"brouillon": dict(b, langue="fr"), "trace": step("Linguistique", "réponse en français", t0)}
    text = compose(b["faits"], target)
    return {"brouillon": dict(b, texte=text, langue=target),
            "trace": step("Linguistique", "réponse en arabe, écrite par le code", t0)}
