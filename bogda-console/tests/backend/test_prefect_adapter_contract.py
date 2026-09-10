from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from prefect.client.schemas.objects import Artifact
from prefect.states import Late

from bogda_console.adapters.prefect_api import PrefectApiAdapter
from bogda_console.contracts.models import RunFilters


class FakePrefectClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.deployment_id = uuid4()
        self.flow_id = uuid4()
        self.run_id = uuid4()
        self.queue_id = uuid4()
        self.queue_paused = False
        self.schedule_id = uuid4()
        self.run = SimpleNamespace(
            id=self.run_id,
            name="late ridge",
            flow_id=self.flow_id,
            deployment_id=self.deployment_id,
            work_pool_name="dorm-x86",
            work_queue_name="cpu",
            work_queue_id=self.queue_id,
            parameters={"project_id": "bogda-main", "autonomy_mode": "supervised"},
            tags=["cpu"],
            state=Late(timestamp=datetime(2026, 8, 24, 8, 0, tzinfo=UTC)),
            expected_start_time=datetime(2026, 8, 24, 8, 0, tzinfo=UTC),
            start_time=None,
            end_time=None,
            updated=datetime(2026, 8, 24, 8, 1, tzinfo=UTC),
        )
        self.schedule = SimpleNamespace(id=self.schedule_id, slug="daily", active=True, updated=datetime(2026, 8, 24, 7, 0, tzinfo=UTC), schedule="0 7 * * *")
        self.deployment = SimpleNamespace(
            id=self.deployment_id,
            name="alpine-assay",
            flow_id=self.flow_id,
            work_pool_name="dorm-x86",
            work_queue_name="cpu",
            parameter_openapi_schema={"type": "object"},
            parameters={"project_id": "bogda-main", "autonomy_mode": "supervised"},
            schedules=[self.schedule],
        )
        valid_payload = {
            "run_id": str(self.run_id), "job_id": "job-1", "execution_status": "Completed", "scientific_status": "unreviewed",
            "started_at": "2026-08-24T07:00:00Z", "finished_at": "2026-08-24T07:30:00Z", "executor": "shell", "attempt": 1,
            "declared_artifacts": [], "summary": "older valid", "future_core_field": "preserved",
        }
        self.artifacts = [
            Artifact(id=uuid4(), key=f"bogda-run-{self.run_id}", type="bogda.run-result", flow_run_id=self.run_id, data={"scientific_status": "proven"}, created=datetime(2026, 8, 24, 8, 2, tzinfo=UTC)),
            Artifact(id=uuid4(), key=f"bogda-run-{self.run_id}", type="bogda.run-result", flow_run_id=self.run_id, data=valid_payload, created=datetime(2026, 8, 24, 8, 1, tzinfo=UTC)),
        ]

    async def read_flow_runs(self, **kwargs):
        self.calls.append(("read_flow_runs", kwargs))
        return [self.run]

    async def read_flow_run(self, run_id):
        self.calls.append(("read_flow_run", run_id))
        return self.run

    async def read_deployment(self, deployment_id):
        self.calls.append(("read_deployment", deployment_id))
        return self.deployment

    async def read_deployments(self, **kwargs):
        self.calls.append(("read_deployments", kwargs))
        return [self.deployment]

    async def read_flow(self, flow_id):
        return SimpleNamespace(id=flow_id, name="alpine-assay")

    async def read_deployment_schedules(self, deployment_id):
        return [self.schedule]

    async def read_work_pools(self, **kwargs):
        return [SimpleNamespace(name="dorm-x86", status="READY", is_paused=False, concurrency_limit=1, active_slots=1)]

    async def read_work_pool(self, name):
        return SimpleNamespace(name=name, status="READY", is_paused=False, concurrency_limit=1, active_slots=1)

    async def read_work_queues(self, **kwargs):
        return [await self.read_work_queue(self.queue_id)]

    async def read_work_queue(self, queue_id):
        return SimpleNamespace(id=self.queue_id, name="cpu", status="PAUSED" if self.queue_paused else "READY", is_paused=self.queue_paused, concurrency_limit=None, updated=datetime(2026, 8, 24, 8, 0, tzinfo=UTC))

    async def read_workers_for_work_pool(self, name, **kwargs):
        return [SimpleNamespace(id=uuid4(), name="dorm-worker", status="ONLINE", last_heartbeat_time=datetime(2026, 8, 24, 8, 1, tzinfo=UTC))]

    async def read_artifacts(self, **kwargs):
        self.calls.append(("read_artifacts", kwargs))
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit")
        return self.artifacts[offset:][:limit]

    async def create_artifact(self, artifact):
        self.calls.append(("create_artifact", artifact))
        created = Artifact(id=uuid4(), created=datetime(2026, 8, 24, 8, 3, tzinfo=UTC), **artifact.model_dump())
        self.artifacts.insert(0, created)
        return created

    async def create_flow_run_from_deployment(self, deployment_id, **kwargs):
        self.calls.append(("create_flow_run_from_deployment", kwargs))
        return self.run

    async def set_flow_run_state(self, run_id, state, force=False):
        self.calls.append(("set_flow_run_state", state))
        self.run.state = state
        return SimpleNamespace()

    async def update_deployment_schedule(self, deployment_id, schedule_id, **kwargs):
        self.calls.append(("update_deployment_schedule", kwargs))
        self.schedule.active = kwargs["active"]

    async def update_work_queue(self, queue_id, **kwargs):
        self.calls.append(("update_work_queue", kwargs))
        self.queue_paused = kwargs["is_paused"]


