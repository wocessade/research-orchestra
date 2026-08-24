from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from bogda_console.contracts.models import PowerSnapshot


class MockPowerAdapter:
    source_mode = "mock"

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._power = copy.deepcopy(fixture["power"])

    @property
    def observed_at(self) -> datetime:
        return datetime.fromisoformat(self._power["observedAt"].replace("Z", "+00:00"))

    async def get_dorm_status(self) -> PowerSnapshot:
        if not self._power["available"]:
            raise ConnectionError("mock Power source unavailable")
        return PowerSnapshot(
            host=self._power["host"],
            mode=self._power["mode"],
            agentReachable=self._power["agentReachable"],
            sleepInhibited=self._power["sleepInhibited"],
            lastTransitionAt=self._power.get("lastTransitionAt"),
        )
