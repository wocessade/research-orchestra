from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from zoneinfo import ZoneInfo

import pytest

from bogda.budget.estimation import (
    DEFAULT_CONTINGENCY_POLICY,
    HistoricalUsageProfile,
    TokenWorkload,
    WorkloadEstimate,
    WorkloadEstimator,
)
from bogda.budget.pricing import PricePeriod
from bogda.contracts import BudgetSource, ModelTier, TaskIntent


BEIJING = ZoneInfo("Asia/Shanghai")
AS_OF = datetime(2026, 8, 28, 8, 0, tzinfo=BEIJING)
OFF_PEAK_START = datetime(2026, 8, 28, 8, 0, tzinfo=BEIJING)
OFF_PEAK_END = datetime(2026, 8, 28, 8, 30, tzinfo=BEIJING)


def workload(**overrides: object) -> TokenWorkload:
    values: dict[str, object] = {
        "expected_calls": 1,
        "cache_hit_input_tokens": 0,
        "cache_miss_input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "allowed_retries": 0,
    }
    values.update(overrides)
    return TokenWorkload(**values)


def estimate(**overrides: object) -> WorkloadEstimate:
    values: dict[str, object] = {
        "intent": TaskIntent.EXECUTE,
        "tier": ModelTier.FLASH,
        "workload": workload(),
        "start": OFF_PEAK_START,
        "end": OFF_PEAK_END,
        "as_of": AS_OF,
    }
    values.update(overrides)
    return WorkloadEstimator().estimate(**values)


def test_total_tokens_are_priced_once_and_retries_use_average_call_cost() -> None:
    result = estimate(
        workload=workload(
            expected_calls=4,
            cache_miss_input_tokens=4_000_000,
            output_tokens=2_000_000,
            allowed_retries=2,
        )
    )

    assert result.expected_cost == Decimal("15")
    assert result.retry_reserve == Decimal("7.5")


def test_token_workload_requires_a_nonzero_baseline_even_with_retries() -> None:
    with pytest.raises(ValueError, match="baseline"):
        TokenWorkload(
            expected_calls=1,
            cache_hit_input_tokens=0,
            cache_miss_input_tokens=0,
            output_tokens=0,
            allowed_retries=1,
        )


