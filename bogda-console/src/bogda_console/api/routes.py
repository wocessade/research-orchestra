from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from bogda_console.contracts.models import (
    ApiEnvelope,
    AutonomyPolicySnapshot,
    CapabilitySnapshot,
    CheckpointDecisionRequest,
    CommandReceipt,
    DeploymentSummary,
    ExpectedVersionRequest,
    InfrastructureView,
    OverviewSnapshot,
    Page,
    QueueSnapshot,
    ReviewRequest,
    RunDetail,
    RunFilters,
    RunResultVersionSummary,
    RunResultView,
    RunSummary,
    SetGlobalAutonomyRequest,
    SetProjectAutonomyRequest,
    SubmitRequest,
    AllowedRunPreferences,
    WorkloadEstimate,
    ModelPolicyPatch,
    WireModel,
    DecisionCenterSnapshot,
    ModelBudgetSnapshot,
    ModelPolicySnapshot,
    UsageBalanceSnapshot,
    RunPreparationPreview,
    RunLogSlice,
)


router = APIRouter(prefix="/api/v1")


class DecisionRequest(WireModel):
    action_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    rationale: str | None = None
    actual_cost_cny: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    new_call_id: str | None = None


class GlobalModelPolicyRequest(WireModel):
    patch: ModelPolicyPatch
    expected_revision: int = Field(ge=0)


class ProjectModelPolicyRequest(WireModel):
    patch: ModelPolicyPatch | None
    expected_revision: int = Field(ge=0)


class RunPreparationPreviewRequest(WireModel):
    project_id: str
    intent: Literal["execute", "brief", "explore", "decide", "audit"]
    requested_model_tier: Literal["auto", "flash", "pro"]
    workload: WorkloadEstimate
    allowed_preferences: AllowedRunPreferences
    deadline: datetime | None = None


def queries(request: Request):
    return request.app.state.container.queries


@router.get("/capabilities", response_model=ApiEnvelope[CapabilitySnapshot])
async def capabilities(request: Request):
    return await queries(request).capabilities()


@router.get("/overview", response_model=ApiEnvelope[OverviewSnapshot])
async def overview(request: Request):
    return await queries(request).overview()


@router.get("/runs", response_model=ApiEnvelope[Page[RunSummary]])
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


@router.get("/runs/{run_id}", response_model=ApiEnvelope[RunDetail])
async def run_detail(run_id: str, request: Request):
    return await queries(request).run_detail(run_id)


@router.get("/runs/{run_id}/result", response_model=ApiEnvelope[RunResultView])
async def result(run_id: str, request: Request):
    return await queries(request).result(run_id)


@router.get("/runs/{run_id}/logs", response_model=ApiEnvelope[RunLogSlice])
async def run_logs(
    run_id: str,
    request: Request,
    source: str = Query(default="stdout"),
    max_bytes: int = Query(default=65536, ge=1, le=262144, alias="maxBytes"),
):
    return await queries(request).run_logs(run_id, source, max_bytes=max_bytes)


