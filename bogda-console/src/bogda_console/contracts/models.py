from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class WireModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
        use_enum_values=True,
    )


class SourceMode(StrEnum):
    REAL = "real"
    MOCK = "mock"


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class ScientificStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ExecutionStatus(StrEnum):
    SCHEDULED = "Scheduled"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CRASHED = "Crashed"
    CANCELLED = "Cancelled"


class AutonomyMode(StrEnum):
    MANUAL = "manual"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class PowerMode(StrEnum):
    SLEEP = "sleep"
    COMPUTE = "compute"
    GAMING = "gaming"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class Availability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"


class ApiErrorCode(StrEnum):
    PREFECT_UNAVAILABLE = "PREFECT_UNAVAILABLE"
    RUN_RESULT_UNAVAILABLE = "RUN_RESULT_UNAVAILABLE"
    POWER_UNAVAILABLE = "POWER_UNAVAILABLE"
    AUTONOMY_POLICY_UNAVAILABLE = "AUTONOMY_POLICY_UNAVAILABLE"
    PROJECT_CONTEXT_UNAVAILABLE = "PROJECT_CONTEXT_UNAVAILABLE"
    RESULT_MISSING = "RESULT_MISSING"
    RESULT_INVALID = "RESULT_INVALID"
    REVIEW_CONFLICT = "REVIEW_CONFLICT"
    RESOURCE_CHANGED = "RESOURCE_CHANGED"
    RESOURCE_NOT_ALLOWLISTED = "RESOURCE_NOT_ALLOWLISTED"
    COMMAND_NOT_APPLICABLE = "COMMAND_NOT_APPLICABLE"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    COMMAND_OUTCOME_MISMATCH = "COMMAND_OUTCOME_MISMATCH"
    COMMAND_OUTCOME_UNKNOWN = "COMMAND_OUTCOME_UNKNOWN"
    INFRASTRUCTURE_MISCONFIGURED = "INFRASTRUCTURE_MISCONFIGURED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class SourceMeta(WireModel):
    source: str
    source_mode: SourceMode
    observed_at: datetime | None
    received_at: datetime
    last_successful_at: datetime | None
    stale_after_seconds: int = Field(ge=1)
    freshness: Freshness


class ApiErrorDetails(WireModel):
    current_resource: dict[str, Any] | None = None
    fields: list[dict[str, str]] = Field(default_factory=list)
    expected: Any | None = None
    observed: Any | None = None


class ApiError(WireModel):
    code: ApiErrorCode
    message: str
    source: str
    retryable: bool
    details: ApiErrorDetails | None = None


T = TypeVar("T")


class ApiEnvelope(WireModel, Generic[T]):
    data: T | None
    sources: dict[str, SourceMeta] = Field(default_factory=dict)
    errors: list[ApiError] = Field(default_factory=list)


