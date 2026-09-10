from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient

from bogda.budget.durable_ledger import SqliteBudgetLedger
from bogda.policy import ModelPolicyStore
from bogda_console.adapters.local_model_control import LocalModelControlAdapter
from bogda_console.app import create_app
from bogda_console.config import Settings
from bogda_console.contracts.models import (
    AllowedRunPreferences,
    DecisionCenterSnapshot,
    ModelPolicyPatch,
    UsageBalanceSnapshot,
    WorkloadEstimate,
)
from bogda_console.contracts.ports import (
    ModelControlConflict,
    ModelControlNotFound,
    ModelControlUnavailable,
)


BEIJING = ZoneInfo("Asia/Shanghai")
PEAK_MORNING = datetime(2026, 9, 11, 10, 0, tzinfo=BEIJING)


class _StubRecovery:
    async def decision_center(self) -> DecisionCenterSnapshot:
        return DecisionCenterSnapshot(items=(), revision=0)

    async def run_budget(self, run_id: str) -> Any:
        raise ModelControlNotFound(run_id)

    async def resolve_decision(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("not exercised")


class _FakeBalance:
    def __init__(self, total: Decimal) -> None:
        self._total = total

    async def get_balance(self) -> UsageBalanceSnapshot:
        return UsageBalanceSnapshot(
            provider="deepseek",
            available=True,
            total_balance=self._total,
            currency="CNY",
            observed_at=datetime.now(UTC),
            source_status="up",
        )


class _BrokenBalance:
    async def get_balance(self) -> UsageBalanceSnapshot:
        raise RuntimeError("balance source down")


def _adapter(tmp_path, *, now: datetime = PEAK_MORNING, balance=None, ledger=None):
    return LocalModelControlAdapter(
        store=ModelPolicyStore(tmp_path / "model-policy.json"),
        recovery=_StubRecovery(),  # type: ignore[arg-type]
        preparations_path=tmp_path / "run-preparations.json",
        balance=balance,
        ledger=ledger,
        now=lambda: now,
    )


def _prefs(**overrides: Any) -> AllowedRunPreferences:
    values: dict[str, Any] = {
        "prefer_off_peak": True,
        "allow_auto_upgrade": False,
        "allow_flash_downgrade": True,
        "auto_resume": False,
    }
    values.update(overrides)
    return AllowedRunPreferences(**values)


def _workload(**overrides: Any) -> WorkloadEstimate:
    values: dict[str, Any] = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "expected_calls": 1,
        "runtime_minutes": 30,
    }
    values.update(overrides)
    return WorkloadEstimate(**values)


@pytest.mark.asyncio
async def test_policy_snapshot_reports_real_catalog_and_store_revision(tmp_path) -> None:
    adapter = _adapter(tmp_path)
    snapshot = await adapter.model_policy("bogda-main")
    assert snapshot.source == "global"
    assert snapshot.inherits_global is True
    assert snapshot.revision == 0
    assert snapshot.price_catalog.status == "ready"
    assert snapshot.price_catalog.version.startswith("deepseek-cn-")
    assert snapshot.price_catalog.review_by is not None


@pytest.mark.asyncio
async def test_set_global_policy_persists_and_stale_revision_conflicts(tmp_path) -> None:
    adapter = _adapter(tmp_path)
    updated = await adapter.set_global_policy(
        ModelPolicyPatch(default_model_tier="flash"), expected_revision=0
    )
    assert updated.default_model_tier == "flash"
    assert updated.revision == 1

    with pytest.raises(ModelControlConflict) as conflict:
        await adapter.set_global_policy(
            ModelPolicyPatch(default_model_tier="pro"), expected_revision=0
        )
    assert conflict.value.current.revision == 1
    assert ModelPolicyStore(tmp_path / "model-policy.json").load().revision == 1


