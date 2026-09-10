from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bogda.budget.guard import BudgetDecision, BudgetDecisionKind, BudgetGuard
from bogda.budget.ledger import LedgerFacts, SingleFlightBudgetLedger
from bogda.budget.pricing import CATALOGS, DEEPSEEK_CN_2026_08_28, PricingCatalogV1
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


def make_guard(
    *, now: datetime = NOW, pricing_catalogs: tuple[PricingCatalogV1, ...] | None = None
) -> tuple[BudgetGuard, SingleFlightBudgetLedger]:
    ledger = SingleFlightBudgetLedger(clock=lambda: NOW)
    arguments: dict[str, object] = {"ledger": ledger, "now": now}
    if pricing_catalogs is not None:
        arguments["pricing_catalogs"] = pricing_catalogs
    return BudgetGuard(**arguments), ledger  # type: ignore[arg-type]


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


def test_active_reservation_conflicts_after_explainable_balance_calculation() -> None:
    guard, ledger = make_guard()
    existing = ledger.reserve(
        run_id="existing", amount=Decimal("4"), expected_revision=0
    )

    decision = guard.evaluate(
        snapshot=snapshot(balance="10"),
        envelope=envelope(minimum="2"),
        reservation_cny=Decimal("4"),
    )
    assert decision.kind is BudgetDecisionKind.RESERVATION_CONFLICT
    assert decision.allowed is False
    assert decision.available_to_start == Decimal("4")
    assert decision.ledger_revision == 1
    assert decision.active_reservations == Decimal("4")
    assert ledger.lookup(existing.id).state.value == "active"


def test_ceiling_breach_precedes_active_reservation_conflict() -> None:
    guard, ledger = make_guard()
    ledger.reserve(run_id="existing", amount=Decimal("1"), expected_revision=0)

    decision = guard.evaluate(
        snapshot=snapshot(balance="10"),
        envelope=envelope(ceiling="1", minimum="1"),
        reservation_cny=Decimal("2"),
    )

    assert decision.kind is BudgetDecisionKind.BUDGET_CEILING_EXCEEDED
    assert decision.allowed is False
    assert decision.active_reservations == Decimal("1")
    assert decision.available_to_start == Decimal("8")


def test_ceiling_breach_is_independent_of_missing_snapshot() -> None:
    guard, _ = make_guard()

    decision = guard.evaluate(
        snapshot=None,
        envelope=envelope(ceiling="1"),
        reservation_cny=Decimal("2"),
    )

    assert decision.kind is BudgetDecisionKind.BUDGET_CEILING_EXCEEDED
    assert decision.allowed is False
    assert decision.balance is None
    assert decision.snapshot_age is None
    assert decision.available_to_start is None


def test_in_ceiling_stale_snapshot_remains_stale() -> None:
    guard, _ = make_guard()

    decision = guard.evaluate(
        snapshot=snapshot(observed_at=NOW - timedelta(seconds=121)),
        envelope=envelope(ceiling="2"),
        reservation_cny=Decimal("2"),
    )

    assert decision.kind is BudgetDecisionKind.STALE_USAGE_SNAPSHOT


def test_exact_available_balance_is_allowed() -> None:
    guard, _ = make_guard()
    decision = guard.evaluate(
        snapshot=snapshot(balance="10"),
        envelope=envelope(ceiling="8", minimum="2"),
        reservation_cny=Decimal("8"),
    )
    assert decision.kind is BudgetDecisionKind.ALLOW
    assert decision.available_to_start == decision.requested_reservation


def test_automatic_approval_ceiling_allows_exactly_twenty_cny() -> None:
    guard, _ = make_guard()

    decision = guard.evaluate(
        snapshot=snapshot(balance="30"),
        envelope=envelope(ceiling="20", minimum="5"),
        reservation_cny=Decimal("20"),
    )

    assert decision.kind is BudgetDecisionKind.ALLOW


def test_over_twenty_cny_requires_owner_approval_before_provider_checks() -> None:
    guard, _ = make_guard()

    decision = guard.evaluate(
        snapshot=None,
        envelope=envelope(ceiling="20.01", minimum="5"),
        reservation_cny=Decimal("20.01"),
    )

    assert decision.allowed is False
    assert decision.kind is BudgetDecisionKind.OWNER_APPROVAL_REQUIRED
    assert decision.reason == "automatic_approval_ceiling_exceeded"
    assert decision.requested_reservation == Decimal("20.01")


def test_high_authorized_envelope_cannot_bypass_approval_with_small_reservation() -> None:
    guard, _ = make_guard()

    decision = guard.evaluate(
        snapshot=snapshot(balance="200"),
        envelope=envelope(ceiling="100", minimum="5"),
        reservation_cny=Decimal("1"),
    )

    assert decision.kind is BudgetDecisionKind.OWNER_APPROVAL_REQUIRED
    assert decision.requested_reservation == Decimal("1")


def test_automatic_approval_ceiling_can_only_be_tightened() -> None:
    ledger = SingleFlightBudgetLedger()
    guard = BudgetGuard(
        ledger,
        now=NOW,
        automatic_approval_ceiling_cny=Decimal("15"),
    )
    assert guard.automatic_approval_ceiling_cny == Decimal("15")

    with pytest.raises(ValueError, match="automatic_approval_ceiling_cny"):
        BudgetGuard(ledger, automatic_approval_ceiling_cny=Decimal("-1"))
    with pytest.raises(ValueError, match="automatic_approval_ceiling_cny"):
        BudgetGuard(ledger, automatic_approval_ceiling_cny=Decimal("20.01"))


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
    assert guard.accepted_pricing_versions == frozenset(
        catalog.version for catalog in CATALOGS
    )
    with pytest.raises(AttributeError):
        guard.accepted_pricing_versions.add("other")  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        BudgetGuard(SingleFlightBudgetLedger(), pricing_catalogs=(object(),))  # type: ignore[arg-type]


