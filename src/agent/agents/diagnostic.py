"""Agent Diagnostic: reads the photo with the four models and decides whether the diagnosis can be trusted.

1. Routeur: leaf, fruit or other. "other" -> ask for another photo.
2. Fruit -> fruit model. Leaf -> disease model AND deficiency model, then one is kept:
     the class named by the farmer's words (lexicon) if one model found it; else the disease model when it sees a
     disease it trusts; else the deficiency model when it sees a deficiency it trusts; else the disease model.
3. Trust (fiable) needs: the confidence above the agent threshold of the task (AGENT_THRESHOLDS, at least the model's
   own `reliable`), and the crop of the class equal to the crop the farmer named, when he named one.
   Diseases use 0.9: on field photos the disease model is right 89 % of the time above 0.9 but only 70 % above 0.5
   (results_vision.md, section 5).
4. Not trusted -> confirmation questions, never a product.
"""
import time

from src.agent import paths  # noqa: F401
from fertilizers import get_fertilizers  # src/tools
from predict import predict  # src/vision
from src.agent.agents.aides import class_name, crop_name, crop_of_class, step

AGENT_THRESHOLDS = {"routing": 0.5, "diseases": 0.9, "deficiency": 0.95, "fruits": 0.65}
GENERAL_QUESTIONS = ["Pouvez-vous envoyer une autre photo, de près, d'une feuille ou d'un fruit atteint, à la lumière "
                     "du jour ?",
                     "Depuis quand voyez-vous ces symptômes, et sur combien de plantes ?",
                     "Les symptômes sont-ils plutôt sur les vieilles feuilles ou sur les jeunes ?"]


def _trusted(p, task):
    return p["reliable"] and p["confidence"] >= AGENT_THRESHOLDS[task]


def _choose_leaf_model(dis, dfc, hints):
    if dfc["class"] in hints and dis["class"] not in hints and dfc["class"] != "healthy":
        return "deficiency", dfc, "le message décrit une carence"
    if dis["class"] in hints:
        return "diseases", dis, "le message décrit cette maladie"
    dis_sick = not dis["class"].endswith("healthy")
    if dis_sick and _trusted(dis, "diseases"):
        return "diseases", dis, "maladie reconnue avec confiance"
    if dfc["class"] != "healthy" and _trusted(dfc, "deficiency"):
        return "deficiency", dfc, "carence reconnue avec confiance"
    return "diseases", dis, "modèle des maladies par défaut"


def diagnostiquer(d):
    t0 = time.time()
    photo = d.get("photo")
    if not photo:
        return {"issue": "autre_photo", "diagnostic": {"sans_photo": True}, "questions": [],
                "trace": step("Diagnostic", "pas de photo : en demander une", t0)}
    route = predict("routing", photo)
    if route["class"] == "other" or not _trusted(route, "routing"):
        return {"issue": "autre_photo", "diagnostic": {"routing": route},
                "questions": [], "trace": step("Diagnostic", f"routeur : {route['class']} "
                                                             f"({route['confidence']}) -> autre photo", t0)}
    hints = set(d.get("termes", {}).get("classes_possibles", []))
    if route["class"] == "fruit":
        task, p, why = "fruits", predict("fruits", photo), "photo de fruit"
        other = None
    else:
        dis, dfc = predict("diseases", photo), predict("deficiency", photo)
        task, p, why = _choose_leaf_model(dis, dfc, hints)
        other = dfc if task == "diseases" else dis

    cls = p["class"]
    doubts = []
    if not _trusted(p, task):
        doubts.append(f"confiance {p['confidence']:.0%} sous le seuil de {AGENT_THRESHOLDS[task]:.0%}")
    farmer_crop, class_crop = d.get("culture_code"), crop_of_class(cls)
    if farmer_crop and class_crop and farmer_crop != class_crop:
        doubts.append(f"la photo ressemble à : {crop_name(class_crop)}, mais vous parlez de : {crop_name(farmer_crop)}")
    diag = {"routing": route["class"], "task": task, "classe": cls, "nom": class_name(cls),
            "confiance": round(100 * p["confidence"]), "top3": p["top3"], "fiable": not doubts,
            "raisons_doute": doubts, "choix_du_modele": why,
            "autre_modele": {"classe": other["class"], "confiance": other["confidence"]} if other else None,
            "sain": cls == "healthy" or cls.endswith("__healthy")}
    out = {"diagnostic": diag, "culture_code": farmer_crop or class_crop}
    if doubts:
        questions = []
        if task == "deficiency" and cls != "healthy":
            questions = get_fertilizers(cls)["questions_confirmation"]
        out.update(issue="question", questions=questions + GENERAL_QUESTIONS[:2])
    else:
        out.update(issue="conseil", questions=[])
    out["trace"] = step("Diagnostic", f"{route['class']} -> {task} : {cls} ({p['confidence']:.2f}), "
                                      f"{'fiable' if not doubts else 'doute : ' + '; '.join(doubts)}", t0)
    return out
