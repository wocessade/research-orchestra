from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from bogda_console.contracts.models import UsageBalanceSnapshot
from bogda_console.contracts.ports import UsageBalanceUnavailable


class DeepSeekBalanceAdapter:
    """Read-only adapter for DeepSeek's official account balance endpoint."""

    source_mode = "real"

    def __init__(
        self,
        api_key: str | None,
        *,
        api_base: str = "https://api.deepseek.com",
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._url = f"{api_base.rstrip('/')}/user/balance"
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._now = now or (lambda: datetime.now(UTC))

    async def get_balance(self) -> UsageBalanceSnapshot:
        if self._api_key is None:
            raise UsageBalanceUnavailable("DeepSeek balance source is not configured")
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.get(
                    self._url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                )
        except httpx.RequestError:
            raise UsageBalanceUnavailable("DeepSeek balance source is unreachable") from None
        if response.status_code in {401, 403}:
            raise UsageBalanceUnavailable("DeepSeek balance authentication failed")
        if not response.is_success:
            raise UsageBalanceUnavailable(
                f"DeepSeek balance source returned HTTP {response.status_code}"
            )
        try:
            payload: Any = response.json()
            if payload.get("is_available") is not True:
                raise ValueError
            cny = next(
                item
                for item in payload["balance_infos"]
                if item.get("currency") == "CNY"
            )
            raw_total = cny["total_balance"]
            if not isinstance(raw_total, str):
                raise ValueError
            total = Decimal(raw_total)
            if not total.is_finite() or total < 0:
                raise ValueError
        except (AttributeError, KeyError, StopIteration, TypeError, ValueError, InvalidOperation):
            raise UsageBalanceUnavailable("DeepSeek balance response is invalid") from None
        return UsageBalanceSnapshot(
            provider="deepseek",
            available=True,
            totalBalance=total,
            currency="CNY",
            observedAt=self._now(),
            sourceStatus="up",
        )


class MockUsageBalanceAdapter:
    source_mode = "mock"

    def __init__(
        self,
        *,
        now: Callable[[], datetime],
        total_balance: Decimal = Decimal("88.00"),
    ) -> None:
        self._now = now
        self._total_balance = total_balance

    async def get_balance(self) -> UsageBalanceSnapshot:
        return UsageBalanceSnapshot(
            provider="deepseek",
            available=True,
            totalBalance=self._total_balance,
            currency="CNY",
            observedAt=self._now(),
            sourceStatus="up",
        )
