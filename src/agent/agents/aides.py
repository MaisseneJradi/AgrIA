"""Small helpers shared by the agents: timing for the trace, readable names of the model classes."""
import ast
import time
from functools import lru_cache

from src.agent import paths  # noqa: F401
from common import query  # src/tools/common.py

NUTRIENTS = {"B": "bore", "Ca": "calcium", "Fe": "fer", "K": "potassium", "Mg": "magnésium", "Mn": "manganèse",
             "N": "azote", "P": "phosphore", "Zn": "zinc"}
CLASS_CROP = {"orange": "citrus"}  # class prefix -> crop code when they differ


def step(agent, action, t0, **extra):
    """One line of the trace."""
    return [{"agent": agent, "action": action, "duree_ms": round((time.time() - t0) * 1000), **extra}]


def crop_of_class(cls):
    if not cls or "__" not in cls:
        return None
    prefix = cls.split("__")[0]
    return CLASS_CROP.get(prefix, prefix)


@lru_cache(maxsize=1)
def _sheet_names():
    out = {}
    for f in query("SELECT nom, classes_modele FROM fiches"):
        try:
            for c in ast.literal_eval(f["classes_modele"] or "[]"):
                out.setdefault(c, f["nom"])
        except (ValueError, SyntaxError):
            pass
    return out


@lru_cache(maxsize=1)
def _crop_names():
    return {r["lien"]: r["concept"].replace("_", " ") for r in query(
        "SELECT lien, concept FROM lexique WHERE type = 'culture' AND lien IS NOT NULL")}


CROP_NAMES = {"citrus": "agrumes", "datepalm": "palmier dattier"}  # clearer than the lexicon concept


def crop_name(code):
    """French name of a crop code: tomato -> tomate, citrus -> agrumes."""
    return CROP_NAMES.get(code) or _crop_names().get(code, code) if code else code


def class_name(cls):
    """Readable French name of a model class."""
    if cls.endswith("_deficiency"):
        n = cls.split("_")[0]
        return f"carence en {NUTRIENTS.get(n, n)} ({n})"
    if cls == "healthy" or cls.endswith("__healthy"):
        crop = crop_name(crop_of_class(cls)) if "__" in cls else ""
        return f"plante saine{f' ({crop})' if crop else ''}"
    return _sheet_names().get(cls) or cls.replace("__", " : ").replace("_", " ")
