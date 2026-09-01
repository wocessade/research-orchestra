from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from bogda.artifacts.safe_log import SafeLogReader
from bogda.budget import (
    BudgetAdmissionService,
    BudgetGuard,
    SqliteBudgetLedger,
    UsageSnapshotV1,
    UsageSourceStatus,
)
from bogda.contracts import ModelTier, TaskIntent
from bogda.events.jsonl import RunEventSink
from bogda.model_runtime.recovery import (
    SqliteUsageUnknownStore,
    UsageUnknownRecoveryService,
)
from bogda_console.adapters.core_model_control import CoreUsageUnknownAdapter
from bogda_console.adapters.mock_power import MockPowerAdapter
from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter
from bogda_console.config import Settings
from bogda_console.services.queries import QueryService


NOW = datetime(2026, 8, 30, 5, 0, tzinfo=timezone.utc)
PRICING = "deepseek-cn-2026-08-28"


class MemorySink(RunEventSink):
    def append(self, event) -> None:
        return None


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


def recovery_for(tmp_path: Path) -> UsageUnknownRecoveryService:
    sink = MemorySink()
    ledger = SqliteBudgetLedger(tmp_path / "ledger.sqlite", clock=lambda: NOW)
    reservation = ledger.reserve(run_id="run-1", amount=Decimal("2"), expected_revision=0)
    budget = BudgetAdmissionService(
        usage=FakeUsage(),
        guard=BudgetGuard(ledger, now=NOW),
        ledger=ledger,
        event_sink=sink,
        clock=lambda: NOW,
    )
    store = SqliteUsageUnknownStore(
        tmp_path / "recovery.sqlite", clock=lambda: NOW, id_factory=lambda: "case-1"
    )
    recovery = UsageUnknownRecoveryService(
        store=store, budget=budget, event_sink=sink, clock=lambda: NOW
    )
    recovery.open_case(
        case_id="case-1",
        run_id="run-1",
        call_id="call-1",
        reservation_id=reservation.id,
        intent=TaskIntent.EXPLORE,
        requested_tier=ModelTier.FLASH,
        effective_tier=ModelTier.FLASH,
        pricing_version=PRICING,
    )
    return recovery


@pytest.mark.asyncio
async def test_core_adapter_lists_and_reconciles_without_same_call_retry(
    tmp_path: Path,
) -> None:
    adapter = CoreUsageUnknownAdapter(recovery_for(tmp_path))
    center = await adapter.decision_center()
    assert center.items[0].decision_id == "case-1"
    assert center.items[0].actions[0].action_id == "reconcile"

    updated = await adapter.resolve_decision(
        "case-1", "reconcile", 0, actual_cost_cny=Decimal("0.40")
    )
    assert updated.items[0].actions[0].action_id == "approve-retry"

    with pytest.raises(Exception):
        await adapter.resolve_decision(
            "case-1",
            "approve-retry",
            updated.items[0].revision,
            new_call_id="call-1",
        )


@pytest.mark.asyncio
async def test_query_service_reads_redacted_logs(tmp_path: Path, fixture_loader) -> None:
    attempt = tmp_path / "run-1" / "attempt-1"
    attempt.mkdir(parents=True)
    (attempt / "stdout.log").write_text(
        "ok\nAuthorization: Bearer secret-token\n", encoding="utf-8"
    )
    fixture = fixture_loader("normal-active")
    service = QueryService(
        settings=Settings.from_env({"BOGDA_ARTIFACT_ROOT": str(tmp_path)}),
        prefect=MockPrefectAdapter(fixture),
        results=MockRunResultAdapter(fixture),
        power=MockPowerAdapter(fixture),
        log_reader=SafeLogReader(tmp_path),
    )
    payload = (await service.run_logs("run-1", "stdout")).data
    assert payload is not None
    assert payload.exists is True
    assert "secret-token" not in payload.content
    assert "[REDACTED]" in payload.content
