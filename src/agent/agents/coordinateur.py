"""Agent Coordinateur: plans the case, gathers what the other agents found, has the answer written and, when the
Vérificateur blocks it, rewrites it without what was blocked (at most MAX_REWRITES times, then the CRDA).

The products and fertilizers of the answer are copied from the specialist agents, never invented: the LLM only
writes the text around them.
"""
import time

from src.agent import paths  # noqa: F401
from src.agent.agents.aides import class_name, step
from src.agent.llm import compose_french, get_llm

MAX_REWRITES = 2


def planifier(d):
    t0 = time.time()
    plan = "Linguistique -> Diagnostic -> (Phytosanitaire + Agronome) -> rédaction -> Linguistique -> Vérificateur"
    if not d.get("photo"):
        plan = "pas de photo : Linguistique -> Diagnostic (demande de photo) -> rédaction -> Vérificateur"
    return {"essais": 0, "sources": [], "trace": step("Coordinateur", f"plan : {plan}", t0)}


def _blocked_names(verification):
    reasons = " ".join((verification or {}).get("raisons", []))
    return reasons


def rediger(d):
    t0 = time.time()
    issue = d.get("issue", "question")
    diag = d.get("diagnostic") or {}
    tr = d.get("traitements") or {}
    ag = d.get("agronomie") or {}
    eng = ag.get("engrais") or {}
    previous = d.get("verification") or {}
    blocked = _blocked_names(previous)

    produits = [p for p in tr.get("produits", []) if f"« {p['nom']}" not in blocked]
    engrais = [e for e in eng.get("produits", []) if f"« {e['nom']}" not in blocked]
    hypothese = bool(eng.get("hypothese")) or "hypothèse" in blocked
    warnings = list(tr.get("avertissements", []))
    if eng.get("avertissement_modele"):
        warnings.append(eng["avertissement_modele"])
    if eng.get("message") and hypothese:
        warnings.append(eng["message"])
    if any(p["dar_jours"] is None for p in produits):
        warnings.append("délai avant récolte non précisé dans la liste officielle pour certains produits : "
                        "voir l'étiquette")
    if issue == "question":
        top = [class_name(c) for c, _ in diag.get("top3", [])[:2]]
        facts = {"issue": "question", "doute": "; ".join(diag.get("raisons_doute", [])), "pistes": top,
                 "questions": d.get("questions", [])}
    elif issue == "autre_photo":
        facts = {"issue": "autre_photo", "sans_photo": bool(diag.get("sans_photo"))}
    else:
        facts = {"issue": issue, "diagnostic": diag, "produits": produits, "aucun_produit": tr.get("aucun_produit"),
                 "conseils": tr.get("conseils", []), "engrais": engrais, "hypothese": hypothese,
                 "questions": eng.get("questions", []) if hypothese else [], "eau": ag.get("eau"),
                 "avertissements": warnings, "gouvernorat": d.get("gouvernorat_officiel")}
    text = get_llm().write("rediger", facts)
    draft = {"task": diag.get("task"), "classe": diag.get("classe"), "culture": d.get("culture_code"),
             "fiable": diag.get("fiable", False), "hypothese": hypothese,
             "produits": [{"nom": p["nom"], "dose": p["dose"], "dar_jours": p["dar_jours"]} for p in produits]
             if issue == "conseil" else [],
             "engrais": [{"nom": e["nom"]} for e in engrais] if issue == "conseil" else [],
             "texte": text, "avertissements": warnings if issue == "conseil" else []}
    n = d.get("essais", 0)
    action = "réponse rédigée" if n == 0 else f"réponse réécrite (essai {n + 1}) sans : {blocked[:120]}"
    return {"brouillon": draft, "trace": step("Coordinateur", action, t0)}


def crda(d):
    """Written by code, not by the LLM: the way out must not depend on the model that was just blocked."""
    t0 = time.time()
    text = compose_french({"issue": "crda", "gouvernorat": d.get("gouvernorat_officiel")})
    diag = d.get("diagnostic") or {}
    return {"issue": "crda", "brouillon": {"task": diag.get("task"), "classe": diag.get("classe"),
                                           "culture": d.get("culture_code"), "fiable": False, "produits": [],
                                           "engrais": [], "texte": text, "avertissements": []},
            "trace": step("Coordinateur", f"{MAX_REWRITES} réécritures bloquées : orientation vers le CRDA", t0)}


SAFE_TEXT = ("Je ne peux pas vous conseiller de produit pour ce cas. Contactez le CRDA de votre gouvernorat : un "
             "technicien pourra examiner la plante.")


def secours(d):
    """Last resort when even the CRDA message was blocked (e.g. a faulty translation): fixed French text, no LLM."""
    t0 = time.time()
    b = dict(d["brouillon"], texte=SAFE_TEXT, langue="fr", produits=[], engrais=[], avertissements=[])
    return {"brouillon": b, "verification": {"valide": True, "raisons": [], "avertissements": [],
                                             "produits_verifies": [], "secours": True},
            "trace": step("Coordinateur", "message CRDA bloqué lui aussi : texte de secours fixe", t0)}


def finaliser(d):
    t0 = time.time()
    b, diag = d["brouillon"], d.get("diagnostic") or {}
    reponse = {
        "issue": d.get("issue"), "texte": b["texte"], "langue": b.get("langue", "fr"),
        "diagnostic": {k: diag.get(k) for k in ("task", "classe", "nom", "confiance", "fiable", "raisons_doute")}
        if diag.get("classe") else None,
        "produits": b["produits"], "engrais": b["engrais"], "avertissements": b.get("avertissements", []),
        "questions": d.get("questions", []) if d.get("issue") == "question" else [],
        "sources": list({s["lien"]: s for s in d.get("sources", [])}.values()), "verification": d.get("verification"),
    }
    return {"reponse": reponse, "trace": step("Coordinateur", f"réponse envoyée ({reponse['issue']})", t0)}
