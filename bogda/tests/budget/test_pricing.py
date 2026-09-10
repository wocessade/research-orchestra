from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from bogda.contracts import ModelTier
from bogda.budget.pricing import (
    CATALOGS,
    DEEPSEEK_CN_2026_08_28,
    DEEPSEEK_CN_2026_09_11,
    DEEPSEEK_CN_2026_09_14,
    PricePeriod,
    PricingCatalogV1,
    TokenPrices,
    catalog_registry,
    current_catalog,
    estimate_token_cost,
    next_off_peak_start,
    period_at,
    period_for_window,
    prices_for,
)


BEIJING = ZoneInfo("Asia/Shanghai")
AS_OF = datetime(2026, 8, 28, 12, 0, tzinfo=BEIJING)


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (datetime(2026, 8, 24, 8, 59, 59, tzinfo=BEIJING), PricePeriod.OFF_PEAK),
        (datetime(2026, 8, 24, 9, 0, tzinfo=BEIJING), PricePeriod.PEAK),
        (datetime(2026, 8, 24, 12, 0, tzinfo=BEIJING), PricePeriod.OFF_PEAK),
        (datetime(2026, 8, 24, 14, 0, tzinfo=BEIJING), PricePeriod.PEAK),
        (datetime(2026, 8, 24, 18, 0, tzinfo=BEIJING), PricePeriod.OFF_PEAK),
        (datetime(2026, 8, 28, 17, 59, 59, tzinfo=BEIJING), PricePeriod.PEAK),
        (datetime(2026, 8, 29, 10, 0, tzinfo=BEIJING), PricePeriod.OFF_PEAK),
        (datetime(2026, 8, 30, 10, 0, tzinfo=BEIJING), PricePeriod.OFF_PEAK),
        (
            datetime(2026, 8, 24, 1, 0, tzinfo=timezone.utc),
            PricePeriod.PEAK,
        ),
    ],
)
def test_period_at_uses_beijing_peak_boundaries(
    instant: datetime, expected: PricePeriod
) -> None:
    assert period_at(instant) is expected


def test_period_functions_require_aware_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        period_at(datetime(2026, 8, 24, 9, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        period_for_window(
            datetime(2026, 8, 24, 9, 0, tzinfo=BEIJING),
            datetime(2026, 8, 24, 10, 0),
        )


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (
            datetime(2026, 8, 28, 11, 59, tzinfo=BEIJING),
            datetime(2026, 8, 28, 12, 0, tzinfo=BEIJING),
            PricePeriod.PEAK,
        ),
        (
            datetime(2026, 8, 28, 12, 0, tzinfo=BEIJING),
            datetime(2026, 8, 28, 14, 0, tzinfo=BEIJING),
            PricePeriod.OFF_PEAK,
        ),
        (
            datetime(2026, 8, 28, 18, 0, tzinfo=BEIJING),
            datetime(2026, 8, 28, 19, 0, tzinfo=BEIJING),
            PricePeriod.OFF_PEAK,
        ),
        (
            datetime(2026, 8, 24, 1, 30, tzinfo=timezone.utc),
            datetime(2026, 8, 24, 3, 30, tzinfo=timezone.utc),
            PricePeriod.PEAK,
        ),
    ],
)
def test_period_for_window_conservatively_marks_any_peak_overlap(
    start: datetime, end: datetime, expected: PricePeriod
) -> None:
    assert period_for_window(start, end) is expected


def test_period_for_window_rejects_non_positive_intervals() -> None:
    start = datetime(2026, 8, 24, 12, 0, tzinfo=BEIJING)
    with pytest.raises(ValueError, match="positive"):
        period_for_window(start, start)
    with pytest.raises(ValueError, match="positive"):
        period_for_window(start + timedelta(hours=1), start)


def test_period_for_window_ignores_saturday_peak_hours() -> None:
    assert period_for_window(
        datetime(2026, 8, 29, 9, 0, tzinfo=BEIJING),
        datetime(2026, 8, 29, 10, 0, tzinfo=BEIJING),
    ) is PricePeriod.OFF_PEAK


def test_period_for_window_ignores_weekend_when_spanning_off_peak_boundaries() -> None:
    assert period_for_window(
        datetime(2026, 8, 28, 18, 0, tzinfo=BEIJING),
        datetime(2026, 8, 31, 9, 0, tzinfo=BEIJING),
    ) is PricePeriod.OFF_PEAK


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (
            datetime(2026, 8, 24, 9, 30, tzinfo=BEIJING),
            datetime(2026, 8, 24, 12, 0, tzinfo=BEIJING),
        ),
        (
            datetime(2026, 8, 24, 14, 0, tzinfo=BEIJING),
            datetime(2026, 8, 24, 18, 0, tzinfo=BEIJING),
        ),
        (
            datetime(2026, 8, 24, 17, 59, 59, tzinfo=BEIJING),
            datetime(2026, 8, 24, 18, 0, tzinfo=BEIJING),
        ),
        (
            datetime(2026, 8, 24, 8, 0, tzinfo=BEIJING),
            datetime(2026, 8, 24, 8, 0, tzinfo=BEIJING),
        ),
        (
            datetime(2026, 8, 24, 12, 30, tzinfo=BEIJING),
            datetime(2026, 8, 24, 12, 30, tzinfo=BEIJING),
        ),
        (
            datetime(2026, 8, 29, 10, 0, tzinfo=BEIJING),
            datetime(2026, 8, 29, 10, 0, tzinfo=BEIJING),
        ),
        (
            datetime(2026, 8, 24, 2, 30, tzinfo=timezone.utc),
            datetime(2026, 8, 24, 12, 0, tzinfo=BEIJING),
        ),
    ],
)
def test_next_off_peak_start_moves_to_the_next_boundary(
    instant: datetime, expected: datetime
) -> None:
    result = next_off_peak_start(instant)
    assert result == expected
    assert period_at(result) is PricePeriod.OFF_PEAK


