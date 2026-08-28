from datetime import datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from bogda.contracts import (
    ExecutorKind,
    ModelTier,
    PricePreference,
    SchedulePolicy,
    TaskIntent,
)


def test_task_axes_have_stable_wire_values() -> None:
    assert [item.value for item in TaskIntent] == [
        "execute", "explore", "decide", "audit", "brief"
    ]
    assert [item.value for item in ModelTier] == ["auto", "flash", "pro"]
    assert [item.value for item in ExecutorKind] == ["dsh", "shell"]


def test_price_preference_has_stable_wire_values() -> None:
    assert [item.value for item in PricePreference] == [
        "immediate", "cheapest_before_deadline"
    ]


@pytest.mark.parametrize(
    "contract",
    [TaskIntent, ModelTier, ExecutorKind, PricePreference],
)
def test_task_contracts_reject_unknown_values_at_pydantic_boundary(contract) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(contract).validate_python("unknown")


def test_schedule_policy_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        SchedulePolicy(unexpected="value")


def test_schedule_policy_requires_aware_ordered_times() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        SchedulePolicy(earliest_start=datetime(2026, 8, 28, 18, 0))

    with pytest.raises(ValidationError, match="deadline must be after earliest_start"):
        SchedulePolicy(
            earliest_start="2026-08-28T20:00:00+08:00",
            deadline="2026-08-28T19:00:00+08:00",
        )


def test_schedule_defaults_to_cheapest_before_deadline() -> None:
    policy = SchedulePolicy()
    assert policy.price_preference is PricePreference.CHEAPEST_BEFORE_DEADLINE
