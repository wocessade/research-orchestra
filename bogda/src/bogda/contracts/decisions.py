from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class CheckpointKind(StrEnum):
    PLAN_APPROVAL = "plan_approval"
    EXPERIMENT_APPROVAL = "experiment_approval"
    SCIENTIFIC_REVIEW = "scientific_review"


class DecisionVerdict(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class StageStatus(StrEnum):
    DONE = "done"
    ACCEPTED = "accepted"


class ResearchDecision(BaseModel):
    run_id: str
    kind: CheckpointKind
    stage: StageStatus = StageStatus.DONE
    verdict: DecisionVerdict | None = None
    rationale: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    command_version: str
