from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict

from bogda_console.contracts.models import RunFilters


router = APIRouter(prefix="/api/v1")


def queries(request: Request):
    return request.app.state.container.queries


@router.get("/capabilities")
async def capabilities(request: Request):
    return await queries(request).capabilities()


@router.get("/overview")
async def overview(request: Request):
    return await queries(request).overview()


@router.get("/runs")
async def runs(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    execution_type: str | None = Query(default=None, alias="executionType"),
    scientific_status: str | None = Query(default=None, alias="scientificStatus"),
    deployment_id: str | None = Query(default=None, alias="deploymentId"),
    project_id: str | None = Query(default=None, alias="projectId"),
):
    return await queries(request).runs(
        RunFilters(
            executionType=execution_type,
            scientificStatus=scientific_status,
            deploymentId=deployment_id,
            projectId=project_id,
        ),
        cursor,
        limit,
    )


@router.get("/runs/{run_id}")
async def run_detail(run_id: str, request: Request):
    return await queries(request).run_detail(run_id)


@router.get("/runs/{run_id}/result")
async def result(run_id: str, request: Request):
    return await queries(request).result(run_id)


@router.get("/runs/{run_id}/result/versions")
async def result_versions(
    run_id: str,
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    return await queries(request).result_versions(run_id, cursor, limit)


@router.get("/deployments")
async def deployments(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    return await queries(request).deployments(cursor, limit)


@router.get("/infrastructure")
async def infrastructure(request: Request):
    return await queries(request).infrastructure()


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal[
        "normal-active",
        "sleep-queued",
        "gaming-paused",
        "degraded-stale",
        "result-missing-invalid-conflict",
        "mobile-dense",
    ]


@router.post("/test/scenario")
async def scenario(body: ScenarioRequest, request: Request):
    container = request.app.state.container
    if not container.settings.test_mode or container.settings.profile != "mock-all":
        from fastapi import HTTPException

        raise HTTPException(status_code=404)
    request.app.state.container = container.for_scenario(body.scenario)
    return {"data": {"scenario": body.scenario}, "sources": {}, "errors": []}
