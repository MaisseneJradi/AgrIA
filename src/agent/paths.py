"""Import paths of the models (src/vision) and of the tools (src/tools) for the agents."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repository root
for sub in ("src/vision", "src/tools"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
