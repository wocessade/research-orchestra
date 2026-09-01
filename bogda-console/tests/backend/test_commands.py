from __future__ import annotations

import copy
from datetime import datetime
from decimal import Decimal

import pytest

from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter
from bogda_console.adapters.mock_model_control import MockModelControlAdapter
from bogda_console.config import Settings
from bogda_console.services.commands import CommandService
from bogda_console.services.errors import ServiceError


def harness(
    fixture: dict[str, object], *, model_control=None
) -> tuple[CommandService, MockPrefectAdapter, MockRunResultAdapter]:
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "mock-all",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service,deployment-dorm",
            "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-service,schedule-dorm",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-service,queue-cpu,queue-gpu",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "pi-service,dorm-x86",
        }
    )
    prefect = MockPrefectAdapter(fixture)
    results = MockRunResultAdapter(fixture)
    now = datetime.fromisoformat(str(fixture["clock"]).replace("Z", "+00:00"))
    return CommandService(
        settings=settings,
        prefect=prefect,
        results=results,
        now=lambda: now,
        model_control=model_control,
    ), prefect, results


@pytest.mark.asyncio
async def test_stale_cancel_intent_stops_before_adapter_call(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    with pytest.raises(ServiceError) as error:
        await service.cancel("run-active", "old-command-version")
    assert error.value.code == "RESOURCE_CHANGED"
    assert prefect.cancel_calls == []


@pytest.mark.asyncio
async def test_cancel_authorization_comes_from_fresh_run_deployment(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    unauthorized = copy.deepcopy(prefect._prefect["deployments"][0])
    unauthorized["deploymentId"] = "deployment-not-allowed"
    prefect._prefect["deployments"].append(unauthorized)
    raw = next(run for run in prefect._prefect["runs"] if run["runId"] == "run-active")
    raw["deploymentId"] = "deployment-not-allowed"
    current = await prefect.get_run("run-active")
    with pytest.raises(ServiceError) as error:
        await service.cancel("run-active", current.run.command_version)
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"
    assert prefect.cancel_calls == []


@pytest.mark.asyncio
async def test_cancel_accepts_authoritative_cancelling_receipt(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    current = await prefect.get_run("run-active")
    receipt = await service.cancel("run-active", current.run.command_version)
    assert receipt.snapshot.state.name == "Cancelling"
    assert receipt.snapshot.deployment_id == "deployment-dorm"


@pytest.mark.asyncio
async def test_terminal_cancel_is_not_a_silent_success(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    current = await prefect.get_run("run-completed")
    with pytest.raises(ServiceError) as error:
        await service.cancel("run-completed", current.run.command_version)
    assert error.value.code == "COMMAND_NOT_APPLICABLE"


@pytest.mark.asyncio
async def test_dorm_submission_requires_prefect_pool_limit_one(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    dorm = next(pool for pool in prefect._prefect["pools"] if pool["name"] == "dorm-x86")
    dorm["concurrencyLimit"] = 2
    with pytest.raises(ServiceError) as error:
        await service.submit("deployment-dorm", {}, "intent-1")
    assert error.value.code == "INFRASTRUCTURE_MISCONFIGURED"
    assert prefect.submit_calls == []


@pytest.mark.asyncio
async def test_submitted_run_inherits_authorization_from_prefect_receipt(fixture_loader) -> None:
    service, _, _ = harness(fixture_loader("normal-active"))
    submitted = await service.submit("deployment-dorm", {"sample": "new"}, "intent-new")
    cancelled = await service.cancel(
        submitted.snapshot.run_id, submitted.snapshot.command_version
    )
    assert cancelled.snapshot.deployment_id == "deployment-dorm"


@pytest.mark.asyncio
async def test_schedule_must_belong_to_allowed_parent(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    service.settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service",
            "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-dorm",
        }
    )
    deployment = await prefect.get_deployment("deployment-dorm")
    with pytest.raises(ServiceError) as error:
        await service.pause_schedule(
            "deployment-dorm", "schedule-dorm", deployment.schedules[0].command_version
        )
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"


@pytest.mark.asyncio
async def test_queue_pause_and_resume_use_exact_pool_membership(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    before = await prefect.get_work_queue("queue-cpu")
    paused = await service.pause_queue("queue-cpu", before.command_version)
    assert paused.snapshot.is_paused is True
    resumed = await service.resume_queue("queue-cpu", paused.snapshot.command_version)
    assert resumed.snapshot.is_paused is False


@pytest.mark.asyncio
async def test_submit_rejects_allowlisted_deployment_on_pool_outside_allowlist(
    fixture_loader,
) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    service.settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "bogda-s2-pool",
        }
    )
    with pytest.raises(ServiceError) as error:
        await service.submit("deployment-service", {}, "intent-pool")
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"
    assert prefect.submit_calls == []


@pytest.mark.asyncio
async def test_queue_pause_rejects_allowlisted_queue_on_pool_outside_allowlist(
    fixture_loader,
) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    service.settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-cpu",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "bogda-s2-pool",
        }
    )
    before = await prefect.get_work_queue("queue-cpu")
    with pytest.raises(ServiceError) as error:
        await service.pause_queue("queue-cpu", before.command_version)
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"


@pytest.mark.asyncio
async def test_real_readonly_mutations_stop_before_adapter(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "real-readonly",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-dorm",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-cpu",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "dorm-x86,pi-service",
        }
    )
    prefect = MockPrefectAdapter(fixture)
    service = CommandService(
        settings=settings,
        prefect=prefect,
        results=MockRunResultAdapter(fixture),
    )
    with pytest.raises(ServiceError) as error:
        await service.submit("deployment-dorm", {}, "intent-ro")
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"
    assert prefect.submit_calls == []


