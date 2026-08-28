from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from bogda.contracts.tasks import ModelTier


class BudgetSource(StrEnum):
    RUN = "run"
    PROJECT = "project"
    GLOBAL_DEFAULT = "global-default"


class RunBudgetEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    currency: Literal["CNY"] = "CNY"
    expected_cost: Decimal = Field(ge=0)
    authorized_ceiling: Decimal = Field(ge=0)
    minimum_remaining: Decimal = Field(ge=0)
    requested_tier: ModelTier
    fallback_tier: ModelTier | None = None
    budget_source: BudgetSource
    pricing_version: str = Field(min_length=1)

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_schema_version_type(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @field_validator(
        "expected_cost", "authorized_ceiling", "minimum_remaining", mode="before"
    )
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

    @field_serializer("expected_cost", "authorized_ceiling", "minimum_remaining")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        if self.expected_cost > self.authorized_ceiling:
            raise ValueError("expected_cost cannot exceed authorized_ceiling")
        if self.fallback_tier not in (None, ModelTier.FLASH):
            raise ValueError("fallback_tier must be flash or null")
        return self
