from types import SimpleNamespace

import pytest

from bogda.contracts import (
    AutonomyMode,
    ExecutorKind,
    ExecutionStatus,
    JobRequest,
    ModelTier,
    ResourceClass,
    RunResult,
    ScientificStatus,
)
from bogda.flows import shell_job


@pytest.fixture(autouse=True)
def auto_approve_checkpoints(monkeypatch) -> None:
    monkeypatch.setattr(shell_job, "wait_for_decision", lambda *_args, **_kwargs: None)


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


def test_shell_request_keeps_conservative_execution_axes() -> None:
    shell_request = request()

    assert shell_request.executor is ExecutorKind.SHELL
    assert shell_request.model_tier is ModelTier.AUTO
    assert shell_request.budget is None


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


def result_for(run_id: str, execution_status: ExecutionStatus) -> RunResult:
    return RunResult.model_validate(
        {
            "run_id": run_id,
            "job_id": "job-1",
            "execution_status": execution_status,
            "scientific_status": "unreviewed",
            "started_at": "2026-08-24T00:00:00Z",
            "finished_at": "2026-08-24T00:00:01Z",
            "executor": "shell",
            "attempt": 1,
            "declared_artifacts": [],
            "summary": "completed",
        }
    )


@pytest.mark.parametrize(("retryable", "expected_retries"), [(False, 0), (True, 1)])
def test_flow_configures_retries_and_saves_completed_result(
    monkeypatch,
    retryable: bool,
    expected_retries: int,
) -> None:
    run_id = "36c86e99-d0a1-4399-a30c-4d6c5044444c"
    retries_seen = []
    saved = []

    class FakeShellTask:
        def with_options(self, *, retries):
            retries_seen.append(retries)

            def invoke(_request_data, _attempts_root, task_run_id):
                return result_for(task_run_id, ExecutionStatus.COMPLETED).model_dump(
                    mode="json"
                )

            return invoke

    monkeypatch.setattr(
        shell_job,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=run_id)),
    )
    monkeypatch.setattr(shell_job, "execute_shell_task", FakeShellTask())
    monkeypatch.setattr(shell_job, "save_run_result", saved.append)

    returned = shell_job.run_shell_job.fn(
        request(retryable=retryable).model_dump(mode="json"),
        "attempts",
    )

    assert retries_seen == [expected_retries]
    assert saved == [RunResult.model_validate(returned)]
    assert saved[0].execution_status is ExecutionStatus.COMPLETED


def test_flow_saves_failed_result_before_reraising(monkeypatch) -> None:
    run_id = "36c86e99-d0a1-4399-a30c-4d6c5044444c"
    saved = []
    failed = result_for(run_id, ExecutionStatus.FAILED)

    class FakeShellTask:
        def with_options(self, *, retries):
            assert retries == 0

            def invoke(_request_data, _attempts_root, _task_run_id):
                raise shell_job.JobExecutionError(failed)

            return invoke

    monkeypatch.setattr(
        shell_job,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=run_id)),
    )
    monkeypatch.setattr(shell_job, "execute_shell_task", FakeShellTask())
    monkeypatch.setattr(shell_job, "save_run_result", saved.append)

    with pytest.raises(shell_job.JobExecutionError) as raised:
        shell_job.run_shell_job.fn(request().model_dump(mode="json"), "attempts")

    assert raised.value.result == failed
    assert saved == [failed]
