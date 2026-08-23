from bogda.contracts import (
    AutonomyMode,
    JobRequest,
    ResourceClass,
    ScientificStatus,
)
from bogda.flows import shell_job


def request(retryable: bool = False) -> JobRequest:
    return JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="shell",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        parameters={"argv": ["python", "-V"]},
        retryable=retryable,
    )


def test_retry_count_is_zero_by_default_and_one_when_declared() -> None:
    assert shell_job.retry_count(request()) == 0
    assert shell_job.retry_count(request(retryable=True)) == 1


def test_apply_review_changes_scientific_state_without_execution_state() -> None:
    original = shell_job.RunResult.model_validate(
        {
            "run_id": "36c86e99-d0a1-4399-a30c-4d6c5044444c",
            "job_id": "job-1",
            "execution_status": "Completed",
            "scientific_status": "unreviewed",
            "started_at": "2026-08-24T00:00:00Z",
            "finished_at": "2026-08-24T00:00:01Z",
            "executor": "shell",
            "attempt": 1,
            "declared_artifacts": [],
            "summary": "completed",
        }
    )

    reviewed = shell_job.apply_review(
        original,
        ScientificStatus.ACCEPTED,
        "human accepted",
    )

    assert reviewed.execution_status == original.execution_status
    assert reviewed.scientific_status is ScientificStatus.ACCEPTED
    assert reviewed.summary == original.summary
    assert reviewed.review_summary == "human accepted"
