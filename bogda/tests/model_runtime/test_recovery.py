from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from bogda.budget import (
    BudgetAdmissionService,
    BudgetGuard,
    ReservationState,
    SqliteBudgetLedger,
    UsageSnapshotV1,
    UsageSourceStatus,
)
from bogda.contracts import ModelTier, RunEventType, TaskIntent
from bogda.events.jsonl import RunEventSink
from bogda.model_runtime.recovery import (
    SqliteUsageUnknownStore,
    UsageUnknownCase,
    UsageUnknownRecoveryService,
    UsageUnknownState,
)


NOW = datetime(2026, 8, 30, 5, 0, tzinfo=timezone.utc)
PRICING = "deepseek-cn-2026-08-28"


class MemorySink(RunEventSink):
    def __init__(self) -> None:
        self.events = []

    def append(self, event) -> None:
        self.events.append(event)


class FakeUsage:
    def get_snapshot(self) -> UsageSnapshotV1:
        return UsageSnapshotV1(
            provider="deepseek",
            available=True,
            total_balance=Decimal("10"),
            currency="CNY",
            observed_at=NOW - timedelta(seconds=30),
            source_status=UsageSourceStatus.UP,
        )


def runtime_for(tmp_path: Path):
    sink = MemorySink()
    ledger = SqliteBudgetLedger(
        tmp_path / "ledger.sqlite",
        clock=lambda: NOW,
        id_factory=lambda: "reservation-1",
    )
    reservation = ledger.reserve(
        run_id="run-1",
        amount=Decimal("2"),
        expected_revision=0,
    )
    budget = BudgetAdmissionService(
        usage=FakeUsage(),
        guard=BudgetGuard(ledger, now=NOW),
        ledger=ledger,
        event_sink=sink,
        clock=lambda: NOW,
    )
    store = SqliteUsageUnknownStore(
        tmp_path / "recovery.sqlite",
        clock=lambda: NOW,
        id_factory=lambda: "case-1",
    )
    recovery = UsageUnknownRecoveryService(
        store=store,
        budget=budget,
        event_sink=sink,
        clock=lambda: NOW,
    )
    case = recovery.open_case(
        case_id="case-1",
        run_id="run-1",
        call_id="call-1",
        reservation_id=reservation.id,
        intent=TaskIntent.EXPLORE,
        requested_tier=ModelTier.FLASH,
        effective_tier=ModelTier.FLASH,
        pricing_version=PRICING,
    )
    return recovery, store, ledger, sink, case


def test_open_case_survives_store_reopen(tmp_path: Path) -> None:
    recovery, store, ledger, _, case = runtime_for(tmp_path)

    store.close()
    reopened = SqliteUsageUnknownStore(tmp_path / "recovery.sqlite")

    assert reopened.get_case(case.case_id) == case
    assert reopened.get_case(case.case_id).state is UsageUnknownState.AWAITING_RECONCILIATION
    reopened.close()
    ledger.close()


def test_duplicate_open_is_idempotent_only_for_identical_context(tmp_path: Path) -> None:
    recovery, store, ledger, _, case = runtime_for(tmp_path)

    assert recovery.open_case(
        case_id=case.case_id,
        run_id=case.run_id,
        call_id=case.call_id,
        reservation_id=case.reservation_id,
        intent=case.intent,
        requested_tier=case.requested_tier,
        effective_tier=case.effective_tier,
        pricing_version=case.pricing_version,
    ) == case

    with pytest.raises(ValueError, match="case context conflicts"):
        recovery.open_case(
            case_id=case.case_id,
            run_id=case.run_id,
            call_id="different-call",
            reservation_id=case.reservation_id,
            intent=case.intent,
            requested_tier=case.requested_tier,
            effective_tier=case.effective_tier,
            pricing_version=case.pricing_version,
        )
    store.close()
    ledger.close()


def test_stale_revision_rejects_and_retry_or_terminate_wait_for_reconciliation(
    tmp_path: Path,
) -> None:
    recovery, store, ledger, _, case = runtime_for(tmp_path)

    with pytest.raises(ValueError, match="revision"):
        recovery.reconcile(case.case_id, Decimal("0.50"), expected_revision=9)
    with pytest.raises(ValueError, match="reconciliation"):
        recovery.approve_retry(
            case.case_id,
            new_call_id="call-2",
            expected_revision=case.revision,
        )
    with pytest.raises(ValueError, match="reconciliation"):
        recovery.terminate(case.case_id, expected_revision=case.revision)
    store.close()
    ledger.close()


