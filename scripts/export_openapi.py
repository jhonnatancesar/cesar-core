"""Exporta o schema OpenAPI atual da aplicação para contracts/openapi.json."""

import json
from pathlib import Path

from cesar_core.api.app import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "contracts" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