def test_next_off_peak_start_requires_aware_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        next_off_peak_start(datetime(2026, 8, 24, 9, 0))


def test_catalog_contains_versioned_decimal_flash_and_pro_rows() -> None:
    catalog = DEEPSEEK_CN_2026_08_28
    assert catalog.schema_version == 1
    assert catalog.version == "deepseek-cn-2026-08-28"
    assert catalog.currency == "CNY"
    assert catalog.timezone == "Asia/Shanghai"
    assert catalog.effective_at.tzinfo is not None
    assert catalog.review_by.tzinfo is not None
    assert catalog.source

    expected = {
        (ModelTier.FLASH, PricePeriod.OFF_PEAK): ("0.05", "1.5", "4.5"),
        (ModelTier.FLASH, PricePeriod.PEAK): ("0.10", "3.0", "9.0"),
        (ModelTier.PRO, PricePeriod.OFF_PEAK): ("0.15", "4.5", "13.5"),
        (ModelTier.PRO, PricePeriod.PEAK): ("0.30", "9.0", "27.0"),
    }
    for (tier, period), values in expected.items():
        prices = prices_for(tier, period, as_of=AS_OF)
        assert (
            prices.cache_hit_input,
            prices.cache_miss_input,
            prices.output,
        ) == tuple(Decimal(value) for value in values)


def test_catalog_rejects_float_money_and_unknown_schema_data() -> None:
    with pytest.raises(ValidationError, match="money values must not be floats"):
        TokenPrices(cache_hit_input=0.05, cache_miss_input="1.5", output="4.5")

    values = DEEPSEEK_CN_2026_08_28.model_dump()
    values["schema_version"] = 2
    with pytest.raises(ValidationError):
        PricingCatalogV1(**values)
    values = DEEPSEEK_CN_2026_08_28.model_dump()
    values["unexpected"] = "reject"
    with pytest.raises(ValidationError):
        PricingCatalogV1(**values)


def test_price_lookup_rejects_auto_and_expired_or_pre_effective_catalog_use() -> None:
    with pytest.raises(ValueError, match="AUTO"):
        prices_for(ModelTier.AUTO, PricePeriod.OFF_PEAK, as_of=AS_OF)
    with pytest.raises(ValueError, match="review"):
        prices_for(
            ModelTier.FLASH,
            PricePeriod.OFF_PEAK,
            as_of=DEEPSEEK_CN_2026_08_28.review_by + timedelta(seconds=1),
            catalog=DEEPSEEK_CN_2026_08_28,
        )
    with pytest.raises(ValueError, match="effective"):
        prices_for(
            ModelTier.FLASH,
            PricePeriod.OFF_PEAK,
            as_of=DEEPSEEK_CN_2026_08_28.effective_at - timedelta(seconds=1),
            catalog=DEEPSEEK_CN_2026_08_28,
        )


def test_estimate_token_cost_uses_exact_decimal_million_token_math() -> None:
    cost = estimate_token_cost(
        ModelTier.FLASH,
        PricePeriod.OFF_PEAK,
        cache_hit_input_tokens=1_000_000,
        cache_miss_input_tokens=2_000_000,
        output_tokens=3_000_000,
        as_of=AS_OF,
    )
    assert cost == Decimal("16.55")
    assert isinstance(cost, Decimal)


def test_catalog_json_is_deterministic_and_serializes_money_as_strings() -> None:
    first = DEEPSEEK_CN_2026_08_28.model_dump_json()
    second = DEEPSEEK_CN_2026_08_28.model_dump_json()
    assert first == second
    payload = json.loads(first)
    assert payload["flash"]["off_peak"]["cache_hit_input"] == "0.05"
    assert payload["pro"]["peak"]["output"] == "27.0"


def _alt_catalog() -> PricingCatalogV1:
    values = DEEPSEEK_CN_2026_08_28.model_dump()
    values["version"] = "alt-catalog-test"
    values["flash"]["peak"]["cache_hit_input"] = "1.00"
    values["flash"]["peak"]["cache_miss_input"] = "30.0"
    values["flash"]["peak"]["output"] = "90.0"
    return PricingCatalogV1.model_validate(values)


