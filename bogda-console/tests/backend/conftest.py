from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def fixture_loader():
    def load(name: str) -> dict[str, object]:
        data = json.loads((Path("fixtures") / f"{name}.json").read_text(encoding="utf-8"))
        return copy.deepcopy(data)

    return load