@pytest.mark.asyncio
async def test_checkpoint_query_uses_artifact_safe_decision_key() -> None:
    run_id = uuid4()
    seen_keys: list[str] = []

    class CheckpointClient:
        async def read_artifacts(self, **kwargs):
            key = kwargs["artifact_filter"].key.any_[0]
            seen_keys.append(key)
            return [
                SimpleNamespace(
                    data={
                        "kind": "plan_approval",
                        "stage": "done",
                        "verdict": None,
                        "command_version": "checkpoint-v1",
                    }
                )
            ]

    checkpoint = await PrefectApiAdapter._checkpoint(CheckpointClient(), str(run_id))

    assert checkpoint is not None
    assert seen_keys == [f"bogda-decision-plan-approval-{run_id}"]


def test_default_client_passes_server_auth_string_to_prefect(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class ConstructorSpy:
        def __init__(self, api, **kwargs):
            captured["api"] = api
            captured["kwargs"] = kwargs

    monkeypatch.setattr("bogda_console.adapters.prefect_api.PrefectClient", ConstructorSpy)
    adapter = PrefectApiAdapter(
        api_url="http://127.0.0.1:8999/api",
        auth_string="auth-sentinel",
        api_key="api-key-sentinel",
    )

    adapter._default_client()

    assert captured == {
        "api": "http://127.0.0.1:8999/api",
        "kwargs": {"auth_string": "auth-sentinel"},
    }


@pytest.fixture
def fake_adapter():
    client = FakePrefectClient()

    @asynccontextmanager
    async def factory():
        yield client

    return PrefectApiAdapter(
        api_url="http://127.0.0.1:8999/api",
        client_factory=factory,
        allowed_deployment_ids=frozenset({str(client.deployment_id)}),
    ), client


@pytest.mark.asyncio
async def test_maps_raw_prefect_state_and_frozen_project_context(fake_adapter) -> None:
    adapter, client = fake_adapter
    page = await adapter.list_runs(RunFilters(executionType="SCHEDULED"), None, 20)
    assert page.next_cursor is None
    assert page.items[0].state.name == "Late"
    assert page.items[0].state.type == "SCHEDULED"
    assert page.items[0].deployment_name == "alpine-assay"
    detail = await adapter.get_run(str(client.run_id))
    assert detail.project_context.effective_autonomy_mode == "supervised"
    assert detail.project_context.mode_source == "frozen-run-request"
    call = next(value for name, value in client.calls if name == "read_flow_runs")
    assert call["limit"] == 21
    assert call["offset"] == 0


@pytest.mark.asyncio
async def test_maps_pool_queues_workers_and_exact_shared_limit(fake_adapter) -> None:
    adapter, _ = fake_adapter
    pool = (await adapter.list_work_pools())[0]
    assert pool.name == "dorm-x86"
    assert pool.concurrency_limit == 1
    assert pool.active_slots == 1
    assert [queue.name for queue in pool.queues] == ["cpu"]
    assert [worker.status for worker in pool.workers] == ["ONLINE"]


@pytest.mark.asyncio
async def test_newest_invalid_artifact_remains_authoritative(fake_adapter) -> None:
    adapter, client = fake_adapter
    latest = await adapter.get_latest(str(client.run_id))
    versions = await adapter.list_versions(str(client.run_id), None, 20)
    assert latest.artifact_id == str(client.artifacts[0].id)
    assert latest.availability == "invalid"
    assert latest.result is None
    assert [item.artifact_id for item in versions.items] == [str(item.id) for item in client.artifacts]


@pytest.mark.asyncio
async def test_append_review_preserves_unknown_fields_and_appends(fake_adapter) -> None:
    adapter, client = fake_adapter
    client.artifacts.pop(0)
    before = await adapter.get_latest(str(client.run_id))
    after = await adapter.append_review(str(client.run_id), before.artifact_id, "accepted", "checked")
    assert after.artifact_id != before.artifact_id
    assert after.result.scientific_status == "accepted"
    assert after.result.execution_status == before.result.execution_status
    assert after.result.model_extra["future_core_field"] == "preserved"
    assert len(client.artifacts) == 2


@pytest.mark.asyncio
async def test_commands_use_prefect_public_client_methods(fake_adapter) -> None:
    adapter, client = fake_adapter
    await adapter.submit_registered_deployment(str(client.deployment_id), {"sample": "ridge"}, "intent-1")
    await adapter.cancel_run(str(client.run_id))
    await adapter.pause_schedule(str(client.deployment_id), str(client.schedule_id))
    await adapter.resume_schedule(str(client.deployment_id), str(client.schedule_id))
    await adapter.pause_work_queue(str(client.queue_id))
    await adapter.resume_work_queue(str(client.queue_id))
    submit = next(value for name, value in client.calls if name == "create_flow_run_from_deployment")
    assert submit["parameters"] == {"sample": "ridge"}
    assert submit["idempotency_key"] == "intent-1"
    queue_updates = [value for name, value in client.calls if name == "update_work_queue"]
    assert queue_updates == [{"is_paused": True}, {"is_paused": False}]
