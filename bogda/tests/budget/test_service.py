from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from bogda.budget import (
    BudgetAdmissionError,
    BudgetAdmissionService,
    BudgetEventCompensationError,
    BudgetEventWriteError,
    BudgetGuard,
    SingleFlightBudgetLedger,
    UsageMonitorError,
    UsageSnapshotFutureError,
    UsageSnapshotStaleError,
    UsageSnapshotV1,
    UsageSourceStatus,
)
from bogda.budget.ledger import LedgerRevisionConflictError
from bogda.budget.pricing import DEEPSEEK_CN_2026_08_28
from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope, RunEventType
from bogda.events.jsonl import JsonlRunEventSink


NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)
PRICING = "deepseek-cn-2026-08-28"
SENTINEL = "monitor-token-sentinel"


def snapshot(
    *, balance: str = "10", age: int = 30, available: bool = True,
    source_status: UsageSourceStatus = UsageSourceStatus.UP,
) -> UsageSnapshotV1:
    return UsageSnapshotV1(
        provider="deepseek",
        available=available,
        total_balance=Decimal(balance),
        currency="CNY",
        observed_at=NOW - timedelta(seconds=age),
        source_status=source_status,
    )


def envelope(*, ceiling: str = "3", minimum: str = "1") -> RunBudgetEnvelope:
    return RunBudgetEnvelope(
        expected_cost=Decimal("1"),
        authorized_ceiling=Decimal(ceiling),
        minimum_remaining=Decimal(minimum),
        requested_tier=ModelTier.FLASH,
        budget_source=BudgetSource.RUN,
        pricing_version=PRICING,
    )


class FakeUsage:
    def __init__(self, value: object) -> None:
        self.value = value

    def get_snapshot(self) -> UsageSnapshotV1:
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value  # type: ignore[return-value]


class MemorySink:
    def __init__(self) -> None:
        self.events = []

    def append(self, event) -> None:
        self.events.append(event)


class FailingSink(MemorySink):
    def __init__(self, fail_on: int) -> None:
        super().__init__()
        self.fail_on = fail_on
        self.failed = False

    def append(self, event) -> None:
        if not self.failed and len(self.events) + 1 == self.fail_on:
            self.failed = True
            raise OSError(SENTINEL)
        super().append(event)


def make_service(usage: object, sink: object, ledger=None) -> tuple[BudgetAdmissionService, object]:
    actual_ledger = ledger or SingleFlightBudgetLedger(clock=lambda: NOW, id_factory=lambda: "reservation-1")
    service = BudgetAdmissionService(
        usage=usage,
        guard=BudgetGuard(actual_ledger, now=NOW),
        ledger=actual_ledger,
        event_sink=sink,
        clock=lambda: NOW,
    )
    return service, actual_ledger


def test_allow_emits_snapshot_then_reserved_and_returns_consistent_result() -> None:
    sink = MemorySink()
    service, ledger = make_service(FakeUsage(snapshot()), sink)

    result = service.admit("run-1", "explore", envelope(), reservation_cny=Decimal("2"))

    assert result.decision.allowed is True
    assert result.reservation is not None
    assert [event.event for event in sink.events] == [
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
    ]
    assert sink.events[0].budget_decision == "allow"
    assert sink.events[1].reservation_id == result.reservation.id
    assert sink.events[1].reserved_cny == Decimal("2")
    assert ledger.active_total == Decimal("2")


@pytest.mark.parametrize(
    ("provided", "expected_reason"),
    [
        (None, "usage_snapshot_unavailable"),
        (UsageMonitorError(), "usage_monitor_error"),
        (snapshot(age=121), "usage_snapshot_not_fresh"),
        (snapshot(balance="1", age=30), "insufficient_available_balance"),
    ],
)
def test_denial_emits_snapshot_then_pause_without_mutating_ledger(
    provided: object, expected_reason: str
) -> None:
    sink = MemorySink()
    service, ledger = make_service(FakeUsage(provided), sink)

    result = service.admit("run-1", "explore", envelope(), reservation_cny=Decimal("2"))

    assert result.reservation is None
    assert result.decision.allowed is False
    assert result.decision.reason == expected_reason
    assert [event.event for event in sink.events] == [
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_PAUSED,
    ]
    assert sink.events[1].reason == expected_reason
    assert sink.events[0].budget_decision == sink.events[1].budget_decision
    assert sink.events[0].reserved_cny is None
    assert sink.events[0].active_reservations_cny == Decimal("0")
    assert sink.events[0].requested_reservation_cny == Decimal("2")
    assert sink.events[1].reserved_cny is None
    assert sink.events[1].active_reservations_cny == Decimal("0")
    assert sink.events[1].requested_reservation_cny == Decimal("2")
    assert ledger.active_total == Decimal("0")


