from __future__ import annotations

import pytest

from bogda_console.adapters.unwired_model_control import UnwiredModelControlAdapter


@pytest.mark.asyncio
async def test_model_control_queries_return_envelopes_with_source_metadata(client) -> None:
    decisions = await client.get("/api/v1/decisions")
    assert decisions.status_code == 200
    payload = decisions.json()
    assert set(payload) == {"data", "sources", "errors"}
    assert payload["sources"]["modelControl"]["sourceMode"] == "mock"
    assert payload["data"]["items"][0]["decisionId"] == "decision-1"

    budget = await client.get("/api/v1/runs/run-1/model-budget")
    assert budget.status_code == 200
    assert budget.json()["data"]["state"] == "awaiting-approval"

    policy = await client.get("/api/v1/model-policy?projectId=project-1")
    assert policy.status_code == 200
    assert policy.json()["data"]["source"] == "global"


@pytest.mark.asyncio
async def test_capabilities_expose_model_control_flags_only_in_mock_all(client) -> None:
    response = await client.get("/api/v1/capabilities")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["canResolveModelDecision"] is True
    assert data["canSetModelPolicy"] is True
    assert data["canPreparePaidRun"] is True


@pytest.mark.asyncio
async def test_preview_passes_workload_and_allowed_preferences_and_body_is_closed(client) -> None:
    body = {
        "projectId": "project-1",
        "intent": "explore",
        "requestedModelTier": "pro",
        "workload": {
            "inputTokens": 1000,
            "outputTokens": 500,
            "expectedCalls": 2,
            "runtimeMinutes": 10,
        },
        "allowedPreferences": {
            "preferOffPeak": True,
            "allowAutoUpgrade": True,
            "allowFlashDowngrade": True,
            "autoResume": False,
        },
        "deadline": "2026-08-29T12:00:00Z",
    }
    preview = await client.post("/api/v1/run-preparations/preview", json=body)
    assert preview.status_code == 200
    assert preview.json()["sources"]["modelControl"]["source"] == "modelControl"
    assert preview.json()["data"]["workload"] == body["workload"]
    assert preview.json()["data"]["allowedPreferences"] == body["allowedPreferences"]

    extra = await client.post(
        "/api/v1/run-preparations/preview", json={**body, "unexpected": True}
    )
    assert extra.status_code == 422
    assert extra.json()["errors"][0]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_revisioned_mutations_return_receipts_and_current_resource_on_conflict(client) -> None:
    decision = await client.post(
        "/api/v1/decisions/decision-1",
        json={"actionId": "approve", "expectedRevision": 0},
    )
    assert decision.status_code == 200
    assert decision.json()["data"]["command"] == "resolveDecision"

    stale = await client.post(
        "/api/v1/model-policy/global",
        json={
            "patch": {"defaultModelTier": "pro"},
            "expectedRevision": 0,
        },
    )
    assert stale.status_code == 409
    error = stale.json()["errors"][0]
    assert error["code"] == "RESOURCE_CHANGED"
    assert error["details"]["currentResource"]["revision"] == 1

    policy = await client.post(
        "/api/v1/model-policy/global",
        json={
            "patch": {"defaultModelTier": "pro"},
            "expectedRevision": 1,
        },
    )
    assert policy.status_code == 200
    assert policy.json()["data"]["command"] == "setGlobalModelPolicy"


@pytest.mark.asyncio
async def test_submit_confirms_exact_preview_before_registered_deployment(client) -> None:
    preview = await client.post(
        "/api/v1/run-preparations/preview",
        json={
            "projectId": "bogda-main",
            "intent": "execute",
            "requestedModelTier": "auto",
            "workload": {
                "inputTokens": 10,
                "outputTokens": 10,
                "expectedCalls": 1,
                "runtimeMinutes": 1,
            },
            "allowedPreferences": {
                "preferOffPeak": True,
                "allowAutoUpgrade": True,
                "allowFlashDowngrade": True,
                "autoResume": True,
            },
        },
    )
    preparation_id = preview.json()["data"]["preparationId"]
    submitted = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={
            "parameters": {"sample": "prepared"},
            "idempotencyKey": "prepared-submit",
            "runPreparationId": preparation_id,
        },
    )
    assert submitted.status_code == 200
    assert client.app.state.container.commands._model_control._preparations[preparation_id].confirmed  # type: ignore[attr-defined]


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["real-readonly", "allowlisted-test"])
async def test_real_profiles_are_unavailable_and_do_not_fallback_to_mock(profile: str) -> None:
    from test_autonomy_policy import _client

    async with await _client(profile) as http:
        assert isinstance(http.app.state.container.model_control, UnwiredModelControlAdapter)  # type: ignore[attr-defined]
        response = await http.get("/api/v1/decisions")
        assert response.status_code == 503
        assert response.json()["data"] is None
        assert response.json()["errors"][0]["code"] == "MODEL_CONTROL_UNAVAILABLE"

        capabilities = await http.get("/api/v1/capabilities")
        data = capabilities.json()["data"]
        assert data["canResolveModelDecision"] is False
        assert data["canSetModelPolicy"] is False
        assert data["canPreparePaidRun"] is False
