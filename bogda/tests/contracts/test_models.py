from datetime import UTC, datetime

from bogda.contracts.models import (
    ArtifactSpec,
    AutonomyMode,
    ExecutionStatus,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
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
