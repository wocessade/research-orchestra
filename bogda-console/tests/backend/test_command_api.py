from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_submit_then_cancel_returns_authoritative_receipts(client) -> None:
    submitted = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={"parameters": {"sample": "new"}, "idempotencyKey": "intent-api"},
    )
    assert submitted.status_code == 200
    run = submitted.json()["data"]["snapshot"]
    cancelled = await client.post(
        f"/api/v1/runs/{run['runId']}/cancel",
        json={"expectedCommandVersion": run["commandVersion"]},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["snapshot"]["state"]["name"] == "Cancelling"


@pytest.mark.asyncio
async def test_stale_version_is_409_with_current_resource(client) -> None:
    response = await client.post(
        "/api/v1/runs/run-active/cancel",
        json={"expectedCommandVersion": "stale"},
    )
    assert response.status_code == 409
    error = response.json()["errors"][0]
    assert error["code"] == "RESOURCE_CHANGED"
    assert error["details"]["currentResource"]["runId"] == "run-active"


@pytest.mark.asyncio
async def test_review_conflict_is_409_and_returns_newest(client) -> None:
    await client.post(
        "/api/v1/test/scenario", json={"scenario": "result-missing-invalid-conflict"}
    )
    response = await client.post(
        "/api/v1/runs/run-review/reviews",
        json={
            "baseArtifactId": "artifact-old",
            "scientificStatus": "rejected",
            "reviewSummary": "stale",
        },
    )
    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "REVIEW_CONFLICT"
    assert response.json()["errors"][0]["details"]["currentResource"]["artifactId"] == "artifact-newest"


@pytest.mark.asyncio
async def test_schedule_and_queue_pause_resume(client) -> None:
    deployments = (await client.get("/api/v1/deployments")).json()["data"]["items"]
    deployment = next(item for item in deployments if item["deploymentId"] == "deployment-dorm")
    schedule = deployment["schedules"][0]
    paused_schedule = await client.post(
        f"/api/v1/deployments/deployment-dorm/schedules/{schedule['scheduleId']}/pause",
        json={"expectedCommandVersion": schedule["commandVersion"]},
    )
    assert paused_schedule.status_code == 200

    infrastructure = (await client.get("/api/v1/infrastructure")).json()["data"]
    dorm = next(pool for pool in infrastructure["pools"] if pool["name"] == "dorm-x86")
    queue = next(item for item in dorm["queues"] if item["queueId"] == "queue-cpu")
    paused_queue = await client.post(
        "/api/v1/work-queues/queue-cpu/pause",
        json={"expectedCommandVersion": queue["commandVersion"]},
    )
    assert paused_queue.status_code == 200
    new_queue = paused_queue.json()["data"]["snapshot"]
    resumed_queue = await client.post(
        "/api/v1/work-queues/queue-cpu/resume",
        json={"expectedCommandVersion": new_queue["commandVersion"]},
    )
    assert resumed_queue.status_code == 200


@pytest.mark.asyncio
async def test_checkpoint_decision_uses_closed_request_body(client) -> None:
    prefect = client.app.state.container.prefect
    prefect._prefect["runs"].insert(
        0,
        {
            "runId": "run-checkpoint",
            "name": "ridge experiment gate",
            "deploymentId": "deployment-dorm",
            "deploymentName": "alpine-assay",
            "projectId": "bogda-main",
            "workPoolName": "dorm-x86",
            "workQueueName": "cpu",
            "state": {
                "type": "PAUSED",
                "name": "Paused",
                "timestamp": "2026-08-24T08:21:00Z",
                "terminal": False,
            },
            "scheduledAt": "2026-08-24T08:18:00Z",
            "startedAt": "2026-08-24T08:20:00Z",
            "endedAt": None,
            "parameters": {"sample": "ridge-a"},
            "tags": ["cpu"],
            "checkpoint": {
                "kind": "experiment_approval",
                "stage": "done",
                "verdict": None,
                "rationale": None,
                "decidedBy": None,
                "commandVersion": "checkpoint-v1",
                "impact": "批准后继续执行实验；拒绝将以 Cancelled 结束，不会记成系统失败。",
            },
        },
    )
    prefect._fixture["runResults"]["artifactsByRun"]["run-checkpoint"] = []
    response = await client.post(
        "/api/v1/runs/run-checkpoint/checkpoints",
        json={
            "expectedCommandVersion": "checkpoint-v1",
            "verdict": "approved",
            "rationale": "可以做",
        },
    )
    assert response.status_code == 200
    snapshot = response.json()["data"]["snapshot"]
    assert snapshot["checkpoint"]["verdict"] == "approved"
    assert snapshot["run"]["state"]["name"] == "Running"


@pytest.mark.asyncio
async def test_request_validation_uses_the_closed_error_envelope(client) -> None:
    response = await client.post(
        "/api/v1/runs/run-active/cancel",
        json={"expectedCommandVersion": ""},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_unexpected_command_failure_uses_the_closed_error_envelope(client, monkeypatch) -> None:
    async def fail_unexpectedly(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(client.app.state.container.commands, "cancel", fail_unexpectedly)
    async with AsyncClient(
        transport=ASGITransport(app=client.app, raise_app_exceptions=False),
        base_url="http://test",
    ) as isolated:
        response = await isolated.post(
            "/api/v1/runs/run-active/cancel",
            json={"expectedCommandVersion": "run-active-v1"},
        )
    assert response.status_code == 500
    assert response.json()["errors"][0]["code"] == "INTERNAL_ERROR"
