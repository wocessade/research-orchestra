from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from bogda_console.contracts.models import (
    AutonomyMode,
    AutonomyPolicySnapshot,
    DeploymentSummary,
    Page,
    PoolSnapshot,
    PowerSnapshot,
    ProjectContext,
    QueueSnapshot,
    RunDetail,
    RunFilters,
    RunResultVersionSummary,
    RunResultView,
    RunSummary,
    ScientificStatus,
    WorkerSnapshot,
    DecisionCenterSnapshot,
    DecisionItem,
    ModelBudgetSnapshot,
    ModelPolicySnapshot,
    RunPreparationPreview,
)


@runtime_checkable
class PrefectQueryPort(Protocol):
    async def health(self) -> bool: ...
    async def list_runs(self, filters: RunFilters, cursor: str | None, limit: int) -> Page[RunSummary]: ...
    async def get_run(self, run_id: str) -> RunDetail: ...
    async def list_registered_deployments(self, cursor: str | None, limit: int) -> Page[DeploymentSummary]: ...
    async def get_deployment(self, deployment_id: str) -> DeploymentSummary: ...
    async def list_work_pools(self) -> list[PoolSnapshot]: ...
    async def list_work_queues(self, work_pool_name: str) -> list[QueueSnapshot]: ...
    async def list_workers(self, work_pool_name: str) -> list[WorkerSnapshot]: ...
    async def get_work_pool_concurrency(self, work_pool_name: str) -> PoolSnapshot: ...


@runtime_checkable
class PrefectCommandPort(Protocol):
    async def submit_registered_deployment(self, deployment_id: str, parameters: dict[str, Any], idempotency_key: str) -> RunSummary: ...
    async def cancel_run(self, run_id: str) -> RunSummary: ...
    async def pause_schedule(self, deployment_id: str, schedule_id: str) -> DeploymentSummary: ...
    async def resume_schedule(self, deployment_id: str, schedule_id: str) -> DeploymentSummary: ...
    async def pause_work_queue(self, queue_id: str) -> QueueSnapshot: ...
    async def resume_work_queue(self, queue_id: str) -> QueueSnapshot: ...
    async def resume_run(self, run_id: str, run_input: dict[str, Any]) -> None: ...


@runtime_checkable
class RunResultPort(Protocol):
    async def get_latest(self, run_id: str) -> RunResultView: ...
    async def list_versions(self, run_id: str, cursor: str | None, limit: int) -> Page[RunResultVersionSummary]: ...
    async def append_review(self, run_id: str, base_artifact_id: str, scientific_status: ScientificStatus, review_summary: str | None) -> RunResultView: ...


@runtime_checkable
class PowerStatusPort(Protocol):
    async def get_dorm_status(self) -> PowerSnapshot: ...


@runtime_checkable
class ProjectContextPort(Protocol):
    async def get_run_context(self, run_id: str) -> ProjectContext | None: ...
    async def get_deployment_context(self, deployment_id: str) -> ProjectContext | None: ...


@runtime_checkable
class AutonomyPolicyPort(Protocol):
    async def get_policy(self) -> AutonomyPolicySnapshot: ...
    async def set_global_mode(self, mode: AutonomyMode, expected_revision: int) -> AutonomyPolicySnapshot: ...
    async def set_project_mode(
        self, project_id: str, mode: AutonomyMode | None, expected_revision: int
    ) -> AutonomyPolicySnapshot: ...


class AutonomyPolicyConflict(Exception):
    def __init__(self, current: AutonomyPolicySnapshot) -> None:
        super().__init__("autonomy policy revision mismatch")
        self.current = current


class ModelControlConflict(Exception):
    def __init__(self, current: Any) -> None:
        super().__init__("model-control revision or idempotency conflict")
        self.current = current


class ModelControlUnavailable(Exception):
    pass


@runtime_checkable
class ModelControlQueryPort(Protocol):
    async def decision_center(self) -> DecisionCenterSnapshot: ...
    async def run_budget(self, run_id: str) -> ModelBudgetSnapshot: ...
    async def model_policy(self, project_id: str | None = None) -> ModelPolicySnapshot: ...
    async def preview_run(
        self,
        project_id: str,
        intent: str,
        requested_model_tier: str,
        deadline: datetime | None = None,
    ) -> RunPreparationPreview: ...


@runtime_checkable
class ModelControlCommandPort(Protocol):
    async def resolve_decision(self, decision_id: str, action_id: str, expected_revision: int) -> DecisionCenterSnapshot: ...
    async def set_global_policy(self, patch: dict[str, Any], expected_revision: int) -> ModelPolicySnapshot: ...
    async def set_project_policy(self, project_id: str, patch: dict[str, Any] | None, expected_revision: int) -> ModelPolicySnapshot: ...
    async def confirm_preparation(self, preparation_id: str, idempotency_key: str) -> RunPreparationPreview: ...
