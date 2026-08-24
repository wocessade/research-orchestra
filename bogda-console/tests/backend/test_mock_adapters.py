from __future__ import annotations

import pytest

from bogda_console.adapters.mock_power import MockPowerAdapter
from bogda_console.adapters.mock_prefect import MockPrefectAdapter
from bogda_console.adapters.mock_run_results import MockRunResultAdapter, ReviewConflict


@pytest.mark.asyncio
async def test_newest_invalid_artifact_never_falls_back(fixture_loader) -> None:
    adapter = MockRunResultAdapter(fixture_loader("result-missing-invalid-conflict"))
    result = await adapter.get_latest("run-invalid")
    assert result.availability == "invalid"
    assert result.artifact_id == "artifact-invalid-newest"
    assert result.result is None
    assert result.validation_issues


@pytest.mark.asyncio
async def test_missing_result_is_authoritative(fixture_loader) -> None:
    adapter = MockRunResultAdapter(fixture_loader("result-missing-invalid-conflict"))
    result = await adapter.get_latest("run-missing")
    assert result.availability == "missing"
    assert result.artifact_id is None


@pytest.mark.asyncio
async def test_dorm_capacity_comes_from_one_pool(fixture_loader) -> None:
    adapter = MockPrefectAdapter(fixture_loader("normal-active"))
    pools = await adapter.list_work_pools()
    dorm = next(pool for pool in pools if pool.name == "dorm-x86")
    assert dorm.concurrency_limit == 1
    assert dorm.active_slots == 1
    assert {queue.name for queue in dorm.queues} == {"cpu", "gpu"}


@pytest.mark.asyncio
async def test_mock_state_resets_with_new_adapter_instance(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    changed = MockPrefectAdapter(fixture)
    await changed.pause_work_queue("queue-cpu")
    assert (await changed.get_work_queue("queue-cpu")).is_paused is True
    reset = MockPrefectAdapter(fixture)
    assert (await reset.get_work_queue("queue-cpu")).is_paused is False


@pytest.mark.asyncio
async def test_review_appends_and_preserves_unknown_payload_fields(fixture_loader) -> None:
    adapter = MockRunResultAdapter(fixture_loader("result-missing-invalid-conflict"))
    before = await adapter.get_latest("run-review")
    after = await adapter.append_review(
        "run-review", before.artifact_id, "accepted", "evidence checked"
    )
    versions = await adapter.list_versions("run-review", None, 20)
    assert after.artifact_id != before.artifact_id
    assert after.result is not None
    assert after.result.scientific_status == "accepted"
    assert after.result.model_extra["future_core_field"] == "kept"
    assert len(versions.items) == 3


@pytest.mark.asyncio
async def test_review_conflict_exposes_current_newest(fixture_loader) -> None:
    adapter = MockRunResultAdapter(fixture_loader("result-missing-invalid-conflict"))
    with pytest.raises(ReviewConflict) as error:
        await adapter.append_review("run-review", "artifact-old", "rejected", "stale")
    assert error.value.current_resource.artifact_id == "artifact-newest"


@pytest.mark.asyncio
async def test_power_adapter_is_read_only_and_mock_labeled(fixture_loader) -> None:
    adapter = MockPowerAdapter(fixture_loader("normal-active"))
    power = await adapter.get_dorm_status()
    assert adapter.source_mode == "mock"
    assert power.mode == "compute"
    assert power.host == "dorm-x86"
