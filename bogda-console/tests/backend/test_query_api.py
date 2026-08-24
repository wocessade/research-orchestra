from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_runs_uses_closed_envelope(client) -> None:
    response = await client.get("/api/v1/runs?executionType=COMPLETED&limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data", "sources", "errors"}
    assert payload["data"]["items"][0]["state"]["type"] == "COMPLETED"
    assert payload["data"]["items"][0]["scientific"]["scientificStatus"] == "unreviewed"


@pytest.mark.asyncio
async def test_all_query_routes_have_stable_shapes(client) -> None:
    for path in (
        "/api/v1/capabilities",
        "/api/v1/overview",
        "/api/v1/runs/run-completed",
        "/api/v1/runs/run-completed/result",
        "/api/v1/runs/run-completed/result/versions",
        "/api/v1/deployments",
        "/api/v1/infrastructure",
        "/api/v1/autonomy-policy",
    ):
        response = await client.get(path)
        assert response.status_code == 200, path
        assert set(response.json()) == {"data", "sources", "errors"}


@pytest.mark.asyncio
async def test_deployments_without_snapshot_is_503(client) -> None:
    app = client.app
    app.state.container.prefect._prefect["source"]["available"] = False
    response = await client.get("/api/v1/deployments")
    assert response.status_code == 503
    assert response.json()["data"] is None
    assert response.json()["errors"][0]["code"] == "PREFECT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_test_scenario_control_is_closed_and_mock_only(client) -> None:
    response = await client.post("/api/v1/test/scenario", json={"scenario": "sleep-queued"})
    assert response.status_code == 200
    power = await client.get("/api/v1/infrastructure")
    assert power.json()["data"]["dormPower"]["mode"] == "sleep"


@pytest.mark.asyncio
async def test_unknown_run_is_404(client) -> None:
    response = await client.get("/api/v1/runs/not-real")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "NOT_FOUND"
