"""Agent tools (step 3): rules and tables only, no LLM. See docs/results_tools.md.

  from src.tools import get_treatments, get_fertilizers, get_water_need, search_knowledge, normalize_terms, check_answer
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the tools import each other by module name

from fertilizers import get_fertilizers  # noqa: E402
from lexicon import crop_code, normalize_terms  # noqa: E402
from rag import search_knowledge  # noqa: E402
from safety import check_answer  # noqa: E402
from treatments import get_treatments  # noqa: E402
from water import get_water_need  # noqa: E402

__all__ = ["get_treatments", "get_fertilizers", "get_water_need", "search_knowledge", "normalize_terms",
           "check_answer", "crop_code"]
