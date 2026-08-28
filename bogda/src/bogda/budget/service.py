"""Budget admission orchestration with durable, secret-free event ordering."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from threading import RLock
from typing import Callable

from bogda.budget.guard import BudgetDecision, BudgetDecisionKind, BudgetGuard
from bogda.budget.ledger import (
    BudgetLedger,
    LedgerRevisionConflictError,
    Reservation,
    ReservationConflictError,
    ReservationState,
)
from bogda.budget.usage import (
    UsageMonitorError,
    UsageSnapshotFutureError,
    UsageSnapshotStaleError,
    UsageSnapshotV1,
    UsagePort,
    snapshot_age_seconds,
)
from bogda.contracts import ModelTier, RunBudgetEnvelope, RunEventType, RunEventV1, TaskIntent
from bogda.events.jsonl import RunEventSink


class BudgetServiceError(RuntimeError):
    """Base class for safe service failures."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class BudgetEventWriteError(BudgetServiceError):
    """An event could not be persisted."""


class BudgetEventCompensationError(BudgetEventWriteError):
    """An event failed and its newly-created reservation could not be released."""


class BudgetAdmissionError(BudgetServiceError):
    """A non-event service dependency failed safely."""


@dataclass(frozen=True, slots=True)
class BudgetAdmissionResult:
    """Immutable result whose reservation presence agrees with the decision."""

    decision: BudgetDecision
    reservation: Reservation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.decision, BudgetDecision):
            raise ValueError("decision must be a BudgetDecision")
        if self.decision.allowed:
            if self.reservation is None or self.reservation.state is not ReservationState.ACTIVE:
                raise ValueError("an allowed admission requires an active reservation")
            requested = self.decision.requested_reservation
            if requested is None or self.reservation.reserved != requested:
                raise ValueError("reservation does not match the admission decision")
        elif self.reservation is not None:
            raise ValueError("a denied admission cannot contain a reservation")


def _aware(value: object) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise BudgetAdmissionError("clock must return a timezone-aware datetime")
    return value


def _intent(value: object) -> TaskIntent:
    try:
        return value if isinstance(value, TaskIntent) else TaskIntent(value)
    except (TypeError, ValueError):
        raise BudgetAdmissionError("intent is invalid") from None


def _tier(value: object) -> ModelTier:
    try:
        return value if isinstance(value, ModelTier) else ModelTier(value)
    except (TypeError, ValueError):
        raise BudgetAdmissionError("requested tier is invalid") from None


