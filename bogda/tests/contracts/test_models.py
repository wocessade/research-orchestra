from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from bogda.contracts import (
    ExecutorKind,
    ModelTier,
    RunBudgetEnvelope,
    TaskIntent,
)
from bogda.contracts.models import (
    ArtifactSpec,
    AutonomyMode,
    ExecutionStatus,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
)


def budget(requested_tier: str = "pro") -> RunBudgetEnvelope:
    return RunBudgetEnvelope(
        expected_cost="2.880000",
        authorized_ceiling="5.320000",
        minimum_remaining="10.000000",
        requested_tier=requested_tier,
        fallback_tier="flash",
        budget_source="project",
        pricing_version="deepseek-cn-2026-08-28",
    )


def test_job_request_defaults_are_conservative() -> None:
    request = JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="shell",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        parameters={"argv": ["python", "-V"]},
        expected_artifacts=(ArtifactSpec(path="result.txt"),),
    )

    assert request.retryable is False
    assert request.resource_class is ResourceClass.CPU
    assert request.expected_artifacts[0].required is True
    assert request.schema_version == 1
    assert request.intent is TaskIntent.EXECUTE
    assert request.model_tier is ModelTier.AUTO
    assert request.executor is ExecutorKind.SHELL
    assert request.budget is None


def test_dsh_request_requires_budget() -> None:
    with pytest.raises(ValidationError, match="dsh requests require a budget"):
        JobRequest(
            job_id="job-2",
            project_id="project-1",
            task_type="legacy-orchestra-task",
            resource_class=ResourceClass.CPU,
            autonomy_mode=AutonomyMode.SUPERVISED,
            executor="dsh",
            model_tier="pro",
        )


def test_explicit_model_tier_must_match_budget() -> None:
    with pytest.raises(
        ValidationError, match="model_tier must match budget.requested_tier"
    ):
        JobRequest(
            job_id="job-3",
            project_id="project-1",
            task_type="research",
            resource_class=ResourceClass.CPU,
            autonomy_mode=AutonomyMode.SUPERVISED,
            executor="dsh",
            model_tier="flash",
            budget=budget("pro"),
        )


def test_versioned_request_round_trips_without_changing_frozen_axes() -> None:
    request = JobRequest(
        job_id="job-4",
        project_id="project-1",
        task_type="shell",
        resource_class="cpu",
        autonomy_mode="supervised",
        intent="audit",
        model_tier="auto",
    )

    restored = JobRequest.model_validate_json(request.model_dump_json())

    assert restored == request
    assert restored.schema_version == 1
    assert restored.intent is TaskIntent.AUDIT
    assert restored.schedule_policy.price_preference.value == (
        "cheapest_before_deadline"
    )


def test_job_request_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError):
        JobRequest(
            schema_version=2,
            job_id="job-5",
            project_id="project-1",
            task_type="shell",
            resource_class="cpu",
            autonomy_mode="supervised",
        )


def test_job_request_rejects_unknown_fields_instead_of_using_defaults() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        JobRequest(
            job_id="job-6",
            project_id="project-1",
            task_type="shell",
            resource_class="cpu",
            autonomy_mode="supervised",
            intnet="audit",
        )


def test_run_result_starts_unreviewed_and_round_trips_json() -> None:
    now = datetime.now(UTC)
    result = RunResult(
        run_id="36c86e99-d0a1-4399-a30c-4d6c5044444c",
        job_id="job-1",
        execution_status=ExecutionStatus.COMPLETED,
        started_at=now,
        finished_at=now,
        executor="shell",
        attempt=1,
        declared_artifacts=(),
        summary="completed",
    )

    restored = RunResult.model_validate_json(result.model_dump_json())

    assert restored.scientific_status is ScientificStatus.UNREVIEWED
    assert restored == result
