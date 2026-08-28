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
    active_reservations_cny: Decimal | None = Field(default=None, ge=0)
    requested_reservation_cny: Decimal | None = Field(default=None, ge=0)
    minimum_remaining_cny: Decimal | None = Field(default=None, ge=0)
    snapshot_age_seconds: int | None = Field(default=None, ge=0)
    reservation_id: str | None = None
    actual_cost_cny: Decimal | None = Field(default=None, ge=0)
    released_cny: Decimal | None = Field(default=None, ge=0)
    overspend_cny: Decimal | None = Field(default=None, ge=0)
    pricing_version: str | None = None
    budget_decision: str | None = None
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
        "balance_cny",
        "reserved_cny",
        "active_reservations_cny",
        "requested_reservation_cny",
        "minimum_remaining_cny",
        "actual_cost_cny",
        "released_cny",
        "overspend_cny",
        mode="before",
    )
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

    @field_serializer(
        "balance_cny",
        "reserved_cny",
        "active_reservations_cny",
        "requested_reservation_cny",
        "minimum_remaining_cny",
    )
    def serialize_money(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")

    @field_serializer("actual_cost_cny", "released_cny", "overspend_cny")
    def serialize_accounting_money(self, value: Decimal | None) -> str | None:
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
        if self.reservation_id is not None and not self.reservation_id.strip():
            raise ValueError("reservation_id must be non-empty")
        if self.pricing_version is not None and not self.pricing_version.strip():
            raise ValueError("pricing_version must be non-empty")
        if self.budget_decision is not None:
            allowed_decisions = {
                "allow",
                "stale_usage_snapshot",
                "usage_unavailable",
                "insufficient_balance",
                "budget_ceiling_exceeded",
                "reservation_conflict",
                "invalid_pricing",
            }
            if self.budget_decision not in allowed_decisions:
                raise ValueError("budget_decision is not a stable decision code")
            if self.event in {
                RunEventType.BUDGET_SNAPSHOT,
                RunEventType.BUDGET_PAUSED,
            } and (self.reason is None or not self.reason.strip()):
                raise ValueError("decided budget events require reason")

        if self.event in {
            RunEventType.BUDGET_SNAPSHOT,
            RunEventType.BUDGET_PAUSED,
        }:
            budget_facts_supplied = any(
                value is not None
                for value in (
                    self.budget_decision,
                    self.reservation_id,
                    self.reserved_cny,
                    self.active_reservations_cny,
                    self.requested_reservation_cny,
                    self.actual_cost_cny,
                    self.released_cny,
                    self.overspend_cny,
                )
            )
            actual_reservation_axes = (
                self.reservation_id,
                self.reserved_cny,
                self.actual_cost_cny,
                self.released_cny,
                self.overspend_cny,
            )
            if budget_facts_supplied and any(
                value is not None for value in actual_reservation_axes
            ):
                raise ValueError(
                    "snapshot and pause events must not contain actual reservation facts"
                )

        # Empty lifecycle events remain source-compatible with Phase A. Once a
        # caller supplies accounting facts, the v1 facts are strict and
        # self-consistent; the budget service always supplies the full set.
        budget_axes_supplied = any(
            value is not None
            for value in (
                self.balance_cny,
                self.reserved_cny,
                self.active_reservations_cny,
                self.requested_reservation_cny,
                self.minimum_remaining_cny,
                self.snapshot_age_seconds,
                self.reservation_id,
                self.actual_cost_cny,
                self.released_cny,
                self.overspend_cny,
                self.pricing_version,
                self.budget_decision,
            )
        )
        accounting_supplied = any(
            value is not None
            for value in (
                self.reservation_id,
                self.budget_decision
                if self.event in {
                    RunEventType.BUDGET_RESERVED,
                    RunEventType.BUDGET_RELEASED,
                }
                else None,
                self.reserved_cny if self.event in {
                    RunEventType.BUDGET_RESERVED,
                    RunEventType.BUDGET_RELEASED,
                } else None,
                self.actual_cost_cny,
                self.released_cny,
                self.overspend_cny,
                self.active_reservations_cny,
                self.requested_reservation_cny,
            )
        )
        if self.event is RunEventType.BUDGET_RESERVED and budget_axes_supplied:
            if any(
                value is not None
                for value in (
                    self.actual_cost_cny,
                    self.released_cny,
                    self.overspend_cny,
                )
            ):
                raise ValueError(
                    "budget_reserved must not contain terminal accounting facts"
                )
            if self.reservation_id is None or self.reserved_cny is None:
                raise ValueError("budget_reserved requires reservation_id and reserved_cny")
            if self.reserved_cny <= 0:
                raise ValueError("budget_reserved requires positive reserved_cny")
        if self.event is RunEventType.BUDGET_RELEASED and accounting_supplied:
            if self.reservation_id is None or self.reserved_cny is None:
                raise ValueError("budget_released requires reservation_id and reserved_cny")
            if self.reserved_cny <= 0 or self.released_cny is None:
                raise ValueError("budget_released requires positive reservation and released_cny")
            if self.actual_cost_cny is None:
                if self.overspend_cny is not None or self.released_cny != self.reserved_cny:
                    raise ValueError("release facts are inconsistent")
            elif self.overspend_cny is None:
                raise ValueError("reconciliation facts require overspend_cny")
            elif self.released_cny != max(self.reserved_cny - self.actual_cost_cny, Decimal("0")):
                raise ValueError("released_cny is inconsistent with actual_cost_cny")
            elif self.overspend_cny != max(self.actual_cost_cny - self.reserved_cny, Decimal("0")):
                raise ValueError("overspend_cny is inconsistent with actual_cost_cny")
        return self