@pytest.mark.asyncio
async def test_preview_schedules_off_peak_and_prices_with_current_catalog(tmp_path) -> None:
    adapter = _adapter(tmp_path, balance=_FakeBalance(Decimal("100")))
    preview = await adapter.preview_run(
        "bogda-main", "execute", "auto", _workload(), _prefs()
    )
    assert preview.price_period == "off-peak"
    assert preview.scheduled_start == datetime(2026, 9, 11, 12, 0, tzinfo=BEIJING)
    assert preview.effective_model_tier == "flash"
    assert preview.fallback_model_tier is None
    assert preview.budget.expected_cost == Decimal("5")
    assert preview.budget.authorized_ceiling > preview.budget.expected_cost
    assert preview.budget.state == "ready"
    assert preview.effective_autonomy_mode == "supervised"


@pytest.mark.asyncio
async def test_preview_upgrades_decide_intent_to_pro_only_when_allowed(tmp_path) -> None:
    adapter = _adapter(tmp_path, balance=_FakeBalance(Decimal("100")))
    upgraded = await adapter.preview_run(
        "bogda-main",
        "decide",
        "auto",
        _workload(),
        _prefs(allow_auto_upgrade=True),
    )
    assert upgraded.effective_model_tier == "pro"
    assert upgraded.fallback_model_tier == "flash"

    held = await adapter.preview_run(
        "bogda-main", "decide", "auto", _workload(), _prefs(allow_auto_upgrade=False)
    )
    assert held.effective_model_tier == "flash"


@pytest.mark.asyncio
async def test_preview_keeps_peak_when_deadline_precedes_off_peak(tmp_path) -> None:
    adapter = _adapter(tmp_path, balance=_FakeBalance(Decimal("100")))
    preview = await adapter.preview_run(
        "bogda-main",
        "execute",
        "flash",
        _workload(),
        _prefs(),
        deadline=datetime(2026, 9, 11, 11, 0, tzinfo=BEIJING),
    )
    assert preview.price_period == "peak"
    assert preview.scheduled_start == PEAK_MORNING


@pytest.mark.asyncio
async def test_preview_fails_closed_when_balance_source_is_down(tmp_path) -> None:
    adapter = _adapter(tmp_path, balance=_BrokenBalance())
    with pytest.raises(ModelControlUnavailable, match="usage source unavailable"):
        await adapter.preview_run("bogda-main", "execute", "auto", _workload(), _prefs())


@pytest.mark.asyncio
async def test_preview_marks_insufficient_when_balance_below_gate(tmp_path) -> None:
    adapter = _adapter(tmp_path, balance=_FakeBalance(Decimal("1")))
    preview = await adapter.preview_run(
        "bogda-main", "execute", "auto", _workload(), _prefs()
    )
    assert preview.budget.state == "insufficient"


@pytest.mark.asyncio
async def test_confirm_preparation_is_idempotent_and_conflict_safe(tmp_path) -> None:
    adapter = _adapter(tmp_path, balance=_FakeBalance(Decimal("100")))
    preview = await adapter.preview_run(
        "bogda-main", "execute", "auto", _workload(), _prefs()
    )
    confirmed = await adapter.confirm_preparation(preview.preparation_id, "key-1")
    assert confirmed.confirmed is True
    assert confirmed.confirmed_at is not None

    again = await adapter.confirm_preparation(preview.preparation_id, "key-1")
    assert again.confirmed is True
    assert again.confirmed_at == confirmed.confirmed_at

    with pytest.raises(ModelControlConflict):
        await adapter.confirm_preparation(preview.preparation_id, "key-2")
    with pytest.raises(ModelControlNotFound):
        await adapter.confirm_preparation("prep_missing", "key-1")


@pytest.mark.asyncio
async def test_run_budget_falls_back_to_ledger_reservations(tmp_path) -> None:
    ledger = SqliteBudgetLedger(tmp_path / "ledger.sqlite")
    first = ledger.reserve(run_id="run-1", amount=Decimal("2"), expected_revision=0)
    ledger.reconcile(first.id, Decimal("0.02"))
    second = ledger.reserve(run_id="run-1", amount=Decimal("1"), expected_revision=2)
    adapter = _adapter(tmp_path, ledger=ledger)

    snapshot = await adapter.run_budget("run-1")
    assert snapshot.used_cost == Decimal("0.02")
    assert snapshot.reserved_cost == second.reserved
    assert snapshot.authorized_ceiling == Decimal("3")
    assert snapshot.state == "ready"
    assert len(snapshot.events) == 3  # two reserves + one release

    with pytest.raises(ModelControlNotFound):
        await adapter.run_budget("run-unknown")
    ledger.close()


