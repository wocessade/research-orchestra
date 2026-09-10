from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bogda_console.adapters.prefect_api import PrefectApiAdapter
from bogda_console.adapters.local_autonomy_policy import LocalAutonomyPolicyAdapter
from bogda_console.adapters.mock_autonomy_policy import MockAutonomyPolicyAdapter
from bogda_console.adapters.mock_power import MockPowerAdapter
from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter
from bogda_console.adapters.mock_model_control import MockModelControlAdapter
from bogda_console.adapters.unwired_autonomy_policy import UnwiredAutonomyPolicyAdapter
from bogda_console.adapters.unwired_model_control import UnwiredModelControlAdapter
from bogda_console.adapters.deepseek_balance import DeepSeekBalanceAdapter, MockUsageBalanceAdapter
from bogda_console.api.routes import router
from bogda_console.api.store_routes import router as store_router
from bogda_console.config import Settings
from bogda_console.contracts.models import (
    ApiEnvelope,
    ApiError,
    ApiErrorCode,
    ApiErrorDetails,
)
from bogda_console.services.errors import ServiceError
from bogda_console.services.commands import CommandService
from bogda_console.services.queries import QueryService


def _lifecycle(settings: Settings):
    if not settings.artifact_root:
        return None
    from bogda.artifacts.lifecycle import ArtifactLifecycle

    return ArtifactLifecycle(Path(settings.artifact_root))


def _approval_store(settings: Settings):
    if not settings.approval_db or not settings.approval_hmac_key:
        return None
    from bogda.budget.approval import SqliteApprovalStore

    return SqliteApprovalStore(Path(settings.approval_db), hmac_key=settings.approval_hmac_key)


def _log_reader(settings: Settings):
    if not settings.artifact_root:
        return None
    from bogda.artifacts.safe_log import SafeLogReader

    return SafeLogReader(Path(settings.artifact_root))


class _BalanceUsagePort:
    """Sync usage port backed by the async DeepSeek balance adapter.

    The budget kernel evaluates synchronously; callers refresh() right before
    an admission so the snapshot the guard sees is current.
    """

    def __init__(self, balance: Any) -> None:
        self._balance = balance
        self._snapshot: Any = None

    def get_snapshot(self):
        from bogda.budget.usage import UsageSnapshotV1, UsageSourceStatus

        if self._snapshot is not None:
            return self._snapshot
        return UsageSnapshotV1(
            provider="deepseek",
            available=False,
            total_balance=Decimal("0"),
            currency="CNY",
            observed_at=datetime.now(timezone.utc),
            source_status=UsageSourceStatus.UNAVAILABLE,
        )

    async def refresh(self) -> None:
        from bogda.budget.usage import UsageSnapshotV1, UsageSourceStatus

        try:
            balance = await self._balance.get_balance()
        except Exception:
            self._snapshot = UsageSnapshotV1(
                provider="deepseek",
                available=False,
                total_balance=Decimal("0"),
                currency="CNY",
                observed_at=datetime.now(timezone.utc),
                source_status=UsageSourceStatus.UNAVAILABLE,
            )
            return
        self._snapshot = UsageSnapshotV1(
            provider="deepseek",
            available=True,
            total_balance=balance.total_balance,
            currency="CNY",
            observed_at=balance.observed_at,
            source_status=UsageSourceStatus.UP,
        )


@dataclass(slots=True)
class CoreStores:
    approvals: Any
    ledger: Any
    guard: Any
    budget: Any
    recovery_store: Any
    recovery: Any
    sink: Any
    balance_usage: Any


def _core_stores(
    settings: Settings, usage_balance: Any, approvals: Any
) -> CoreStores | None:
    if not settings.usage_unknown_db:
        return None
    try:
        from bogda.budget.durable_ledger import SqliteBudgetLedger
        from bogda.budget.guard import BudgetGuard
        from bogda.budget.service import BudgetAdmissionService
        from bogda.events.jsonl import JsonlRunEventSink
        from bogda.model_runtime.recovery import (
            SqliteUsageUnknownStore,
            UsageUnknownRecoveryService,
        )
    except ImportError:
        return None

    db = Path(settings.usage_unknown_db)
    db.parent.mkdir(parents=True, exist_ok=True)
    ledger = SqliteBudgetLedger(db.with_name(db.stem + "-ledger.sqlite"))
    guard = BudgetGuard(ledger)
    usage = _BalanceUsagePort(usage_balance)
    sink = JsonlRunEventSink(db.with_name(db.stem + "-events.jsonl"))
    budget = BudgetAdmissionService(
        usage=usage,
        guard=guard,
        ledger=ledger,
        event_sink=sink,
        approvals=approvals,
    )
    recovery_store = SqliteUsageUnknownStore(db)
    recovery = UsageUnknownRecoveryService(
        store=recovery_store,
        budget=budget,
        event_sink=sink,
    )
    return CoreStores(
        approvals=approvals,
        ledger=ledger,
        guard=guard,
        budget=budget,
        recovery_store=recovery_store,
        recovery=recovery,
        sink=sink,
        balance_usage=usage,
    )


