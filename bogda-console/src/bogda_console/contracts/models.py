from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
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
    MODEL_CONTROL_UNAVAILABLE = "MODEL_CONTROL_UNAVAILABLE"
    USAGE_BALANCE_UNAVAILABLE = "USAGE_BALANCE_UNAVAILABLE"
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


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
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


class RunLogSlice(WireModel):
    run_id: str
    source: str
    exists: bool
    content: str
    truncated: bool
    size_bytes: int | None = Field(default=None, ge=0)


class CapabilitySnapshot(WireModel):
    profile: str
    project_id: str
    actor_id: str
    role: str
    effective_autonomy_mode: AutonomyMode | None = None
    can_submit_registered_deployment: bool
    can_cancel_run: bool
    can_pause_schedule: bool
    can_pause_work_queue: bool
    can_decide_checkpoint: bool
    can_review_scientific_result: bool
    can_set_autonomy_mode: bool
    can_resolve_model_decision: bool
    can_set_model_policy: bool
    can_prepare_paid_run: bool
    allowed_deployment_ids: list[str] = Field(default_factory=list)
    allowed_schedule_ids: list[str] = Field(default_factory=list)
    allowed_queue_ids: list[str] = Field(default_factory=list)
    allowed_work_pool_names: list[str] = Field(default_factory=list)


class RunFilters(WireModel):
    execution_type: str | None = None
    scientific_status: ScientificStatus | None = None
    deployment_id: str | None = None
    project_id: str | None = None


class SubmitRequest(WireModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)
    run_preparation_id: str | None = None


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


class ImmutableWireModel(WireModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
        use_enum_values=True,
        frozen=True,
    )


class BudgetState(StrEnum):
    READY = "ready"
    STALE = "stale"
    INSUFFICIENT = "insufficient"
    SCHEDULED_OFF_PEAK = "scheduled-off-peak"
    AWAITING_APPROVAL = "awaiting-approval"
    USAGE_UNKNOWN = "usage-unknown"
    TERMINATED = "terminated"


class DecisionKind(StrEnum):
    PLAN_APPROVAL = "plan-approval"
    SCIENTIFIC_RESULT = "scientific-result"
    BUDGET_INCREASE = "budget-increase"
    PRO_UNAVAILABLE = "pro-unavailable"
    PEAK_OVERRIDE = "peak-override"
    USAGE_UNKNOWN = "usage-unknown"
    EXTERNAL_ACTION = "external-action"


class UrgencyGroup(StrEnum):
    NEEDS_OWNER_NOW = "needs-owner-now"
    HAS_DEADLINE = "has-deadline"
    FOR_INFORMATION = "for-information"


class DecisionAction(ImmutableWireModel):
    action_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    cost_impact: str = Field(min_length=1)
    quality_impact: str | None = None
    irreversible_consequence: str | None = None
    requires_rationale: bool = False
    requires_confirmation: bool = True
    actual_cost_required: bool = False
    new_call_id_required: bool = False


class EvidenceReference(ImmutableWireModel):
    kind: str = Field(min_length=1)
    ref_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    uri: str | None = None


class DecisionItem(ImmutableWireModel):
    decision_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    title: str = Field(min_length=1)
    urgency_group: UrgencyGroup
    project_id: str = Field(min_length=1)
    run_id: str | None = None
    reason: str = Field(min_length=1)
    risk: str = Field(min_length=1)
    estimated_cost: Decimal = Field(ge=0)
    deadline: datetime | None = None
    evidence: tuple[EvidenceReference, ...] = ()
    actions: tuple[DecisionAction, ...] = Field(min_length=1)
    revision: int = Field(ge=0)
    log_summary: str = Field(min_length=1)

    _deadline_aware = field_validator("deadline")(_utc_datetime)


class DecisionCenterSnapshot(ImmutableWireModel):
    items: tuple[DecisionItem, ...] = ()
    revision: int = Field(ge=0)


class ModelEventRow(ImmutableWireModel):
    event_id: str = Field(min_length=1)
    event_type: Literal[
        "budget_snapshot", "budget_reserved", "budget_released", "route_selected",
        "tier_upgrade_requested", "tier_downgraded", "model_call_started",
        "model_call_finished", "model_call_usage_unknown", "budget_paused", "budget_resumed", "budget_override_approved",
    ]
    occurred_at: datetime
    summary: str | None = None

    _event_utc = field_validator("occurred_at")(_utc_datetime)


class ModelArtifactReference(ImmutableWireModel):
    artifact_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    uri: str = Field(min_length=1)