def test_release_and_reconcile_emit_terminal_facts_once() -> None:
    sink = MemorySink()
    service, ledger = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope(), reservation_cny=Decimal("2"))
    assert admitted.reservation is not None

    released = service.release(
        admitted.reservation.id, intent="explore", requested_tier="flash",
        pricing_version=PRICING,
    )
    repeated = service.release(
        admitted.reservation.id, intent="explore", requested_tier="flash",
        pricing_version=PRICING,
    )
    assert released == repeated
    release_events = [event for event in sink.events if event.event is RunEventType.BUDGET_RELEASED]
    assert len(release_events) == 1
    assert release_events[0].pricing_version == PRICING

    sink2 = MemorySink()
    service2, _ = make_service(FakeUsage(snapshot()), sink2)
    admitted2 = service2.admit("run-2", "explore", envelope(), reservation_cny=Decimal("2"))
    assert admitted2.reservation is not None
    reconciled = service2.reconcile(
        admitted2.reservation.id,
        Decimal("1.25"),
        intent="explore",
        requested_tier="flash",
        pricing_version=PRICING,
    )
    repeated_reconcile = service2.reconcile(
        admitted2.reservation.id,
        Decimal("1.25"),
        intent="explore",
        requested_tier="flash",
        pricing_version=PRICING,
    )
    assert reconciled == repeated_reconcile
    terminal = [event for event in sink2.events if event.event is RunEventType.BUDGET_RELEASED]
    assert len(terminal) == 1
    assert terminal[0].actual_cost_cny == Decimal("1.25")
    assert terminal[0].released_cny == Decimal("0.75")
    assert terminal[0].overspend_cny == Decimal("0")
    assert terminal[0].budget_decision is None
    assert terminal[0].intent.value == "explore"
    assert terminal[0].requested_tier.value == "flash"
    assert terminal[0].pricing_version == PRICING


def test_event_failure_before_reserve_does_not_mutate_ledger() -> None:
    sink = FailingSink(fail_on=1)
    service, ledger = make_service(FakeUsage(snapshot()), sink)

    with pytest.raises(BudgetEventWriteError):
        service.admit("run-1", "explore", envelope())
    assert ledger.active_total == Decimal("0")


def test_event_failure_after_reserve_compensates_and_hides_secret() -> None:
    sink = FailingSink(fail_on=2)
    service, ledger = make_service(FakeUsage(snapshot()), sink)

    with pytest.raises(BudgetEventWriteError) as raised:
        service.admit("run-1", "explore", envelope())
    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in repr(raised.value)
    assert ledger.active_total == Decimal("0")
    assert ledger.lookup("reservation-1").state.value == "released"


def test_compensation_failure_is_typed_and_safe() -> None:
    class BrokenCompensationLedger(SingleFlightBudgetLedger):
        def release(self, reservation_id: str, *, now=None):
            raise RuntimeError(SENTINEL)

    sink = FailingSink(fail_on=2)
    ledger = BrokenCompensationLedger(clock=lambda: NOW, id_factory=lambda: "reservation-1")
    service, _ = make_service(FakeUsage(snapshot()), sink, ledger)

    with pytest.raises(BudgetEventCompensationError) as raised:
        service.admit("run-1", "explore", envelope())
    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in repr(raised.value)


def test_reservation_race_emits_snapshot_then_conflict_pause() -> None:
    class RacingLedger(SingleFlightBudgetLedger):
        def reserve(self, **kwargs):
            raise LedgerRevisionConflictError("race detail")

    sink = MemorySink()
    ledger = RacingLedger(clock=lambda: NOW, id_factory=lambda: "unused")
    service, _ = make_service(FakeUsage(snapshot()), sink, ledger)

    result = service.admit("run-1", "explore", envelope())

    assert result.reservation is None
    assert result.decision.kind.value == "reservation_conflict"
    assert [event.event for event in sink.events] == [
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_PAUSED,
    ]
    assert sink.events[-1].reason == "reservation_conflict"


