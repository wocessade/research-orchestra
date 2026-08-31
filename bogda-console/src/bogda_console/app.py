from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bogda_console.adapters.prefect_api import PrefectApiAdapter
from bogda_console.adapters.mock_autonomy_policy import MockAutonomyPolicyAdapter
from bogda_console.adapters.mock_power import MockPowerAdapter
from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter
from bogda_console.adapters.mock_model_control import MockModelControlAdapter
from bogda_console.adapters.unwired_autonomy_policy import UnwiredAutonomyPolicyAdapter
from bogda_console.adapters.unwired_model_control import UnwiredModelControlAdapter
from bogda_console.adapters.deepseek_balance import DeepSeekBalanceAdapter, MockUsageBalanceAdapter
from bogda_console.api.routes import router
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
            policy = UnwiredAutonomyPolicyAdapter()
            model_control = UnwiredModelControlAdapter()
            usage_balance = DeepSeekBalanceAdapter(
                settings.deepseek_api_key,
                api_base=settings.deepseek_api_base,
            )
            queries = QueryService(settings=settings, prefect=prefect, results=prefect, power=power, policy=policy, model_control=model_control, usage_balance=usage_balance)
            commands = CommandService(settings=settings, prefect=prefect, results=prefect, policy=policy, model_control=model_control)
            return cls(settings, prefect, prefect, power, queries, commands, policy, model_control, usage_balance)
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
        )
        commands = CommandService(
            settings=settings,
            prefect=prefect,
            results=results,
            now=lambda: clock,
            policy=policy,
            model_control=model_control,
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