def _pricing_version(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BudgetAdmissionError("pricing version is invalid")
    return value


def _stable_monitor_reason(error: UsageMonitorError) -> str:
    if isinstance(error, (UsageSnapshotStaleError, UsageSnapshotFutureError)):
        return "usage_snapshot_not_fresh"
    return "usage_monitor_error"


class BudgetAdmissionService:
    """Coordinate usage, guard, atomic ledger mutation, and event persistence.

    Terminal delivery tracking is process-local. Cross-process exactly-once
    delivery requires a durable outbox or sink implementation, which is a
    later replacement point for this Phase B service.
    """

    def __init__(
        self,
        *,
        usage: UsagePort,
        guard: BudgetGuard,
        ledger: BudgetLedger,
        event_sink: RunEventSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not callable(getattr(usage, "get_snapshot", None)):
            raise ValueError("usage must implement UsagePort")
        if not callable(getattr(event_sink, "append", None)):
            raise ValueError("event_sink must implement RunEventSink")
        if not callable(getattr(ledger, "reserve", None)):
            raise ValueError("ledger must implement BudgetLedger")
        if not isinstance(guard, BudgetGuard):
            raise ValueError("guard must be a BudgetGuard")
        if guard.ledger is not ledger:
            raise ValueError("guard and ledger must be the same instance")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        self._usage = usage
        self._guard = guard
        self._ledger = ledger
        self._event_sink = event_sink
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._terminal_lock = RLock()
        self._delivered_terminal_events: dict[tuple[object, ...], RunEventV1] = {}
        self._terminal_contexts: dict[
            tuple[object, ...], tuple[TaskIntent, ModelTier, str]
        ] = {}
        self._admission_contexts: dict[
            str, tuple[TaskIntent, ModelTier, str]
        ] = {}

    def _now(self) -> datetime:
        try:
            return _aware(self._clock())
        except BudgetAdmissionError:
            raise
        except Exception:
            raise BudgetAdmissionError("clock failed") from None

    def _append(self, event: RunEventV1) -> None:
        try:
            self._event_sink.append(event)
        except Exception:
            raise BudgetEventWriteError("event write failed") from None

    def _snapshot(
        self,
    ) -> tuple[UsageSnapshotV1 | None, str | None, BudgetDecisionKind | None]:
        try:
            snapshot = self._usage.get_snapshot()
        except UsageMonitorError as error:
            reason = _stable_monitor_reason(error)
            kind = (
                BudgetDecisionKind.STALE_USAGE_SNAPSHOT
                if reason == "usage_snapshot_not_fresh"
                else None
            )
            return None, reason, kind
        except Exception:
            return None, "usage_monitor_error", None
        if snapshot is None:
            return None, "usage_snapshot_unavailable", None
        if not isinstance(snapshot, UsageSnapshotV1):
            return None, "usage_snapshot_invalid", None
        return snapshot, None, None

    @staticmethod
    def _snapshot_age(snapshot: UsageSnapshotV1 | None, now: datetime) -> int | None:
        if snapshot is None:
            return None
        try:
            return snapshot_age_seconds(snapshot, now=now)
        except Exception:
            return None

    @staticmethod
    def _event_context(
        *,
        run_id: str,
        intent: TaskIntent,
        requested_tier: ModelTier,
        now: datetime,
        decision: BudgetDecision,
        snapshot: UsageSnapshotV1 | None,
        event: RunEventType,
        reason: str | None = None,
        reservation_id: str | None = None,
        reserved_cny: Decimal | None = None,
        active_reservations_cny: Decimal | None = None,
        requested_reservation_cny: Decimal | None = None,
        actual_cost_cny: Decimal | None = None,
        released_cny: Decimal | None = None,
        overspend_cny: Decimal | None = None,
        budget_decision: str | None = None,
    ) -> RunEventV1:
        return RunEventV1(
            event=event,
            run_id=run_id,
            occurred_at=now,
            intent=intent,
            requested_tier=requested_tier,
            reason=reason or decision.reason,
            balance_cny=decision.balance,
            reserved_cny=reserved_cny,
            active_reservations_cny=active_reservations_cny,
            requested_reservation_cny=requested_reservation_cny,
            minimum_remaining_cny=decision.minimum_remaining,
            snapshot_age_seconds=decision.snapshot_age
            if decision.snapshot_age is not None
            else BudgetAdmissionService._snapshot_age(snapshot, now),
            reservation_id=reservation_id,
            actual_cost_cny=actual_cost_cny,
            released_cny=released_cny,
            overspend_cny=overspend_cny,
            pricing_version=decision.pricing_version,
            budget_decision=budget_decision,
        )

    @staticmethod
    def _terminal_key(operation: str, reservation: Reservation) -> tuple[object, ...]:
        return (
            operation,
            reservation.id,
            reservation.run_id,
            reservation.state,
            reservation.reserved,
            reservation.actual_cost,
            reservation.released_amount,
            reservation.overspend,
            reservation.updated_at,
        )

    @staticmethod
    def _terminal_event(
        *,
        reservation: Reservation,
        intent: TaskIntent,
        requested_tier: ModelTier,
        pricing_version: str,
        operation: str,
    ) -> RunEventV1:
        decision = BudgetDecision(
            allowed=True,
            kind=BudgetDecisionKind.ALLOW,
            reason=("budget_released" if operation == "release" else "budget_reconciled"),
            balance=None,
            active_reservations=Decimal("0"),
            minimum_remaining=None,
            available_to_start=None,
            requested_reservation=reservation.reserved,
            snapshot_age=None,
            ledger_revision=0,
            pricing_version=pricing_version,
        )
        return BudgetAdmissionService._event_context(
            run_id=reservation.run_id,
            intent=intent,
            requested_tier=requested_tier,
            now=reservation.updated_at,
            decision=decision,
            snapshot=None,
            event=RunEventType.BUDGET_RELEASED,
            reason=decision.reason,
            reservation_id=reservation.id,
            reserved_cny=reservation.reserved,
            active_reservations_cny=Decimal("0"),
            requested_reservation_cny=reservation.reserved,
            actual_cost_cny=reservation.actual_cost,
            released_cny=reservation.released_amount,
            overspend_cny=reservation.overspend,
            budget_decision=None,
        )

    def _conflict_decision(self, decision: BudgetDecision) -> BudgetDecision:
        if decision.kind is BudgetDecisionKind.RESERVATION_CONFLICT:
            return decision
        return replace(
            decision,
            allowed=False,
            kind=BudgetDecisionKind.RESERVATION_CONFLICT,
            reason="reservation_conflict",
        )

    def admit(
        self,
        run_id: str,
        intent: TaskIntent,
        envelope: RunBudgetEnvelope,
        reservation_cny: Decimal | None = None,
    ) -> BudgetAdmissionResult:
        if not isinstance(run_id, str) or not run_id:
            raise BudgetAdmissionError("run_id must be a non-empty string")
        intent = _intent(intent)
        if not isinstance(envelope, RunBudgetEnvelope):
            raise BudgetAdmissionError("budget envelope is invalid")
        requested = envelope.authorized_ceiling if reservation_cny is None else reservation_cny
        now = self._now()
        snapshot, monitor_reason, monitor_kind = self._snapshot()
        try:
            decision = self._guard.evaluate(
                snapshot=snapshot,
                envelope=envelope,
                reservation_cny=requested,
                now=now,
            )
        except Exception:
            raise BudgetAdmissionError("budget evaluation failed") from None
        if (
            monitor_kind is not None
            and decision.kind is BudgetDecisionKind.USAGE_UNAVAILABLE
        ):
            decision = replace(
                decision,
                allowed=False,
                kind=monitor_kind,
                reason=monitor_reason or "usage_snapshot_not_fresh",
            )
        elif monitor_reason is not None and decision.reason == "usage_snapshot_unavailable":
            decision = replace(decision, reason=monitor_reason)

        snapshot_event = self._event_context(
            run_id=run_id,
            intent=intent,
            requested_tier=envelope.requested_tier,
            now=now,
            decision=decision,
            snapshot=snapshot,
            event=RunEventType.BUDGET_SNAPSHOT,
            reserved_cny=None,
            active_reservations_cny=decision.active_reservations,
            requested_reservation_cny=decision.requested_reservation,
            budget_decision=decision.kind.value,
        )
        # This is deliberately before every possible reserve call.
        self._append(snapshot_event)

        if not decision.allowed:
            self._append(
                self._event_context(
                    run_id=run_id,
                    intent=intent,
                    requested_tier=envelope.requested_tier,
                    now=now,
                    decision=decision,
                    snapshot=snapshot,
                    event=RunEventType.BUDGET_PAUSED,
                    reserved_cny=None,
                    active_reservations_cny=decision.active_reservations,
                    requested_reservation_cny=decision.requested_reservation,
                    budget_decision=decision.kind.value,
                )
            )
            return BudgetAdmissionResult(decision=decision)

        try:
            reservation = self._ledger.reserve(
                run_id=run_id,
                amount=requested,
                expected_revision=decision.ledger_revision,
                now=now,
            )
        except (LedgerRevisionConflictError, ReservationConflictError):
            try:
                raced = self._guard.evaluate(
                    snapshot=snapshot,
                    envelope=envelope,
                    reservation_cny=requested,
                    now=now,
                )
            except Exception:
                raise BudgetAdmissionError("reservation conflict evaluation failed") from None
            conflict = self._conflict_decision(raced)
            self._append(
                self._event_context(
                    run_id=run_id,
                    intent=intent,
                    requested_tier=envelope.requested_tier,
                    now=now,
                    decision=conflict,
                    snapshot=snapshot,
                    event=RunEventType.BUDGET_PAUSED,
                    reserved_cny=None,
                    active_reservations_cny=conflict.active_reservations,
                    requested_reservation_cny=conflict.requested_reservation,
                    budget_decision=conflict.kind.value,
                )
            )
            return BudgetAdmissionResult(decision=conflict)
        except Exception:
            raise BudgetAdmissionError("reservation failed") from None

        try:
            self._append(
                self._event_context(
                    run_id=run_id,
                    intent=intent,
                    requested_tier=envelope.requested_tier,
                    now=now,
                    decision=decision,
                    snapshot=snapshot,
                    event=RunEventType.BUDGET_RESERVED,
                    reservation_id=reservation.id,
                    reserved_cny=reservation.reserved,
                    active_reservations_cny=decision.active_reservations,
                    requested_reservation_cny=decision.requested_reservation,
                    budget_decision=decision.kind.value,
                )
            )
        except BudgetEventWriteError:
            try:
                self._ledger.release(reservation.id, now=now)
            except Exception:
                raise BudgetEventCompensationError("reservation compensation failed") from None
            raise
        self._admission_contexts[reservation.id] = (
            intent,
            envelope.requested_tier,
            envelope.pricing_version,
        )
        return BudgetAdmissionResult(decision=decision, reservation=reservation)

    def release(
        self,
        reservation_id: str,
        *,
        intent: TaskIntent,
        requested_tier: ModelTier,
        pricing_version: str,
    ) -> Reservation:
        intent = _intent(intent)
        requested_tier = _tier(requested_tier)
        pricing_version = _pricing_version(pricing_version)
        with self._terminal_lock:
            before = self._ledger.lookup(reservation_id)
            self._validate_admission_context(
                before.id,
                intent=intent,
                requested_tier=requested_tier,
                pricing_version=pricing_version,
            )
            if before.state is ReservationState.RECONCILED:
                raise BudgetAdmissionError("reconciled reservation cannot be released")
            if before.state is ReservationState.RELEASED:
                self._append_terminal_event(
                    before,
                    intent=intent,
                    requested_tier=requested_tier,
                    pricing_version=pricing_version,
                    operation="release",
                )
                return before

            now = self._now()
            try:
                released = self._ledger.release(reservation_id, now=now)
            except Exception:
                raise BudgetAdmissionError("reservation release failed") from None
            self._append_terminal_event(
                released,
                intent=intent,
                requested_tier=requested_tier,
                pricing_version=pricing_version,
                operation="release",
            )
            return released

    def reconcile(
        self,
        reservation_id: str,
        actual_cost_cny: Decimal,
        *,
        intent: TaskIntent,
        requested_tier: ModelTier,
        pricing_version: str,
    ) -> Reservation:
        intent = _intent(intent)
        requested_tier = _tier(requested_tier)
        pricing_version = _pricing_version(pricing_version)
        with self._terminal_lock:
            before = self._ledger.lookup(reservation_id)
            self._validate_admission_context(
                before.id,
                intent=intent,
                requested_tier=requested_tier,
                pricing_version=pricing_version,
            )
            if before.state is ReservationState.RELEASED:
                raise BudgetAdmissionError("released reservation cannot be reconciled")
            if before.state is ReservationState.RECONCILED:
                if before.actual_cost != actual_cost_cny:
                    raise BudgetAdmissionError("reconciliation conflicts with recorded cost")
                self._append_terminal_event(
                    before,
                    intent=intent,
                    requested_tier=requested_tier,
                    pricing_version=pricing_version,
                    operation="reconcile",
                )
                return before

            now = self._now()
            try:
                reconciled = self._ledger.reconcile(
                    reservation_id, actual_cost_cny, now=now
                )
            except Exception:
                raise BudgetAdmissionError("reservation reconciliation failed") from None
            self._append_terminal_event(
                reconciled,
                intent=intent,
                requested_tier=requested_tier,
                pricing_version=pricing_version,
                operation="reconcile",
            )
            return reconciled

    def _append_terminal_event(
        self,
        reservation: Reservation,
        *,
        intent: TaskIntent,
        requested_tier: ModelTier,
        pricing_version: str,
        operation: str,
    ) -> None:
        self._validate_admission_context(
            reservation.id,
            intent=intent,
            requested_tier=requested_tier,
            pricing_version=pricing_version,
        )
        key = self._terminal_key(operation, reservation)
        delivered = self._delivered_terminal_events.get(key)
        context = self._terminal_contexts.get(key)
        if delivered is not None:
            context = (
                delivered.intent,
                delivered.requested_tier,
                delivered.pricing_version,
            )
        requested_context = (intent, requested_tier, pricing_version)
        if context is not None and context != requested_context:
            raise BudgetAdmissionError("terminal event context conflicts")
        self._terminal_contexts.setdefault(key, requested_context)
        if key in self._delivered_terminal_events:
            return
        event = self._terminal_event(
            reservation=reservation,
            intent=intent,
            requested_tier=requested_tier,
            pricing_version=pricing_version,
            operation=operation,
        )
        self._append(event)
        self._delivered_terminal_events[key] = event

    def _validate_admission_context(
        self,
        reservation_id: str,
        *,
        intent: TaskIntent,
        requested_tier: ModelTier,
        pricing_version: str,
    ) -> None:
        expected = self._admission_contexts.get(reservation_id)
        if expected is not None and expected != (
            intent,
            requested_tier,
            pricing_version,
        ):
            raise BudgetAdmissionError("terminal event context conflicts")


__all__ = [
    "BudgetAdmissionError",
    "BudgetAdmissionResult",
    "BudgetAdmissionService",
    "BudgetEventCompensationError",
    "BudgetEventWriteError",
    "BudgetServiceError",
]
