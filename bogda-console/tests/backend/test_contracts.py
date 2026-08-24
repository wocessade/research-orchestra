from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from bogda_console.contracts.models import (
    ApiErrorCode,
    PrefectStateSnapshot,
    ProjectContext,
    RunSummary,
    ScientificSummary,
    ValidRunResult,
    command_version,
)


def valid_payload() -> dict[str, object]:
    return {
        "run_id": "run-1",
        "job_id": "job-1",
        "execution_status": "Completed",
        "scientific_status": "unreviewed",
        "started_at": "2026-08-24T00:00:00Z",
        "finished_at": "2026-08-24T00:02:00Z",
        "executor": "shell",
        "attempt": 1,
        "declared_artifacts": [],
        "summary": "done",
        "review_summary": None,
        "future_core_field": "preserve me",
    }


def test_completed_and_unreviewed_are_separate_fields() -> None:
    run = RunSummary.model_validate(
        {
            "runId": "run-1",
            "name": "alpine assay",
            "state": {
                "type": "COMPLETED",
                "name": "Completed",
                "timestamp": "2026-08-24T01:00:00Z",
                "terminal": True,
            },
            "scientific": {
                "availability": "available",
                "artifactId": "artifact-1",
                "artifactCreatedAt": "2026-08-24T01:01:00Z",
                "scientificStatus": "unreviewed",
                "reviewSummary": None,
                "validationIssues": [],
            },
            "commandVersion": "opaque",
        }
    )
    assert run.state.type == "COMPLETED"
    assert run.scientific is not None
    assert run.scientific.scientific_status == "unreviewed"


def test_unavailable_project_mode_has_one_wire_shape() -> None:
    context = ProjectContext(
        projectId="p1", effectiveAutonomyMode=None, modeSource="unavailable", writable=False
    )
    assert context.effective_autonomy_mode is None
    with pytest.raises(ValidationError, match="unavailable"):
        ProjectContext(
            projectId="p1",
            effectiveAutonomyMode="supervised",
            modeSource="unavailable",
            writable=False,
        )


def test_error_codes_are_closed() -> None:
    assert ApiErrorCode("COMMAND_OUTCOME_UNKNOWN").value == "COMMAND_OUTCOME_UNKNOWN"
    with pytest.raises(ValueError):
        ApiErrorCode("AD_HOC_ERROR")


def test_valid_result_keeps_unknown_core_fields() -> None:
    result = ValidRunResult.model_validate(valid_payload())
    assert result.model_extra == {"future_core_field": "preserve me"}


def test_invalid_newest_result_does_not_parse() -> None:
    payload = valid_payload()
    payload["scientific_status"] = "proven"
    with pytest.raises(ValidationError):
        ValidRunResult.model_validate(payload)


def test_run_result_requires_utc_aware_times() -> None:
    payload = valid_payload()
    payload["started_at"] = "2026-08-24T00:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        ValidRunResult.model_validate(payload)


def test_wire_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ScientificSummary.model_validate(
            {
                "availability": "missing",
                "validationIssues": [],
                "surprise": True,
            }
        )


def test_command_version_is_deterministic_and_changes_with_authority() -> None:
    first = command_version({"runId": "r1", "type": "RUNNING", "name": "Running"})
    same = command_version({"name": "Running", "type": "RUNNING", "runId": "r1"})
    changed = command_version({"runId": "r1", "type": "COMPLETED", "name": "Completed"})
    assert first == same
    assert first != changed
    assert len(first) == 64


def test_prefect_state_preserves_raw_intermediate_name() -> None:
    state = PrefectStateSnapshot(
        type="SCHEDULED",
        name="AwaitingConcurrencySlot",
        timestamp=datetime(2026, 8, 24, tzinfo=UTC),
        terminal=False,
    )
    assert state.name == "AwaitingConcurrencySlot"