@router.get(
    "/runs/{run_id}/result/versions",
    response_model=ApiEnvelope[Page[RunResultVersionSummary]],
)
async def result_versions(
    run_id: str,
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    return await queries(request).result_versions(run_id, cursor, limit)


@router.get("/deployments", response_model=ApiEnvelope[Page[DeploymentSummary]])
async def deployments(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    return await queries(request).deployments(cursor, limit)


@router.get("/infrastructure", response_model=ApiEnvelope[InfrastructureView])
async def infrastructure(request: Request):
    return await queries(request).infrastructure()


@router.get("/autonomy-policy", response_model=ApiEnvelope[AutonomyPolicySnapshot])
async def autonomy_policy(request: Request):
    return await queries(request).autonomy_policy()


@router.get("/decisions", response_model=ApiEnvelope[DecisionCenterSnapshot])
async def decisions(request: Request):
    return await queries(request).decisions()


@router.get("/runs/{run_id}/model-budget", response_model=ApiEnvelope[ModelBudgetSnapshot])
async def run_model_budget(run_id: str, request: Request):
    return await queries(request).run_budget(run_id)


@router.get("/model-policy", response_model=ApiEnvelope[ModelPolicySnapshot])
async def model_policy(request: Request, project_id: str | None = Query(default=None, alias="projectId")):
    return await queries(request).model_policy(project_id)


@router.get("/usage-balance", response_model=ApiEnvelope[UsageBalanceSnapshot])
async def usage_balance(request: Request):
    return await queries(request).usage_balance_snapshot()


@router.post("/run-preparations/preview", response_model=ApiEnvelope[RunPreparationPreview])
async def preview_run(body: RunPreparationPreviewRequest, request: Request):
    return await queries(request).preview_run(
        body.project_id,
        body.intent,
        body.requested_model_tier,
        body.workload,
        body.allowed_preferences,
        body.deadline,
    )


def commands(request: Request):
    return request.app.state.container.commands


def command_envelope(receipt):
    return ApiEnvelope(data=receipt, sources={}, errors=[])


@router.post(
    "/deployments/{deployment_id}/runs",
    response_model=ApiEnvelope[CommandReceipt[RunSummary]],
)
async def submit(deployment_id: str, body: SubmitRequest, request: Request):
    return command_envelope(
        await commands(request).submit(
            deployment_id, body.parameters, body.idempotency_key, body.run_preparation_id
        )
    )


@router.post(
    "/runs/{run_id}/cancel",
    response_model=ApiEnvelope[CommandReceipt[RunSummary]],
)
async def cancel(run_id: str, body: ExpectedVersionRequest, request: Request):
    return command_envelope(
        await commands(request).cancel(run_id, body.expected_command_version)
    )


@router.post(
    "/deployments/{deployment_id}/schedules/{schedule_id}/pause",
    response_model=ApiEnvelope[CommandReceipt[DeploymentSummary]],
)
async def pause_schedule(
    deployment_id: str, schedule_id: str, body: ExpectedVersionRequest, request: Request
):
    return command_envelope(
        await commands(request).pause_schedule(
            deployment_id, schedule_id, body.expected_command_version
        )
    )


@router.post(
    "/deployments/{deployment_id}/schedules/{schedule_id}/resume",
    response_model=ApiEnvelope[CommandReceipt[DeploymentSummary]],
)
async def resume_schedule(
    deployment_id: str, schedule_id: str, body: ExpectedVersionRequest, request: Request
):
    return command_envelope(
        await commands(request).resume_schedule(
            deployment_id, schedule_id, body.expected_command_version
        )
    )


@router.post(
    "/work-queues/{queue_id}/pause",
    response_model=ApiEnvelope[CommandReceipt[QueueSnapshot]],
)
async def pause_queue(queue_id: str, body: ExpectedVersionRequest, request: Request):
    return command_envelope(
        await commands(request).pause_queue(queue_id, body.expected_command_version)
    )


@router.post(
    "/work-queues/{queue_id}/resume",
    response_model=ApiEnvelope[CommandReceipt[QueueSnapshot]],
)
async def resume_queue(queue_id: str, body: ExpectedVersionRequest, request: Request):
    return command_envelope(
        await commands(request).resume_queue(queue_id, body.expected_command_version)
    )


@router.post(
    "/runs/{run_id}/reviews",
    response_model=ApiEnvelope[CommandReceipt[RunResultView]],
)
async def review(run_id: str, body: ReviewRequest, request: Request):
    return command_envelope(
        await commands(request).review(
            run_id, body.base_artifact_id, body.scientific_status, body.review_summary
        )
    )


@router.post(
    "/runs/{run_id}/checkpoints",
    response_model=ApiEnvelope[CommandReceipt[RunDetail]],
)
async def decide_checkpoint(
    run_id: str, body: CheckpointDecisionRequest, request: Request
):
    return command_envelope(
        await commands(request).decide_checkpoint(
            run_id, body.expected_command_version, body.verdict, body.rationale
        )
    )


@router.post(
    "/autonomy-policy/global",
    response_model=ApiEnvelope[CommandReceipt[AutonomyPolicySnapshot]],
)
async def set_global_autonomy(body: SetGlobalAutonomyRequest, request: Request):
    return command_envelope(
        await commands(request).set_global_autonomy(body.mode, body.expected_revision)
    )


@router.post(
    "/autonomy-policy/projects/{project_id}",
    response_model=ApiEnvelope[CommandReceipt[AutonomyPolicySnapshot]],
)
async def set_project_autonomy(project_id: str, body: SetProjectAutonomyRequest, request: Request):
    return command_envelope(
        await commands(request).set_project_autonomy(
            project_id, body.mode, body.expected_revision
        )
    )


@router.post("/decisions/{decision_id}", response_model=ApiEnvelope[CommandReceipt[DecisionCenterSnapshot]])
async def resolve_decision(decision_id: str, body: DecisionRequest, request: Request):
    return command_envelope(
        await commands(request).resolve_decision(
            decision_id,
            body.action_id,
            body.expected_revision,
            body.rationale,
            actual_cost_cny=body.actual_cost_cny,
            new_call_id=body.new_call_id,
        )
    )


@router.post("/model-policy/global", response_model=ApiEnvelope[CommandReceipt[ModelPolicySnapshot]])
async def set_global_model_policy(body: GlobalModelPolicyRequest, request: Request):
    return command_envelope(await commands(request).set_global_model_policy(body.patch, body.expected_revision))


@router.post("/model-policy/projects/{project_id}", response_model=ApiEnvelope[CommandReceipt[ModelPolicySnapshot]])
async def set_project_model_policy(project_id: str, body: ProjectModelPolicyRequest, request: Request):
    return command_envelope(await commands(request).set_project_model_policy(project_id, body.patch, body.expected_revision))


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