@pytest.mark.parametrize("operation", ["release", "reconcile"])
def test_terminal_mutation_survives_terminal_event_write_failure(operation: str) -> None:
    sink = FailingSink(fail_on=3)
    service, ledger = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope())
    assert admitted.reservation is not None

    with pytest.raises(BudgetEventWriteError):
        if operation == "release":
            service.release(
                admitted.reservation.id, intent="explore", requested_tier="flash",
                pricing_version=PRICING,
            )
        else:
            service.reconcile(
                admitted.reservation.id,
                Decimal("1"),
                intent="explore",
                requested_tier="flash",
                pricing_version=PRICING,
            )

    terminal = ledger.lookup(admitted.reservation.id)
    assert terminal.state.value == ("released" if operation == "release" else "reconciled")


@pytest.mark.parametrize("error", [UsageSnapshotStaleError(), UsageSnapshotFutureError()])
def test_raised_stale_monitor_outcomes_are_not_reported_as_unavailable(
    error: UsageMonitorError,
) -> None:
    sink = MemorySink()
    service, ledger = make_service(FakeUsage(error), sink)

    result = service.admit("run-1", "explore", envelope())

    assert result.decision.kind.value == "stale_usage_snapshot"
    assert result.decision.reason == "usage_snapshot_not_fresh"
    assert sink.events[0].budget_decision == "stale_usage_snapshot"
    assert sink.events[1].budget_decision == "stale_usage_snapshot"
    assert ledger.active_total == Decimal("0")


def test_raised_stale_monitor_does_not_override_invalid_pricing() -> None:
    expired = DEEPSEEK_CN_2026_08_28.model_copy(
        update={"review_by": NOW - timedelta(seconds=1)}
    )
    ledger = SingleFlightBudgetLedger(clock=lambda: NOW, id_factory=lambda: "reservation-1")
    sink = MemorySink()
    service = BudgetAdmissionService(
        usage=FakeUsage(UsageSnapshotStaleError()),
        guard=BudgetGuard(ledger, pricing_catalogs=(expired,), now=NOW),
        ledger=ledger,
        event_sink=sink,
        clock=lambda: NOW,
    )

    result = service.admit("run-1", "explore", envelope())

    assert result.decision.kind.value == "invalid_pricing"
    assert [event.budget_decision for event in sink.events] == [
        "invalid_pricing",
        "invalid_pricing",
    ]
    assert [event.reason for event in sink.events] == [
        "pricing_or_reservation_invalid",
        "pricing_or_reservation_invalid",
    ]


def test_raised_stale_monitor_does_not_mask_over_ceiling() -> None:
    sink = MemorySink()
    service, ledger = make_service(FakeUsage(UsageSnapshotStaleError()), sink)

    result = service.admit(
        "run-1", "explore", envelope(ceiling="1"), reservation_cny=Decimal("2")
    )

    assert result.decision.kind.value == "budget_ceiling_exceeded"
    assert [event.budget_decision for event in sink.events] == [
        "budget_ceiling_exceeded",
        "budget_ceiling_exceeded",
    ]
    assert ledger.active_total == Decimal("0")


def test_snapshot_and_pause_do_not_overload_reserved_amount() -> None:
    sink = MemorySink()
    service, ledger = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope(), reservation_cny=Decimal("2"))
    assert admitted.reservation is not None

    snapshot_event, reserved_event = sink.events
    assert snapshot_event.reserved_cny is None
    assert snapshot_event.active_reservations_cny == Decimal("0")
    assert snapshot_event.requested_reservation_cny == Decimal("2")
    assert reserved_event.reserved_cny == Decimal("2")
    assert reserved_event.requested_reservation_cny == Decimal("2")
    assert reserved_event.active_reservations_cny == Decimal("0")
    ledger.release(admitted.reservation.id)


def test_release_and_reconcile_require_truthful_context() -> None:
    sink = MemorySink()
    service, _ = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope())
    assert admitted.reservation is not None

    with pytest.raises(TypeError):
        service.release(admitted.reservation.id)
    with pytest.raises(TypeError):
        service.reconcile(admitted.reservation.id, Decimal("1"))
    with pytest.raises(TypeError):
        service.release(admitted.reservation.id, intent="explore", requested_tier="flash")
    with pytest.raises(TypeError):
        service.reconcile(
            admitted.reservation.id,
            Decimal("1"),
            intent="explore",
            requested_tier="flash",
        )
    with pytest.raises(BudgetAdmissionError, match="pricing version"):
        service.release(
            admitted.reservation.id,
            intent="explore",
            requested_tier="flash",
            pricing_version="",
        )


