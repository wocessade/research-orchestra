from __future__ import annotations

import copy
from datetime import datetime

import pytest

from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter
from bogda_console.config import Settings
from bogda_console.services.commands import CommandService
from bogda_console.services.errors import ServiceError


def harness(fixture: dict[str, object]) -> tuple[CommandService, MockPrefectAdapter, MockRunResultAdapter]:
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
    return CommandService(settings=settings, prefect=prefect, results=results, now=lambda: now), prefect, results


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
