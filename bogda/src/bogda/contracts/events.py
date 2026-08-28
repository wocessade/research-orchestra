from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from bogda.contracts.tasks import ModelTier, TaskIntent


class RunEventType(StrEnum):
    BUDGET_SNAPSHOT = "budget_snapshot"
    BUDGET_RESERVED = "budget_reserved"
    BUDGET_RELEASED = "budget_released"
    ROUTE_SELECTED = "route_selected"
    TIER_UPGRADE_REQUESTED = "tier_upgrade_requested"
    TIER_DOWNGRADED = "tier_downgraded"
    MODEL_CALL_STARTED = "model_call_started"
    MODEL_CALL_FINISHED = "model_call_finished"
    BUDGET_PAUSED = "budget_paused"
    BUDGET_RESUMED = "budget_resumed"
    BUDGET_OVERRIDE_APPROVED = "budget_override_approved"


class RunEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    event: RunEventType
    run_id: str = Field(min_length=1)
    call_id: str | None = None
    occurred_at: datetime
    intent: TaskIntent | None = None
    requested_tier: ModelTier | None = None
    effective_tier: ModelTier | None = None
    reason: str | None = None
    balance_cny: Decimal | None = Field(default=None, ge=0)
    reserved_cny: Decimal | None = Field(default=None, ge=0)
    minimum_remaining_cny: Decimal | None = Field(default=None, ge=0)
    snapshot_age_seconds: int | None = Field(default=None, ge=0)
    prompt_hash: str | None = None
    prompt_artifact: str | None = None
    usage_reference: str | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def reject_non_strict_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be integer 1")
        return value

    @field_validator(
        "balance_cny", "reserved_cny", "minimum_remaining_cny", mode="before"
    )
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

    @field_serializer("balance_cny", "reserved_cny", "minimum_remaining_cny")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.event in {
            RunEventType.MODEL_CALL_STARTED,
            RunEventType.MODEL_CALL_FINISHED,
        } and (not self.call_id or not self.call_id.strip()):
            raise ValueError("call_id is required for model call events")
        if self.event in {
            RunEventType.TIER_UPGRADE_REQUESTED,
            RunEventType.TIER_DOWNGRADED,
            RunEventType.ROUTE_SELECTED,
        } and (self.requested_tier is None or self.effective_tier is None):
            raise ValueError("tier events require requested_tier and effective_tier")
        return self
