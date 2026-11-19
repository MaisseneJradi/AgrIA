"""Agent Identification de la culture: which plant is on the photo, before any diagnosis.

Model: models/crop = crop_v3a (EfficientNet-B0, 15 classes: the 14 crops of the project and "autre_plante"), trained
on every leaf image of the project with its crop as label (src/vision/dataset.py, task "crop"), including the new
olive and citrus sources (lemon_bd, olive_cam...). Alone: 85.9 % on the 199 field photos. In the vote with the disease
model (docs/eval_ensemble.md): 86.9 % on field photos with 2.0 % sure and wrong, 99.5 % on the new sources.
The previous model (crop_v1) is kept in models/crop_v1: as good on field photos, but 0/36 on lemon leaves (lemon_bd).
Why: without the crop, the diagnosis models answer with the disease of another plant (first tests in the app: a citrus
leaf answered "bacterial spot of tomato", "healthy apple"...); with the crop, the diagnosis is restricted to it.

The model PROPOSES, the farmer CONFIRMS. On photos from the Internet (plain or white background) the model was very
sure of a wrong crop 5 times out of 15 (a citrus leaf "pepper 98 %", an olive leaf "apple 100 %"): it partly learnt the
style of the photos of each source. So:
  - the app calls recognise() as soon as a photo is chosen (POST /identify) and pre-fills the crop field; the farmer
    keeps or corrects it, then the diagnosis runs on the confirmed crop;
  - in the graph, a crop given by the farmer is kept; if the model is very sure of another crop (>= CONTRADICT), the
    contradiction becomes a reason for doubt (question);
  - no crop given: the recognised crop is only proposed, never imposed: the answer asks to confirm it, no product;
  - a plant the model is sure is not a crop of the project is said to be not covered.
"""
import time

from src.agent import paths  # noqa: F401
from src.agent.agents.aides import crop_name, step
from src.agent.paths import ROOT
from predict import predict  # src/vision
from src.agent import ensemble as E

ACCEPT = 0.85      # confidence above which a crop is proposed (field photos: ~93 % right above 0.85)
CONTRADICT = 0.95  # model sure enough to question the crop the farmer gave (field photos: 95.6 % right)
CROP_QUESTION = "Quelle est la culture (tomate, olivier, agrumes, poivron, vigne…) ?"


def crop_model_available():
    return (ROOT / "models" / "crop" / "model.pt").exists()


def recognise(photo):
    """Router, then the crop VOTE of several opinions (src/agent/ensemble.py: crop model, disease and leaf models
    summed per crop, VLM when enabled, with the weights learnt on the validation sets). Used by the agent and by
    POST /identify. "opinions" holds every model output, reused by the Diagnostic agent."""
    route = predict("routing", photo)
    out = {"routage": route, "feuille": route["class"] == "leaf"}
    if route["class"] != "leaf" or not crop_model_available():
        return out
    op = E.opinions(photo)
    vote = E.crop_decision(op)  # vote of the models, the VLM (if enabled) as check and fallback
    out.update(predite=vote["culture"], confiance=vote["confiance"], top3=vote["top3"],
               sure=vote["sure"], autre_plante=vote["culture"] == "autre_plante",
               avis=vote["avis"], accord=vote["accord"], n_avis=vote["n_avis"], opinions=op,
               source_culture=vote["source"], desaccord_vlm=vote.get("desaccord_vlm", False))
    return out


def identifier(d):
    t0 = time.time()
    photo, given = d.get("photo"), d.get("culture_code")
    if not photo:
        return {"culture_info": {"source": d.get("culture_source")},
                "trace": step("Identification", "pas de photo", t0)}
    r = recognise(photo)
    out = {"routage": r["routage"], "opinions": r.get("opinions")}
    if "predite" not in r:
        why = "photo de fruit ou autre : culture laissée au diagnostic" if not r["feuille"] else "modèle de culture absent"
        out.update(culture_info={"source": d.get("culture_source")}, trace=step("Identification", why, t0))
        return out
    info = {k: r[k] for k in ("predite", "confiance", "top3", "avis", "accord", "n_avis", "source_culture",
                              "desaccord_vlm")}
    info["source"] = d.get("culture_source")
    seen = (f"{'autre plante' if r['autre_plante'] else crop_name(r['predite'])} ({r['confiance']:.0%}, "
            f"{r['accord']}/{r['n_avis']} avis d'accord"
            f"{', proposée par le VLM' if r['source_culture'] == 'vlm' else ''}"
            f"{', le VLM voit une autre culture' if r['desaccord_vlm'] else ''})")
    if given:
        if r["predite"] != given and r["sure"] and r["confiance"] >= CONTRADICT:  # never on the VLM alone
            info["contradiction"] = True
            action = f"vous dites {crop_name(given)}, la photo montre {seen} : à confirmer"
        else:
            action = f"culture confirmée : {crop_name(given)} ; photo : {seen}"
    elif r["autre_plante"] and r["sure"]:
        info["non_couverte"] = True
        action = f"photo : {seen}, plante non couverte par AgrIA"
    else:
        info["inconnue"] = True
        if r["sure"]:
            info["proposee"] = r["predite"]
            action = f"culture proposée : {seen}, à confirmer par l'agriculteur"
        else:
            action = f"culture incertaine sur la photo ({seen}) : la demander"
    out.update(culture_info=info, trace=step("Identification", action, t0))
    return out