@pytest.mark.parametrize("value", [None, 1, 0.5, "0.5", Decimal("NaN"), Decimal("Infinity"), Decimal("-0.1")])
def test_reconciliation_requires_finite_non_negative_decimal(
    tmp_path: Path, value: object
) -> None:
    recovery, store, ledger, _, case = runtime_for(tmp_path)

    with pytest.raises(ValueError, match="actual_cost_cny"):
        recovery.reconcile(case.case_id, value, expected_revision=case.revision)
    store.close()
    ledger.close()


def test_reconciliation_is_idempotent_and_emits_contract_valid_manual_event(
    tmp_path: Path,
) -> None:
    recovery, store, ledger, sink, case = runtime_for(tmp_path)

    reconciled = recovery.reconcile(
        case.case_id,
        Decimal("0.50"),
        expected_revision=case.revision,
    )
    repeated = recovery.reconcile(
        case.case_id,
        Decimal("0.50"),
        expected_revision=reconciled.revision,
    )

    assert repeated == reconciled
    assert reconciled.state is UsageUnknownState.AWAITING_RETRY_DECISION
    assert reconciled.actual_cost_cny == Decimal("0.50")
    assert ledger.lookup(case.reservation_id).state is ReservationState.RECONCILED
    finished = [event for event in sink.events if event.event is RunEventType.MODEL_CALL_FINISHED]
    assert len(finished) == 1
    assert finished[0].call_id == case.call_id
    assert finished[0].actual_cost_cny == Decimal("0.50")
    assert finished[0].usage_reference == "manual-reconciliation:case-1"
    assert finished[0].reason == "manual_usage_reconciliation"
    assert [event.event for event in sink.events] == [
        RunEventType.BUDGET_RELEASED,
        RunEventType.MODEL_CALL_FINISHED,
    ]

    with pytest.raises(ValueError, match="cost"):
        recovery.reconcile(
            case.case_id,
            Decimal("0.51"),
            expected_revision=reconciled.revision,
        )
    store.close()
    ledger.close()


def test_reconciled_case_allows_exactly_one_new_retry_call(tmp_path: Path) -> None:
    recovery, store, ledger, sink, case = runtime_for(tmp_path)
    reconciled = recovery.reconcile(
        case.case_id, Decimal("0.50"), expected_revision=case.revision
    )

    approved = recovery.approve_retry(
        case.case_id,
        new_call_id="call-2",
        expected_revision=reconciled.revision,
    )
    repeated = recovery.approve_retry(
        case.case_id,
        new_call_id="call-2",
        expected_revision=approved.revision,
    )

    assert approved.state is UsageUnknownState.RETRY_APPROVED
    assert approved.new_call_id == "call-2"
    assert approved.call_id == "call-1"
    assert repeated == approved
    resumed = [event for event in sink.events if event.event is RunEventType.BUDGET_RESUMED]
    assert len(resumed) == 1
    assert resumed[0].call_id == "call-2"
    assert resumed[0].call_id != case.call_id

    with pytest.raises(ValueError, match="new_call_id"):
        recovery.approve_retry(
            case.case_id,
            new_call_id=case.call_id,
            expected_revision=approved.revision,
        )
    store.close()
    ledger.close()


def test_terminate_requires_reconciliation_and_survives_reopen_without_release(
    tmp_path: Path,
) -> None:
    recovery, store, ledger, _, case = runtime_for(tmp_path)
    reconciled = recovery.reconcile(
        case.case_id, Decimal("0.50"), expected_revision=case.revision
    )

    terminated = recovery.terminate(
        case.case_id, expected_revision=reconciled.revision
    )
    store.close()
    ledger.close()

    reopened_store = SqliteUsageUnknownStore(tmp_path / "recovery.sqlite")
    loaded = reopened_store.get_case(case.case_id)
    reopened_ledger = SqliteBudgetLedger(tmp_path / "ledger.sqlite")

    assert terminated.state is UsageUnknownState.TERMINATED
    assert loaded == terminated
    assert reopened_ledger.lookup(case.reservation_id).state is ReservationState.RECONCILED
    reopened_store.close()
    reopened_ledger.close()


def test_case_is_immutable() -> None:
    assert UsageUnknownCase.__dataclass_params__.frozen is True


def test_list_open_cases_excludes_terminal_states(tmp_path: Path) -> None:
    recovery, store, ledger, _, case = runtime_for(tmp_path)
    assert [item.case_id for item in store.list_open_cases()] == [case.case_id]

    reconciled = recovery.reconcile(
        case.case_id, Decimal("0.50"), expected_revision=case.revision
    )
    assert [item.case_id for item in store.list_open_cases()] == [case.case_id]

    recovery.terminate(case.case_id, expected_revision=reconciled.revision)
    assert store.list_open_cases() == []
    ledger.close()
    store.close()
