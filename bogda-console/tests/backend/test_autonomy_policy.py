from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from bogda_console.app import create_app
from bogda_console.config import Settings


MOCK_ENV = {
    "BOGDA_CONSOLE_PROFILE": "mock-all",
    "BOGDA_CONSOLE_FIXTURE": "normal-active",
    "BOGDA_CONSOLE_TEST_MODE": "1",
    "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service,deployment-dorm",
    "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-service,schedule-dorm",
    "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-service,queue-cpu,queue-gpu",
    "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "pi-service,dorm-x86",
}


def _settings(profile: str = "mock-all", **extra: str) -> Settings:
    env = dict(MOCK_ENV)
    env["BOGDA_CONSOLE_PROFILE"] = profile
    if profile != "mock-all":
        env["PREFECT_API_URL"] = "http://127.0.0.1:4200/api"
    env.update(extra)
    return Settings.from_env(env)


async def _client(profile: str = "mock-all"):
    app = create_app(_settings(profile))
    http = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    http.app = app  # type: ignore[attr-defined]
    return http


def _snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload["data"]
    if isinstance(data, dict) and "snapshot" in data:
        return data["snapshot"]
    return data


@pytest.mark.asyncio
async def test_mock_policy_defaults_to_supervised_revision_zero(client) -> None:
    response = await client.get("/api/v1/autonomy-policy")
    assert response.status_code == 200
    snapshot = _snapshot(response.json())
    assert snapshot["globalDefault"] == "supervised"
    assert snapshot["projectOverrides"] == {}
    assert snapshot["revision"] == 0


@pytest.mark.asyncio
async def test_setting_global_mode_increments_revision(client) -> None:
    first = await client.post(
        "/api/v1/autonomy-policy/global",
        json={"mode": "manual", "expectedRevision": 0},
    )
    assert first.status_code == 200
    snapshot = _snapshot(first.json())
    assert snapshot["globalDefault"] == "manual"
    assert snapshot["revision"] == 1

    confirmed = await client.get("/api/v1/autonomy-policy")
    assert _snapshot(confirmed.json()) == snapshot


@pytest.mark.asyncio
async def test_project_override_takes_precedence_over_global(client) -> None:
    await client.post(
        "/api/v1/autonomy-policy/global",
        json={"mode": "manual", "expectedRevision": 0},
    )
    overridden = await client.post(
        "/api/v1/autonomy-policy/projects/bogda-main",
        json={"mode": "autonomous", "expectedRevision": 1},
    )
    assert overridden.status_code == 200
    snapshot = _snapshot(overridden.json())
    assert snapshot["globalDefault"] == "manual"
    assert snapshot["projectOverrides"]["bogda-main"] == "autonomous"
    assert snapshot["revision"] == 2


@pytest.mark.asyncio
async def test_null_project_mode_restores_global_inheritance(client) -> None:
    await client.post(
        "/api/v1/autonomy-policy/global",
        json={"mode": "manual", "expectedRevision": 0},
    )
    await client.post(
        "/api/v1/autonomy-policy/projects/bogda-main",
        json={"mode": "autonomous", "expectedRevision": 1},
    )
    cleared = await client.post(
        "/api/v1/autonomy-policy/projects/bogda-main",
        json={"mode": None, "expectedRevision": 2},
    )
    assert cleared.status_code == 200
    snapshot = _snapshot(cleared.json())
    assert "bogda-main" not in snapshot["projectOverrides"]
    assert snapshot["globalDefault"] == "manual"
    assert snapshot["revision"] == 3


@pytest.mark.asyncio
async def test_stale_expected_revision_is_409_and_does_not_overwrite(client) -> None:
    await client.post(
        "/api/v1/autonomy-policy/global",
        json={"mode": "manual", "expectedRevision": 0},
    )
    stale = await client.post(
        "/api/v1/autonomy-policy/global",
        json={"mode": "autonomous", "expectedRevision": 0},
    )
    assert stale.status_code == 409
    error = stale.json()["errors"][0]
    assert error["code"] == "RESOURCE_CHANGED"
    assert error["details"]["currentResource"]["globalDefault"] == "manual"
    assert error["details"]["currentResource"]["revision"] == 1

    current = await client.get("/api/v1/autonomy-policy")
    assert _snapshot(current.json())["globalDefault"] == "manual"
    assert _snapshot(current.json())["revision"] == 1


@pytest.mark.asyncio
async def test_mock_all_capability_can_set_autonomy_mode(client) -> None:
    response = await client.get("/api/v1/capabilities")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["profile"] == "mock-all"
    assert data["canSetAutonomyMode"] is True
    assert data["projectId"] == "bogda-main"


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["real-readonly", "allowlisted-test"])
async def test_real_profiles_keep_can_set_autonomy_mode_false(profile: str) -> None:
    async with await _client(profile) as http:
        response = await http.get("/api/v1/capabilities")
        assert response.status_code == 200
        assert response.json()["data"]["profile"] == profile
        assert response.json()["data"]["canSetAutonomyMode"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["real-readonly", "allowlisted-test"])
