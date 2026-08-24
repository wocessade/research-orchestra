from __future__ import annotations

import json
from pathlib import Path

import pytest


FIXTURES = (
    "normal-active",
    "sleep-queued",
    "gaming-paused",
    "degraded-stale",
    "result-missing-invalid-conflict",
    "mobile-dense",
)


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_has_all_source_sections(name: str) -> None:
    data = json.loads((Path("fixtures") / f"{name}.json").read_text(encoding="utf-8"))
    assert set(data) == {"clock", "prefect", "runResults", "power"}
    assert data["power"]["sourceMode"] == "mock"


def test_power_modes_are_collectively_complete() -> None:
    modes = {
        json.loads(path.read_text(encoding="utf-8"))["power"]["mode"]
        for path in Path("fixtures").glob("*.json")
    }
    assert modes == {"sleep", "compute", "gaming", "maintenance"}


def test_normal_fixture_has_required_topology_and_dual_status() -> None:
    data = json.loads(Path("fixtures/normal-active.json").read_text(encoding="utf-8"))
    pools = {pool["name"]: pool for pool in data["prefect"]["pools"]}
    assert set(pools) == {"pi-service", "dorm-x86"}
    assert pools["dorm-x86"]["concurrencyLimit"] == 1
    assert {queue["name"] for queue in pools["dorm-x86"]["queues"]} == {"cpu", "gpu"}
    completed = next(run for run in data["prefect"]["runs"] if run["state"]["type"] == "COMPLETED")
    latest = data["runResults"]["artifactsByRun"][completed["runId"]][-1]
    assert latest["payload"]["scientific_status"] == "unreviewed"


def test_attention_fixture_has_missing_invalid_and_conflict_versions() -> None:
    data = json.loads(
        Path("fixtures/result-missing-invalid-conflict.json").read_text(encoding="utf-8")
    )
    by_run = data["runResults"]["artifactsByRun"]
    assert by_run["run-missing"] == []
    assert by_run["run-invalid"][-1]["artifactId"] == "artifact-invalid-newest"
    assert len(by_run["run-review"]) >= 2
