from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from bogda.wiring.store_api import canonical_body, sign_request
from bogda_console.app import create_app
from bogda_console.config import Settings

KEY_HEX = "ab" * 32
ADMIT_PATH = "/api/v1/store/budget/admit"
RELEASE_PATH = "/api/v1/store/budget/release"
RECONCILE_PATH = "/api/v1/store/budget/reconcile"
BLOCKED_PATH = "/api/v1/store/usage-unknown/blocked"
CASES_PATH = "/api/v1/store/usage-unknown/cases"

ENVELOPE = {
    "expected_cost": "0.10",
    "authorized_ceiling": "1",
    "minimum_remaining": "0",
    "requested_tier": "flash",
    "fallback_tier": None,
    "budget_source": "run",
    "pricing_version": "deepseek-cn-2026-08-28",
}


def _settings(tmp_path, **overrides) -> Settings:
    env = {
        "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
        "PREFECT_API_URL": "http://127.0.0.1:4200/api",
        "BOGDA_APPROVAL_DB": str(tmp_path / "approvals.sqlite"),
        "BOGDA_APPROVAL_HMAC_KEY": KEY_HEX,
        "BOGDA_USAGE_UNKNOWN_DB": str(tmp_path / "usage-unknown.sqlite"),
        "BOGDA_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
    }
    env.update(overrides)
    return Settings.from_env(env)


def _headers(method: str, path: str, body: bytes, key_hex: str = KEY_HEX) -> dict:
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return {
        "X-Bogda-Timestamp": str(timestamp),
        "X-Bogda-Signature": sign_request(bytes.fromhex(key_hex), method, path, body, timestamp),
        "Content-Type": "application/json",
    }


async def _post(http: AsyncClient, path: str, payload: dict, key_hex: str = KEY_HEX):
    body = canonical_body(payload)
    return await http.post(path, content=body, headers=_headers("POST", path, body, key_hex))


async def _get(http: AsyncClient, path: str, params: dict, key_hex: str = KEY_HEX):
    return await http.get(path, params=params, headers=_headers("GET", path, b"", key_hex))


def _up_balance(app) -> None:
    async def fake_get_balance():
        return SimpleNamespace(
            provider="deepseek",
            total_balance=Decimal("100"),
            currency="CNY",
            observed_at=datetime.now(timezone.utc),
        )

    app.state.container.usage_balance.get_balance = fake_get_balance


@pytest.fixture()
async def http(tmp_path):
    app = create_app(_settings(tmp_path))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.app = app  # type: ignore[attr-defined]
        yield client


@pytest.mark.asyncio
async def test_admit_allows_small_envelope_and_reconciles(http) -> None:
    _up_balance(http.app)
    response = await _post(
        http,
        ADMIT_PATH,
        {"run_id": "run-1", "intent": "execute", "envelope": ENVELOPE},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["decision"]["allowed"] is True
    reservation = result["reservation"]
    assert reservation["state"] == "active"

    reconciled = await _post(
        http,
        RECONCILE_PATH,
        {
            "reservation_id": reservation["id"],
            "actual_cost_cny": "0.05",
            "intent": "execute",
            "requested_tier": "flash",
            "pricing_version": "deepseek-cn-2026-08-28",
        },
    )
    assert reconciled.status_code == 200
    settled = reconciled.json()["reservation"]
    assert settled["state"] == "reconciled"
    assert Decimal(settled["actual_cost"]) == Decimal("0.05")


@pytest.mark.asyncio
async def test_admit_requires_owner_approval_over_threshold_then_consumes_credential(
    http,
) -> None:
    _up_balance(http.app)
    big = dict(ENVELOPE, authorized_ceiling="25")
    first = await _post(
        http, ADMIT_PATH, {"run_id": "run-2", "intent": "execute", "envelope": big}
    )
    assert first.status_code == 200
    decision = first.json()["result"]["decision"]
    assert decision["allowed"] is False
    assert decision["kind"] == "owner_approval_required"

    from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope

    envelope = RunBudgetEnvelope(
        expected_cost=Decimal("0.10"),
        authorized_ceiling=Decimal("25"),
        minimum_remaining=Decimal("0"),
        requested_tier=ModelTier.FLASH,
        fallback_tier=None,
        budget_source=BudgetSource.RUN,
        pricing_version="deepseek-cn-2026-08-28",
    )
    stores = http.app.state.container.stores
    stores.approvals.issue(
        run_id="run-2",
        envelope=envelope,
        actor_id="box-console",
        ttl=timedelta(seconds=600),
    )

    second = await _post(
        http, ADMIT_PATH, {"run_id": "run-2", "intent": "execute", "envelope": big}
    )
    assert second.status_code == 200
    approved = second.json()["result"]
    assert approved["decision"]["allowed"] is True
    assert approved["decision"]["reason"] == "owner_approval_consumed"
    assert stores.approvals.get_open("run-2") is None


@pytest.mark.asyncio
async def test_store_rejects_unsigned_or_wrong_key_requests(http) -> None:
    unsigned = await http.post(
        ADMIT_PATH,
        content=canonical_body(
            {"run_id": "run-1", "intent": "execute", "envelope": ENVELOPE}
        ),
        headers={"Content-Type": "application/json"},
    )
    assert unsigned.status_code == 401

    wrong = await _post(
        http,
        ADMIT_PATH,
        {"run_id": "run-1", "intent": "execute", "envelope": ENVELOPE},
        key_hex="cd" * 32,
    )
    assert wrong.status_code == 401

    stale_headers = _headers(
        "POST", ADMIT_PATH, canonical_body({"x": 1})
    )
    stale_headers["X-Bogda-Timestamp"] = str(int(stale_headers["X-Bogda-Timestamp"]) - 3600)
    body = canonical_body({"run_id": "run-1", "intent": "execute", "envelope": ENVELOPE})
    stale_headers["X-Bogda-Signature"] = sign_request(
        bytes.fromhex(KEY_HEX), "POST", ADMIT_PATH, body, int(stale_headers["X-Bogda-Timestamp"])
    )
    stale = await http.post(ADMIT_PATH, content=body, headers=stale_headers)
    assert stale.status_code == 401


@pytest.mark.asyncio
async def test_store_disabled_without_hmac_key(tmp_path) -> None:
    settings = _settings(
        tmp_path, BOGDA_APPROVAL_DB="", BOGDA_APPROVAL_HMAC_KEY=""
    )
    app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await _post(
            client,
            ADMIT_PATH,
            {"run_id": "run-1", "intent": "execute", "envelope": ENVELOPE},
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_usage_unknown_open_case_and_blocked_lookup(http) -> None:
    blocked_before = await _get(
        http, BLOCKED_PATH, {"run_id": "run-3", "call_id": "call-3"}
    )
    assert blocked_before.status_code == 200
    assert blocked_before.json() == {"blocked": False}

    opened = await _post(
        http,
        CASES_PATH,
        {
            "run_id": "run-3",
            "call_id": "call-3",
            "reservation_id": "reservation-3",
            "intent": "execute",
            "requested_tier": "flash",
            "effective_tier": "flash",
            "pricing_version": "deepseek-cn-2026-08-28",
        },
    )
    assert opened.status_code == 200
    case = opened.json()["case"]
    assert case["state"] == "awaiting_reconciliation"
    assert case["revision"] == 0

    blocked_after = await _get(
        http, BLOCKED_PATH, {"run_id": "run-3", "call_id": "call-3"}
    )
    assert blocked_after.json() == {"blocked": True}