async def test_write_disabled_profiles_cannot_call_policy_mutation(profile: str) -> None:
    async with await _client(profile) as http:
        policy = http.app.state.container.policy  # type: ignore[attr-defined]
        mutations: list[str] = []
        original_global = policy.set_global_mode
        original_project = policy.set_project_mode

        async def spy_global(*args: Any, **kwargs: Any) -> Any:
            mutations.append("global")
            return await original_global(*args, **kwargs)

        async def spy_project(*args: Any, **kwargs: Any) -> Any:
            mutations.append("project")
            return await original_project(*args, **kwargs)

        policy.set_global_mode = spy_global
        policy.set_project_mode = spy_project
        http.app.state.container.commands.policy = policy  # type: ignore[attr-defined]

        global_write = await http.post(
            "/api/v1/autonomy-policy/global",
            json={"mode": "manual", "expectedRevision": 0},
        )
        project_write = await http.post(
            "/api/v1/autonomy-policy/projects/bogda-main",
            json={"mode": "autonomous", "expectedRevision": 0},
        )
        assert global_write.status_code == 403
        assert project_write.status_code == 403
        assert global_write.json()["errors"][0]["code"] == "RESOURCE_NOT_ALLOWLISTED"
        assert project_write.json()["errors"][0]["code"] == "RESOURCE_NOT_ALLOWLISTED"
        assert mutations == []


@pytest.mark.asyncio
async def test_successful_write_returns_authoritative_snapshot(client) -> None:
    written = await client.post(
        "/api/v1/autonomy-policy/global",
        json={"mode": "autonomous", "expectedRevision": 0},
    )
    assert written.status_code == 200
    snapshot = _snapshot(written.json())
    reread = _snapshot((await client.get("/api/v1/autonomy-policy")).json())
    assert snapshot == reread
    assert snapshot["globalDefault"] == "autonomous"
    assert snapshot["revision"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["real-readonly", "allowlisted-test"])
async def test_real_profiles_do_not_silently_use_mock_policy(profile: str) -> None:
    from bogda_console.adapters.mock_autonomy_policy import MockAutonomyPolicyAdapter

    async with await _client(profile) as http:
        policy = http.app.state.container.policy  # type: ignore[attr-defined]
        assert not isinstance(policy, MockAutonomyPolicyAdapter)
        response = await http.get("/api/v1/autonomy-policy")
        assert response.status_code == 503
        assert response.json()["data"] is None
        assert response.json()["errors"][0]["code"] == "AUTONOMY_POLICY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_policy_path_wires_real_store_for_owner(tmp_path) -> None:
    from bogda.policy import PolicyStore

    path = tmp_path / "autonomy-policy.json"
    env = {
        "BOGDA_CONSOLE_ROLE": "owner",
        "BOGDA_AUTONOMY_POLICY_PATH": str(path),
    }
    app = create_app(_settings("allowlisted-test", **env))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        caps = (await http.get("/api/v1/capabilities")).json()["data"]
        assert caps["canSetAutonomyMode"] is True
        assert caps["effectiveAutonomyMode"] == "supervised"

        initial = await http.get("/api/v1/autonomy-policy")
        assert initial.status_code == 200
        assert _snapshot(initial.json())["revision"] == 0

        written = await http.post(
            "/api/v1/autonomy-policy/global",
            json={"mode": "manual", "expectedRevision": 0},
        )
        assert written.status_code == 200
        assert _snapshot(written.json())["globalDefault"] == "manual"
        assert _snapshot(written.json())["revision"] == 1

    resolved = PolicyStore(path).resolve_mode("bogda-main")
    assert resolved.effective_mode.value == "manual"
    assert resolved.policy_revision == 1

    restarted = create_app(_settings("allowlisted-test", **env))
    async with AsyncClient(
        transport=ASGITransport(app=restarted), base_url="http://test"
    ) as http:
        persisted = _snapshot((await http.get("/api/v1/autonomy-policy")).json())
        assert persisted == {"globalDefault": "manual", "projectOverrides": {}, "revision": 1}


@pytest.mark.asyncio
async def test_policy_path_still_requires_owner(tmp_path) -> None:
    env = {
        "BOGDA_CONSOLE_ROLE": "operator",
        "BOGDA_AUTONOMY_POLICY_PATH": str(tmp_path / "autonomy-policy.json"),
    }
    app = create_app(_settings("allowlisted-test", **env))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        caps = (await http.get("/api/v1/capabilities")).json()["data"]
        assert caps["canSetAutonomyMode"] is False
        denied = await http.post(
            "/api/v1/autonomy-policy/global",
            json={"mode": "manual", "expectedRevision": 0},
        )
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_real_store_revision_conflict_is_409(tmp_path) -> None:
    env = {
        "BOGDA_CONSOLE_ROLE": "owner",
        "BOGDA_AUTONOMY_POLICY_PATH": str(tmp_path / "autonomy-policy.json"),
    }
    app = create_app(_settings("allowlisted-test", **env))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        first = await http.post(
            "/api/v1/autonomy-policy/projects/bogda-main",
            json={"mode": "autonomous", "expectedRevision": 0},
        )
        assert first.status_code == 200
        stale = await http.post(
            "/api/v1/autonomy-policy/projects/bogda-main",
            json={"mode": "manual", "expectedRevision": 0},
        )
        assert stale.status_code == 409
        error = stale.json()["errors"][0]
        assert error["code"] == "RESOURCE_CHANGED"
        assert error["details"]["currentResource"]["revision"] == 1
        assert (
            error["details"]["currentResource"]["projectOverrides"]["bogda-main"]
            == "autonomous"
        )
