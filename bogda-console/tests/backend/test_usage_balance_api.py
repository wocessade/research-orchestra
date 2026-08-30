from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from bogda_console.adapters.deepseek_balance import DeepSeekBalanceAdapter
from bogda_console.config import Settings
from bogda_console.contracts.ports import UsageBalanceUnavailable


@pytest.mark.asyncio
async def test_deepseek_balance_adapter_normalizes_cny_without_exposing_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "is_available": True,
                "balance_infos": [
                    {"currency": "USD", "total_balance": "1.00"},
                    {"currency": "CNY", "total_balance": "37.1250"},
                ],
            },
        )

    adapter = DeepSeekBalanceAdapter(
        api_key="secret-sentinel",
        transport=httpx.MockTransport(handler),
        now=lambda: datetime(2026, 8, 31, 0, 20, tzinfo=UTC),
    )

    snapshot = await adapter.get_balance()

    assert seen == {"authorization": "Bearer secret-sentinel"}
    assert snapshot.model_dump(mode="json", by_alias=True) == {
        "provider": "deepseek",
        "available": True,
        "totalBalance": "37.1250",
        "currency": "CNY",
        "observedAt": "2026-08-31T00:20:00Z",
        "sourceStatus": "up",
    }


@pytest.mark.asyncio
async def test_deepseek_balance_adapter_rejects_non_string_money() -> None:
    adapter = DeepSeekBalanceAdapter(
        api_key="secret-sentinel",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={
            "is_available": True,
            "balance_infos": [{"currency": "CNY", "total_balance": 37.125}],
        })),
    )

    with pytest.raises(UsageBalanceUnavailable, match="response is invalid"):
        await adapter.get_balance()


@pytest.mark.asyncio
async def test_mock_profile_exposes_balance_contract_without_external_call(client) -> None:
    response = await client.get("/api/v1/usage-balance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["provider"] == "deepseek"
    assert payload["data"]["currency"] == "CNY"
    assert payload["sources"]["usageBalance"]["sourceMode"] == "mock"


@pytest.mark.asyncio
async def test_real_readonly_balance_without_key_fails_closed_and_does_not_leak_config() -> None:
    from httpx import ASGITransport, AsyncClient

    from bogda_console.app import create_app

    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "real-readonly",
            "PREFECT_API_URL": "http://127.0.0.1:4200/api",
        }
    )
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/api/v1/usage-balance")

    assert response.status_code == 503
    serialized = json.dumps(response.json())
    assert "USAGE_BALANCE_UNAVAILABLE" in serialized
    assert "DEEPSEEK_API_KEY" not in serialized
