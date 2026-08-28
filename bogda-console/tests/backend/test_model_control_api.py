from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from bogda_console.app import create_app
from bogda_console.config import Settings


REAL_ENV = {
    "BOGDA_CONSOLE_PROFILE": "real-readonly",
    "PREFECT_API_URL": "http://127.0.0.1:4200/api",
}


async def real_profile_client(profile: str) -> AsyncClient:
    env = {**REAL_ENV, "BOGDA_CONSOLE_PROFILE": profile}
    app = create_app(Settings.from_env(env))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


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
    missing_rationale = await client.post(
        "/api/v1/decisions/decision-1",
        json={"actionId": "approve", "expectedRevision": 0},
    )
    assert missing_rationale.status_code == 409
    assert missing_rationale.json()["errors"][0]["code"] == "COMMAND_NOT_APPLICABLE"

    decision = await client.post(
        "/api/v1/decisions/decision-1",
        json={"actionId": "approve", "expectedRevision": 0, "rationale": "owner approved the budget trade-off"},
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
async def test_model_control_validation_and_not_found_are_typed(client) -> None:
    invalid_bodies = [
        ("/api/v1/decisions/decision-1", {"actionId": "", "expectedRevision": -1}),
        ("/api/v1/run-preparations/preview", {
            "projectId": "project-1", "intent": "invalid", "requestedModelTier": "turbo",
            "workload": {"inputTokens": 1, "outputTokens": 1, "expectedCalls": 1, "runtimeMinutes": 1},
            "allowedPreferences": {"preferOffPeak": True, "allowAutoUpgrade": True, "allowFlashDowngrade": True, "autoResume": True},
        }),
    ]
    for path, body in invalid_bodies:
        response = await client.post(path, json=body)
        assert response.status_code == 422
        assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"

    assert (await client.get("/api/v1/runs/not-real/model-budget")).json()["errors"][0]["code"] == "NOT_FOUND"
    assert (await client.post("/api/v1/decisions/not-real", json={"actionId": "approve", "expectedRevision": 0, "rationale": "x"})).json()["errors"][0]["code"] == "NOT_FOUND"
    unknown_preparation = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={"idempotencyKey": "unknown-preparation", "runPreparationId": "prep_missing"},
    )
    assert unknown_preparation.status_code == 404
    assert unknown_preparation.json()["errors"][0]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_stale_resolved_decision_conflicts_but_current_unknown_decision_is_not_found(client) -> None:
    resolved = await client.post(
        "/api/v1/decisions/decision-1",
        json={"actionId": "approve", "expectedRevision": 0, "rationale": "approved"},
    )
    assert resolved.status_code == 200

    stale = await client.post(
        "/api/v1/decisions/decision-1",
        json={"actionId": "approve", "expectedRevision": 0, "rationale": "retry"},
    )
    assert stale.status_code == 409
    stale_error = stale.json()["errors"][0]
    assert stale_error["code"] == "RESOURCE_CHANGED"
    assert stale_error["details"]["currentResource"]["revision"] == 1

    unknown = await client.post(
        "/api/v1/decisions/not-real",
        json={"actionId": "approve", "expectedRevision": 1, "rationale": "not applicable"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["errors"][0]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_policy_request_shapes_split_global_and_project_restore(client) -> None:
    global_missing_patch = await client.post(
        "/api/v1/model-policy/global", json={"expectedRevision": 0}
    )
    assert global_missing_patch.status_code == 422

    global_negative_revision = await client.post(
        "/api/v1/model-policy/global",
        json={"patch": {"defaultModelTier": "pro"}, "expectedRevision": -1},
    )
    assert global_negative_revision.status_code == 422

    project_restore = await client.post(
        "/api/v1/model-policy/projects/project-1",
        json={"patch": None, "expectedRevision": 0},
    )
    assert project_restore.status_code == 200
    project_negative_revision = await client.post(
        "/api/v1/model-policy/projects/project-1",
        json={"patch": None, "expectedRevision": -1},
    )
    assert project_negative_revision.status_code == 422


@pytest.mark.asyncio
async def test_precheck_failure_does_not_consume_preparation(client) -> None:
    preview = await client.post(
        "/api/v1/run-preparations/preview",
        json={
            "projectId": "bogda-main", "intent": "execute", "requestedModelTier": "auto",
            "workload": {"inputTokens": 10, "outputTokens": 10, "expectedCalls": 1, "runtimeMinutes": 1},
            "allowedPreferences": {"preferOffPeak": True, "allowAutoUpgrade": True, "allowFlashDowngrade": True, "autoResume": True},
        },
    )
    preparation_id = preview.json()["data"]["preparationId"]
    rejected = await client.post(
        "/api/v1/deployments/not-allowlisted/runs",
        json={"idempotencyKey": "bad", "runPreparationId": preparation_id},
    )
    assert rejected.status_code == 403
    accepted = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={"idempotencyKey": "good", "runPreparationId": preparation_id},
    )
    assert accepted.status_code == 200
    conflict = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={"idempotencyKey": "different", "runPreparationId": preparation_id},
    )
    assert conflict.status_code == 409
    assert conflict.json()["errors"][0]["code"] == "RESOURCE_CHANGED"


