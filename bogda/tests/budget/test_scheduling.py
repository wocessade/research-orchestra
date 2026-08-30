from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from bogda.budget.scheduling import (
    PriceAwareScheduler,
    ScheduleDisposition,
)
from bogda.contracts import ModelTier, PricePreference, SchedulePolicy, TaskIntent
from bogda.budget.estimation import TokenWorkload
from bogda.budget.pricing import PricePeriod


BEIJING = ZoneInfo("Asia/Shanghai")


def workload() -> TokenWorkload:
    return TokenWorkload(
        expected_calls=1,
        cache_hit_input_tokens=0,
        cache_miss_input_tokens=1_000_000,
        output_tokens=1_000_000,
    )


def plan(**overrides: object):
    values: dict[str, object] = {
        "intent": TaskIntent.EXECUTE,
        "tier": ModelTier.FLASH,
        "workload": workload(),
        "runtime_minutes": 30,
        "policy": SchedulePolicy(),
        "now": datetime(2026, 8, 28, 8, 0, tzinfo=BEIJING),
    }
    values.update(overrides)
    return PriceAwareScheduler().plan(**values)


def test_off_peak_run_starts_now() -> None:
    result = plan()

    assert result.disposition is ScheduleDisposition.START_NOW
    assert result.reason == "already_off_peak"
    assert result.scheduled_start == datetime(2026, 8, 28, 8, 0, tzinfo=BEIJING)
    assert result.current_period is PricePeriod.OFF_PEAK
    assert result.scheduled_period is PricePeriod.OFF_PEAK
    assert result.estimated_savings == Decimal("0")
    assert result.deadline_forced is False


def test_weekday_peak_run_waits_until_noon_when_deadline_allows_it() -> None:
    result = plan(
        now=datetime(2026, 8, 28, 10, 0, tzinfo=BEIJING),
        policy=SchedulePolicy(
            deadline=datetime(2026, 8, 28, 13, 0, tzinfo=BEIJING)
        ),
    )

    assert result.disposition is ScheduleDisposition.WAIT_FOR_OFF_PEAK
    assert result.reason == "cheapest_before_deadline"
    assert result.scheduled_start == datetime(2026, 8, 28, 12, 0, tzinfo=BEIJING)
    assert result.current_period is PricePeriod.PEAK
    assert result.scheduled_period is PricePeriod.OFF_PEAK
    assert result.scheduled_start + timedelta(minutes=30) == datetime(
        2026, 8, 28, 12, 30, tzinfo=BEIJING
    )
    assert result.current_estimate.authorized_ceiling == Decimal("14.4")
    assert result.scheduled_estimate.authorized_ceiling == Decimal("7.2")
    assert result.estimated_savings == Decimal("7.2")


def test_weekday_thirteen_hundred_run_remains_off_peak() -> None:
    result = plan(now=datetime(2026, 8, 28, 13, 0, tzinfo=BEIJING))

    assert result.disposition is ScheduleDisposition.START_NOW
    assert result.scheduled_start == datetime(2026, 8, 28, 13, 0, tzinfo=BEIJING)
    assert result.scheduled_period is PricePeriod.OFF_PEAK


def test_weekday_afternoon_peak_run_waits_until_eighteen_hundred_boundary() -> None:
    result = plan(
        now=datetime(2026, 8, 28, 15, 0, tzinfo=BEIJING),
        policy=SchedulePolicy(
            deadline=datetime(2026, 8, 28, 19, 0, tzinfo=BEIJING)
        ),
    )

    assert result.disposition is ScheduleDisposition.WAIT_FOR_OFF_PEAK
    assert result.scheduled_start == datetime(2026, 8, 28, 18, 0, tzinfo=BEIJING)
    assert result.scheduled_period is PricePeriod.OFF_PEAK


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 8, 28, 19, 0, tzinfo=BEIJING),
        datetime(2026, 8, 29, 10, 0, tzinfo=BEIJING),
        datetime(2026, 8, 30, 10, 0, tzinfo=BEIJING),
    ],
)
def test_friday_evening_and_weekends_stay_off_peak(now: datetime) -> None:
    result = plan(now=now)

    assert result.disposition is ScheduleDisposition.START_NOW
    assert result.scheduled_start == now
    assert result.scheduled_period is PricePeriod.OFF_PEAK


def test_immediate_preference_starts_now_during_peak() -> None:
    result = plan(
        now=datetime(2026, 8, 28, 10, 0, tzinfo=BEIJING),
        policy=SchedulePolicy(price_preference=PricePreference.IMMEDIATE),
    )

    assert result.disposition is ScheduleDisposition.START_NOW
    assert result.reason == "immediate"
    assert result.scheduled_start == datetime(2026, 8, 28, 10, 0, tzinfo=BEIJING)
    assert result.scheduled_period is PricePeriod.PEAK
    assert result.deadline_forced is False


def test_future_earliest_start_is_respected() -> None:
    result = plan(
        now=datetime(2026, 8, 28, 10, 0, tzinfo=BEIJING),
        policy=SchedulePolicy(
            earliest_start=datetime(2026, 8, 28, 13, 0, tzinfo=BEIJING),
            deadline=datetime(2026, 8, 28, 14, 0, tzinfo=BEIJING),
        ),
    )

    assert result.scheduled_start == datetime(2026, 8, 28, 13, 0, tzinfo=BEIJING)
    assert result.scheduled_period is PricePeriod.OFF_PEAK


def test_deadline_that_cannot_fit_off_peak_run_starts_now_and_forces_deadline() -> None:
    result = plan(
        now=datetime(2026, 8, 28, 10, 0, tzinfo=BEIJING),
        runtime_minutes=60,
        policy=SchedulePolicy(
            deadline=datetime(2026, 8, 28, 12, 30, tzinfo=BEIJING)
        ),
    )

    assert result.disposition is ScheduleDisposition.START_NOW
    assert result.scheduled_start == datetime(2026, 8, 28, 10, 0, tzinfo=BEIJING)
    assert result.deadline_forced is True
    assert result.current_period is PricePeriod.PEAK
    assert result.scheduled_period is PricePeriod.PEAK


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"now": datetime(2026, 8, 28, 10, 0)}, "now must be timezone-aware"),
        ({"runtime_minutes": 0}, "runtime_minutes must be positive"),
        ({"runtime_minutes": -1}, "runtime_minutes must be positive"),
    ],
)
def test_scheduler_rejects_naive_now_and_non_positive_runtime(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        plan(**overrides)