def test_prices_for_and_estimate_use_supplied_catalog_not_the_default() -> None:
    alt = _alt_catalog()
    default_prices = prices_for(ModelTier.FLASH, PricePeriod.PEAK, as_of=AS_OF)
    pinned = prices_for(ModelTier.FLASH, PricePeriod.PEAK, as_of=AS_OF, catalog=alt)
    assert pinned.cache_miss_input == Decimal("30.0")
    assert default_prices.cache_miss_input == Decimal("3.0")
    default_cost = estimate_token_cost(
        ModelTier.FLASH,
        PricePeriod.PEAK,
        cache_hit_input_tokens=3,
        cache_miss_input_tokens=9,
        output_tokens=8,
        as_of=AS_OF,
    )
    pinned_cost = estimate_token_cost(
        ModelTier.FLASH,
        PricePeriod.PEAK,
        cache_hit_input_tokens=3,
        cache_miss_input_tokens=9,
        output_tokens=8,
        as_of=AS_OF,
        catalog=alt,
    )
    assert pinned_cost == Decimal("3") * Decimal("1.00") / Decimal("1000000") + Decimal("9") * Decimal("30.0") / Decimal("1000000") + Decimal("8") * Decimal("90.0") / Decimal("1000000")
    assert pinned_cost != default_cost


def test_official_2026_09_11_catalog_matches_deepseek_cn_page() -> None:
    catalog = DEEPSEEK_CN_2026_09_11
    assert catalog.version == "deepseek-cn-2026-09-11"
    expected = {
        (ModelTier.FLASH, PricePeriod.OFF_PEAK): ("0.02", "1", "4"),
        (ModelTier.FLASH, PricePeriod.PEAK): ("0.04", "2", "8"),
        (ModelTier.PRO, PricePeriod.OFF_PEAK): ("0.15", "4.5", "13.5"),
        (ModelTier.PRO, PricePeriod.PEAK): ("0.30", "9.0", "27.0"),
    }
    for (tier, period), values in expected.items():
        prices = prices_for(tier, period, as_of=catalog.effective_at, catalog=catalog)
        assert (
            prices.cache_hit_input,
            prices.cache_miss_input,
            prices.output,
        ) == tuple(Decimal(value) for value in values)


def test_official_2026_09_14_catalog_bills_pro_at_retired_flash_rates() -> None:
    catalog = DEEPSEEK_CN_2026_09_14
    assert catalog.effective_at > DEEPSEEK_CN_2026_09_11.effective_at
    for period in (PricePeriod.OFF_PEAK, PricePeriod.PEAK):
        pro = prices_for(ModelTier.PRO, period, as_of=catalog.effective_at, catalog=catalog)
        flash = prices_for(
            ModelTier.FLASH, period, as_of=catalog.effective_at, catalog=catalog
        )
        assert pro == flash


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (datetime(2026, 9, 10, 23, 59, 59, tzinfo=BEIJING), DEEPSEEK_CN_2026_08_28),
        (datetime(2026, 9, 11, 0, 0, tzinfo=BEIJING), DEEPSEEK_CN_2026_09_11),
        (datetime(2026, 9, 14, 11, 59, 59, tzinfo=BEIJING), DEEPSEEK_CN_2026_09_11),
        (datetime(2026, 9, 14, 12, 0, tzinfo=BEIJING), DEEPSEEK_CN_2026_09_14),
    ],
)
def test_current_catalog_switches_at_official_effective_moments(
    as_of: datetime, expected: PricingCatalogV1
) -> None:
    assert current_catalog(as_of) is expected


def test_current_catalog_fails_closed_outside_reviewed_windows() -> None:
    with pytest.raises(ValueError, match="no pricing catalog is effective yet"):
        current_catalog(DEEPSEEK_CN_2026_08_28.effective_at - timedelta(seconds=1))
    with pytest.raises(ValueError, match="review deadline has passed"):
        current_catalog(DEEPSEEK_CN_2026_09_14.review_by + timedelta(seconds=1))


def test_catalog_registry_indexes_every_catalog() -> None:
    registry = catalog_registry()
    assert set(registry) == {catalog.version for catalog in CATALOGS}
    assert registry["deepseek-cn-2026-09-14"] is DEEPSEEK_CN_2026_09_14


def test_default_price_lookup_follows_the_current_official_catalog() -> None:
    peak_morning = datetime(2026, 9, 11, 10, 0, tzinfo=BEIJING)
    prices = prices_for(ModelTier.FLASH, PricePeriod.PEAK, as_of=peak_morning)
    assert (prices.cache_hit_input, prices.cache_miss_input, prices.output) == (
        Decimal("0.04"),
        Decimal("2"),
        Decimal("8"),
    )
    after_retirement = datetime(2026, 9, 14, 13, 0, tzinfo=BEIJING)
    pro = prices_for(ModelTier.PRO, PricePeriod.OFF_PEAK, as_of=after_retirement)
    flash = prices_for(ModelTier.FLASH, PricePeriod.OFF_PEAK, as_of=after_retirement)
    assert pro == flash
