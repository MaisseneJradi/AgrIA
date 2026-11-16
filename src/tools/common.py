"""Shared helpers of the agent tools: paths, text folding, SQLite access, governorate names.

The tools never read the CSV files directly: they query data/processed/agria.db, built by build_db.py from the clean
tables (it is rebuilt automatically when missing). No LLM is used anywhere in src/tools.
"""
import re
import sqlite3
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
DB_PATH = PROC / "agria.db"

ARABIC_DIACRITICS = re.compile("[ً-ْٰـ]")  # harakat, dagger alif, tatweel
ARABIC_LETTERS = re.compile("[؀-ۿ]")


def fold(text):
    """Lower case, no accents, unified Arabic letters, single spaces: the form every comparison uses."""
    if text is None:
        return ""
    t = str(text).lower().replace("’", "'").replace("‑", "-")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    t = ARABIC_DIACRITICS.sub("", t)
    t = re.sub("[أإآٱ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"\s+", " ", t).strip()


def connect():
    if not DB_PATH.exists():
        from build_db import build  # noqa: E402  (same folder)
        build()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def query(sql, params=()):
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params)]


# The 24 governorates: name used in the tables -> other spellings (French, Arabic, without article)
GOVERNORATE_ALIASES = {
    "Tunis": ["تونس"], "Ariana": ["اريانه", "أريانة"], "Ben Arous": ["بن عروس"], "Manouba": ["منوبه", "la manouba"],
    "Nabeul": ["نابل"], "Zaghouan": ["زغوان"], "Bizerte": ["بنزرت", "binzart"], "Béja": ["باجه", "beja"],
    "Jendouba": ["جندوبه"], "Le Kef": ["الكاف", "kef", "el kef"], "Siliana": ["سليانه"], "Sousse": ["سوسه"],
    "Monastir": ["المنستير"], "Mahdia": ["المهديه"], "Sfax": ["صفاقس"], "Kairouan": ["القيروان"],
    "Kasserine": ["القصرين"], "Sidi Bouzid": ["سيدي بوزيد"], "Gabès": ["قابس", "gabes"], "Médenine": ["مدنين"],
    "Tataouine": ["تطاوين"], "Gafsa": ["قفصه"], "Tozeur": ["توزر"], "Kébili": ["قبلي", "kebili"],
}
_GOV = {fold(k): k for k in GOVERNORATE_ALIASES}
_GOV.update({fold(a): k for k, aliases in GOVERNORATE_ALIASES.items() for a in aliases})


def governorate(name):
    """Official name of a governorate written in any usual way, or ValueError."""
    key = fold(name).replace("-", " ")
    if key in _GOV:
        return _GOV[key]
    for prefix in ("gouvernorat de ", "gouvernorat d'", "ولاية "):
        if key.startswith(prefix) and key[len(prefix):] in _GOV:
            return _GOV[key[len(prefix):]]
    raise ValueError(f"gouvernorat inconnu : {name!r}")
