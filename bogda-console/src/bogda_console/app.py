from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bogda_console.adapters.mock_power import MockPowerAdapter
from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter
from bogda_console.api.routes import router
from bogda_console.config import Settings
from bogda_console.contracts.models import ApiEnvelope, ApiError, ApiErrorCode
from bogda_console.services.errors import ServiceError
from bogda_console.services.commands import CommandService
from bogda_console.services.queries import QueryService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((PROJECT_ROOT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


@dataclass(slots=True)
class Container:
    settings: Settings
    prefect: MockPrefectAdapter
    results: MockRunResultAdapter
    power: MockPowerAdapter
    queries: QueryService
    commands: CommandService

    @classmethod
    def build(cls, settings: Settings, scenario: str | None = None) -> "Container":
        fixture = load_fixture(scenario or settings.fixture_scenario)
        prefect = MockPrefectAdapter(fixture)
        results = MockRunResultAdapter(fixture)
        power = MockPowerAdapter(fixture)
        clock = datetime.fromisoformat(str(fixture["clock"]).replace("Z", "+00:00"))
        queries = QueryService(
            settings=settings,
            prefect=prefect,
            results=results,
            power=power,
            now=lambda: clock,
        )
        commands = CommandService(
            settings=settings,
            prefect=prefect,
            results=results,
            now=lambda: clock,
        )
        return cls(settings, prefect, results, power, queries, commands)

    def for_scenario(self, scenario: str) -> "Container":
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


def create_app(settings: Settings | None = None) -> FastAPI:
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

    return app