def test_claimed_cache_hits_require_verified_evidence_and_are_floor_capped() -> None:
    no_history = estimate(
        workload=workload(cache_hit_input_tokens=3, cache_miss_input_tokens=0),
    )
    with_history = estimate(
        workload=workload(cache_hit_input_tokens=3, cache_miss_input_tokens=0),
        history=HistoricalUsageProfile(verified_cache_hit_ratio=Decimal("0.5")),
    )

    assert no_history.effective_cache_hit_input_tokens == 0
    assert no_history.effective_cache_miss_input_tokens == 3
    assert with_history.effective_cache_hit_input_tokens == 1
    assert with_history.effective_cache_miss_input_tokens == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expected_calls", True),
        ("expected_calls", 1.0),
        ("cache_miss_input_tokens", -1),
        ("allowed_retries", 1.0),
    ],
)
def test_workload_rejects_unsafe_counts(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        workload(**{field: value})


@pytest.mark.parametrize("value", [True, 1.0, "1.0"])
def test_money_and_ratios_reject_unsafe_numeric_coercion(value: object) -> None:
    with pytest.raises(ValueError):
        HistoricalUsageProfile(p90_cost=value)
    with pytest.raises(ValueError):
        HistoricalUsageProfile(verified_cache_hit_ratio=value)


def test_history_requires_ordered_costs_and_bounded_ratio() -> None:
    with pytest.raises(ValueError, match="p90"):
        HistoricalUsageProfile(p50_cost=Decimal("3"), p90_cost=Decimal("2"))
    with pytest.raises(ValueError):
        HistoricalUsageProfile(verified_cache_hit_ratio=Decimal("1.01"))


def test_auto_and_naive_runtime_are_rejected() -> None:
    with pytest.raises(ValueError, match="AUTO"):
        estimate(tier=ModelTier.AUTO)
    with pytest.raises(ValueError, match="timezone-aware"):
        estimate(start=datetime(2026, 8, 28, 8, 0))


@pytest.mark.parametrize(
    ("intent", "tier", "expected"),
    [
        (TaskIntent.EXECUTE, ModelTier.FLASH, Decimal("1.20")),
        (TaskIntent.BRIEF, ModelTier.FLASH, Decimal("1.15")),
        (TaskIntent.EXPLORE, ModelTier.PRO, Decimal("1.60")),
        (TaskIntent.DECIDE, ModelTier.PRO, Decimal("1.70")),
        (TaskIntent.AUDIT, ModelTier.PRO, Decimal("1.60")),
    ],
)
def test_default_contingency_policy_is_intent_and_tier_aware(
    intent: TaskIntent, tier: ModelTier, expected: Decimal
) -> None:
    result = estimate(intent=intent, tier=tier)
    assert result.contingency_factor == expected


def test_injected_policy_must_cover_exactly_all_concrete_pairs() -> None:
    incomplete = dict(DEFAULT_CONTINGENCY_POLICY)
    incomplete.pop((TaskIntent.EXECUTE, ModelTier.FLASH))
    with pytest.raises(ValueError, match="missing"):
        WorkloadEstimator(contingency_policy=incomplete)

    with pytest.raises(ValueError):
        WorkloadEstimator(
            contingency_policy={
                **dict(DEFAULT_CONTINGENCY_POLICY),
                (TaskIntent.EXECUTE, ModelTier.AUTO): Decimal("1.2"),
            }
        )
    with pytest.raises(ValueError):
        WorkloadEstimator(
            contingency_policy={
                **dict(DEFAULT_CONTINGENCY_POLICY),
                (TaskIntent.EXECUTE, ModelTier.FLASH): 1.2,
            }
        )


def test_contingency_factors_cannot_underfund_the_expected_cost() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        WorkloadEstimator(
            contingency_policy={
                **dict(DEFAULT_CONTINGENCY_POLICY),
                (TaskIntent.EXECUTE, ModelTier.FLASH): Decimal("0.5"),
            }
        )


def test_contingency_policy_is_immutable() -> None:
    assert isinstance(DEFAULT_CONTINGENCY_POLICY, MappingProxyType)
    with pytest.raises(TypeError):
        DEFAULT_CONTINGENCY_POLICY[(TaskIntent.EXECUTE, ModelTier.FLASH)] = Decimal(
            "2"
        )


def test_p90_raises_ceiling_before_retry_reserve_is_added() -> None:
    result = estimate(
        workload=workload(
            cache_miss_input_tokens=1_000_000,
            output_tokens=0,
            allowed_retries=1,
        ),
        history=HistoricalUsageProfile(p90_cost=Decimal("10")),
    )

    assert result.expected_cost == Decimal("1.5")
    assert result.retry_reserve == Decimal("1.5")
    assert result.authorized_ceiling == Decimal("11.5")
    assert result.historical_p90_cost == Decimal("10")


def test_manual_estimate_rejects_an_authorized_ceiling_below_expected_cost() -> None:
    with pytest.raises(ValueError, match="authorized_ceiling"):
        WorkloadEstimate(
            intent=TaskIntent.EXECUTE,
            tier=ModelTier.FLASH,
            workload=workload(),
            effective_cache_hit_input_tokens=0,
            effective_cache_miss_input_tokens=1_000_000,
            effective_output_tokens=1_000_000,
            expected_cost=Decimal("1.50"),
            retry_reserve=Decimal("0"),
            contingency_factor=Decimal("1"),
            historical_p90_cost=None,
            authorized_ceiling=Decimal("0.75"),
            period=PricePeriod.OFF_PEAK,
            pricing_version="test-pricing",
        )


def test_manual_estimate_rejects_contingency_factor_below_one() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        WorkloadEstimate(
            intent=TaskIntent.EXECUTE,
            tier=ModelTier.FLASH,
            workload=workload(),
            effective_cache_hit_input_tokens=0,
            effective_cache_miss_input_tokens=1_000_000,
            effective_output_tokens=1_000_000,
            expected_cost=Decimal("1.50"),
            retry_reserve=Decimal("0"),
            contingency_factor=Decimal("0.5"),
            historical_p90_cost=None,
            authorized_ceiling=Decimal("2.00"),
            period=PricePeriod.OFF_PEAK,
            pricing_version="test-pricing",
        )


def test_peak_crossing_window_uses_peak_without_time_charge() -> None:
    result = estimate(
        start=datetime(2026, 8, 28, 11, 30, tzinfo=BEIJING),
        end=datetime(2026, 8, 28, 20, 0, tzinfo=BEIJING),
    )

    assert result.period.value == "peak"
    assert result.expected_cost == Decimal("12")


def test_long_off_peak_window_does_not_add_direct_time_charge() -> None:
    start = datetime(2026, 8, 28, 19, 0, tzinfo=BEIJING)
    short = estimate(start=start, end=start + timedelta(minutes=1))
    long = estimate(start=start, end=start + timedelta(hours=5))
    assert long.expected_cost == short.expected_cost


def test_catalog_review_deadline_covers_entire_window() -> None:
    with pytest.raises(ValueError, match="review"):
        estimate(end=datetime(2026, 9, 28, 1, 0, tzinfo=BEIJING))


def test_estimate_exposes_effective_partition_and_catalog_metadata() -> None:
    result = estimate(
        workload=workload(
            cache_hit_input_tokens=3,
            cache_miss_input_tokens=7,
            output_tokens=11,
        ),
        history=HistoricalUsageProfile(verified_cache_hit_ratio=Decimal("0.5")),
    )

    assert result.effective_cache_hit_input_tokens == 3
    assert result.effective_cache_miss_input_tokens == 7
    assert result.effective_output_tokens == 11
    assert result.pricing_version == "deepseek-cn-2026-08-28"


def test_to_budget_envelope_preserves_calling_budget_controls() -> None:
    result = estimate(tier=ModelTier.PRO)
    envelope = WorkloadEstimator().to_budget_envelope(
        result,
        budget_source=BudgetSource.PROJECT,
        minimum_remaining=Decimal("20"),
        fallback_tier=ModelTier.FLASH,
    )

    assert envelope.requested_tier is ModelTier.PRO
    assert envelope.budget_source is BudgetSource.PROJECT
    assert envelope.minimum_remaining == Decimal("20")
    assert envelope.fallback_tier is ModelTier.FLASH
    assert envelope.expected_cost == result.expected_cost
    assert envelope.authorized_ceiling == result.authorized_ceiling
    assert envelope.pricing_version == result.pricing_version


def test_default_catalog_resolves_to_the_current_official_version() -> None:
    start = datetime(2026, 9, 14, 13, 0, tzinfo=BEIJING)
    result = estimate(start=start, end=start + timedelta(minutes=30), as_of=start)
    assert result.pricing_version == "deepseek-cn-2026-09-14"
