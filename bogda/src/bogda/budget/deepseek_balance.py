"""Read-only DeepSeek official balance client.

GET https://api.deepseek.com/user/balance with Bearer API key.
Observed time is the local clock at a successful response; the provider
payload has no timestamp. Never log or include the API key in errors.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import socket

from bogda.budget.usage import (
    UsageMonitorAuthenticationError,
    UsageMonitorBalanceUnavailableError,
    UsageMonitorCurrencyError,
    UsageMonitorHTTPError,
    UsageMonitorPayloadError,
    UsageMonitorTimeoutError,
    UsageMonitorTransportError,
    UsageSnapshotV1,
    UsageSourceStatus,
    UsageTransport,
    _UrllibTransport,
    _decode_payload,
    _is_timeout_reason,
    _raise_http_status,
    _response_parts,
    require_fresh_snapshot,
)


DEFAULT_DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_BALANCE_URL = f"{DEFAULT_DEEPSEEK_API_BASE}/user/balance"


def _balance_url(base_url: str) -> str:
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
    if base_path.endswith("/user/balance"):
        raise ValueError("base_url must be the API base, not the user/balance endpoint")
    return f"{base_url.rstrip('/')}/user/balance"


def _cny_info(infos: object) -> dict[str, object]:
    if not isinstance(infos, list) or not infos:
        raise UsageMonitorPayloadError()
    cny: dict[str, object] | None = None
    saw_other_currency = False
    for item in infos:
        if not isinstance(item, dict):
            raise UsageMonitorPayloadError()
        currency = item.get("currency")
        if currency == "CNY":
            if cny is None:
                cny = item
            continue
        if isinstance(currency, str) and currency:
            saw_other_currency = True
            continue
        raise UsageMonitorPayloadError()
    if cny is not None:
        return cny
    if saw_other_currency:
        raise UsageMonitorCurrencyError()
    raise UsageMonitorPayloadError()


def _normalize_balance(payload: object, *, observed_at: datetime) -> UsageSnapshotV1:
    if not isinstance(payload, dict):
        raise UsageMonitorPayloadError()
    available = payload.get("is_available")
    if type(available) is not bool:
        raise UsageMonitorPayloadError()
    if not available:
        raise UsageMonitorBalanceUnavailableError()
    info = _cny_info(payload.get("balance_infos"))
    total = info.get("total_balance")
    if not isinstance(total, str):
        raise UsageMonitorPayloadError()
    try:
        return UsageSnapshotV1(
            provider="deepseek",
            available=True,
            total_balance=total,
            currency="CNY",
            observed_at=observed_at,
            source_status=UsageSourceStatus.UP,
        )
    except Exception:
        raise UsageMonitorPayloadError() from None


class DeepSeekBalanceClient:
    """Read-only adapter for GET /user/balance."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_DEEPSEEK_API_BASE,
        timeout: float = 10.0,
        transport: UsageTransport | Callable[..., object] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty string")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not isfinite(float(timeout))
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite positive number")
        self._api_key = api_key
        self._url = _balance_url(base_url)
        self._timeout = float(timeout)
        self._transport = transport or _UrllibTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_snapshot(self) -> UsageSnapshotV1:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
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
        snapshot = _normalize_balance(payload, observed_at=self._clock())
        return require_fresh_snapshot(snapshot, now=self._clock())


__all__ = [
    "DEFAULT_DEEPSEEK_API_BASE",
    "DEFAULT_DEEPSEEK_BALANCE_URL",
    "DeepSeekBalanceClient",
]
