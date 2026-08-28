from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope


def envelope(**updates) -> RunBudgetEnvelope:
    values = {
        "expected_cost": "2.880000",
        "authorized_ceiling": "5.320000",
        "minimum_remaining": "10.000000",
        "requested_tier": "pro",
        "fallback_tier": "flash",
        "budget_source": "project",
        "pricing_version": "deepseek-cn-2026-08-28",
    }
    values.update(updates)
    return RunBudgetEnvelope(**values)


def test_budget_money_round_trips_as_decimal_strings() -> None:
    budget = envelope()
    payload = budget.model_dump(mode="json")
    assert budget.schema_version == 1
    assert budget.expected_cost == Decimal("2.880000")
    assert payload["expected_cost"] == "2.880000"
    assert payload["authorized_ceiling"] == "5.320000"
    assert budget.budget_source is BudgetSource.PROJECT


def test_budget_rejects_tight_ceiling_and_invalid_fallback() -> None:
    with pytest.raises(ValidationError, match="expected_cost cannot exceed"):
        envelope(expected_cost="6", authorized_ceiling="5")
    with pytest.raises(ValidationError, match="fallback_tier must be flash"):
        envelope(fallback_tier=ModelTier.PRO)


def test_budget_rejects_float_money_input() -> None:
    with pytest.raises(ValidationError, match="money values must not be floats"):
        envelope(expected_cost=2.88)


def test_budget_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        envelope(unexpected="rejected")
