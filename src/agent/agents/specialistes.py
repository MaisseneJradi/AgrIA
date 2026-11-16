"""The two specialist agents, run in parallel once the diagnosis is trusted.

Agent Phytosanitaire: registered pesticides for the disease or pest, on the farmer's crop (get_treatments), and
  prevention advice from the sheets (search_knowledge). Products are chosen HERE, in code: at most MAX_PRODUCTS,
  relation direct or vecteur first, a known DAR first; "proche" only when nothing else exists, with a warning.
Agent Agronome: fertilizers for a deficiency (get_fertilizers: reliability on this crop, soil of the governorate,
  confirmation questions) and the irrigation need of the month (get_water_need).
"""
import datetime
import time

from src.agent import paths  # noqa: F401
from fertilizers import get_fertilizers  # src/tools
from rag import search_knowledge
from src.agent.agents.aides import step
from treatments import get_treatments
from water import get_water_need

MAX_PRODUCTS = 3
MONTHS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]


def phytosanitaire(d):
    t0 = time.time()
    diag = d["diagnostic"]
    if diag["task"] == "deficiency" or diag["sain"]:
        return {"traitements": {"concerne": False},
                "trace": step("Phytosanitaire", "rien à traiter (carence ou plante saine)", t0)}
    cls, crop = diag["classe"], d.get("culture_code")
    usages = get_treatments(cls, crop)
    main = [u for u in usages if u["relation"] in ("direct", "vecteur", "groupe")] or usages
    chosen, seen = [], set()
    for u in main:  # already sorted: relation, then known DAR first
        if u["produit"] not in seen:
            seen.add(u["produit"])
            chosen.append(u)
        if len(chosen) >= MAX_PRODUCTS:
            break
    warnings = []
    for u in chosen:
        if u["relation"] in ("vecteur", "proche"):
            warnings.append(f"{u['produit']} : {u['relation_sens']}")
        if u["autorisation_provisoire"]:
            warnings.append(f"{u['produit']} : autorisation provisoire de vente")
        if u["restriction"]:
            warnings.append(f"{u['produit']} : {u['restriction']}")
    passages = search_knowledge("lutte prévention traitement", k=2, classe=cls)
    produits = [{"nom": u["produit"], "substances": u["substances"], "dose": u["dose"], "dar_jours": u["dar_jours"],
                 "dar_message": u["dar_message"], "relation": u["relation"], "product_id": u["product_id"]}
                for u in chosen]
    return {"traitements": {"concerne": True, "produits": produits, "nb_usages": len(usages),
                            "aucun_produit": not usages, "avertissements": warnings,
                            "conseils": [p["extrait"][:300] for p in passages]},
            "sources": [{"fiche": p["nom"], "lien": p["source"], "licence": p["licence"]} for p in passages],
            "trace": step("Phytosanitaire", f"{len(usages)} usages homologués, {len(produits)} retenus", t0)}


def agronome(d):
    t0 = time.time()
    diag, crop, gov = d["diagnostic"], d.get("culture_code"), d.get("gouvernorat_officiel")
    out, notes = {}, []
    if diag["task"] == "deficiency" and not diag["sain"]:
        f = get_fertilizers(diag["classe"], crop, gov, max_products=3)
        out["engrais"] = {"produits": [{"nom": p["nom"], "nutriment": p["nutriment"], "teneur_pct": p["teneur_pct"],
                                        "doses": p["doses"][:2], "url": p["url"]} for p in f["produits"]],
                          "fiabilite": f["fiabilite"], "hypothese": f["fiabilite"] == "hypothese",
                          "questions": f["questions_confirmation"], "message": f["message"],
                          "avertissement_modele": f.get("avertissement_modele"), "sol": f["sol"]}
        notes.append(f"{len(f['produits'])} engrais, fiabilité {f['fiabilite']}")
    month = d.get("mois") or datetime.date.today().month
    if gov and crop:
        try:
            w = get_water_need(gov, crop, month)
            if w["en_saison"]:
                out["eau"] = (f"Irrigation en {MONTHS[month]} à {gov} : besoin moyen d'environ {w['deficit_mm']} mm "
                              f"({w['deficit_m3_ha']} m³/ha), soit {w['deficit_mm_jour']} mm par jour après la pluie.")
                notes.append("besoin en eau calculé")
        except ValueError as e:
            notes.append(f"pas de besoin en eau ({e})")
    return {"agronomie": out, "trace": step("Agronome", "; ".join(notes) or "rien à ajouter", t0)}
