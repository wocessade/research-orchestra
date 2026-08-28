from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

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
    model_tier: ModelTier
    prompt: str = Field(min_length=1, repr=False)


class ModelCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ModelCallOutcome
    output: str | None = None
    usage: DshTokenUsageV1 | None = None


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
