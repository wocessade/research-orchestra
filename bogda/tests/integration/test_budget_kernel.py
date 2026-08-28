from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from pathlib import Path
from threading import Barrier, Lock, Thread
from zoneinfo import ZoneInfo

import pytest

from bogda.budget import (
    BudgetAdmissionService,
    BudgetDecisionKind,
    BudgetGuard,
    HistoricalUsageProfile,
    SingleFlightBudgetLedger,
    TokenWorkload,
    UsageMonitorError,
    UsageSnapshotStaleError,
    UsageSnapshotV1,
    UsageSourceStatus,
    WorkloadEstimator,
)
from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope, RunEventType, RunEventV1, TaskIntent
from bogda.events.jsonl import JsonlRunEventSink


BEIJING = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 28, 8, 0, tzinfo=BEIJING)
PRICING = "deepseek-cn-2026-08-28"


class FakeUsage:
    def __init__(self, value: object) -> None:
        self.value = value

    def get_snapshot(self) -> UsageSnapshotV1 | None:
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value  # type: ignore[return-value]


def snapshot(
    *, balance: str = "10", now: datetime = NOW, age: int = 30
) -> UsageSnapshotV1:
    return UsageSnapshotV1(
        provider="deepseek",
        available=True,
        total_balance=Decimal(balance),
        currency="CNY",
        observed_at=now - timedelta(seconds=age),
        source_status=UsageSourceStatus.UP,
    )


def envelope(*, ceiling: str = "2", minimum: str = "1") -> RunBudgetEnvelope:
    return RunBudgetEnvelope(
        expected_cost=Decimal("1"),
        authorized_ceiling=Decimal(ceiling),
        minimum_remaining=Decimal(minimum),
        requested_tier=ModelTier.FLASH,
        budget_source=BudgetSource.RUN,
        pricing_version=PRICING,
    )


def service_for(
    usage: FakeUsage,
    path: Path,
    *,
    now: datetime = NOW,
    ledger: SingleFlightBudgetLedger | None = None,
) -> tuple[BudgetAdmissionService, SingleFlightBudgetLedger]:
    ids = count(1)
    actual_ledger = ledger or SingleFlightBudgetLedger(
        clock=lambda: now,
        id_factory=lambda: f"reservation-{next(ids)}",
    )
    return (
        BudgetAdmissionService(
            usage=usage,
            guard=BudgetGuard(actual_ledger, now=now),
            ledger=actual_ledger,
            event_sink=JsonlRunEventSink(path),
            clock=lambda: now,
        ),
        actual_ledger,
    )


def read_events(path: Path) -> list[RunEventV1]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines
    return [RunEventV1.model_validate_json(line) for line in lines]


def test_flash_fake_provider_freezes_envelope_and_round_trips_ordered_events(
    tmp_path: Path,
) -> None:
    estimator = WorkloadEstimator()
    estimate = estimator.estimate(
        intent=TaskIntent.EXPLORE,
        tier=ModelTier.FLASH,
        workload=TokenWorkload(
            expected_calls=1,
            cache_hit_input_tokens=0,
            cache_miss_input_tokens=100_000,
            output_tokens=100_000,
        ),
        start=NOW,
        end=NOW + timedelta(minutes=1),
        as_of=NOW,
    )
    frozen = estimator.to_budget_envelope(
        estimate,
        budget_source=BudgetSource.RUN,
        minimum_remaining=Decimal("1"),
        fallback_tier=None,
    )
    before = frozen.model_dump(mode="json")
    service, ledger = service_for(FakeUsage(snapshot()), tmp_path / "events.jsonl")

    result = service.admit("run-flash", TaskIntent.EXPLORE, frozen)

    assert result.decision.kind is BudgetDecisionKind.ALLOW
    assert result.reservation is not None
    assert frozen.model_dump(mode="json") == before
    assert ledger.active_total == result.reservation.reserved == frozen.authorized_ceiling
    events = read_events(tmp_path / "events.jsonl")
    assert [event.event for event in events] == [
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
    ]
    assert events[0].budget_decision == "allow"
    assert events[0].requested_reservation_cny == frozen.authorized_ceiling
    assert events[1].reservation_id == result.reservation.id
    assert events[1].reserved_cny == frozen.authorized_ceiling


def test_raised_stale_snapshot_is_distinct_from_generic_unavailable(
    tmp_path: Path,
) -> None:
    stale_service, stale_ledger = service_for(
        FakeUsage(UsageSnapshotStaleError()), tmp_path / "stale.jsonl"
    )
    stale = stale_service.admit("run-stale", TaskIntent.EXPLORE, envelope())

    assert stale.decision.kind is BudgetDecisionKind.STALE_USAGE_SNAPSHOT
    assert stale.decision.reason == "usage_snapshot_not_fresh"
    assert stale.reservation is None
    assert stale_ledger.active_total == Decimal("0")
    stale_events = read_events(tmp_path / "stale.jsonl")
    assert [event.budget_decision for event in stale_events] == [
        "stale_usage_snapshot",
        "stale_usage_snapshot",
    ]
    assert [event.event for event in stale_events] == [
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_PAUSED,
    ]

    unavailable_service, unavailable_ledger = service_for(
        FakeUsage(UsageMonitorError()), tmp_path / "unavailable.jsonl"
    )
    unavailable = unavailable_service.admit(
        "run-unavailable", TaskIntent.EXPLORE, envelope()
    )

    assert unavailable.decision.kind is BudgetDecisionKind.USAGE_UNAVAILABLE
    assert unavailable.decision.kind is not stale.decision.kind
    assert unavailable.decision.reason == "usage_monitor_error"
    assert unavailable.reservation is None
    assert unavailable_ledger.active_total == Decimal("0")
    assert read_events(tmp_path / "unavailable.jsonl")[1].budget_decision == (
        "usage_unavailable"
    )


