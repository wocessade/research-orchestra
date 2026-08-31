from __future__ import annotations

from datetime import datetime

import pytest

from bogda_console.adapters.mock_power import MockPowerAdapter
from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter
from bogda_console.config import Settings
from bogda_console.contracts.models import RunFilters
from bogda_console.services.errors import SourceUnavailable
from bogda_console.services.queries import QueryService


def service_for(fixture: dict[str, object], **overrides: str) -> QueryService:
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service,deployment-dorm",
            "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-service,schedule-dorm",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-service,queue-cpu,queue-gpu",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "pi-service,dorm-x86",
            **overrides,
        }
    )
    clock = datetime.fromisoformat(str(fixture["clock"]).replace("Z", "+00:00"))
    return QueryService(
        settings=settings,
        prefect=MockPrefectAdapter(fixture),
        results=MockRunResultAdapter(fixture),
        power=MockPowerAdapter(fixture),
        now=lambda: clock,
    )


@pytest.mark.asyncio
async def test_capabilities_report_sorted_allowlist_scope_and_checkpoint_decision(fixture_loader) -> None:
    service = service_for(
        fixture_loader("normal-active"),
        BOGDA_CONSOLE_PROFILE="allowlisted-test",
        BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS="deployment-z,deployment-a",
        BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS="schedule-z,schedule-a",
        BOGDA_CONSOLE_ALLOWED_QUEUE_IDS="queue-z,queue-a",
        BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES="pool-z,pool-a",
    )

    snapshot = (await service.capabilities()).data

    assert snapshot.can_decide_checkpoint is True
    assert snapshot.can_review_scientific_result is True
    assert snapshot.allowed_deployment_ids == ["deployment-a", "deployment-z"]
    assert snapshot.allowed_schedule_ids == ["schedule-a", "schedule-z"]
    assert snapshot.allowed_queue_ids == ["queue-a", "queue-z"]
    assert snapshot.allowed_work_pool_names == ["pool-a", "pool-z"]


@pytest.mark.asyncio
async def test_readonly_capabilities_report_configured_scope_without_enabling_commands(fixture_loader) -> None:
    service = service_for(
        fixture_loader("normal-active"),
        BOGDA_CONSOLE_PROFILE="real-readonly",
        BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS="deployment-a",
        BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS="schedule-a",
        BOGDA_CONSOLE_ALLOWED_QUEUE_IDS="queue-a",
        BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES="pool-a",
    )

    snapshot = (await service.capabilities()).data

    assert snapshot.can_decide_checkpoint is False
    assert snapshot.can_review_scientific_result is False
    assert snapshot.can_submit_registered_deployment is False
    assert snapshot.allowed_deployment_ids == ["deployment-a"]
    assert snapshot.allowed_schedule_ids == ["schedule-a"]
    assert snapshot.allowed_queue_ids == ["queue-a"]
    assert snapshot.allowed_work_pool_names == ["pool-a"]


@pytest.mark.asyncio
async def test_multi_replica_mock_all_disables_checkpoint_decisions(fixture_loader) -> None:
    service = service_for(
        fixture_loader("normal-active"),
        BOGDA_CONSOLE_PROFILE="mock-all",
        BOGDA_CONSOLE_REPLICA_COUNT="2",
    )

    snapshot = (await service.capabilities()).data

    assert snapshot.can_decide_checkpoint is False
    assert snapshot.can_review_scientific_result is False


@pytest.mark.asyncio
async def test_run_list_projects_science_without_merging_authorities(fixture_loader) -> None:
    service = service_for(fixture_loader("normal-active"))
    response = await service.runs(RunFilters(), None, 50)
    completed = next(item for item in response.data.items if item.run_id == "run-completed")
    assert completed.state.type == "COMPLETED"
    assert completed.scientific.scientific_status == "unreviewed"
    assert response.sources["prefect"].freshness == "fresh"
    assert response.sources["runResult"].freshness == "fresh"


@pytest.mark.asyncio
async def test_prefect_failure_after_success_returns_stale_run_snapshot(fixture_loader) -> None:
    service = service_for(fixture_loader("normal-active"))
    first = await service.runs(RunFilters(), None, 50)
    service.prefect._prefect["source"]["available"] = False
    second = await service.runs(RunFilters(), None, 50)
    assert [run.run_id for run in second.data.items] == [run.run_id for run in first.data.items]
    assert second.sources["prefect"].freshness == "stale"
    assert second.errors[0].code == "PREFECT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_run_list_never_fabricates_empty_when_prefect_unavailable(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    fixture["prefect"]["source"]["available"] = False
    service = service_for(fixture)
    with pytest.raises(SourceUnavailable) as error:
        await service.runs(RunFilters(), None, 50)
    assert error.value.code == "PREFECT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_infrastructure_keeps_power_when_prefect_has_no_snapshot(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    fixture["prefect"]["source"]["available"] = False
    service = service_for(fixture)
    response = await service.infrastructure()
    assert response.data.pools is None
    assert response.data.dorm_power.mode == "compute"
    assert response.sources["prefect"].freshness == "unavailable"
    assert response.sources["power"].freshness == "fresh"


@pytest.mark.asyncio
async def test_last_good_run_pages_are_scoped_to_the_complete_query(fixture_loader) -> None:
    service = service_for(fixture_loader("normal-active"))
    first = await service.runs(RunFilters(executionType="RUNNING"), None, 1)
    assert [run.run_id for run in first.data.items] == ["run-active"]
    service.prefect._prefect["source"]["available"] = False
    with pytest.raises(SourceUnavailable):
        await service.runs(RunFilters(executionType="COMPLETED"), None, 20)


@pytest.mark.asyncio
async def test_overview_preserves_a_partial_source_failure(fixture_loader, monkeypatch) -> None:
    service = service_for(fixture_loader("normal-active"))

    async def unavailable_runs(*args, **kwargs):
        raise SourceUnavailable(
            "PREFECT_UNAVAILABLE",
            "prefect read failed",
            source="prefect",
            retryable=True,
            status_code=503,
        )

    monkeypatch.setattr(service, "runs", unavailable_runs)

    response = await service.overview()

    assert response.data.execution is None
    # Infrastructure still observed Prefect successfully, so its source metadata
    # remains fresh while the failed runs projection is retained as an error.
    assert response.sources["prefect"].freshness == "fresh"
    assert any(error.code == "PREFECT_UNAVAILABLE" for error in response.errors)


@pytest.mark.asyncio
async def test_overview_does_not_present_missing_run_results_as_empty_science(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    fixture["runResults"]["source"]["available"] = False

    response = await service_for(fixture).overview()

    assert response.data.execution is not None
    assert response.data.science is None
    assert any(error.code == "RUN_RESULT_UNAVAILABLE" for error in response.errors)


@pytest.mark.asyncio
async def test_overview_keeps_power_but_marks_missing_pool_source_unavailable(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    fixture["prefect"]["source"]["available"] = False

    response = await service_for(fixture).overview()

    assert response.data.infrastructure is None
    assert response.data.power is not None
    assert response.data.power.mode == "compute"