@pytest.mark.asyncio
async def test_misconfigured_deployment_precheck_does_not_consume_preparation(client, monkeypatch) -> None:
    preview = await client.post(
        "/api/v1/run-preparations/preview",
        json={
            "projectId": "bogda-main", "intent": "execute", "requestedModelTier": "auto",
            "workload": {"inputTokens": 10, "outputTokens": 10, "expectedCalls": 1, "runtimeMinutes": 1},
            "allowedPreferences": {"preferOffPeak": True, "allowAutoUpgrade": True, "allowFlashDowngrade": True, "autoResume": True},
        },
    )
    preparation_id = preview.json()["data"]["preparationId"]
    prefect = client.app.state.container.prefect
    original = prefect.get_work_pool_concurrency

    async def misconfigured(name: str):
        return (await original(name)).model_copy(update={"concurrency_limit": 2})

    monkeypatch.setattr(prefect, "get_work_pool_concurrency", misconfigured)
    rejected = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={"idempotencyKey": "bad-config", "runPreparationId": preparation_id},
    )
    assert rejected.status_code == 409
    monkeypatch.undo()
    accepted = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={"idempotencyKey": "good-config", "runPreparationId": preparation_id},
    )
    assert accepted.status_code == 200


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
    conflict = await client.post(
        "/api/v1/deployments/deployment-dorm/runs",
        json={"idempotencyKey": "different-prepared-submit", "runPreparationId": preparation_id},
    )
    assert conflict.status_code == 409
    assert conflict.json()["errors"][0]["code"] == "RESOURCE_CHANGED"


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["real-readonly", "allowlisted-test"])
async def test_real_profiles_are_unavailable_and_do_not_fallback_to_mock(profile: str) -> None:
    async with await real_profile_client(profile) as http:
        response = await http.get("/api/v1/decisions")
        assert response.status_code == 503
        assert response.json()["data"] is None
        assert response.json()["errors"][0]["code"] == "MODEL_CONTROL_UNAVAILABLE"

        capabilities = await http.get("/api/v1/capabilities")
        data = capabilities.json()["data"]
        assert data["canResolveModelDecision"] is False
        assert data["canSetModelPolicy"] is False
        assert data["canPreparePaidRun"] is False

        preview = await http.post("/api/v1/run-preparations/preview", json={
            "projectId": "project-1", "intent": "execute", "requestedModelTier": "auto",
            "workload": {"inputTokens": 1, "outputTokens": 1, "expectedCalls": 1, "runtimeMinutes": 1},
            "allowedPreferences": {"preferOffPeak": True, "allowAutoUpgrade": True, "allowFlashDowngrade": True, "autoResume": True},
        })
        assert preview.status_code == 503
        assert preview.json()["errors"][0]["code"] == "MODEL_CONTROL_UNAVAILABLE"
        mutation = await http.post("/api/v1/decisions/decision-1", json={"actionId": "approve", "expectedRevision": 0, "rationale": "x"})
        assert mutation.status_code == 403
        policy_mutation = await http.post("/api/v1/model-policy/global", json={"patch": {"defaultModelTier": "pro"}, "expectedRevision": 0})
        assert policy_mutation.status_code == 403