def _settings(profile: str, **extra: str) -> Settings:
    env = {
        "BOGDA_CONSOLE_PROFILE": profile,
        "BOGDA_CONSOLE_FIXTURE": "normal-active",
        "BOGDA_CONSOLE_TEST_MODE": "1",
        "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service,deployment-dorm",
        "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "pi-service,dorm-x86",
    }
    if profile != "mock-all":
        env["PREFECT_API_URL"] = "http://127.0.0.1:4200/api"
    env.update(extra)
    return Settings.from_env(env)


@pytest.mark.asyncio
async def test_model_policy_path_wires_real_adapter_over_http(tmp_path) -> None:
    env = {
        "BOGDA_CONSOLE_ROLE": "owner",
        "BOGDA_MODEL_POLICY_PATH": str(tmp_path / "model-policy.json"),
        "BOGDA_USAGE_UNKNOWN_DB": str(tmp_path / "usage-unknown.sqlite"),
    }
    app = create_app(_settings("allowlisted-test", **env))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        http.app = app  # type: ignore[attr-defined]
        caps = (await http.get("/api/v1/capabilities")).json()["data"]
        assert caps["canSetModelPolicy"] is True
        assert caps["canPreparePaidRun"] is True

        policy = (await http.get("/api/v1/model-policy")).json()["data"]
        assert policy["revision"] == 0
        assert policy["priceCatalog"]["status"] == "ready"

        written = await http.post(
            "/api/v1/model-policy/global",
            json={"patch": {"defaultModelTier": "flash"}, "expectedRevision": 0},
        )
        assert written.status_code == 200
        snapshot = written.json()["data"]["snapshot"]
        assert snapshot["defaultModelTier"] == "flash"
        assert snapshot["revision"] == 1

        stale = await http.post(
            "/api/v1/model-policy/global",
            json={"patch": {"defaultModelTier": "pro"}, "expectedRevision": 0},
        )
        assert stale.status_code == 409
        assert stale.json()["errors"][0]["code"] == "RESOURCE_CHANGED"

        http.app.state.container.model_control._balance = _FakeBalance(  # type: ignore[attr-defined]
            Decimal("100")
        )
        preview = await http.post(
            "/api/v1/run-preparations/preview",
            json={
                "projectId": "bogda-main",
                "intent": "execute",
                "requestedModelTier": "auto",
                "workload": {
                    "inputTokens": 1000,
                    "outputTokens": 1000,
                    "expectedCalls": 1,
                    "runtimeMinutes": 5,
                },
                "allowedPreferences": {
                    "preferOffPeak": True,
                    "allowAutoUpgrade": False,
                    "allowFlashDowngrade": True,
                    "autoResume": False,
                },
            },
        )
        assert preview.status_code == 200
        data = preview.json()["data"]
        assert data["policyRevision"] == 1
        assert data["confirmed"] is False
        assert Decimal(data["budget"]["expectedCost"]) > Decimal("0")
        source = preview.json()["sources"]["modelControl"]
        assert source["freshness"] == "fresh"
        assert source["sourceMode"] == "real"
        assert source["observedAt"] is not None


@pytest.mark.asyncio
async def test_model_policy_path_still_requires_owner(tmp_path) -> None:
    env = {
        "BOGDA_CONSOLE_ROLE": "operator",
        "BOGDA_MODEL_POLICY_PATH": str(tmp_path / "model-policy.json"),
        "BOGDA_USAGE_UNKNOWN_DB": str(tmp_path / "usage-unknown.sqlite"),
    }
    app = create_app(_settings("allowlisted-test", **env))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        caps = (await http.get("/api/v1/capabilities")).json()["data"]
        assert caps["canSetModelPolicy"] is False
        denied = await http.post(
            "/api/v1/model-policy/global",
            json={"patch": {"defaultModelTier": "flash"}, "expectedRevision": 0},
        )
        assert denied.status_code == 403
