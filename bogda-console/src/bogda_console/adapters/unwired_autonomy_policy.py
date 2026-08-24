from __future__ import annotations

from bogda_console.contracts.models import (
    ApiErrorCode,
    AutonomyMode,
    AutonomyPolicySnapshot,
)
from bogda_console.services.errors import ServiceError


class UnwiredAutonomyPolicyAdapter:
    async def get_policy(self) -> AutonomyPolicySnapshot:
        raise ServiceError(
            ApiErrorCode.AUTONOMY_POLICY_UNAVAILABLE,
            "real Bogda Policy backend is not wired",
            source="autonomyPolicy",
            retryable=False,
            status_code=503,
        )

    async def set_global_mode(
        self, mode: AutonomyMode, expected_revision: int
    ) -> AutonomyPolicySnapshot:
        raise ServiceError(
            ApiErrorCode.AUTONOMY_POLICY_UNAVAILABLE,
            "real Bogda Policy backend is not wired",
            source="autonomyPolicy",
            retryable=False,
            status_code=503,
        )

    async def set_project_mode(
        self, project_id: str, mode: AutonomyMode | None, expected_revision: int
    ) -> AutonomyPolicySnapshot:
        raise ServiceError(
            ApiErrorCode.AUTONOMY_POLICY_UNAVAILABLE,
            "real Bogda Policy backend is not wired",
            source="autonomyPolicy",
            retryable=False,
            status_code=503,
        )
