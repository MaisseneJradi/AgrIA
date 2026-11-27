"""Write the OpenAPI schema of the API to frontend/src/api/openapi.json (no server needed); `npm run api:types` then
generates frontend/src/api/schema.d.ts from it. tests/api/test_api.py checks that the file is up to date.

    python -m src.api.export_openapi
"""
import json
from pathlib import Path

from src.api.main import app

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"


def schema_text():
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(schema_text(), encoding="utf-8")
    print(OUT)
