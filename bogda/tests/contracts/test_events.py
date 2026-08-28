from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda.contracts import RunEventType, RunEventV1


def event(**updates) -> RunEventV1:
    values = {
        "event": "budget_snapshot",
        "run_id": "run-123",
        "intent": "explore",
        "occurred_at": "2026-08-28T20:10:00+08:00",
    }
    values.update(updates)
    return RunEventV1(**values)


def test_tier_downgrade_event_round_trips_money_as_strings() -> None:
    event = RunEventV1(
        event="tier_downgraded",
        run_id="run-123",
        intent="explore",
        requested_tier="pro",
        effective_tier="flash",
        reason="insufficient_budget",
        balance_cny="13.42",
        reserved_cny="5.00",
        minimum_remaining_cny="10.00",
        snapshot_age_seconds=18,
        occurred_at="2026-08-28T20:10:00+08:00",
    )

    payload = event.model_dump(mode="json")

    assert event.balance_cny == Decimal("13.42")
    assert payload["balance_cny"] == "13.42"
    assert payload["reserved_cny"] == "5.00"
    assert payload["minimum_remaining_cny"] == "10.00"
    assert event.event is RunEventType.TIER_DOWNGRADED


def test_model_call_event_requires_call_id() -> None:
    with pytest.raises(ValidationError, match="call_id is required"):
        RunEventV1(
            event="model_call_started",
            run_id="run-123",
            occurred_at="2026-08-28T20:10:00+08:00",
        )

    with pytest.raises(ValidationError, match="call_id is required"):
        RunEventV1(
            event="model_call_finished",
            run_id="run-123",
            call_id="",
            occurred_at="2026-08-28T20:10:00+08:00",
        )


def test_model_call_start_and_finish_can_be_paired_by_call_id() -> None:
    started = event(event="model_call_started", call_id="call-123")
    finished = event(event="model_call_finished", call_id="call-123")

    assert started.call_id == finished.call_id == "call-123"


@pytest.mark.parametrize("event_name", ["route_selected", "tier_upgrade_requested", "tier_downgraded"])
def test_tier_route_and_change_events_require_both_tiers(event_name: str) -> None:
    with pytest.raises(ValidationError, match="requested_tier and effective_tier"):
        event(event=event_name, requested_tier="pro")

    with pytest.raises(ValidationError, match="requested_tier and effective_tier"):
        event(event=event_name, effective_tier="flash")


@pytest.mark.parametrize("schema_version", [True, "1", 1.0, 2])
def test_schema_version_is_strictly_v1(schema_version: object) -> None:
    with pytest.raises(ValidationError):
        event(schema_version=schema_version)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event", "unknown"),
        ("intent", "unknown"),
        ("requested_tier", "unknown"),
        ("effective_tier", "unknown"),
    ],
)
def test_event_rejects_unknown_axes(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        event(**{field: value})


def test_event_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        event(unexpected="rejected")


@pytest.mark.parametrize(
    "field",
    ["balance_cny", "reserved_cny", "minimum_remaining_cny"],
)
def test_event_rejects_float_money(field: str) -> None:
    with pytest.raises(ValidationError, match="money values must not be floats"):
        event(**{field: 1.25})


def test_event_requires_timezone_aware_occurred_at() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        event(occurred_at=datetime(2026, 8, 28, 20, 10))


def test_event_allows_only_references_for_prompt_and_usage_data() -> None:
    accepted = event(
        prompt_hash="sha256:abc123",
        prompt_artifact="artifact://prompt/123",
        usage_reference="artifact://usage/123",
    )

    assert accepted.prompt_hash == "sha256:abc123"
    assert accepted.prompt_artifact == "artifact://prompt/123"
    assert accepted.usage_reference == "artifact://usage/123"


@pytest.mark.parametrize(
    "secret_field",
    [
        "prompt",
        "response",
        "headers",
        "api_key",
        "authorization",
        "secret",
        "token",
    ],
)
def test_event_rejects_secret_bearing_fields(secret_field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        event(**{secret_field: "do-not-store"})
