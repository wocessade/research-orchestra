from __future__ import annotations

import pytest


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
