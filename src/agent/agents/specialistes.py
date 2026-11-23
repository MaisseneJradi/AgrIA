"""The two specialist agents, run in parallel once the diagnosis is trusted.

Agent Phytosanitaire: registered pesticides for the disease or pest, on the farmer's crop (get_treatments), and
  prevention advice from the sheets (search_knowledge), cleaned of any chemical control (prevention.py). Products are
  chosen HERE, in code (ranking.py): the uses that do not fit the situation are set aside (DAR longer than the days
  to harvest, export with a substance not approved in the EU, organic farm), the others are ranked (relation, early
  stage -> organic-allowed first, toxicity, shorter DAR, rotation of groups) and the MAX_PRODUCTS first are kept, each
  with its reasons; "proche" only when nothing else exists, with a warning. The context fields still unknown that
  would change this choice become questions (at most 3). When nothing is registered, or nothing fits: validated
  prevention advice and the CRDA referral, never a product.
Agent Agronome: fertilizers for a deficiency (get_fertilizers: reliability on this crop, soil of the governorate,
  confirmation questions) and the irrigation need of the month (get_water_need).
"""
import datetime
import time

from src.agent import paths  # noqa: F401
from dose_calc import practical_dose  # src/tools
from fertilizers import get_fertilizers
from hazard import bee_toxic, who_class
from weather import spray_conditions
from prevention import cultural_sentences, prevention_advice
from rag import search_knowledge
from ranking import decisive_fields, rank
from src.agent.agents.aides import step
from treatments import get_treatments
from water import get_water_need

MAX_PRODUCTS = 3


def phytosanitaire(d):
    t0 = time.time()
    diag = d["diagnostic"]
    if diag["task"] == "deficiency" or diag["sain"]:
        return {"traitements": {"concerne": False},
                "trace": step("Phytosanitaire", "rien à traiter (carence ou plante saine)", t0)}
    cls, crop = diag["classe"], d.get("culture_code")
    ctx = d.get("contexte") or {}
    usages = get_treatments(cls, crop)
    main = [u for u in usages if u["relation"] in ("direct", "vecteur", "groupe")] or usages
    ranked = rank(main, ctx, MAX_PRODUCTS)  # filters of the situation, then the score written in ranking.py
    chosen = ranked["retenus"]
    questions = decisive_fields(main, ctx, MAX_PRODUCTS) if main else []
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
                 "dar_message": u["dar_message"], "relation": u["relation"], "product_id": u["product_id"],
                 "bio_ue": u["bio_ue"], "ue_approuve": u["ue_approuve"], "raisons": u["raisons"],
                 # the registered dose for a 16 L sprayer and the farmer's area (dose_calc.py): None when unreadable
                 "dose_pratique": practical_dose(u["dose"], ctx.get("area")),
                 # applicator and bee safety (validated rows of docs/substance_hazard.csv and docs/bee_hazard.csv)
                 "classe_oms": who_class(u), "abeilles": bool(bee_toxic(u))}
                for u in chosen]
    # weather of the next hours (Open-Meteo, cached; nothing when unreachable; not under a greenhouse)
    meteo = spray_conditions(d.get("gouvernorat_officiel")) if produits and ctx.get("greenhouse") != "y" else None
    # advice never carries a product: sentences of the sheets without chemistry, and, when nothing is registered,
    # the validated prevention advice of docs/conseils_prevention.csv and the CRDA referral
    conseils = cultural_sentences(passages)
    prevention = prevention_advice(cls) if not usages else []
    # registered products exist, but none fits the farmer's situation (DAR, export, organic): say why, then the CRDA
    none_fits = bool(main) and not chosen
    note = f"{len(usages)} usages homologués, {len(produits)} retenus"
    if ranked["ecartes"]:
        note += f", {len(ranked['ecartes'])} écartés pour la situation ({ctx})"
    if questions:
        note += f" ; à demander : {', '.join(questions)}"
    if not usages:
        note += f" ; {len(prevention)} mesures de prévention validées, orientation CRDA"
    return {"traitements": {"concerne": True, "produits": produits, "nb_usages": len(usages),
                            "aucun_produit": not usages, "avertissements": warnings, "conseils": conseils,
                            "prevention": prevention, "orientation_crda": not usages or none_fits,
                            "ecartes": ranked["ecartes"], "aucun_adapte": none_fits,
                            "n_candidats": ranked["n_candidats"], "questions_contexte": questions,
                            "dernier_groupe": ranked["dernier_groupe"], "meteo": meteo,
                            "rotation_impossible": ranked["rotation_impossible"],
                            # one line on rotation when a product of the answer has a known FRAC / IRAC group
                            "rotation_conseil": any(r[0] in ("groupe", "rotation") for p in produits
                                                    for r in p["raisons"])},
            "sources": [{"fiche": p["nom"], "lien": p["source"], "licence": p["licence"]} for p in passages],
            "trace": step("Phytosanitaire", note, t0)}


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
                out["eau"] = {"mois": month, "gouvernorat": gov, "mm": w["deficit_mm"], "m3": w["deficit_m3_ha"],
                              "mmj": w["deficit_mm_jour"]}
                notes.append("besoin en eau calculé")
        except ValueError as e:
            notes.append(f"pas de besoin en eau ({e})")
    return {"agronomie": out, "trace": step("Agronome", "; ".join(notes) or "rien à ajouter", t0)}
