from __future__ import annotations

from bogda.contracts import AutonomyMode as CoreAutonomyMode
from bogda.policy import PolicyRevisionConflict, PolicyStore

from bogda_console.contracts.models import AutonomyMode, AutonomyPolicySnapshot
from bogda_console.contracts.ports import AutonomyPolicyConflict


class LocalAutonomyPolicyAdapter:
    """Autonomy policy backed by the box-local core PolicyStore file."""

    def __init__(self, path: str) -> None:
        self._store = PolicyStore(path)

    def _snapshot(self) -> AutonomyPolicySnapshot:
        policy = self._store.load()
        return AutonomyPolicySnapshot(
            globalDefault=AutonomyMode(policy.global_default.value),
            projectOverrides={
                project: AutonomyMode(mode.value)
                for project, mode in policy.project_overrides.items()
            },
            revision=policy.revision,
        )

    async def get_policy(self) -> AutonomyPolicySnapshot:
        return self._snapshot()

    async def set_global_mode(
        self, mode: AutonomyMode, expected_revision: int
    ) -> AutonomyPolicySnapshot:
        try:
            self._store.set_mode(
                None,
                CoreAutonomyMode(mode.value),
                expected_revision=expected_revision,
            )
        except PolicyRevisionConflict as error:
            raise AutonomyPolicyConflict(self._snapshot()) from error
        return self._snapshot()

    async def set_project_mode(
        self, project_id: str, mode: AutonomyMode | None, expected_revision: int
    ) -> AutonomyPolicySnapshot:
        try:
            if mode is None:
                self._store.clear_project_override(
                    project_id, expected_revision=expected_revision
                )
            else:
                self._store.set_mode(
                    project_id,
                    CoreAutonomyMode(mode.value),
                    expected_revision=expected_revision,
                )
        except PolicyRevisionConflict as error:
            raise AutonomyPolicyConflict(self._snapshot()) from error
        return self._snapshot()
