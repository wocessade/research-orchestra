from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from bogda_console.app import create_app
from bogda_console.config import Settings


@pytest.fixture
def fixture_loader():
    def load(name: str) -> dict[str, object]:
        data = json.loads((Path("fixtures") / f"{name}.json").read_text(encoding="utf-8"))
        return copy.deepcopy(data)

    return load


@pytest.fixture
async def client():
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "mock-all",
            "BOGDA_CONSOLE_FIXTURE": "normal-active",
            "BOGDA_CONSOLE_TEST_MODE": "1",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service,deployment-dorm",
            "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-service,schedule-dorm",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-service,queue-cpu,queue-gpu",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "pi-service,dorm-x86",
        }
    )
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        http.app = app  # type: ignore[attr-defined]
        yield http
