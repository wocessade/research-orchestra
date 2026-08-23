from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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
    job_id: str
    project_id: str
    task_type: str
    resource_class: ResourceClass
    autonomy_mode: AutonomyMode
    parameters: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    expected_artifacts: tuple[ArtifactSpec, ...] = ()


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
