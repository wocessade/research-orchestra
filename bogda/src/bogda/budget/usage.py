from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
from math import isfinite
import socket
from typing import Callable, Literal, Mapping, NoReturn, Protocol, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


MAX_SNAPSHOT_FUTURE_TOLERANCE_SECONDS = 5
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 120


class UsageMonitorError(RuntimeError):
    """Base class for secret-safe, fail-closed monitor errors."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class UsageMonitorAuthenticationError(UsageMonitorError):
    def __init__(self, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__("usage monitor authentication failed")


class UsageMonitorHTTPError(UsageMonitorError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__("usage monitor returned a non-success HTTP status")


class UsageMonitorTimeoutError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage monitor request timed out")


class UsageMonitorTransportError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage monitor transport failed")


class UsageMonitorPayloadError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage monitor returned an invalid payload")


class UsageMonitorSourceUnavailableError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage monitor source is unavailable")


class UsageMonitorBalanceUnavailableError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage monitor balance is unavailable")


class UsageMonitorCurrencyError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage monitor returned an unsupported currency")


class UsageSnapshotStaleError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage snapshot is stale")


class UsageSnapshotFutureError(UsageMonitorError):
    def __init__(self) -> None:
        super().__init__("usage snapshot is materially in the future")


class UsageSourceStatus(StrEnum):
    UP = "up"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    INVALID = "invalid"


class UsageSnapshotV1(BaseModel):
    """Strict, immutable and provider-specific usage snapshot contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    provider: Literal["deepseek"]
    available: bool
    total_balance: Decimal
    currency: Literal["CNY"]
    observed_at: datetime
    source_status: UsageSourceStatus

    @field_validator("schema_version", mode="before")
    @classmethod
    def require_integer_schema_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @field_validator("available", mode="before")
    @classmethod
    def require_boolean_availability(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("available must be a boolean")
        return value

    @field_validator("total_balance", mode="before")
    @classmethod
    def parse_decimal_balance(cls, value: object) -> Decimal:
        if isinstance(value, bool) or isinstance(value, (int, float)):
            raise ValueError("total_balance must be a decimal string")
        if not isinstance(value, (str, Decimal)):
            raise ValueError("total_balance must be a decimal string")
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(value)
        except (InvalidOperation, ValueError):
            raise ValueError("total_balance must be a decimal string") from None
        if not parsed.is_finite() or parsed < 0:
            raise ValueError("total_balance must be a finite non-negative amount")
        return parsed

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value

    @field_serializer("total_balance")
    def serialize_decimal_balance(self, value: Decimal) -> str:
        return format(value, "f")


@runtime_checkable
class UsagePort(Protocol):
    def get_snapshot(self) -> UsageSnapshotV1:
        ...


@runtime_checkable
class UsageTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
    ) -> object:
        ...


@dataclass(frozen=True)
class UsageResponse:
    status: int
    body: bytes | str


class _UrllibTransport:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
    ) -> UsageResponse:
        request = Request(url, method=method, headers=dict(headers))
        try:
            with urlopen(request, timeout=timeout) as response:
                return UsageResponse(int(response.status), response.read())
        except HTTPError as exc:
            return UsageResponse(int(exc.code), b"")


def _dashboard_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("base_url must be a non-empty URL")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP URL")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not contain credentials")
    if parsed.query or "?" in base_url:
        raise ValueError("base_url must not contain a query")
    if parsed.fragment or "#" in base_url:
        raise ValueError("base_url must not contain a fragment")
    base_path = parsed.path.rstrip("/")
    if base_path.endswith("/api/dashboard"):
        raise ValueError("base_url must be the monitor base, not the dashboard endpoint")
    return f"{base_url.rstrip('/')}/api/dashboard"


