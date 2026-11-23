"""Agent Coordinateur: plans the case, gathers what the other agents found, has the answer written and, when the
Vérificateur blocks it, rewrites it without what was blocked (at most MAX_REWRITES times, then the CRDA).

The products and fertilizers of the answer are copied from the specialist agents, never invented, and the text is
written by code (src/agent/redaction.py). The facts are kept in the draft ("faits") for the Agent Linguistique.
"""
import time

from src.agent import paths  # noqa: F401
from src.agent.agents.aides import class_name, step
from src.agent.redaction import compose

MAX_REWRITES = 2


def planifier(d):
    t0 = time.time()
    plan = ("Linguistique -> Identification de la culture -> Diagnostic -> (Phytosanitaire + Agronome) -> rédaction "
            "-> Linguistique -> Vérificateur")
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
    if any(p["dar_jours"] is None for p in produits):
        warnings.append("délai avant récolte non précisé dans la liste officielle pour certains produits : "
                        "voir l'étiquette")
    if issue == "question":
        top = [(c, class_name(c)) for c, _ in diag.get("top3", [])[:2]]
        facts = {"issue": "question", "doute": "; ".join(diag.get("raisons_doute", [])), "pistes": top,
                 "questions": d.get("questions", [])}
    elif issue == "autre_photo":
        facts = {"issue": "autre_photo", "sans_photo": bool(diag.get("sans_photo"))}
    else:
        # blocked for chemical control outside the registered products: the quoted passages go, the facts stay
        conseils = [] if "lutte chimique" in blocked else tr.get("conseils", [])
        facts = {"issue": issue, "diagnostic": diag, "produits": produits, "aucun_produit": tr.get("aucun_produit"),
                 "conseils": conseils, "prevention": tr.get("prevention", []),
                 "orientation_crda": tr.get("orientation_crda", False), "engrais": engrais, "hypothese": hypothese,
                 "questions": eng.get("questions", []) if hypothese else [], "eau": ag.get("eau"),
                 "avertissements": warnings, "gouvernorat": d.get("gouvernorat_officiel"),
                 "sources": list({s["lien"]: s for s in d.get("sources", [])}.values())}
    text = compose(facts, "fr")
    draft = {"task": diag.get("task"), "classe": diag.get("classe"), "culture": d.get("culture_code"),
             "fiable": diag.get("fiable", False), "hypothese": hypothese,
             "produits": [{"nom": p["nom"], "dose": p["dose"], "dar_jours": p["dar_jours"]} for p in produits]
             if issue == "conseil" else [],
             "engrais": [{"nom": e["nom"]} for e in engrais] if issue == "conseil" else [],
             "texte": text, "avertissements": warnings if issue == "conseil" else [], "faits": facts}
    n = d.get("essais", 0)
    action = "réponse rédigée" if n == 0 else f"réponse réécrite (essai {n + 1}) sans : {blocked[:120]}"
    return {"brouillon": draft, "trace": step("Coordinateur", action, t0)}


def crda(d):
    """Way out after MAX_REWRITES blocked answers: no product, the CRDA of the governorate."""
    t0 = time.time()
    facts = {"issue": "crda", "gouvernorat": d.get("gouvernorat_officiel")}
    text = compose(facts, "fr")
    diag = d.get("diagnostic") or {}
    return {"issue": "crda", "brouillon": {"task": diag.get("task"), "classe": diag.get("classe"),
                                           "culture": d.get("culture_code"), "fiable": False, "produits": [],
                                           "engrais": [], "texte": text, "avertissements": [],
                                           "faits": facts},
            "trace": step("Coordinateur", f"{MAX_REWRITES} réécritures bloquées : orientation vers le CRDA", t0)}


SAFE_TEXT = ("Je ne peux pas vous conseiller de produit pour ce cas. Contactez le CRDA de votre gouvernorat : un "
             "technicien pourra examiner la plante.")


def secours(d):
    """Last resort when even the CRDA message was blocked (should never happen): fixed French text."""
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
        "diagnostic": {k: diag.get(k) for k in ("routing", "task", "classe", "nom", "confiance", "fiable",
                                                 "raisons_doute", "top3", "autre_modele", "choix_du_modele")}
        if diag.get("classe") else None,
        "culture": {"code": d.get("culture_code"), **(d.get("culture_info") or {})} if d.get("photo") else None,
        "produits": b["produits"], "engrais": b["engrais"], "avertissements": b.get("avertissements", []),
        "questions": d.get("questions", []) if d.get("issue") == "question" else [],
        "sources": list({s["lien"]: s for s in d.get("sources", [])}.values()), "verification": d.get("verification"),
    }
    return {"reponse": reponse, "trace": step("Coordinateur", f"réponse envoyée ({reponse['issue']})", t0)}
