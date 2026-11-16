"""The shared case file (« dossier ») that the six agents read and complete, in the LangGraph state.

Each agent writes only its own keys. The trace keeps one line per agent step (who, what, time) so that every answer
can be explained to the farmer, the supervisor or the jury.
"""
import operator
from typing import Annotated, List, Optional, TypedDict


class Dossier(TypedDict, total=False):
    # request (API)
    photo: Optional[str]          # path of the photo
    message: str                  # what the farmer wrote, any language
    gouvernorat: Optional[str]
    culture: Optional[str]        # crop given by the farmer, optional
    langue: Optional[str]         # language wanted for the answer: fr, ar, darija; else the one of the message
    mois: Optional[int]           # month for the irrigation advice (default: current month)

    # Agent Linguistique, input side
    termes: dict                  # normalize_terms(message)
    langue_reponse: str
    culture_code: Optional[str]   # crop code (tomato, olive...) from the request, the message or the diagnosis
    gouvernorat_officiel: Optional[str]

    # Agent Diagnostic
    diagnostic: dict              # routing, task, classe, confiance, top3, fiable, raisons_doute
    issue: str                    # conseil | question | autre_photo | crda
    questions: List[str]

    # specialist agents
    traitements: dict             # Agent Phytosanitaire
    agronomie: dict               # Agent Agronome: engrais, eau
    sources: Annotated[list, operator.add]

    # Agent Coordinateur
    brouillon: dict               # texte, produits, engrais, hypothese (format of check_answer)

    # Agent Vérificateur
    verification: dict
    essais: int

    reponse: dict                 # final answer returned by the API
    trace: Annotated[list, operator.add]
