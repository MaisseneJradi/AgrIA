"""Puts src/tools on the import path of the tests (the tools import each other by module name)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "tools"))
