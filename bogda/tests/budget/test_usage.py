from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from bogda.budget.usage import (
    UsageMonitorAuthenticationError,
    UsageMonitorBalanceUnavailableError,
    UsageMonitorClient,
    UsageMonitorCurrencyError,
    UsageMonitorHTTPError,
    UsageMonitorPayloadError,
    UsageMonitorSourceUnavailableError,
    UsageMonitorTimeoutError,
    UsageMonitorTransportError,
    UsageSnapshotFutureError,
    UsageSnapshotStaleError,
    UsageSnapshotV1,
    UsageSourceStatus,
    require_fresh_snapshot,
    snapshot_age_seconds,
)


NOW = datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)
SENTINEL = "monitor-secret-sentinel"


def dashboard(
    *,
    total: object = "16.58",
    currency: object = "CNY",
    available: object = True,
    observed_at: object = NOW.timestamp(),
    source: object = "up",
) -> dict[str, object]:
    return {
        "balance": {
            "total": total,
            "currency": currency,
            "is_available": available,
            "ignored": "not normalized",
        },
        "last_updated": {"balance": observed_at, "usage": 1},
        "services": {"deepseek_api": source, "other": "ignored"},
        "unknown": {"must": "be ignored"},
    }


class FakeResponse:
    def __init__(self, status: int = 200, body: object | None = None) -> None:
        self.status = status
        body = body if body is not None else dashboard()
        if isinstance(body, bytes):
            self.body = body
        elif isinstance(body, str):
            self.body = body.encode()
        else:
            self.body = json.dumps(body).encode()


class FakeTransport:
    def __init__(self, response: object | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, str, dict[str, str], float]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
    ) -> object:
        self.calls.append((method, url, headers, timeout))
        if self.error is not None:
            raise self.error
        return self.response or FakeResponse()


def client(
    transport: FakeTransport,
    *,
    token: str | None = SENTINEL,
    clock=lambda: NOW,
) -> UsageMonitorClient:
    return UsageMonitorClient(
        "http://monitor.example/base/",
        monitor_token=token,
        timeout=7.5,
        transport=transport,
        clock=clock,
    )


def test_client_normalizes_only_supported_dashboard_fields_and_sends_contract_request() -> None:
    transport = FakeTransport(
        FakeResponse(
            body=dashboard(
                observed_at=NOW.timestamp(),
            )
        )
    )

    snapshot = client(transport).get_snapshot()

    assert snapshot.schema_version == 1
    assert snapshot.provider == "deepseek"
    assert snapshot.available is True
    assert snapshot.total_balance == Decimal("16.58")
    assert snapshot.currency == "CNY"
    assert snapshot.observed_at == NOW
    assert snapshot.observed_at.tzinfo == timezone.utc
    assert snapshot.source_status is UsageSourceStatus.UP
    assert transport.calls == [
        (
            "GET",
            "http://monitor.example/base/api/dashboard",
            {"X-Monitor-Token": SENTINEL},
            7.5,
        )
    ]


def test_snapshot_is_frozen_strict_and_serializes_decimal_as_string() -> None:
    snapshot = UsageSnapshotV1(
        provider="deepseek",
        available=True,
        total_balance="0.10",
        currency="CNY",
        observed_at=NOW,
        source_status="up",
    )

    assert snapshot.model_dump(mode="json")["total_balance"] == "0.10"
    with pytest.raises(ValidationError):
        snapshot.total_balance = Decimal("1")  # type: ignore[misc]
    with pytest.raises(ValidationError):
        UsageSnapshotV1(total_balance=1.5, observed_at=NOW, source_status="up")
    with pytest.raises(ValidationError):
        UsageSnapshotV1(total_balance=True, observed_at=NOW, source_status="up")
    with pytest.raises(ValidationError):
        UsageSnapshotV1(total_balance=1, observed_at=NOW, source_status="up")
    with pytest.raises(ValidationError):
        UsageSnapshotV1(
            schema_version=True,
            observed_at=NOW,
            source_status="up",
        )
    with pytest.raises(ValidationError):
        UsageSnapshotV1(
            observed_at=NOW,
            source_status="up",
            unexpected="reject",
        )


