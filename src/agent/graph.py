"""The graph of the seven agents (LangGraph) and the entry point used by the API.

  from src.agent.graph import diagnose
  diagnose(photo="feuille.jpg", message="tmatem fiha mildiou", gouvernorat="Nabeul")
  -> {"issue": "conseil" | "question" | "autre_photo" | "crda", "texte": ..., "langue": ..., "diagnostic": ...,
      "produits": [...], "engrais": [...], "avertissements": [...], "questions": [...], "sources": [...],
      "verification": {...}, "trace": [...], "duree_s": ...}

  START -> Coordinateur.planifier -> Linguistique.comprendre -> Identification de la culture -> Diagnostic
        -> conseil:              Phytosanitaire + Agronome (in parallel) -> Coordinateur.rediger
        -> question, autre photo: Coordinateur.rediger
  Coordinateur.rediger -> Linguistique.traduire -> Vérificateur
        -> valid:                         Coordinateur.finaliser -> END
        -> blocked, rewrites left:        Coordinateur.rediger (without what was blocked)
        -> blocked, no rewrite left:      Coordinateur.crda (text by code) -> Linguistique.traduire -> Vérificateur
        -> CRDA message blocked too:      Coordinateur.secours (fixed text) -> Coordinateur.finaliser -> END
Draw it: python src/agent/graph.py --mermaid
"""
import time
from functools import lru_cache

# importing LangGraph 0.6.11 prints a LangChainPendingDeprecationWarning about `allowed_objects`: a notice on a
# future default of langchain_core, harmless here (no deserialisation of untrusted data)
from langgraph.graph import END, START, StateGraph

from src.agent import paths  # noqa: F401
from src.agent.agents.coordinateur import MAX_REWRITES, crda, finaliser, planifier, rediger, secours
from src.agent.agents.diagnostic import diagnostiquer
from src.agent.agents.identification import identifier
from src.agent.agents.linguistique import CONTEXT_FIELDS, comprendre, traduire
from src.agent.agents.specialistes import agronome, phytosanitaire
from src.agent.agents.verificateur import verifier
from src.agent.state import Dossier


def _after_diagnosis(d):
    return ["phytosanitaire", "agronome"] if d["issue"] == "conseil" else "rediger"


def _after_check(d):
    if d["verification"]["valide"]:
        return "finaliser"
    if d.get("issue") == "crda":
        return "secours"  # even the CRDA message was blocked: fixed text, the graph always ends
    return "rediger" if d["essais"] <= MAX_REWRITES else "crda"


@lru_cache(maxsize=1)
def build():
    g = StateGraph(Dossier)
    g.add_node("planifier", planifier)
    g.add_node("comprendre", comprendre)
    g.add_node("identifier", identifier)
    g.add_node("diagnostiquer", diagnostiquer)
    g.add_node("phytosanitaire", phytosanitaire)
    g.add_node("agronome", agronome)
    g.add_node("rediger", rediger)
    g.add_node("traduire", traduire)
    g.add_node("verifier", verifier)
    g.add_node("crda", crda)
    g.add_node("secours", secours)
    g.add_node("finaliser", finaliser)

    g.add_edge(START, "planifier")
    g.add_edge("planifier", "comprendre")
    g.add_edge("comprendre", "identifier")
    g.add_edge("identifier", "diagnostiquer")
    g.add_conditional_edges("diagnostiquer", _after_diagnosis, ["phytosanitaire", "agronome", "rediger"])
    g.add_edge("phytosanitaire", "rediger")
    g.add_edge("agronome", "rediger")
    g.add_edge("rediger", "traduire")
    g.add_edge("crda", "traduire")
    g.add_edge("traduire", "verifier")
    g.add_conditional_edges("verifier", _after_check, ["finaliser", "rediger", "crda", "secours"])
    g.add_edge("secours", "finaliser")
    g.add_edge("finaliser", END)
    return g.compile()


def diagnose(photo=None, message="", gouvernorat=None, culture=None, langue=None, mois=None, contexte=None):
    """contexte: optional fields of the plot (days_to_harvest, market, organic, greenhouse, stage,
    last_treatment_group, area), as the form sends them."""
    t0 = time.time()
    fields = {k: v for k, v in (contexte or {}).items() if k in CONTEXT_FIELDS and v not in (None, "")}
    state = build().invoke({"photo": photo, "message": message, "gouvernorat": gouvernorat, "culture": culture,
                            "langue": langue, "mois": mois, "trace": [], **fields})
    return dict(state["reponse"], trace=state["trace"], duree_s=round(time.time() - t0, 2))


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo")
    ap.add_argument("--message", default="")
    ap.add_argument("--gouvernorat")
    ap.add_argument("--culture")
    ap.add_argument("--langue")
    ap.add_argument("--mermaid", action="store_true", help="print the graph as a Mermaid diagram")
    a = ap.parse_args()
    if a.mermaid:
        print(build().get_graph().draw_mermaid())
    else:
        r = diagnose(a.photo, a.message, a.gouvernorat, a.culture, a.langue)
        print(r["texte"], "\n")
        print(json.dumps({k: v for k, v in r.items() if k != "texte"}, ensure_ascii=False, indent=1))