class ModelBudgetSnapshot(ImmutableWireModel):
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    state: BudgetState
    currency: str = Field(min_length=1)
    expected_cost: Decimal = Field(ge=0)
    authorized_ceiling: Decimal = Field(ge=0)
    used_cost: Decimal = Field(ge=0)
    reserved_cost: Decimal = Field(ge=0)
    remaining_cost: Decimal = Field(ge=0)
    decision_id: str | None = None
    revision: int = Field(ge=0)
    intent: Literal["execute", "brief", "explore", "decide", "audit"] = "execute"
    requested_model_tier: Literal["auto", "flash", "pro"] = "auto"
    effective_model_tier: Literal["flash", "pro"] | None = None
    effective_autonomy_mode: AutonomyMode = AutonomyMode.SUPERVISED
    price_period: Literal["peak", "off-peak"] = "off-peak"
    scheduled_start: datetime | None = None
    pause_reason: str | None = None
    recovery_conditions: tuple[str, ...] = ()
    events: tuple[ModelEventRow, ...] = ()
    artifacts: tuple[ModelArtifactReference, ...] = ()

    _scheduled_utc = field_validator("scheduled_start")(_utc_datetime)


class HardSafetyBaselines(ImmutableWireModel):
    usage_snapshot_fail_closed: bool = True
    minimum_remaining_enforced: bool = True
    decide_audit_no_silent_downgrade: bool = True
    human_scientific_judgment: bool = True
    human_external_actions: bool = True
    unknown_usage_recovery_gate: bool = True
    structured_event_log: bool = True
    prompt_archiving_required: bool = True
    budget_increase_approval_required: bool = True


class PriceCatalog(ImmutableWireModel):
    status: Literal["ready", "stale", "missing", "invalid"]
    version: str | None = None
    source: str | None = None
    effective_at: datetime | None = None
    review_by: datetime | None = None

    _catalog_dates_utc = field_validator("effective_at", "review_by")(_utc_datetime)


class ModelPolicyPatch(ImmutableWireModel):
    default_model_tier: Literal["auto", "flash", "pro"] | None = None
    allow_auto_upgrade: bool | None = None
    allow_flash_downgrade: bool | None = None
    prefer_off_peak: bool | None = None
    auto_resume: bool | None = None
    minimum_remaining: Decimal | None = Field(default=None, ge=0)
    critical_notifications: bool | None = None
    workload_safety_margin: Decimal | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_actual_change(self) -> "ModelPolicyPatch":
        if not self.model_fields_set or any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("policy patch must contain at least one non-null field")
        return self


class WorkloadEstimate(ImmutableWireModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    expected_calls: int = Field(ge=1)
    runtime_minutes: int = Field(ge=0)


class AllowedRunPreferences(ImmutableWireModel):
    prefer_off_peak: bool
    allow_auto_upgrade: bool
    allow_flash_downgrade: bool
    auto_resume: bool


class ModelPolicySnapshot(ImmutableWireModel):
    project_id: str | None = None
    source: Literal["global", "project"]
    inherits_global: bool
    default_model_tier: Literal["auto", "flash", "pro"]
    allow_auto_upgrade: bool
    allow_flash_downgrade: bool
    prefer_off_peak: bool
    auto_resume: bool
    minimum_remaining: Decimal = Field(ge=0)
    usage_snapshot_stale_after_seconds: int = Field(default=120, ge=1)
    critical_notifications: bool
    workload_safety_margin: Decimal = Field(default=Decimal("1"), ge=1)
    price_catalog: PriceCatalog
    hard_safety_baselines: HardSafetyBaselines = HardSafetyBaselines()
    revision: int = Field(ge=0)


class UsageBalanceSnapshot(ImmutableWireModel):
    provider: Literal["deepseek"]
    available: Literal[True]
    total_balance: Decimal = Field(ge=0)
    currency: Literal["CNY"]
    observed_at: datetime
    source_status: Literal["up"]

    _balance_observed_utc = field_validator("observed_at")(_utc_datetime)


class RunPreparationPreview(ImmutableWireModel):
    preparation_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    intent: Literal["execute", "brief", "explore", "decide", "audit"]
    requested_model_tier: Literal["auto", "flash", "pro"]
    effective_model_tier: Literal["flash", "pro"] | None
    effective_autonomy_mode: AutonomyMode
    fallback_model_tier: Literal["flash"] | None
    price_period: Literal["peak", "off-peak"]
    scheduled_start: datetime | None = None
    workload: WorkloadEstimate
    allowed_preferences: AllowedRunPreferences
    deadline: datetime | None = None
    budget: ModelBudgetSnapshot
    policy_revision: int = Field(ge=0)
    confirmed: bool = False
    confirmed_at: datetime | None = None

    _preview_deadline_aware = field_validator("deadline", "confirmed_at")(_utc_datetime)
    _preview_start_aware = field_validator("scheduled_start")(_utc_datetime)


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