def test_guard_exposes_its_bound_ledger_read_only() -> None:
    guard, ledger = make_guard()
    assert guard.ledger is ledger


@pytest.mark.parametrize(
    ("allowed", "kind"),
    [
        (True, BudgetDecisionKind.INSUFFICIENT_BALANCE),
        (False, BudgetDecisionKind.ALLOW),
    ],
)
def test_budget_decision_requires_allowed_to_match_kind(
    allowed: bool, kind: BudgetDecisionKind
) -> None:
    with pytest.raises(ValueError, match="allowed"):
        BudgetDecision(
            allowed=allowed,
            kind=kind,
            reason="test",
            balance=Decimal("1"),
            active_reservations=Decimal("0"),
            minimum_remaining=Decimal("0"),
            available_to_start=Decimal("1"),
            requested_reservation=Decimal("1"),
            snapshot_age=1,
            ledger_revision=0,
            pricing_version=PRICING,
        )


class CoherentFactsOnlyLedger:
    @property
    def revision(self) -> int:
        raise AssertionError("guard must not read revision separately")

    @property
    def active_total(self) -> Decimal:
        raise AssertionError("guard must not read active_total separately")

    def facts(self) -> LedgerFacts:
        return LedgerFacts(revision=7, active_total=Decimal("0"))

    def lookup(self, reservation_id: str) -> object:
        raise AssertionError("guard must not look up reservations")

    def reserve(self, **kwargs: object) -> object:
        raise AssertionError("guard must not reserve")

    def release(self, reservation_id: str, **kwargs: object) -> object:
        raise AssertionError("guard must not release")

    def reconcile(self, reservation_id: str, actual_cost: Decimal, **kwargs: object) -> object:
        raise AssertionError("guard must not reconcile")


def test_guard_uses_one_coherent_ledger_facts_snapshot() -> None:
    guard = BudgetGuard(CoherentFactsOnlyLedger(), now=NOW)
    decision = guard.evaluate(
        snapshot=snapshot(balance="10"),
        envelope=envelope(minimum="1"),
        reservation_cny=Decimal("2"),
    )
    assert decision.kind is BudgetDecisionKind.ALLOW
    assert decision.ledger_revision == 7
    assert decision.active_reservations == Decimal("0")


def custom_catalog() -> PricingCatalogV1:
    return DEEPSEEK_CN_2026_08_28.model_copy(
        update={
            "version": "custom-pricing",
            "effective_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
            "review_by": datetime(2026, 10, 1, tzinfo=timezone.utc),
        }
    )


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc),
        datetime(2026, 10, 1, 0, 0, 1, tzinfo=timezone.utc),
    ],
)
def test_custom_catalog_is_invalid_outside_its_effective_review_window(
    now: datetime,
) -> None:
    catalog = custom_catalog()
    guard, _ = make_guard(now=now, pricing_catalogs=(catalog,))
    decision = guard.evaluate(
        snapshot=snapshot(observed_at=now - timedelta(seconds=30)),
        envelope=envelope(pricing_version=catalog.version),
        reservation_cny=Decimal("1"),
    )
    assert decision.kind is BudgetDecisionKind.INVALID_PRICING
    assert decision.allowed is False


def test_custom_catalog_is_valid_inside_its_effective_review_window() -> None:
    catalog = custom_catalog()
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    guard, _ = make_guard(now=now, pricing_catalogs=(catalog,))
    decision = guard.evaluate(
        snapshot=snapshot(observed_at=now - timedelta(seconds=30)),
        envelope=envelope(pricing_version=catalog.version),
        reservation_cny=Decimal("1"),
    )
    assert decision.kind is BudgetDecisionKind.ALLOW


def test_current_catalog_is_invalid_after_review_deadline() -> None:
    now = datetime(2026, 9, 28, 0, 0, 1, tzinfo=timezone.utc)
    guard, _ = make_guard(now=now)
    decision = guard.evaluate(
        snapshot=snapshot(observed_at=now - timedelta(seconds=30)),
        envelope=envelope(),
        reservation_cny=Decimal("1"),
    )
    assert decision.kind is BudgetDecisionKind.INVALID_PRICING


def test_pricing_catalog_metadata_rejects_duplicates_and_invalid_windows() -> None:
    catalog = custom_catalog()
    with pytest.raises(ValueError, match="duplicate"):
        BudgetGuard(
            SingleFlightBudgetLedger(), pricing_catalogs=(catalog, catalog)
        )
    invalid = catalog.model_copy(
        update={"effective_at": datetime(2026, 10, 2, tzinfo=timezone.utc)}
    )
    with pytest.raises(ValueError, match="effective_at"):
        BudgetGuard(SingleFlightBudgetLedger(), pricing_catalogs=(invalid,))

    invalid_version = catalog.model_copy(update={"version": ""})
    with pytest.raises(ValueError, match="version"):
        BudgetGuard(SingleFlightBudgetLedger(), pricing_catalogs=(invalid_version,))

    invalid_schema = catalog.model_copy(update={"schema_version": 2})
    with pytest.raises(ValueError, match="schema_version"):
        BudgetGuard(SingleFlightBudgetLedger(), pricing_catalogs=(invalid_schema,))


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
