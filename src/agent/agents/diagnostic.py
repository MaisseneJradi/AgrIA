"""Agent Diagnostic: reads the photo with the four models and decides whether the diagnosis can be trusted.

1. Routeur: leaf, fruit or other. "other" -> ask for another photo.
2. The crop named by the farmer restricts the answer to the classes of that crop (predict(..., allowed=...)): a tomato
   leaf is never answered with an apple disease. If the photo holds little of the model's belief for that crop
   (mass < MIN_CROP_MASS), or the crop is not covered by the model, the agent says so and asks questions.
3. Fruit -> fruit model. Leaf -> the LEAF model (models/leaf: 51 disease classes and 9 deficiencies learnt together)
   decides the KIND of problem: deficiency (yellowing, discoloration) or disease (spots, mould, lesions), from the sum
   of its probabilities over the deficiency classes against the classes of the farmer's crop. Test set: 97.0 % of
   deficiencies and 98.9 % of diseases sorted right (results_vision.md, section 10). Then each kind goes to the best
   model for it:
     deficiency -> the leaf model's deficiency (89.4 % right class on test, against 86.4 % for the deficiency model);
     disease    -> the disease model, restricted to the crop (61.8 % on field photos and better calibrated than the
                   leaf model, which is over-confident on field photos: 77 % right above 0.9, against 89 %).
   Without models/leaf (older install), two models: disease model, unless there is a reason for the deficiency model:
     the farmer's words describe a deficiency (yellowing...), or the disease model sees a healthy leaf and the
     deficiency model a deficiency it trusts. The deficiency model was trained on deficiencies only: on a diseased
     leaf it answers "K deficiency" at 95 %+ (first tests on Internet photos of septoria and citrus canker), so it
     never overrides the disease model on its own confidence.
4. Trust (fiable) needs: the confidence above the agent threshold of the task (AGENT_THRESHOLDS, at least the model's
   own `reliable`), and the crop of the class equal to the crop the farmer named, when he named one.
   Diseases use 0.9: on field photos the disease model is right 89 % of the time above 0.9 but only 70 % above 0.5
   (results_vision.md, section 5).
5. Not trusted -> confirmation questions, never a product.
"""
import time

from src.agent import paths  # noqa: F401
from src.agent.paths import ROOT
from fertilizers import get_fertilizers  # src/tools
from predict import class_names, predict  # src/vision
from src.agent.agents.aides import class_name, crop_name, crop_of_class, step
from src.agent import ensemble as E
from src.agent.agents.identification import CROP_QUESTION, ROUTE_MIN

AGENT_THRESHOLDS = {"routing": ROUTE_MIN, "diseases": 0.9, "deficiency": 0.95, "fruits": 0.65}
MIN_CROP_MASS = 0.2
GENERAL_QUESTIONS = ["Pouvez-vous envoyer une autre photo, de près, d'une feuille ou d'un fruit atteint, à la lumière "
                     "du jour ?",
                     "Depuis quand voyez-vous ces symptômes, et sur combien de plantes ?",
                     "Les symptômes sont-ils plutôt sur les vieilles feuilles ou sur les jeunes ?"]


def _trusted(p, task):
    return p["reliable"] and p["confidence"] >= AGENT_THRESHOLDS[task]


def _threshold_note(p, task):
    return f"confiance {p['confidence']:.0%} sous le seuil de {AGENT_THRESHOLDS[task]:.0%}" \
        if p["confidence"] < AGENT_THRESHOLDS[task] else f"confiance {p['confidence']:.0%} sous le seuil du modèle"


def _crop_classes(task, crop):
    return [c for c in class_names(task) if crop_of_class(c) == crop]


def _predict_for_crop(task, photo, crop, doubts):
    """Prediction restricted to the crop the farmer named (if any); adds the reasons for doubt it finds."""
    if not crop:
        return predict(task, photo)
    allowed = _crop_classes(task, crop)
    if not allowed:
        doubts.append(f"le modèle ne connaît pas les maladies de : {crop_name(crop)}")
        return predict(task, photo)
    p = predict(task, photo, allowed)
    if p["mass"] < MIN_CROP_MASS:
        doubts.append(f"la photo ressemble peu à une plante de : {crop_name(crop)}")
    return p


def _leaf_model_available():
    return (ROOT / "models" / "leaf" / "model.pt").exists()


def _predict_leaf(d, photo, crop, doubts):
    """Combination of the leaf, disease and deficiency models and of the VLM (src/agent/ensemble.py).
    Returns (task, prediction, why, share of deficiency)."""
    op = d.get("opinions") or E.opinions(photo)
    share = E.kind_share(op, crop=crop)
    v = op.get("vlm") or {}
    seen = f" ; VLM : {v['probleme']} ({v.get('symptomes', '')})" if v.get("probleme") else ""
    if share >= 0.5:
        probs = E.deficiency_probs(op)
        ranked = E.top(probs, 3)
        p = {"class": ranked[0][0], "confidence": round(ranked[0][1] * share, 4), "top3": ranked, "reliable": True}
        return "deficiency", p, f"combinaison : carence ({share:.0%}){seen}", share
    probs, mass = E.disease_probs(op, crop)
    if crop and not probs:
        doubts.append(f"le modèle ne connaît pas les maladies de : {crop_name(crop)}")
        probs, mass = E.disease_probs(op, None)
    elif crop and mass is not None and mass < MIN_CROP_MASS:
        doubts.append(f"la photo ressemble peu à une plante de : {crop_name(crop)}")
    ranked = E.top(probs, 3)
    p = {"class": ranked[0][0], "confidence": ranked[0][1], "top3": ranked, "reliable": True, "mass": mass}
    return "diseases", p, f"combinaison : maladie ou feuille saine ({1 - share:.0%}){seen}", share


