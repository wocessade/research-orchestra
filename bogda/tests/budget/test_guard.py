from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bogda.budget.guard import BudgetDecisionKind, BudgetGuard
from bogda.budget.ledger import SingleFlightBudgetLedger
from bogda.budget.usage import UsageSnapshotV1, UsageSourceStatus
from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope


NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)
PRICING = "deepseek-cn-2026-08-28"


def snapshot(
    *,
    balance: str = "10.000000000000000001",
    observed_at: datetime = NOW - timedelta(seconds=30),
    available: bool = True,
    source_status: UsageSourceStatus = UsageSourceStatus.UP,
) -> UsageSnapshotV1:
    return UsageSnapshotV1(
        provider="deepseek",
        available=available,
        total_balance=Decimal(balance),
        currency="CNY",
        observed_at=observed_at,
        source_status=source_status,
    )


def envelope(
    *,
    ceiling: str = "5",
    minimum: str = "1",
    pricing_version: str = PRICING,
) -> RunBudgetEnvelope:
    return RunBudgetEnvelope(
        expected_cost=Decimal("1"),
        authorized_ceiling=Decimal(ceiling),
        minimum_remaining=Decimal(minimum),
        requested_tier=ModelTier.FLASH,
        fallback_tier=None,
        budget_source=BudgetSource.RUN,
        pricing_version=pricing_version,
    )


def make_guard() -> tuple[BudgetGuard, SingleFlightBudgetLedger]:
    ledger = SingleFlightBudgetLedger(clock=lambda: NOW)
    return BudgetGuard(ledger=ledger, now=NOW), ledger


def test_fresh_sufficient_balance_allows_without_mutating_ledger() -> None:
    guard, ledger = make_guard()
    decision = guard.evaluate(
        snapshot=snapshot(), envelope=envelope(), reservation_cny=Decimal("3")
    )

    assert decision.allowed is True
    assert decision.kind is BudgetDecisionKind.ALLOW
    assert decision.reason == "budget_admitted"
    assert decision.balance == Decimal("10.000000000000000001")
    assert decision.active_reservations == Decimal("0")
    assert decision.available_to_start == Decimal("9.000000000000000001")
    assert decision.requested_reservation == Decimal("3")
    assert decision.snapshot_age == 30
    assert decision.ledger_revision == 0
    assert decision.pricing_version == PRICING
    assert ledger.revision == 0
    assert ledger.active_total == Decimal("0")

    with pytest.raises((AttributeError, TypeError)):
        decision.allowed = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("provided", "kind"),
    [
        (None, BudgetDecisionKind.USAGE_UNAVAILABLE),
        (
            snapshot(source_status=UsageSourceStatus.UNAVAILABLE),
            BudgetDecisionKind.USAGE_UNAVAILABLE,
        ),
        (snapshot(available=False), BudgetDecisionKind.USAGE_UNAVAILABLE),
        (
            snapshot(observed_at=NOW - timedelta(seconds=121)),
            BudgetDecisionKind.STALE_USAGE_SNAPSHOT,
        ),
    ],
)
def test_unavailable_wrong_state_and_stale_snapshots_deny(
    provided: UsageSnapshotV1 | None, kind: BudgetDecisionKind
) -> None:
    guard, _ = make_guard()
    decision = guard.evaluate(
        snapshot=provided, envelope=envelope(), reservation_cny=Decimal("1")
    )
    assert decision.allowed is False
    assert decision.kind is kind


def test_minimum_remaining_and_active_reservations_reduce_available_balance() -> None:
    guard, ledger = make_guard()
    existing = ledger.reserve(
        run_id="existing", amount=Decimal("4"), expected_revision=0
    )

    decision = guard.evaluate(
        snapshot=snapshot(balance="10"),
        envelope=envelope(minimum="2"),
        reservation_cny=Decimal("4"),
    )
    assert decision.kind is BudgetDecisionKind.ALLOW
    assert decision.available_to_start == Decimal("4")
    assert ledger.lookup(existing.id).state.value == "active"

    denied = guard.evaluate(
        snapshot=snapshot(balance="10"),
        envelope=envelope(minimum="2"),
        reservation_cny=Decimal("4.000000000000000001"),
    )
    assert denied.kind is BudgetDecisionKind.INSUFFICIENT_BALANCE


def test_exact_available_balance_is_allowed() -> None:
    guard, _ = make_guard()
    decision = guard.evaluate(
        snapshot=snapshot(balance="10"),
        envelope=envelope(ceiling="8", minimum="2"),
        reservation_cny=Decimal("8"),
    )
    assert decision.kind is BudgetDecisionKind.ALLOW
    assert decision.available_to_start == decision.requested_reservation


@pytest.mark.parametrize(
    ("reservation", "ceiling", "kind"),
    [
        (Decimal("5.01"), "5", BudgetDecisionKind.BUDGET_CEILING_EXCEEDED),
        (Decimal("0"), "5", BudgetDecisionKind.INVALID_PRICING),
        (Decimal("-1"), "5", BudgetDecisionKind.INVALID_PRICING),
        (1.0, "5", BudgetDecisionKind.INVALID_PRICING),
    ],
)
def test_reservation_must_be_positive_decimal_and_within_frozen_ceiling(
    reservation: object, ceiling: str, kind: BudgetDecisionKind
) -> None:
    guard, _ = make_guard()
    decision = guard.evaluate(
        snapshot=snapshot(),
        envelope=envelope(ceiling=ceiling),
        reservation_cny=reservation,
    )
    assert decision.allowed is False
    assert decision.kind is kind


def test_wrong_pricing_version_denies_without_touching_ledger() -> None:
    guard, ledger = make_guard()
    decision = guard.evaluate(
        snapshot=snapshot(),
        envelope=envelope(pricing_version="unaccepted"),
        reservation_cny=Decimal("1"),
    )
    assert decision.kind is BudgetDecisionKind.INVALID_PRICING
    assert decision.ledger_revision == 0
    assert ledger.active_total == Decimal("0")


def test_pricing_version_configuration_is_immutable_and_not_a_string() -> None:
    guard, _ = make_guard()
    assert guard.accepted_pricing_versions == frozenset({PRICING})
    with pytest.raises(AttributeError):
        guard.accepted_pricing_versions.add("other")  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        BudgetGuard(SingleFlightBudgetLedger(), accepted_pricing_versions=PRICING)


def test_insufficient_balance_is_explainable() -> None:
    guard, _ = make_guard()
    decision = guard.evaluate(
        snapshot=snapshot(balance="2"),
        envelope=envelope(minimum="1"),
        reservation_cny=Decimal("1.000000000000000001"),
    )
    assert decision.kind is BudgetDecisionKind.INSUFFICIENT_BALANCE
    assert decision.reason == "insufficient_available_balance"
    assert decision.balance == Decimal("2")
    assert decision.minimum_remaining == Decimal("1")
    assert decision.available_to_start == Decimal("1")
