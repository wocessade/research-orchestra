from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bogda_console.app import create_app
from bogda_console.config import Settings


def export(path: Path) -> None:
    schema = create_app(Settings.from_env({})).openapi()
    path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    export(ROOT / "openapi.json")
