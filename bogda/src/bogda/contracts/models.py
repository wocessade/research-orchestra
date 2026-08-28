from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bogda.contracts.budgets import RunBudgetEnvelope
from bogda.contracts.tasks import ExecutorKind, ModelTier, SchedulePolicy, TaskIntent


class AutonomyMode(StrEnum):
    MANUAL = "manual"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class ResourceClass(StrEnum):
    PI = "pi"
    CPU = "cpu"
    GPU = "gpu"


class ExecutionStatus(StrEnum):
    SCHEDULED = "Scheduled"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CRASHED = "Crashed"
    CANCELLED = "Cancelled"


class ScientificStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ArtifactSpec(BaseModel):
    path: str
    kind: str = "file"
    required: bool = True


class ArtifactRecord(BaseModel):
    uri: str
    kind: str
    exists: bool
    size_bytes: int | None = None


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    job_id: str
    project_id: str
    task_type: str
    resource_class: ResourceClass
    autonomy_mode: AutonomyMode
    policy_revision: int = Field(default=0, ge=0)
    intent: TaskIntent = TaskIntent.EXECUTE
    model_tier: ModelTier = ModelTier.AUTO
    executor: ExecutorKind = ExecutorKind.SHELL
    budget: RunBudgetEnvelope | None = None
    schedule_policy: SchedulePolicy = Field(default_factory=SchedulePolicy)
    parameters: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    expected_artifacts: tuple[ArtifactSpec, ...] = ()

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_schema_version_type(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def validate_tier_budget_consistency(self) -> Self:
        if self.executor is ExecutorKind.DSH and self.budget is None:
            raise ValueError("dsh requests require a budget envelope")
        if self.model_tier is not ModelTier.AUTO and self.budget is None:
            raise ValueError("explicit model_tier requires a budget envelope")
        if (
            self.budget is not None
            and self.model_tier is not ModelTier.AUTO
            and self.budget.requested_tier is not self.model_tier
        ):
            raise ValueError("model_tier must match budget.requested_tier")
        return self


class RunResult(BaseModel):
    run_id: str
    job_id: str
    execution_status: ExecutionStatus
    scientific_status: ScientificStatus = ScientificStatus.UNREVIEWED
    started_at: datetime
    finished_at: datetime
    executor: str
    attempt: int
    declared_artifacts: tuple[ArtifactRecord, ...]
    summary: str
    review_summary: str | None = None