@pytest.mark.asyncio
async def test_observer_submit_stops_before_adapter_despite_allowlist(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    service.settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ROLE": "observer",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-dorm",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "dorm-x86",
        }
    )
    with pytest.raises(ServiceError) as error:
        await service.submit("deployment-dorm", {}, "intent-observer")
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"
    assert prefect.submit_calls == []


@pytest.mark.asyncio
async def test_review_appends_after_fresh_prefect_ownership_read(fixture_loader) -> None:
    service, _, results = harness(fixture_loader("result-missing-invalid-conflict"))
    before = await results.get_latest("run-review")
    receipt = await service.review(
        "run-review", before.artifact_id, "accepted", "evidence checked"
    )
    assert receipt.snapshot.artifact_id != before.artifact_id
    assert receipt.snapshot.result.scientific_status == "accepted"
    assert receipt.snapshot.result.model_extra["future_core_field"] == "kept"


@pytest.mark.asyncio
async def test_review_conflict_exposes_current_resource(fixture_loader) -> None:
    service, _, _ = harness(fixture_loader("result-missing-invalid-conflict"))
    with pytest.raises(ServiceError) as error:
        await service.review("run-review", "artifact-old", "rejected", "stale form")
    assert error.value.code == "REVIEW_CONFLICT"
    assert error.value.details.current_resource["artifactId"] == "artifact-newest"