def _choose_leaf_model(dis, dfc, hints):
    deficiency_words = any(h.endswith("_deficiency") for h in hints)
    disease_words = any("__" in h for h in hints)
    if dfc["class"] != "healthy" and (dfc["class"] in hints or (deficiency_words and not disease_words)):
        return "deficiency", dfc, "le message décrit une carence"
    if dis["class"].endswith("healthy") and _trusted(dis, "diseases") and dfc["class"] != "healthy" \
            and _trusted(dfc, "deficiency"):
        return "deficiency", dfc, "aucune maladie visible, carence reconnue avec confiance"
    return "diseases", dis, "modèle des maladies (le modèle des carences n'a jamais vu de feuille malade)"


def diagnostiquer(d):
    t0 = time.time()
    photo = d.get("photo")
    if not photo:
        return {"issue": "autre_photo", "diagnostic": {"sans_photo": True}, "questions": [],
                "trace": step("Diagnostic", "pas de photo : en demander une", t0)}
    route = d.get("routage") or predict("routing", photo)  # already run by the Identification agent
    if route["class"] == "other" or not _trusted(route, "routing"):
        return {"issue": "autre_photo", "diagnostic": {"routing": route},
                "questions": [], "trace": step("Diagnostic", f"routeur : {route['class']} "
                                                             f"({route['confidence']}) -> autre photo", t0)}
    hints = set(d.get("termes", {}).get("classes_possibles", []))
    farmer_crop = d.get("culture_code")
    crop_doubts = []
    if route["class"] == "fruit":
        task, p, why = "fruits", _predict_for_crop("fruits", photo, farmer_crop, crop_doubts), "photo de fruit"
        other = None
    elif _leaf_model_available():
        task, p, why, share = _predict_leaf(d, photo, farmer_crop, crop_doubts)
        other = {"class": "part de carence (modèle feuille)", "confidence": round(share, 4)}
    else:
        dis = _predict_for_crop("diseases", photo, farmer_crop, crop_doubts)
        dfc = predict("deficiency", photo)
        task, p, why = _choose_leaf_model(dis, dfc, hints)
        other = dfc if task == "diseases" else dis
        if task == "deficiency":
            crop_doubts = []  # deficiencies are not tied to a crop in the model

    cls = p["class"]
    doubts = list(crop_doubts)
    info = d.get("culture_info") or {}
    if info.get("contradiction"):
        doubts.append(f"la photo ressemble à : {crop_name(info['predite'])} ({info['confiance']:.0%}), mais vous "
                      f"parlez de : {crop_name(farmer_crop)}")
    if info.get("non_couverte"):
        doubts.append("cette plante ne fait pas partie des cultures connues d'AgrIA")
    if info.get("inconnue"):
        doubts.append(f"culture à confirmer : la photo ressemble à : {crop_name(info['proposee'])} "
                      f"({info['confiance']:.0%})" if info.get("proposee") else "culture non reconnue sur la photo")
    if not _trusted(p, task):
        doubts.append(_threshold_note(p, task))
    class_crop = crop_of_class(cls)
    if farmer_crop and class_crop and farmer_crop != class_crop:
        doubts.append(f"la photo ressemble à : {crop_name(class_crop)}, mais vous parlez de : {crop_name(farmer_crop)}")
    diag = {"routing": route["class"], "task": task, "classe": cls, "nom": class_name(cls),
            "confiance": round(100 * p["confidence"]), "top3": p["top3"], "fiable": not doubts,
            "raisons_doute": doubts, "choix_du_modele": why, "masse_culture": p.get("mass"),
            "autre_modele": {"classe": other["class"], "confiance": other["confidence"]} if other else None,
            "sain": cls == "healthy" or cls.endswith("__healthy")}
    out = {"diagnostic": diag, "culture_code": farmer_crop or class_crop}
    if doubts:
        questions = []
        if task == "deficiency" and cls != "healthy":
            questions = get_fertilizers(cls)["questions_confirmation"]
        if info.get("inconnue") or info.get("contradiction"):
            questions = [CROP_QUESTION] + questions
        out.update(issue="question", questions=questions + GENERAL_QUESTIONS[:2])
    else:
        out.update(issue="conseil", questions=[])
    out["trace"] = step("Diagnostic", f"{route['class']} -> {task} : {cls} ({p['confidence']:.2f}"
                                      f"{', culture ' + farmer_crop if farmer_crop and task != 'deficiency' else ''}), "
                                      f"{'fiable' if not doubts else 'doute : ' + '; '.join(doubts)}", t0)
    return out
