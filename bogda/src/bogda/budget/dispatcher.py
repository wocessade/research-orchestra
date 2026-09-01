"""Owner three-way command over a frozen peak/valley plan. No live Prefect."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Callable, Protocol

from bogda.budget.guard import BudgetDecisionKind, BudgetGuard
from bogda.budget.scheduling import PriceAwareSchedulePlan
from bogda.budget.usage import UsageSnapshotV1
from bogda.contracts import RunBudgetEnvelope


class OwnerScheduleCommand(StrEnum):
    WAIT_FOR_OFF_PEAK = "wait_for_off_peak"
    START_NOW = "start_now"
    CANCEL = "cancel"


class PaidStartPort(Protocol):
    def start(self, run_id: str, scheduled_start: datetime) -> None:
        ...


@dataclass(frozen=True, slots=True)
class DispatchResult:
    started: bool
    cancelled: bool
    scheduled_start: datetime | None
    budget_kind: BudgetDecisionKind | None = None


class PriceAwareDispatcher:
    """Apply an owner command to a plan without enqueueing production research."""

    def __init__(
        self,
        starter: PaidStartPort,
        *,
        guard: BudgetGuard | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not callable(getattr(starter, "start", None)):
            raise ValueError("starter must implement PaidStartPort")
        self._starter = starter
        self._guard = guard
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def dispatch(
        self,
        run_id: str,
        plan: PriceAwareSchedulePlan,
        command: OwnerScheduleCommand,
        *,
        envelope: RunBudgetEnvelope | None = None,
        snapshot: UsageSnapshotV1 | None = None,
        reservation_cny: Decimal | None = None,
    ) -> DispatchResult:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(plan, PriceAwareSchedulePlan):
            raise ValueError("plan must be a PriceAwareSchedulePlan")
        if not isinstance(command, OwnerScheduleCommand):
            raise ValueError("command is invalid")
        if command is OwnerScheduleCommand.CANCEL:
            return DispatchResult(started=False, cancelled=True, scheduled_start=None)
        if command is OwnerScheduleCommand.WAIT_FOR_OFF_PEAK:
            return DispatchResult(
                started=False,
                cancelled=False,
                scheduled_start=plan.scheduled_start,
            )
        now = self._clock()
        if self._guard is not None:
            if envelope is None or reservation_cny is None:
                raise ValueError("start_now requires envelope and reservation_cny")
            decision = self._guard.evaluate(
                snapshot=snapshot,
                envelope=envelope,
                reservation_cny=reservation_cny,
                now=now,
            )
            if not decision.allowed:
                return DispatchResult(
                    started=False,
                    cancelled=False,
                    scheduled_start=None,
                    budget_kind=decision.kind,
                )
        self._starter.start(run_id, now)
        return DispatchResult(
            started=True,
            cancelled=False,
            scheduled_start=now,
            budget_kind=BudgetDecisionKind.ALLOW if self._guard is not None else None,
        )