@pytest.mark.parametrize(
    ("intent", "requested_tier", "pricing_version"),
    [
        ("audit", "flash", PRICING),
        ("explore", "pro", PRICING),
        ("explore", "flash", "other-pricing"),
    ],
)
def test_first_terminal_call_must_match_successful_admission_context(
    intent: str, requested_tier: str, pricing_version: str
) -> None:
    sink = MemorySink()
    service, ledger = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope())
    assert admitted.reservation is not None

    with pytest.raises(BudgetAdmissionError, match="context"):
        service.release(
            admitted.reservation.id,
            intent=intent,
            requested_tier=requested_tier,
            pricing_version=pricing_version,
        )

    assert ledger.lookup(admitted.reservation.id).state.value == "active"
    assert not [event for event in sink.events if event.event is RunEventType.BUDGET_RELEASED]


def test_failed_terminal_delivery_retains_admission_context_for_retry() -> None:
    sink = FailingSink(fail_on=3)
    service, ledger = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope())
    assert admitted.reservation is not None

    with pytest.raises(BudgetEventWriteError):
        service.release(
            admitted.reservation.id,
            intent="explore",
            requested_tier="flash",
            pricing_version=PRICING,
        )

    with pytest.raises(BudgetAdmissionError, match="context"):
        service.release(
            admitted.reservation.id,
            intent="audit",
            requested_tier="flash",
            pricing_version=PRICING,
        )
    assert ledger.lookup(admitted.reservation.id).state.value == "released"

    service.release(
        admitted.reservation.id,
        intent="explore",
        requested_tier="flash",
        pricing_version=PRICING,
    )


def test_terminal_event_failure_is_retried_once_on_replay() -> None:
    sink = FailingSink(fail_on=3)
    service, ledger = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope())
    assert admitted.reservation is not None

    with pytest.raises(BudgetEventWriteError):
        service.release(
            admitted.reservation.id, intent="explore", requested_tier="flash",
            pricing_version=PRICING,
        )
    assert ledger.lookup(admitted.reservation.id).state.value == "released"

    service.release(
        admitted.reservation.id, intent="explore", requested_tier="flash",
        pricing_version=PRICING,
    )
    service.release(
        admitted.reservation.id, intent="explore", requested_tier="flash",
        pricing_version=PRICING,
    )
    terminal = [event for event in sink.events if event.event is RunEventType.BUDGET_RELEASED]
    assert len(terminal) == 1
    assert terminal[0].budget_decision is None


def test_concurrent_terminal_replay_delivers_once() -> None:
    sink = FailingSink(fail_on=99)
    service, _ = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope())
    assert admitted.reservation is not None

    from threading import Barrier, Thread

    barrier = Barrier(8)
    failures: list[BaseException] = []

    def release() -> None:
        try:
            barrier.wait()
            service.release(
                admitted.reservation.id, intent="explore", requested_tier="flash",
                pricing_version=PRICING,
            )
        except BaseException as error:  # pragma: no cover - diagnostic only
            failures.append(error)

    threads = [Thread(target=release) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert len([event for event in sink.events if event.event is RunEventType.BUDGET_RELEASED]) == 1


def test_delivered_terminal_facts_reject_conflicting_context() -> None:
    sink = MemorySink()
    service, _ = make_service(FakeUsage(snapshot()), sink)
    admitted = service.admit("run-1", "explore", envelope())
    assert admitted.reservation is not None
    service.release(
        admitted.reservation.id, intent="explore", requested_tier="flash",
        pricing_version=PRICING,
    )

    with pytest.raises(BudgetAdmissionError, match="context"):
        service.release(
            admitted.reservation.id, intent="audit", requested_tier="pro",
            pricing_version=PRICING,
        )
    with pytest.raises(BudgetAdmissionError, match="context"):
        service.release(
            admitted.reservation.id, intent="explore", requested_tier="flash",
            pricing_version="other-pricing",
        )


def test_service_rejects_split_ledger_wiring() -> None:
    ledger_a = SingleFlightBudgetLedger(clock=lambda: NOW)
    ledger_b = SingleFlightBudgetLedger(clock=lambda: NOW)
    with pytest.raises(ValueError, match="same instance"):
        BudgetAdmissionService(
            usage=FakeUsage(snapshot()),
            guard=BudgetGuard(ledger_a, now=NOW),
            ledger=ledger_b,
            event_sink=MemorySink(),
            clock=lambda: NOW,
        )


def test_jsonl_sink_persists_only_secret_free_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlRunEventSink(path)
    service, _ = make_service(FakeUsage(snapshot()), sink)
    service.admit("run-1", "explore", envelope())
    output = path.read_text(encoding="utf-8")
    assert SENTINEL not in output
