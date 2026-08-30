from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from bogda.budget.deepseek_balance import (
    DEFAULT_DEEPSEEK_BALANCE_URL,
    DeepSeekBalanceClient,
)
from bogda.budget.usage import (
    UsageMonitorAuthenticationError,
    UsageMonitorBalanceUnavailableError,
    UsageMonitorCurrencyError,
    UsageMonitorHTTPError,
    UsageMonitorPayloadError,
    UsageMonitorTimeoutError,
    UsageMonitorTransportError,
    UsageSourceStatus,
)


NOW = datetime(2026, 8, 30, 5, 30, tzinfo=timezone.utc)
SENTINEL = "deepseek-key-sentinel"
CONFORMANCE = json.loads(
    (Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "deepseek-balance-v1.json").read_text(
        encoding="utf-8"
    )
)["cases"]


def balance_payload(
    *,
    available: object = True,
    infos: object | None = None,
    currency: object = "CNY",
    total: object = "16.58",
    granted: object = "1.00",
    topped_up: object = "15.58",
) -> dict[str, object]:
    if infos is None:
        infos = [
            {
                "currency": currency,
                "total_balance": total,
                "granted_balance": granted,
                "topped_up_balance": topped_up,
            }
        ]
    return {"is_available": available, "balance_infos": infos}


class FakeResponse:
    def __init__(self, status: int = 200, body: object | None = None) -> None:
        self.status = status
        body = body if body is not None else balance_payload()
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
    api_key: str = SENTINEL,
    clock=lambda: NOW,
    base_url: str = "https://api.deepseek.com",
) -> DeepSeekBalanceClient:
    return DeepSeekBalanceClient(
        api_key,
        base_url=base_url,
        timeout=7.5,
        transport=transport,
        clock=clock,
    )


def test_client_reads_cny_total_and_sends_official_balance_request() -> None:
    transport = FakeTransport(FakeResponse(body=balance_payload()))

    snapshot = client(transport).get_snapshot()

    assert snapshot.schema_version == 1
    assert snapshot.provider == "deepseek"
    assert snapshot.available is True
    assert snapshot.total_balance == Decimal("16.58")
    assert snapshot.currency == "CNY"
    assert snapshot.observed_at == NOW
    assert snapshot.source_status is UsageSourceStatus.UP
    assert transport.calls == [
        (
            "GET",
            DEFAULT_DEEPSEEK_BALANCE_URL,
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {SENTINEL}",
            },
            7.5,
        )
    ]


@pytest.mark.parametrize("case", CONFORMANCE, ids=lambda case: case["id"])
def test_shared_balance_payload_conformance(case: dict[str, object]) -> None:
    operation = lambda: client(
        FakeTransport(FakeResponse(body=case["payload"]))
    ).get_snapshot()

    if case["valid"]:
        snapshot = operation()
        assert snapshot.total_balance == Decimal(str(case["totalBalance"]))
        assert snapshot.currency == "CNY"
    else:
        with pytest.raises(
            (
                UsageMonitorBalanceUnavailableError,
                UsageMonitorCurrencyError,
                UsageMonitorPayloadError,
            )
        ):
            operation()


def test_prefers_cny_when_usd_is_also_present() -> None:
    transport = FakeTransport(
        FakeResponse(
            body=balance_payload(
                infos=[
                    {
                        "currency": "USD",
                        "total_balance": "2.00",
                        "granted_balance": "0.00",
                        "topped_up_balance": "2.00",
                    },
                    {
                        "currency": "CNY",
                        "total_balance": "88.00",
                        "granted_balance": "0.00",
                        "topped_up_balance": "88.00",
                    },
                ]
            )
        )
    )

    snapshot = client(transport).get_snapshot()

    assert snapshot.total_balance == Decimal("88.00")
    assert snapshot.currency == "CNY"


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, UsageMonitorAuthenticationError),
        (403, UsageMonitorAuthenticationError),
        (429, UsageMonitorHTTPError),
        (500, UsageMonitorHTTPError),
    ],
)
def test_http_failures_are_typed_and_secret_safe(
    status: int, exception: type[Exception]
) -> None:
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


def test_urllib_timeout_reason_preserves_timeout_type_without_leaking_reason() -> None:
    transport = FakeTransport(error=URLError(TimeoutError(SENTINEL)))

    with pytest.raises(UsageMonitorTimeoutError) as raised:
        client(transport).get_snapshot()

    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in repr(raised.value)


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, UsageMonitorAuthenticationError),
        (403, UsageMonitorAuthenticationError),
        (429, UsageMonitorHTTPError),
        (500, UsageMonitorHTTPError),
    ],
)
def test_custom_http_error_is_mapped_by_status_without_reading_error_body(
    status: int, exception: type[Exception]
) -> None:
    transport = FakeTransport(
        error=HTTPError(
            DEFAULT_DEEPSEEK_BALANCE_URL,
            status,
            SENTINEL,
            hdrs=None,
            fp=io.BytesIO(SENTINEL.encode()),
        )
    )

    with pytest.raises(exception) as raised:
        client(transport).get_snapshot()

    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in repr(raised.value)


@pytest.mark.parametrize(
    "body",
    [b"not-json", [], {"is_available": True}, {"balance_infos": []}],
)
def test_invalid_json_or_missing_payload_fields_fail_closed(body: object) -> None:
    with pytest.raises(UsageMonitorPayloadError) as raised:
        client(FakeTransport(FakeResponse(body=body))).get_snapshot()

    assert SENTINEL not in str(raised.value)


@pytest.mark.parametrize("total", [1, 1.0, True])
def test_numeric_balance_is_not_coerced(total: object) -> None:
    with pytest.raises(UsageMonitorPayloadError):
        client(
            FakeTransport(FakeResponse(body=balance_payload(total=total)))
        ).get_snapshot()


def test_usd_only_and_unavailable_state_fail_closed() -> None:
    with pytest.raises(UsageMonitorCurrencyError):
        client(
            FakeTransport(FakeResponse(body=balance_payload(currency="USD")))
        ).get_snapshot()
    with pytest.raises(UsageMonitorBalanceUnavailableError):
        client(
            FakeTransport(FakeResponse(body=balance_payload(available=False)))
        ).get_snapshot()


def test_empty_api_key_is_rejected_before_any_request() -> None:
    transport = FakeTransport()
    with pytest.raises(ValueError, match="api_key"):
        DeepSeekBalanceClient("", transport=transport)
    with pytest.raises(ValueError, match="api_key"):
        DeepSeekBalanceClient("   ", transport=transport)
    assert transport.calls == []


def test_base_url_query_and_duplicate_endpoint_are_rejected() -> None:
    transport = FakeTransport()
    with pytest.raises(ValueError, match="query"):
        DeepSeekBalanceClient(SENTINEL, base_url="https://api.deepseek.com?x=1")
    with pytest.raises(ValueError, match="user/balance"):
        DeepSeekBalanceClient(SENTINEL, base_url=DEFAULT_DEEPSEEK_BALANCE_URL)
    assert transport.calls == []


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), float("-inf")])
def test_timeout_must_be_finite(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        DeepSeekBalanceClient(SENTINEL, timeout=timeout)