def _core_model_control(stores: CoreStores | None):
    if stores is None:
        return UnwiredModelControlAdapter()
    try:
        from bogda_console.adapters.core_model_control import CoreUsageUnknownAdapter
    except ImportError:
        return UnwiredModelControlAdapter()
    return CoreUsageUnknownAdapter(stores.recovery)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((PROJECT_ROOT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


@dataclass(slots=True)
class Container:
    settings: Settings
    prefect: Any
    results: Any
    power: MockPowerAdapter
    queries: QueryService
    commands: CommandService
    policy: Any
    model_control: Any
    usage_balance: Any
    stores: Any = None

    @classmethod
    def build(cls, settings: Settings, scenario: str | None = None) -> "Container":
        if settings.profile != "mock-all":
            if not settings.prefect_api_url:
                raise ValueError("PREFECT_API_URL is required for real Prefect profiles")
            prefect = PrefectApiAdapter(
                api_url=settings.prefect_api_url,
                auth_string=settings.prefect_api_auth_string,
                api_key=settings.prefect_api_key,
                allowed_deployment_ids=settings.allowed_deployment_ids,
            )
            power = MockPowerAdapter(load_fixture(settings.fixture_scenario))
            if settings.autonomy_policy_path:
                policy = LocalAutonomyPolicyAdapter(settings.autonomy_policy_path)
            else:
                policy = UnwiredAutonomyPolicyAdapter()
            usage_balance = DeepSeekBalanceAdapter(
                settings.deepseek_api_key,
                api_base=settings.deepseek_api_base,
            )
            approvals = _approval_store(settings)
            stores = _core_stores(settings, usage_balance, approvals)
            model_control = _core_model_control(stores)
            queries = QueryService(
                settings=settings,
                prefect=prefect,
                results=prefect,
                power=power,
                policy=policy,
                model_control=model_control,
                usage_balance=usage_balance,
                log_reader=_log_reader(settings),
            )
            commands = CommandService(
                settings=settings,
                prefect=prefect,
                results=prefect,
                policy=policy,
                model_control=model_control,
                approvals=approvals,
                lifecycle=_lifecycle(settings),
            )
            return cls(settings, prefect, prefect, power, queries, commands, policy, model_control, usage_balance, stores)
        fixture = load_fixture(scenario or settings.fixture_scenario)
        prefect = MockPrefectAdapter(fixture)
        results = MockRunResultAdapter(fixture)
        power = MockPowerAdapter(fixture)
        clock = datetime.fromisoformat(str(fixture["clock"]).replace("Z", "+00:00"))
        policy = MockAutonomyPolicyAdapter()
        model_control = MockModelControlAdapter()
        usage_balance = MockUsageBalanceAdapter(now=lambda: clock)
        queries = QueryService(
            settings=settings,
            prefect=prefect,
            results=results,
            power=power,
            now=lambda: clock,
            policy=policy,
            model_control=model_control,
            usage_balance=usage_balance,
            log_reader=_log_reader(settings),
        )
        commands = CommandService(
            settings=settings,
            prefect=prefect,
            results=results,
            now=lambda: clock,
            policy=policy,
            model_control=model_control,
            approvals=_approval_store(settings),
            lifecycle=_lifecycle(settings),
        )
        return cls(settings, prefect, results, power, queries, commands, policy, model_control, usage_balance)

    def for_scenario(self, scenario: str) -> "Container":
        if self.settings.profile != "mock-all":
            raise ValueError("scenarios are available only in mock-all")
        return self.build(self.settings, scenario)


def _error_envelope(error: ServiceError) -> dict[str, Any]:
    return ApiEnvelope[dict[str, Any]](
        data=None,
        sources={},
        errors=[
            ApiError(
                code=error.code,
                message=str(error),
                source=error.source,
                retryable=error.retryable,
                details=error.details,
            )
        ],
    ).model_dump(mode="json", by_alias=True)


def create_app(settings: Settings | None = None, *, frontend_dist: Path | None = None) -> FastAPI:
    resolved = settings or Settings.from_env(os.environ)
    app = FastAPI(title="Bogda Console API", version="1.0.0")
    app.state.container = Container.build(resolved)
    app.include_router(router)
    app.include_router(store_router)

    @app.exception_handler(ServiceError)
    async def service_error_handler(_request: Request, error: ServiceError):
        return JSONResponse(status_code=error.status_code, content=_error_envelope(error))

    @app.exception_handler(KeyError)
    async def not_found_handler(_request: Request, error: KeyError):
        service_error = ServiceError(
            ApiErrorCode.NOT_FOUND,
            f"Resource not found: {error.args[0]}",
            source="prefect",
            retryable=False,
        )
        return JSONResponse(status_code=404, content=_error_envelope(service_error))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, error: RequestValidationError):
        service_error = ServiceError(
            ApiErrorCode.VALIDATION_ERROR,
            "Request validation failed",
            source="request",
            retryable=False,
            status_code=422,
            details=ApiErrorDetails(
                fields=[
                    {
                        "field": ".".join(str(part) for part in issue["loc"]),
                        "message": issue["msg"],
                    }
                    for issue in error.errors()
                ]
            ),
        )
        return JSONResponse(status_code=422, content=_error_envelope(service_error))

    @app.exception_handler(Exception)
    async def internal_error_handler(_request: Request, _error: Exception):
        service_error = ServiceError(
            ApiErrorCode.INTERNAL_ERROR,
            "Unexpected server failure",
            source="console",
            retryable=False,
            status_code=500,
        )
        return JSONResponse(status_code=500, content=_error_envelope(service_error))

    if frontend_dist is not None:
        index = frontend_dist / "index.html"
        assets = frontend_dist / "assets"
        if not index.is_file() or not assets.is_dir():
            raise RuntimeError("frontend build missing; run npm run build before production serving")
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

        @app.get("/", include_in_schema=False)
        async def frontend_root():
            return FileResponse(index)

        @app.get("/{path:path}", include_in_schema=False)
        async def frontend_fallback(path: str):
            if path.startswith("api/"):
                raise HTTPException(status_code=404)
            return FileResponse(index)

    return app
