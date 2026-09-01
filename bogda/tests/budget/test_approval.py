from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bogda.budget.approval import (
    ApprovalError,
    SqliteApprovalStore,
    envelope_digest,
)
from bogda.budget.guard import BudgetDecisionKind, BudgetGuard
from bogda.budget.ledger import SingleFlightBudgetLedger
from bogda.budget.service import BudgetAdmissionService
from bogda.budget.usage import UsageSnapshotV1, UsageSourceStatus
from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope, RunEventType, TaskIntent
from bogda.events.jsonl import RunEventSink


NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)
PRICING = "deepseek-cn-2026-08-28"
KEY = b"test-approval-hmac-key"


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
            total_balance=Decimal("200"),
            currency="CNY",
            observed_at=NOW - timedelta(seconds=30),
            source_status=UsageSourceStatus.UP,
        )


def envelope(*, ceiling: str = "25") -> RunBudgetEnvelope:
    return RunBudgetEnvelope(
        expected_cost=Decimal("21"),
        authorized_ceiling=Decimal(ceiling),
        minimum_remaining=Decimal("1"),
        requested_tier=ModelTier.FLASH,
        fallback_tier=None,
        budget_source=BudgetSource.RUN,
        pricing_version=PRICING,
    )


def test_forged_expired_wrong_run_and_replay_are_rejected(tmp_path) -> None:
    store = SqliteApprovalStore(tmp_path / "approval.sqlite", hmac_key=KEY, clock=lambda: NOW)
    env = envelope()
    credential = store.issue(
        run_id="run-1",
        envelope=env,
        actor_id="owner-1",
        ttl=timedelta(minutes=10),
    )

    forged = replace(credential, mac="00" * 32)
    with pytest.raises(ApprovalError, match="mac"):
        store.consume(forged, envelope=env, run_id="run-1")

    expired = store.issue(
        run_id="run-1",
        envelope=env,
        actor_id="owner-1",
        ttl=timedelta(seconds=0),
    )
    with pytest.raises(ApprovalError, match="expired"):
        store.consume(expired, envelope=env, run_id="run-1")

    with pytest.raises(ApprovalError, match="run_id"):
        store.consume(credential, envelope=env, run_id="run-other")

    store.consume(credential, envelope=env, run_id="run-1")
    with pytest.raises(ApprovalError, match="consumed"):
        store.consume(credential, envelope=env, run_id="run-1")


def test_valid_credential_admits_above_automatic_ceiling(tmp_path) -> None:
    store = SqliteApprovalStore(tmp_path / "approval.sqlite", hmac_key=KEY, clock=lambda: NOW)
    env = envelope()
    credential = store.issue(
        run_id="run-1",
        envelope=env,
        actor_id="owner-1",
        ttl=timedelta(minutes=10),
    )
    ledger = SingleFlightBudgetLedger(clock=lambda: NOW)
    sink = MemorySink()
    service = BudgetAdmissionService(
        usage=FakeUsage(),
        guard=BudgetGuard(ledger, now=NOW),
        ledger=ledger,
        event_sink=sink,
        clock=lambda: NOW,
        approvals=store,
    )

    denied = service.admit("run-1", TaskIntent.EXECUTE, env, reservation_cny=Decimal("21"))
    assert denied.decision.kind is BudgetDecisionKind.OWNER_APPROVAL_REQUIRED
    assert denied.reservation is None

    allowed = service.admit(
        "run-1",
        TaskIntent.EXECUTE,
        env,
        reservation_cny=Decimal("21"),
        approval=credential,
    )
    assert allowed.decision.allowed is True
    assert allowed.reservation is not None
    assert any(event.event is RunEventType.BUDGET_OVERRIDE_APPROVED for event in sink.events)

    replay = service.admit(
        "run-1",
        TaskIntent.EXECUTE,
        env,
        reservation_cny=Decimal("21"),
        approval=credential,
    )
    assert replay.decision.kind is BudgetDecisionKind.OWNER_APPROVAL_REQUIRED
    assert replay.reservation is None


def test_envelope_digest_changes_when_ceiling_changes() -> None:
    assert envelope_digest(envelope(ceiling="25")) != envelope_digest(envelope(ceiling="30"))