def test_pro_peak_estimate_uses_dynamic_p90_retry_and_contingency_ceiling(
    tmp_path: Path,
) -> None:
    start = datetime(2026, 8, 28, 11, 30, tzinfo=BEIJING)
    end = start + timedelta(hours=1)
    estimate = WorkloadEstimator().estimate(
        intent=TaskIntent.EXPLORE,
        tier=ModelTier.PRO,
        workload=TokenWorkload(
            expected_calls=2,
            cache_hit_input_tokens=0,
            cache_miss_input_tokens=1_000_000,
            output_tokens=1_000_000,
            allowed_retries=2,
        ),
        start=start,
        end=end,
        as_of=start,
        history=HistoricalUsageProfile(p90_cost=Decimal("100")),
    )
    envelope_from_estimate = WorkloadEstimator().to_budget_envelope(
        estimate,
        budget_source=BudgetSource.PROJECT,
        minimum_remaining=Decimal("1"),
        fallback_tier=ModelTier.FLASH,
    )
    service, ledger = service_for(
        FakeUsage(snapshot(balance="200", now=start)),
        tmp_path / "pro-peak.jsonl",
        now=start,
    )

    result = service.admit("run-pro-peak", TaskIntent.EXPLORE, envelope_from_estimate)

    assert estimate.period.value == "peak"
    assert estimate.expected_cost == Decimal("36")
    assert estimate.contingency_factor == Decimal("1.60")
    assert estimate.historical_p90_cost == Decimal("100")
    assert estimate.retry_reserve == Decimal("36")
    assert estimate.authorized_ceiling == Decimal("136.00")
    assert estimate.authorized_ceiling > estimate.expected_cost
    assert estimate.authorized_ceiling != Decimal("5.32")
    assert result.decision.allowed is True
    assert result.reservation is not None
    assert ledger.active_total == Decimal("136.00")
    assert read_events(tmp_path / "pro-peak.jsonl")[1].reserved_cny == Decimal("136.00")


def test_balance_recovery_rechecks_same_envelope_without_expanding_it(
    tmp_path: Path,
) -> None:
    usage = FakeUsage(snapshot(balance="2"))
    service, ledger = service_for(usage, tmp_path / "recovery.jsonl")
    frozen = envelope(ceiling="2", minimum="1")
    before = frozen.model_dump(mode="json")

    denied = service.admit("run-recovery", TaskIntent.EXPLORE, frozen)
    usage.value = snapshot(balance="5")
    admitted = service.admit("run-recovery", TaskIntent.EXPLORE, frozen)

    assert denied.decision.kind is BudgetDecisionKind.INSUFFICIENT_BALANCE
    assert denied.reservation is None
    assert admitted.decision.kind is BudgetDecisionKind.ALLOW
    assert admitted.reservation is not None
    assert frozen.model_dump(mode="json") == before
    assert admitted.reservation.reserved == Decimal("2")
    assert ledger.active_total == Decimal("2")
    events = read_events(tmp_path / "recovery.jsonl")
    assert [event.event for event in events] == [
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_PAUSED,
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
    ]
    assert events[1].budget_decision == "insufficient_balance"
    assert events[3].budget_decision == "allow"


def test_competing_admissions_have_one_winner_and_parseable_events(
    tmp_path: Path,
) -> None:
    barrier = Barrier(2)

    class BarrierUsage(FakeUsage):
        def get_snapshot(self) -> UsageSnapshotV1:
            barrier.wait(timeout=5)
            return self.value  # type: ignore[return-value]

    usage = BarrierUsage(snapshot())
    service, ledger = service_for(usage, tmp_path / "competing.jsonl")
    results: dict[str, object] = {}
    failures: list[BaseException] = []
    result_lock = Lock()

    def admit(run_id: str) -> None:
        try:
            result = service.admit(run_id, TaskIntent.EXPLORE, envelope())
            with result_lock:
                results[run_id] = result
        except BaseException as error:  # pragma: no cover - diagnostic assertion
            with result_lock:
                failures.append(error)

    threads = [Thread(target=admit, args=(f"run-{index}",)) for index in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert failures == []
    assert len(results) == 2
    admitted = [result for result in results.values() if result.reservation is not None]
    denied = [result for result in results.values() if result.reservation is None]
    assert len(admitted) == 1
    assert len(denied) == 1
    assert denied[0].decision.kind is BudgetDecisionKind.RESERVATION_CONFLICT
    assert ledger.active_total == admitted[0].reservation.reserved

    events = read_events(tmp_path / "competing.jsonl")
    assert len(events) == 4
    by_run: dict[str, list[RunEventV1]] = {}
    for event in events:
        by_run.setdefault(event.run_id, []).append(event)
    assert set(by_run) == {"run-1", "run-2"}
    for run_events in by_run.values():
        assert run_events[0].event is RunEventType.BUDGET_SNAPSHOT
        assert run_events[1].event in {
            RunEventType.BUDGET_RESERVED,
            RunEventType.BUDGET_PAUSED,
        }
    assert sum(event.event is RunEventType.BUDGET_RESERVED for event in events) == 1
    assert sum(event.event is RunEventType.BUDGET_PAUSED for event in events) == 1
