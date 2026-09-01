from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from bogda.budget.dispatcher import (
    OwnerScheduleCommand,
    PriceAwareDispatcher,
)
from bogda.budget.guard import BudgetDecisionKind, BudgetGuard
from bogda.budget.ledger import SingleFlightBudgetLedger
from bogda.budget.scheduling import PriceAwareScheduler, ScheduleDisposition
from bogda.budget.usage import UsageSnapshotV1, UsageSourceStatus
from bogda.contracts import (
    BudgetSource,
    ModelTier,
    RunBudgetEnvelope,
    SchedulePolicy,
    TaskIntent,
)
from bogda.budget.estimation import TokenWorkload


BEIJING = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 28, 10, 0, tzinfo=BEIJING)


class RecordingStart:
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime]] = []

    def start(self, run_id: str, scheduled_start: datetime) -> None:
        self.calls.append((run_id, scheduled_start))


def workload() -> TokenWorkload:
    return TokenWorkload(
        expected_calls=1,
        cache_hit_input_tokens=0,
        cache_miss_input_tokens=1_000_000,
        output_tokens=1_000_000,
    )


def peak_plan():
    return PriceAwareScheduler().plan(
        intent=TaskIntent.EXECUTE,
        tier=ModelTier.FLASH,
        workload=workload(),
        runtime_minutes=30,
        policy=SchedulePolicy(deadline=datetime(2026, 8, 28, 13, 0, tzinfo=BEIJING)),
        now=NOW,
    )


def test_wait_and_cancel_do_not_start(tmp_path) -> None:
    starter = RecordingStart()
    dispatcher = PriceAwareDispatcher(starter)
    plan = peak_plan()
    assert plan.disposition is ScheduleDisposition.WAIT_FOR_OFF_PEAK

    waited = dispatcher.dispatch("run-1", plan, OwnerScheduleCommand.WAIT_FOR_OFF_PEAK)
    cancelled = dispatcher.dispatch("run-1", plan, OwnerScheduleCommand.CANCEL)

    assert waited.started is False
    assert waited.scheduled_start == plan.scheduled_start
    assert cancelled.started is False
    assert cancelled.cancelled is True
    assert starter.calls == []


def test_start_now_at_peak_requires_budget_admission() -> None:
    starter = RecordingStart()
    ledger = SingleFlightBudgetLedger()
    guard = BudgetGuard(ledger, now=NOW)
    dispatcher = PriceAwareDispatcher(starter, guard=guard, clock=lambda: NOW)
    plan = peak_plan()
    envelope = RunBudgetEnvelope(
        expected_cost=plan.current_estimate.expected_cost,
        authorized_ceiling=plan.current_estimate.authorized_ceiling,
        minimum_remaining=Decimal("1"),
        requested_tier=ModelTier.FLASH,
        fallback_tier=None,
        budget_source=BudgetSource.RUN,
        pricing_version="deepseek-cn-2026-08-28",
    )

    result = dispatcher.dispatch(
        "run-1",
        plan,
        OwnerScheduleCommand.START_NOW,
        envelope=envelope,
        snapshot=UsageSnapshotV1(
            provider="deepseek",
            available=True,
            total_balance=Decimal("200"),
            currency="CNY",
            observed_at=NOW,
            source_status=UsageSourceStatus.UP,
        ),
        reservation_cny=plan.current_estimate.authorized_ceiling,
    )

    assert plan.current_estimate.authorized_ceiling <= Decimal("20")
    assert result.started is True
    assert result.budget_kind is BudgetDecisionKind.ALLOW
    assert starter.calls == [("run-1", NOW)]
