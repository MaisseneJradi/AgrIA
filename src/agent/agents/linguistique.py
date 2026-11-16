"""Agent Linguistique: understands the farmer's message (French, Arabic, darija, arabizi) and writes the final answer in
the farmer's language.

comprendre: terms of the lexicon, crop, governorate, language of the answer.
traduire:   French answer -> language of the farmer, by the LLM. Product names, doses and DAR are kept as written
            (the Vérificateur checks the translated text). Without an LLM the answer stays in French and says so.
"""
import time

from src.agent import paths  # noqa: F401
from common import governorate  # src/tools
from lexicon import crop_code, normalize_terms
from src.agent.agents.aides import step
from src.agent.llm import get_llm

LANGUAGES = {"fr": "fr", "ar": "ar", "arabizi": "darija", "darija": "darija"}


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
    t0 = time.time()
    b = d["brouillon"]
    target = d.get("langue_reponse", "fr")
    llm = get_llm()
    text = b["texte"] if target == "fr" else llm.write("traduire", {"texte": b["texte"], "langue": target})
    done = target == "fr" or llm.name != "template"
    out = dict(b, texte=text, langue=target if done else "fr")
    note = "réponse en français" if target == "fr" else (
        f"traduite en {target}" if done else f"traduction en {target} indisponible sans LLM : réponse en français")
    return {"brouillon": out, "trace": step("Linguistique", note, t0)}
