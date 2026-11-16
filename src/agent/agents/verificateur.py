"""Agent Vérificateur: checks the final text, in the farmer's language, with the rules of src/tools/safety.py.
Code only, no LLM: a language model cannot talk it out of a rule. A blocked answer goes back to the Coordinateur.
"""
import time

from src.agent import paths  # noqa: F401
from safety import check_answer  # src/tools
from src.agent.agents.aides import step


def verifier(d):
    t0 = time.time()
    v = check_answer(d["brouillon"])
    n = d.get("essais", 0) + 1
    action = "réponse validée" if v["valide"] else "réponse bloquée : " + " | ".join(v["raisons"])
    return {"verification": v, "essais": n, "trace": step("Vérificateur", action, t0)}