def _require_aware_datetime(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _epoch_to_utc(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UsageMonitorPayloadError()
    if not isfinite(float(value)) or value < 0:
        raise UsageMonitorPayloadError()
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise UsageMonitorPayloadError() from None


def _mapping_field(payload: object, field: str) -> object:
    if not isinstance(payload, dict) or field not in payload:
        raise UsageMonitorPayloadError()
    return payload[field]


def _normalize_dashboard(payload: object) -> UsageSnapshotV1:
    if not isinstance(payload, dict):
        raise UsageMonitorPayloadError()
    balance = _mapping_field(payload, "balance")
    last_updated = _mapping_field(payload, "last_updated")
    services = _mapping_field(payload, "services")
    total = _mapping_field(balance, "total")
    currency = _mapping_field(balance, "currency")
    available = _mapping_field(balance, "is_available")
    epoch = _mapping_field(last_updated, "balance")
    source = _mapping_field(services, "deepseek_api")

    if currency != "CNY":
        raise UsageMonitorCurrencyError()
    if type(available) is not bool:
        raise UsageMonitorPayloadError()
    if not isinstance(source, str):
        raise UsageMonitorPayloadError()
    if source == "unauthorized" or source == "no_key":
        raise UsageMonitorAuthenticationError()
    if source != "up":
        if source.startswith("http_"):
            status_text = source.removeprefix("http_")
            if len(status_text) == 3 and status_text.isdigit():
                status_code = int(status_text)
                if 100 <= status_code <= 599:
                    if status_code in {401, 403}:
                        raise UsageMonitorAuthenticationError()
                    raise UsageMonitorSourceUnavailableError()
            raise UsageMonitorPayloadError()
        if source in {"unknown", "unavailable", "timeout", "error", "down"} or source.startswith("error_"):
            raise UsageMonitorSourceUnavailableError()
        raise UsageMonitorPayloadError()
    if not available:
        raise UsageMonitorBalanceUnavailableError()
    if not isinstance(total, (str, Decimal)) or isinstance(total, (bool, int, float)):
        raise UsageMonitorPayloadError()

    try:
        return UsageSnapshotV1(
            provider="deepseek",
            available=available,
            total_balance=total,
            observed_at=_epoch_to_utc(epoch),
            currency="CNY",
            source_status=UsageSourceStatus.UP,
        )
    except UsageMonitorError:
        raise
    except Exception:
        raise UsageMonitorPayloadError() from None


def _response_parts(response: object) -> tuple[int, bytes | str]:
    status = getattr(response, "status", getattr(response, "status_code", None))
    body = getattr(response, "body", None)
    if type(status) is not int or not isinstance(body, (bytes, str)):
        raise UsageMonitorTransportError()
    return status, body


def _raise_http_status(status_code: object) -> NoReturn:
    if type(status_code) is not int:
        raise UsageMonitorTransportError()
    if status_code in {401, 403}:
        raise UsageMonitorAuthenticationError(status_code)
    raise UsageMonitorHTTPError(status_code)


def _is_timeout_reason(reason: object) -> bool:
    return isinstance(reason, (TimeoutError, socket.timeout))


def _decode_payload(body: bytes | str) -> object:
    try:
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        raise UsageMonitorPayloadError() from None


def snapshot_age_seconds(snapshot: UsageSnapshotV1, *, now: datetime) -> int:
    """Return non-negative whole seconds, allowing only 5 seconds of clock skew."""

    now = _require_aware_datetime(now, "now")
    if not isinstance(snapshot, UsageSnapshotV1):
        raise ValueError("snapshot must be a UsageSnapshotV1")
    delta = now - snapshot.observed_at
    if delta < -timedelta(seconds=MAX_SNAPSHOT_FUTURE_TOLERANCE_SECONDS):
        raise UsageSnapshotFutureError()
    return max(0, int(delta.total_seconds()))


def require_fresh_snapshot(
    snapshot: UsageSnapshotV1,
    *,
    now: datetime,
    max_age_seconds: int = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
) -> UsageSnapshotV1:
    """Fail closed for snapshots older than 120 seconds or materially future-dated."""

    now = _require_aware_datetime(now, "now")
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int):
        raise ValueError("max_age_seconds must be a non-negative integer")
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be a non-negative integer")
    if not isinstance(snapshot, UsageSnapshotV1):
        raise ValueError("snapshot must be a UsageSnapshotV1")
    delta = now - snapshot.observed_at
    if delta < -timedelta(seconds=MAX_SNAPSHOT_FUTURE_TOLERANCE_SECONDS):
        raise UsageSnapshotFutureError()
    if delta > timedelta(seconds=max_age_seconds):
        raise UsageSnapshotStaleError()
    return snapshot


class UsageMonitorClient:
    """Read-only adapter for the monitor's GET /api/dashboard contract."""

    def __init__(
        self,
        base_url: str,
        *,
        monitor_token: str | None = None,
        timeout: float = 10.0,
        transport: UsageTransport | Callable[..., object] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if monitor_token is not None and not isinstance(monitor_token, str):
            raise ValueError("monitor_token must be a string or None")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not isfinite(float(timeout))
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite positive number")
        self._url = _dashboard_url(base_url)
        self._monitor_token = monitor_token
        self._timeout = float(timeout)
        self._transport = transport or _UrllibTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_snapshot(self) -> UsageSnapshotV1:
        headers: dict[str, str] = {}
        if self._monitor_token:
            headers["X-Monitor-Token"] = self._monitor_token
        try:
            if hasattr(self._transport, "request"):
                response = self._transport.request(  # type: ignore[union-attr]
                    "GET", self._url, headers=headers, timeout=self._timeout
                )
            else:
                response = self._transport(  # type: ignore[operator]
                    "GET", self._url, headers=headers, timeout=self._timeout
                )
        except (TimeoutError, socket.timeout):
            raise UsageMonitorTimeoutError() from None
        except HTTPError as exc:
            _raise_http_status(exc.code)
        except URLError as exc:
            if _is_timeout_reason(exc.reason):
                raise UsageMonitorTimeoutError() from None
            raise UsageMonitorTransportError() from None
        except OSError:
            raise UsageMonitorTransportError() from None
        except Exception:
            raise UsageMonitorTransportError() from None

        status, body = _response_parts(response)
        if status in {401, 403}:
            raise UsageMonitorAuthenticationError(status)
        if not 200 <= status < 300:
            raise UsageMonitorHTTPError(status)
        payload = _decode_payload(body)
        snapshot = _normalize_dashboard(payload)
        return require_fresh_snapshot(snapshot, now=self._clock())


__all__ = [
    "DEFAULT_MAX_SNAPSHOT_AGE_SECONDS",
    "MAX_SNAPSHOT_FUTURE_TOLERANCE_SECONDS",
    "UsageMonitorAuthenticationError",
    "UsageMonitorBalanceUnavailableError",
    "UsageMonitorClient",
    "UsageMonitorCurrencyError",
    "UsageMonitorError",
    "UsageMonitorHTTPError",
    "UsageMonitorPayloadError",
    "UsageMonitorSourceUnavailableError",
    "UsageMonitorTimeoutError",
    "UsageMonitorTransportError",
    "UsagePort",
    "UsageResponse",
    "UsageSnapshotFutureError",
    "UsageSnapshotStaleError",
    "UsageSnapshotV1",
    "UsageSourceStatus",
    "UsageTransport",
    "require_fresh_snapshot",
    "snapshot_age_seconds",
]