@pytest.mark.asyncio
async def test_prefect_pre_read_unavailable_is_source_scoped(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    prefect._prefect["source"]["available"] = False
    with pytest.raises(ServiceError) as error:
        await service.cancel("run-active", "unreadable")
    assert (error.value.code, error.value.status_code) == ("PREFECT_UNAVAILABLE", 503)


@pytest.mark.asyncio
async def test_rejection_and_failed_post_read_are_distinct(
    fixture_loader, monkeypatch
) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    current = await prefect.get_run("run-active")

    async def reject(_run_id: str):
        raise ValueError("transition rejected")

    monkeypatch.setattr(prefect, "cancel_run", reject)
    with pytest.raises(ServiceError) as rejected:
        await service.cancel("run-active", current.run.command_version)
    assert (rejected.value.code, rejected.value.status_code) == ("COMMAND_REJECTED", 409)

    service, prefect, _ = harness(fixture_loader("normal-active"))
    current = await prefect.get_run("run-active")
    original_get = prefect.get_run
    reads = 0

    async def fail_post_read(run_id: str):
        nonlocal reads
        reads += 1
        if reads == 2:
            raise ConnectionError("post-read unavailable")
        return await original_get(run_id)

    monkeypatch.setattr(prefect, "get_run", fail_post_read)
    with pytest.raises(ServiceError) as unknown:
        await service.cancel("run-active", current.run.command_version)
    assert (unknown.value.code, unknown.value.status_code) == ("COMMAND_OUTCOME_UNKNOWN", 503)


def _paused_checkpoint_run() -> dict[str, object]:
    return {
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
            "message": "waiting for experiment_approval",
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
    }


@pytest.mark.asyncio
async def test_checkpoint_approve_resumes_paused_run(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    fixture["prefect"]["runs"].insert(0, _paused_checkpoint_run())
    fixture["runResults"]["artifactsByRun"]["run-checkpoint"] = []
    service, prefect, _ = harness(fixture)
    receipt = await service.decide_checkpoint(
        "run-checkpoint", "checkpoint-v1", "approved", "可以做"
    )
    assert receipt.snapshot.run.state.name == "Running"
    assert receipt.snapshot.checkpoint.verdict == "approved"
    assert receipt.snapshot.checkpoint.stage == "accepted"
    assert prefect.resume_calls == ["run-checkpoint"]


@pytest.mark.asyncio
async def test_checkpoint_reject_cancels_instead_of_failing(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    fixture["prefect"]["runs"].insert(0, _paused_checkpoint_run())
    fixture["runResults"]["artifactsByRun"]["run-checkpoint"] = []
    service, _, _ = harness(fixture)
    receipt = await service.decide_checkpoint(
        "run-checkpoint", "checkpoint-v1", "rejected", "unsafe"
    )
    assert receipt.snapshot.run.state.type == "CANCELLED"
    assert receipt.snapshot.run.state.name == "Cancelled"
    assert receipt.snapshot.checkpoint.verdict == "rejected"
    assert receipt.snapshot.checkpoint.stage == "done"


@pytest.mark.asyncio
async def test_stale_checkpoint_version_stops_before_resume(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    fixture["prefect"]["runs"].insert(0, _paused_checkpoint_run())
    fixture["runResults"]["artifactsByRun"]["run-checkpoint"] = []
    service, prefect, _ = harness(fixture)
    with pytest.raises(ServiceError) as error:
        await service.decide_checkpoint("run-checkpoint", "stale", "approved", "no")
    assert error.value.code == "RESOURCE_CHANGED"
    assert prefect.resume_calls == []


@pytest.mark.asyncio
async def test_checkpoint_decision_is_disabled_for_multi_replica_mock_all(
    fixture_loader,
) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    service.settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "mock-all",
            "BOGDA_CONSOLE_REPLICA_COUNT": "2",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service,deployment-dorm",
        }
    )
    fixture = fixture_loader("normal-active")
    fixture["prefect"]["runs"].insert(0, _paused_checkpoint_run())
    prefect = MockPrefectAdapter(fixture)
    service.prefect = prefect

    with pytest.raises(ServiceError) as error:
        await service.decide_checkpoint(
            "run-checkpoint", "checkpoint-v1", "approved", "not safe to write"
        )

    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"
    assert prefect.resume_calls == []


@pytest.mark.asyncio
async def test_run_result_pre_read_unavailable_is_source_scoped(fixture_loader) -> None:
    service, _, results = harness(fixture_loader("result-missing-invalid-conflict"))
    results._source["source"]["available"] = False
    with pytest.raises(ServiceError) as error:
        await service.review("run-review", "artifact-newest", "accepted", "checked")
    assert (error.value.code, error.value.status_code) == ("RUN_RESULT_UNAVAILABLE", 503)


@pytest.mark.asyncio
async def test_decision_command_forwards_backend_required_owner_inputs(fixture_loader) -> None:
    model_control = MockModelControlAdapter()
    service, _, _ = harness(
        fixture_loader("normal-active"), model_control=model_control
    )

    reconciled = await service.resolve_decision(
        "decision-usage-unknown",
        "reconcile",
        0,
        actual_cost_cny=Decimal("0.50"),
    )
    item = next(
        value
        for value in reconciled.snapshot.items
        if value.decision_id == "decision-usage-unknown"
    )
    resolved = await service.resolve_decision(
        item.decision_id,
        "approve-retry",
        item.revision,
        new_call_id="call-retry-command",
    )

    assert item.actions[0].new_call_id_required is True
    assert item.decision_id not in {value.decision_id for value in resolved.snapshot.items}
