from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

import pytest
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    ArtifactCreate,
    DeploymentScheduleCreate,
    WorkPoolCreate,
)
from prefect.client.schemas.schedules import IntervalSchedule
from prefect.settings import PREFECT_API_URL
from prefect.testing.utilities import prefect_test_harness

from bogda_console.adapters.prefect_api import PrefectApiAdapter
from bogda_console.config import Settings
from bogda_console.contracts.models import RunFilters
from bogda_console.services.commands import CommandService


@flow
def seeded_research_flow(sample: str = "ridge") -> str:
    return sample


@pytest.mark.asyncio
async def test_thin_adapter_against_official_local_prefect_harness() -> None:
    with prefect_test_harness(server_startup_timeout=60):
        api_url = PREFECT_API_URL.value()
        assert api_url is not None
        assert urlparse(api_url).port != 3100

        async with get_client() as client:
            flow_id = await client.create_flow(seeded_research_flow)
            await client.create_work_pool(
                WorkPoolCreate(
                    name="dorm-x86",
                    type="process",
                    base_job_template={},
                    concurrency_limit=1,
                )
            )
            cpu_queue = await client.create_work_queue(
                "cpu", work_pool_name="dorm-x86"
            )
            gpu_queue = await client.create_work_queue(
                "gpu", work_pool_name="dorm-x86"
            )
            deployment_id = await client.create_deployment(
                flow_id,
                "alpine-assay",
                schedules=[
                    DeploymentScheduleCreate(
                        schedule=IntervalSchedule(interval=timedelta(hours=1)),
                        active=True,
                        slug="hourly",
                    )
                ],
                parameters={
                    "project_id": "bogda-main",
                    "autonomy_mode": "supervised",
                },
                work_pool_name="dorm-x86",
                work_queue_name="cpu",
                parameter_openapi_schema={"type": "object"},
            )
            schedules = await client.read_deployment_schedules(deployment_id)
            schedule_id = schedules[0].id
            seeded_run = await client.create_flow_run_from_deployment(
                deployment_id,
                parameters={
                    "sample": "summit",
                    "project_id": "bogda-main",
                    "autonomy_mode": "supervised",
                },
            )
            base_payload = {
                "run_id": str(seeded_run.id),
                "job_id": "job-seeded",
                "execution_status": "Scheduled",
                "scientific_status": "unreviewed",
                "started_at": "2026-08-24T08:00:00Z",
                "finished_at": "2026-08-24T08:01:00Z",
                "executor": "prefect",
                "attempt": 1,
                "declared_artifacts": [],
                "summary": "first artifact",
                "future_core_field": "preserve-me",
            }
            await client.create_artifact(
                ArtifactCreate(
                    key=f"bogda-run-{seeded_run.id}",
                    type="bogda.run-result",
                    data=base_payload,
                    flow_run_id=seeded_run.id,
                )
            )
            latest_payload = {**base_payload, "summary": "newest artifact"}
            await client.create_artifact(
                ArtifactCreate(
                    key=f"bogda-run-{seeded_run.id}",
                    type="bogda.run-result",
                    data=latest_payload,
                    flow_run_id=seeded_run.id,
                )
            )

        settings = Settings.from_env(
            {
                "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
                "PREFECT_API_URL": api_url,
                "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": str(deployment_id),
                "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": str(schedule_id),
                "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": (
                    f"{cpu_queue.id},{gpu_queue.id}"
                ),
                "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "dorm-x86",
                "BOGDA_CONSOLE_REPLICA_COUNT": "1",
            }
        )
        adapter = PrefectApiAdapter(
            api_url=api_url,
            allowed_deployment_ids=settings.allowed_deployment_ids,
        )
        commands = CommandService(
            settings=settings,
            prefect=adapter,
            results=adapter,
        )

        pools = await adapter.list_work_pools()
        dorm = next(pool for pool in pools if pool.name == "dorm-x86")
        assert dorm.concurrency_limit == 1
        queue_names = {queue.name for queue in dorm.queues}
        assert {"cpu", "gpu"}.issubset(queue_names)

        runs = await adapter.list_runs(RunFilters(), None, 20)
        assert str(seeded_run.id) in {run.run_id for run in runs.items}
        latest = await adapter.get_latest(str(seeded_run.id))
        versions = await adapter.list_versions(str(seeded_run.id), None, 20)
        assert latest.result is not None
        assert latest.result.summary == "newest artifact"
        assert len(versions.items) == 2

        review = await commands.review(
            str(seeded_run.id),
            latest.artifact_id,
            "accepted",
            "reviewed against declared artifacts",
        )
        assert review.snapshot.result is not None
        assert review.snapshot.result.scientific_status == "accepted"
        assert review.snapshot.result.model_extra["future_core_field"] == "preserve-me"
        assert len((await adapter.list_versions(str(seeded_run.id), None, 20)).items) == 3

        submitted = await adapter.submit_registered_deployment(
            str(deployment_id),
            {"sample": "second"},
            "integration-submit-1",
        )
        assert submitted.deployment_id == str(deployment_id)
        await adapter.cancel_run(submitted.run_id)

        paused_deployment = await adapter.pause_schedule(
            str(deployment_id), str(schedule_id)
        )
        assert paused_deployment.schedules[0].active is False
        resumed_deployment = await adapter.resume_schedule(
            str(deployment_id), str(schedule_id)
        )
        assert resumed_deployment.schedules[0].active is True

        paused_queue = await adapter.pause_work_queue(str(cpu_queue.id))
        assert paused_queue.is_paused is True
        resumed_queue = await adapter.resume_work_queue(str(cpu_queue.id))
        assert resumed_queue.is_paused is False
