from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, field_validator

from bogda.contracts import ScientificStatus
from bogda.contracts.decisions import CheckpointKind


class AgentBudget(BaseModel):
    max_steps: int
    max_model_calls: int
    max_cost_cny: Decimal
    allowed_experiment_types: tuple[str, ...] = ("shell",)

    @field_validator("max_cost_cny", mode="before")
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value


class ResearchPlan(BaseModel):
    goal: str
    steps: tuple[str, ...]
    rationale: str
    sufficient: bool = False


class ExperimentProposal(BaseModel):
    experiment_type: str
    description: str
    expected_artifacts: tuple[str, ...] = ()
    supports_conclusion: bool = False


class CoordinatorResult(BaseModel):
    status: str
    checkpoint: CheckpointKind | None = None
    scientific_status: ScientificStatus = ScientificStatus.UNREVIEWED
    plan: ResearchPlan | None = None
    proposal: ExperimentProposal | None = None
    steps_used: int = 0
    model_calls_used: int = 0
    cost_cny_used: Decimal = Decimal("0")

    @field_validator("cost_cny_used", mode="before")
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value
