from __future__ import annotations

from bogda_console.contracts.models import AutonomyMode, AutonomyPolicySnapshot
from bogda_console.contracts.ports import AutonomyPolicyConflict


class MockAutonomyPolicyAdapter:
    def __init__(self) -> None:
        self._global_default = AutonomyMode.SUPERVISED
        self._project_overrides: dict[str, AutonomyMode] = {}
        self._revision = 0

    def snapshot(self) -> AutonomyPolicySnapshot:
        return AutonomyPolicySnapshot(
            globalDefault=self._global_default,
            projectOverrides=dict(self._project_overrides),
            revision=self._revision,
        )

    async def get_policy(self) -> AutonomyPolicySnapshot:
        return self.snapshot()

    async def set_global_mode(
        self, mode: AutonomyMode, expected_revision: int
    ) -> AutonomyPolicySnapshot:
        current = self.snapshot()
        if expected_revision != self._revision:
            raise AutonomyPolicyConflict(current)
        self._global_default = AutonomyMode(mode)
        self._revision += 1
        return self.snapshot()

    async def set_project_mode(
        self, project_id: str, mode: AutonomyMode | None, expected_revision: int
    ) -> AutonomyPolicySnapshot:
        current = self.snapshot()
        if expected_revision != self._revision:
            raise AutonomyPolicyConflict(current)
        if mode is None:
            self._project_overrides.pop(project_id, None)
        else:
            self._project_overrides[project_id] = AutonomyMode(mode)
        self._revision += 1
        return self.snapshot()
