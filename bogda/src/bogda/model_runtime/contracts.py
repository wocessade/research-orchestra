from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import Protocol, Self, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from bogda.contracts import ModelTier


class PromptArtifactV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ModelCallOutcome(StrEnum):
    FINISHED = "finished"
    NOT_STARTED = "not_started"
    USAGE_UNKNOWN = "usage_unknown"


class DshTokenUsageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(ge=0, strict=True)
    cache_read_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)
    actual_cost_cny: Decimal | None = Field(default=None, ge=0)
    reference: str = Field(min_length=1)

    @field_validator("actual_cost_cny", mode="before")
    @classmethod
    def parse_decimal_cost(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, bool) or isinstance(value, (int, float)):
            raise ValueError("actual_cost_cny must be a decimal string")
        if not isinstance(value, (str, Decimal)):
            raise ValueError("actual_cost_cny must be a decimal string")
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(value)
        except (InvalidOperation, ValueError):
            raise ValueError("actual_cost_cny must be a decimal string") from None
        if not parsed.is_finite() or parsed < 0:
            raise ValueError("actual_cost_cny must be a finite non-negative amount")
        return parsed

    @field_serializer("actual_cost_cny")
    def serialize_decimal_cost(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")


class ModelCallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    effective_tier: ModelTier
    attempt_dir: Path
    timeout_seconds: float = Field(gt=0)
    prompt: str = Field(min_length=1, repr=False)

    @field_validator("effective_tier")
    @classmethod
    def require_concrete_tier(cls, value: ModelTier) -> ModelTier:
        if value is ModelTier.AUTO:
            raise ValueError("effective_tier must be concrete")
        return value

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def require_finite_positive_timeout(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("timeout_seconds must be a finite positive number")
        if not isfinite(float(value)) or value <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        return value


class ModelCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ModelCallOutcome
    output: str | None = Field(default=None, repr=False)
    usage: DshTokenUsageV1 | None = None

    @model_validator(mode="after")
    def validate_outcome_state(self) -> Self:
        if self.outcome is ModelCallOutcome.FINISHED:
            if self.output is None or self.usage is None:
                raise ValueError("finished results require output and usage")
        elif self.outcome is ModelCallOutcome.NOT_STARTED:
            if self.output is not None or self.usage is not None:
                raise ValueError("not_started results cannot contain output or usage")
        elif self.usage is not None:
            raise ValueError("usage_unknown results cannot contain usage")
        return self


@runtime_checkable
class ModelExecutionPort(Protocol):
    def invoke(self, request: ModelCallRequest) -> ModelCallResult:
        ...


@runtime_checkable
class UsageReceiptPort(Protocol):
    def read(self, attempt_dir: Path) -> DshTokenUsageV1 | None:
        ...


@runtime_checkable
class PromptArchivePort(Protocol):
    def archive(self, run_id: str, call_id: str, prompt: str) -> PromptArtifactV1:
        ...


__all__ = [
    "DshTokenUsageV1",
    "ModelCallOutcome",
    "ModelCallRequest",
    "ModelCallResult",
    "ModelExecutionPort",
    "PromptArchivePort",
    "PromptArtifactV1",
    "UsageReceiptPort",
]