def test_token_is_omitted_when_not_configured() -> None:
    transport = FakeTransport(
        FakeResponse(body=dashboard(observed_at=NOW.timestamp()))
    )

    client(transport, token=None).get_snapshot()

    assert transport.calls[0][2] == {}


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, UsageMonitorAuthenticationError),
        (403, UsageMonitorAuthenticationError),
        (429, UsageMonitorHTTPError),
        (500, UsageMonitorHTTPError),
    ],
)
def test_http_failures_are_typed_and_secret_safe(status: int, exception: type[Exception]) -> None:
    transport = FakeTransport(FakeResponse(status=status, body={"secret": SENTINEL}))

    with pytest.raises(exception) as raised:
        client(transport).get_snapshot()

    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in repr(raised.value)


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timed out with " + SENTINEL), OSError("socket leaked " + SENTINEL)],
)
def test_transport_failures_are_typed_and_secret_safe(error: Exception) -> None:
    transport = FakeTransport(error=error)

    with pytest.raises((UsageMonitorTimeoutError, UsageMonitorTransportError)) as raised:
        client(transport).get_snapshot()

    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in repr(raised.value)


@pytest.mark.parametrize(
    "body",
    [b"not-json", [], {"balance": {}}],
)
def test_invalid_json_or_missing_payload_fields_fail_closed(body: object) -> None:
    transport = FakeTransport(FakeResponse(body=body))

    with pytest.raises(UsageMonitorPayloadError) as raised:
        client(transport).get_snapshot()

    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in repr(raised.value)


@pytest.mark.parametrize("total", [1, 1.0, True])
def test_dashboard_numeric_balance_is_not_coerced(total: object) -> None:
    transport = FakeTransport(
        FakeResponse(body=dashboard(total=total, observed_at=NOW.timestamp()))
    )

    with pytest.raises(UsageMonitorPayloadError):
        client(transport).get_snapshot()


def test_wrong_currency_and_unavailable_state_fail_closed() -> None:
    with pytest.raises(UsageMonitorCurrencyError):
        client(
            FakeTransport(
                FakeResponse(
                    body=dashboard(currency="USD", observed_at=NOW.timestamp())
                )
            )
        ).get_snapshot()
    with pytest.raises(UsageMonitorBalanceUnavailableError):
        client(
            FakeTransport(
                FakeResponse(
                    body=dashboard(available=False, observed_at=NOW.timestamp())
                )
            )
        ).get_snapshot()
    with pytest.raises(UsageMonitorSourceUnavailableError):
        client(
            FakeTransport(
                FakeResponse(
                    body=dashboard(source="unknown", observed_at=NOW.timestamp())
                )
            )
        ).get_snapshot()


def test_base_url_query_and_duplicate_endpoint_are_rejected() -> None:
    transport = FakeTransport()
    with pytest.raises(ValueError, match="query"):
        UsageMonitorClient("http://monitor.example/base?x=1", transport=transport)
    with pytest.raises(ValueError, match="dashboard"):
        UsageMonitorClient(
            "http://monitor.example/api/dashboard", transport=transport
        )


def test_invalid_epoch_fails_closed_without_local_timezone_dependency() -> None:
    for epoch in [True, "not-an-epoch", float("inf"), -1]:
        transport = FakeTransport(
            FakeResponse(body=dashboard(observed_at=epoch))
        )
        with pytest.raises(UsageMonitorPayloadError):
            client(transport).get_snapshot()


def snapshot_at(observed_at: datetime) -> UsageSnapshotV1:
    return UsageSnapshotV1(
        provider="deepseek",
        available=True,
        total_balance="1.00",
        currency="CNY",
        observed_at=observed_at,
        source_status=UsageSourceStatus.UP,
    )


def test_freshness_accepts_exactly_120_seconds_and_rejects_older() -> None:
    exact = snapshot_at(NOW - timedelta(seconds=120))
    assert snapshot_age_seconds(exact, now=NOW) == 120
    assert require_fresh_snapshot(exact, now=NOW) is exact

    old = snapshot_at(NOW - timedelta(seconds=120, microseconds=1))
    with pytest.raises(UsageSnapshotStaleError):
        require_fresh_snapshot(old, now=NOW)


def test_freshness_rejects_naive_now_and_materially_future_snapshot() -> None:
    snapshot = snapshot_at(NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        snapshot_age_seconds(snapshot, now=NOW.replace(tzinfo=None))

    tolerated = snapshot_at(NOW + timedelta(seconds=5))
    assert require_fresh_snapshot(tolerated, now=NOW) is tolerated

    future = snapshot_at(NOW + timedelta(seconds=6))
    with pytest.raises(UsageSnapshotFutureError):
        require_fresh_snapshot(future, now=NOW)


def test_snapshot_rejects_naive_observed_at() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        UsageSnapshotV1(
            provider="deepseek",
            available=True,
            total_balance="1.00",
            currency="CNY",
            observed_at=NOW.replace(tzinfo=None),
            source_status="up",
        )