class Page(WireModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = None


class PrefectStateSnapshot(WireModel):
    type: str
    name: str
    timestamp: datetime
    terminal: bool
    message: str | None = None


class ScientificSummary(WireModel):
    availability: Availability
    artifact_id: str | None = None
    artifact_created_at: datetime | None = None
    scientific_status: ScientificStatus | None = None
    review_summary: str | None = None
    validation_issues: list[str] = Field(default_factory=list)


class ProjectContext(WireModel):
    project_id: str
    effective_autonomy_mode: AutonomyMode | None
    mode_source: Literal["frozen-run-request", "deployment-default", "unavailable"]
    writable: Literal[False] = False

    @model_validator(mode="after")
    def validate_mode_shape(self) -> "ProjectContext":
        unavailable = self.mode_source == "unavailable"
        if unavailable != (self.effective_autonomy_mode is None):
            raise ValueError("modeSource unavailable requires a null effectiveAutonomyMode")
        return self


class ArtifactRecord(WireModel):
    uri: str
    kind: str
    exists: bool
    size_bytes: int | None = Field(default=None, ge=0)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


class ValidRunResult(BaseModel):
    model_config = ConfigDict(extra="allow", use_enum_values=True)

    run_id: str
    job_id: str
    execution_status: ExecutionStatus
    scientific_status: ScientificStatus = ScientificStatus.UNREVIEWED
    started_at: datetime
    finished_at: datetime
    executor: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    declared_artifacts: list[ArtifactRecord]
    summary: str
    review_summary: str | None = None

    _started_utc = field_validator("started_at")(_utc_datetime)
    _finished_utc = field_validator("finished_at")(_utc_datetime)


class RunResultView(WireModel):
    availability: Availability
    artifact_id: str | None = None
    artifact_created_at: datetime | None = None
    result: ValidRunResult | None = None
    validation_issues: list[str] = Field(default_factory=list)


class RunResultVersionSummary(WireModel):
    artifact_id: str
    created_at: datetime
    availability: Literal["available", "invalid"]
    scientific_status: ScientificStatus | None = None
    review_summary: str | None = None


class RunSummary(WireModel):
    run_id: str
    name: str
    deployment_id: str | None = None
    deployment_name: str | None = None
    project_id: str | None = None
    work_pool_name: str | None = None
    work_queue_name: str | None = None
    state: PrefectStateSnapshot
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    scientific: ScientificSummary | None = None
    command_version: str


class ResearchCheckpointView(WireModel):
    kind: str
    stage: str
    verdict: str | None = None
    rationale: str | None = None
    decided_by: str | None = None
    command_version: str
    impact: str | None = None


def checkpoint_impact(kind: str) -> str:
    return {
        "plan_approval": "批准后进入实验；拒绝将以 Cancelled 结束，不会记成系统失败。",
        "experiment_approval": "批准后继续执行实验；拒绝将以 Cancelled 结束，不会记成系统失败。",
        "scientific_review": "批准后结束本检查点，不把科研状态标为 accepted；拒绝将以 Cancelled 结束，不会记成系统失败。",
    }.get(kind, "批准后继续；拒绝将以 Cancelled 结束，不会记成系统失败。")


class RunDetail(WireModel):
    run: RunSummary
    parameters: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    project_context: ProjectContext | None = None
    checkpoint: ResearchCheckpointView | None = None


class ScheduleSummary(WireModel):
    schedule_id: str
    label: str
    active: bool
    updated_at: datetime | None = None
    command_version: str


class DeploymentSummary(WireModel):
    deployment_id: str
    name: str
    flow_name: str
    project_context: ProjectContext | None = None
    work_pool_name: str | None = None
    work_queue_name: str | None = None
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    allowlisted: bool
    schedules: list[ScheduleSummary] = Field(default_factory=list)


class QueueSnapshot(WireModel):
    queue_id: str
    name: str
    status: str
    is_paused: bool
    concurrency_limit: int | None = None
    command_version: str


class WorkerSnapshot(WireModel):
    worker_id: str
    name: str
    status: str
    last_heartbeat_time: datetime | None = None


class PoolSnapshot(WireModel):
    name: str
    status: str
    is_paused: bool
    concurrency_limit: int | None = None
    active_slots: int = 0
    queues: list[QueueSnapshot] = Field(default_factory=list)
    workers: list[WorkerSnapshot] = Field(default_factory=list)


class PowerSnapshot(WireModel):
    host: str
    mode: PowerMode
    agent_reachable: bool | Literal["unknown"]
    sleep_inhibited: bool | Literal["unknown"]
    last_transition_at: datetime | None = None


class OverviewSnapshot(WireModel):
    execution: dict[str, Any] | None = None
    science: dict[str, Any] | None = None
    infrastructure: dict[str, PoolSnapshot | None] | None = None
    power: PowerSnapshot | None = None


class InfrastructureView(WireModel):
    pools: list[PoolSnapshot] | None = None
    dorm_power: PowerSnapshot | None = None


class CapabilitySnapshot(WireModel):
    profile: str
    project_id: str
    effective_autonomy_mode: AutonomyMode | None = None
    can_submit_registered_deployment: bool
    can_cancel_run: bool
    can_pause_schedule: bool
    can_pause_work_queue: bool
    can_review_scientific_result: bool
    can_set_autonomy_mode: bool


class RunFilters(WireModel):
    execution_type: str | None = None
    scientific_status: ScientificStatus | None = None
    deployment_id: str | None = None
    project_id: str | None = None


class SubmitRequest(WireModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)


class ExpectedVersionRequest(WireModel):
    expected_command_version: str = Field(min_length=1)


class ReviewRequest(WireModel):
    base_artifact_id: str = Field(min_length=1)
    scientific_status: ScientificStatus
    review_summary: str | None = None


class CheckpointDecisionRequest(WireModel):
    expected_command_version: str = Field(min_length=1)
    verdict: Literal["approved", "rejected"]
    rationale: str | None = None


class AutonomyPolicySnapshot(WireModel):
    global_default: AutonomyMode
    project_overrides: dict[str, AutonomyMode] = Field(default_factory=dict)
    revision: int = Field(ge=0)


class SetGlobalAutonomyRequest(WireModel):
    mode: AutonomyMode
    expected_revision: int = Field(ge=0)


class SetProjectAutonomyRequest(WireModel):
    mode: AutonomyMode | None = None
    expected_revision: int = Field(ge=0)


class CommandReceipt(WireModel, Generic[T]):
    command: str
    resource_id: str
    accepted_at: datetime
    snapshot: T


def command_version(authoritative_fields: dict[str, Any]) -> str:
    payload = json.dumps(
        authoritative_fields,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
