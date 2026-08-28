"""Provider-neutral, fail-closed budget admission decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Callable, Iterable

from bogda.budget.ledger import BudgetLedger
from bogda.budget.pricing import DEEPSEEK_CN_2026_08_28
from bogda.budget.usage import (
    UsageSnapshotStaleError,
    UsageSnapshotV1,
    UsageSnapshotFutureError,
    UsageSourceStatus,
    require_fresh_snapshot,
    snapshot_age_seconds,
)
from bogda.contracts import RunBudgetEnvelope


class BudgetGuardError(ValueError):
    """The ledger supplied invalid facts and could not be evaluated safely."""


class BudgetDecisionKind(StrEnum):
    ALLOW = "allow"
    STALE_USAGE_SNAPSHOT = "stale_usage_snapshot"
    USAGE_UNAVAILABLE = "usage_unavailable"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    BUDGET_CEILING_EXCEEDED = "budget_ceiling_exceeded"
    RESERVATION_CONFLICT = "reservation_conflict"
    INVALID_PRICING = "invalid_pricing"


def _money(value: object, name: str, *, non_negative: bool = True) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ValueError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if non_negative and value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    """Immutable explanation of one deterministic budget evaluation."""

    allowed: bool
    kind: BudgetDecisionKind
    reason: str
    balance: Decimal | None
    active_reservations: Decimal
    minimum_remaining: Decimal | None
    available_to_start: Decimal | None
    requested_reservation: Decimal | None
    snapshot_age: int | None
    ledger_revision: int
    pricing_version: str | None

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise ValueError("allowed must be a boolean")
        if not isinstance(self.kind, BudgetDecisionKind):
            raise ValueError("kind must be a BudgetDecisionKind")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be a non-empty string")
        if self.balance is not None:
            _money(self.balance, "balance")
        _money(self.active_reservations, "active_reservations")
        if self.minimum_remaining is not None:
            _money(self.minimum_remaining, "minimum_remaining")
        if self.available_to_start is not None:
            _money(self.available_to_start, "available_to_start", non_negative=False)
        if self.requested_reservation is not None:
            _money(self.requested_reservation, "requested_reservation", non_negative=False)
            if self.requested_reservation <= 0:
                raise ValueError("requested_reservation must be positive")
        if self.snapshot_age is not None:
            if type(self.snapshot_age) is not int or self.snapshot_age < 0:
                raise ValueError("snapshot_age must be a non-negative integer or None")
        if type(self.ledger_revision) is not int or self.ledger_revision < 0:
            raise ValueError("ledger_revision must be a non-negative integer")
        if self.pricing_version is not None and (
            not isinstance(self.pricing_version, str) or not self.pricing_version
        ):
            raise ValueError("pricing_version must be a non-empty string or None")

    @property
    def snapshot_age_seconds(self) -> int | None:
        return self.snapshot_age


class BudgetGuard:
    """Read-only admission policy over a usage snapshot and ledger facts."""

    def __init__(
        self,
        ledger: BudgetLedger,
        *,
        accepted_pricing_versions: Iterable[str] | None = None,
        now: datetime | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(ledger, BudgetLedger):
            raise ValueError("ledger must implement BudgetLedger")
        if isinstance(accepted_pricing_versions, str):
            raise ValueError("accepted_pricing_versions must be an iterable of strings")
        versions = (
            (DEEPSEEK_CN_2026_08_28.version,)
            if accepted_pricing_versions is None
            else tuple(accepted_pricing_versions)
        )
        if not versions or any(not isinstance(version, str) or not version for version in versions):
            raise ValueError("accepted_pricing_versions must contain non-empty strings")
        if now is not None:
            _aware(now, "now")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        self._ledger = ledger
        self._accepted_pricing_versions = frozenset(versions)
        self._fixed_now = now
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def accepted_pricing_versions(self) -> frozenset[str]:
        return self._accepted_pricing_versions

    def _now(self, supplied: datetime | None) -> datetime:
        value = supplied if supplied is not None else self._fixed_now
        if value is None:
            value = self._clock()
        return _aware(value, "now")

    def _facts(self) -> tuple[int, Decimal]:
        revision = self._ledger.revision
        active = self._ledger.active_total
        if type(revision) is not int or revision < 0:
            raise BudgetGuardError("ledger revision is invalid")
        return revision, _money(active, "active_reservations")

    @staticmethod
    def _decision(
        *,
        kind: BudgetDecisionKind,
        reason: str,
        revision: int,
        active: Decimal,
        balance: Decimal | None = None,
        minimum: Decimal | None = None,
        available: Decimal | None = None,
        requested: Decimal | None = None,
        age: int | None = None,
        pricing_version: str | None = None,
    ) -> BudgetDecision:
        return BudgetDecision(
            allowed=kind is BudgetDecisionKind.ALLOW,
            kind=kind,
            reason=reason,
            balance=balance,
            active_reservations=active,
            minimum_remaining=minimum,
            available_to_start=available,
            requested_reservation=requested,
            snapshot_age=age,
            ledger_revision=revision,
            pricing_version=pricing_version,
        )

    def evaluate(
        self,
        *,
        snapshot: UsageSnapshotV1 | None,
        envelope: RunBudgetEnvelope,
        reservation_cny: Decimal,
        now: datetime | None = None,
    ) -> BudgetDecision:
        """Evaluate without mutating the ledger; reserve separately with revision."""

        revision, active = self._facts()
        try:
            current = self._now(now)
        except (ValueError, TypeError):
            return self._decision(
                kind=BudgetDecisionKind.INVALID_PRICING,
                reason="evaluation_time_invalid",
                revision=revision,
                active=active,
            )

        if not isinstance(envelope, RunBudgetEnvelope):
            return self._decision(
                kind=BudgetDecisionKind.INVALID_PRICING,
                reason="budget_envelope_invalid",
                revision=revision,
                active=active,
            )
        pricing_version = envelope.pricing_version
        try:
            expected = _money(envelope.expected_cost, "expected_cost")
            ceiling = _money(envelope.authorized_ceiling, "authorized_ceiling")
            minimum = _money(envelope.minimum_remaining, "minimum_remaining")
            if expected > ceiling or pricing_version not in self._accepted_pricing_versions:
                raise ValueError("pricing is not accepted")
            if not isinstance(reservation_cny, Decimal) or isinstance(reservation_cny, bool):
                raise ValueError("reservation_cny must be a Decimal")
            if not reservation_cny.is_finite() or reservation_cny <= 0:
                raise ValueError("reservation_cny must be positive and finite")
            requested = reservation_cny
        except (TypeError, ValueError):
            requested = (
                reservation_cny
                if isinstance(reservation_cny, Decimal)
                and reservation_cny.is_finite()
                and reservation_cny > 0
                else None
            )
            return self._decision(
                kind=BudgetDecisionKind.INVALID_PRICING,
                reason="pricing_or_reservation_invalid",
                revision=revision,
                active=active,
                requested=requested,
                pricing_version=pricing_version if isinstance(pricing_version, str) else None,
            )

        balance: Decimal | None = None
        age: int | None = None
        if snapshot is None:
            return self._decision(
                kind=BudgetDecisionKind.USAGE_UNAVAILABLE,
                reason="usage_snapshot_unavailable",
                revision=revision,
                active=active,
                minimum=minimum,
                requested=requested,
                pricing_version=pricing_version,
            )
        if not isinstance(snapshot, UsageSnapshotV1):
            return self._decision(
                kind=BudgetDecisionKind.USAGE_UNAVAILABLE,
                reason="usage_snapshot_invalid",
                revision=revision,
                active=active,
                minimum=minimum,
                requested=requested,
                pricing_version=pricing_version,
            )
        try:
            age = snapshot_age_seconds(snapshot, now=current)
        except UsageSnapshotFutureError:
            age = 0
        except (ValueError, TypeError):
            return self._decision(
                kind=BudgetDecisionKind.USAGE_UNAVAILABLE,
                reason="usage_snapshot_invalid",
                revision=revision,
                active=active,
                minimum=minimum,
                requested=requested,
                pricing_version=pricing_version,
            )
        balance = snapshot.total_balance
        if snapshot.provider != "deepseek" or snapshot.currency != "CNY":
            return self._decision(
                kind=BudgetDecisionKind.USAGE_UNAVAILABLE,
                reason="usage_snapshot_wrong_provider_or_currency",
                revision=revision,
                active=active,
                balance=balance,
                minimum=minimum,
                requested=requested,
                age=age,
                pricing_version=pricing_version,
            )
        if snapshot.source_status is not UsageSourceStatus.UP or not snapshot.available:
            return self._decision(
                kind=BudgetDecisionKind.USAGE_UNAVAILABLE,
                reason="usage_snapshot_source_unavailable",
                revision=revision,
                active=active,
                balance=balance,
                minimum=minimum,
                requested=requested,
                age=age,
                pricing_version=pricing_version,
            )
        try:
            require_fresh_snapshot(snapshot, now=current)
        except (UsageSnapshotStaleError, UsageSnapshotFutureError):
            return self._decision(
                kind=BudgetDecisionKind.STALE_USAGE_SNAPSHOT,
                reason="usage_snapshot_not_fresh",
                revision=revision,
                active=active,
                balance=balance,
                minimum=minimum,
                requested=requested,
                age=age,
                pricing_version=pricing_version,
            )
        available = balance - active - minimum
        if requested > ceiling:
            return self._decision(
                kind=BudgetDecisionKind.BUDGET_CEILING_EXCEEDED,
                reason="reservation_exceeds_authorized_ceiling",
                revision=revision,
                active=active,
                balance=balance,
                minimum=minimum,
                available=available,
                requested=requested,
                age=age,
                pricing_version=pricing_version,
            )
        if requested > available:
            return self._decision(
                kind=BudgetDecisionKind.INSUFFICIENT_BALANCE,
                reason="insufficient_available_balance",
                revision=revision,
                active=active,
                balance=balance,
                minimum=minimum,
                available=available,
                requested=requested,
                age=age,
                pricing_version=pricing_version,
            )
        return self._decision(
            kind=BudgetDecisionKind.ALLOW,
            reason="budget_admitted",
            revision=revision,
            active=active,
            balance=balance,
            minimum=minimum,
            available=available,
            requested=requested,
            age=age,
            pricing_version=pricing_version,
        )


__all__ = ["BudgetDecision", "BudgetDecisionKind", "BudgetGuard", "BudgetGuardError"]
