from pathlib import Path
from typing import Any

from prefect import flow, task
from prefect.context import get_run_context

from bogda.artifacts import load_run_result, save_run_result
from bogda.contracts import (
    ExecutionStatus,
    JobRequest,
    RunResult,
    ScientificStatus,
)
from bogda.executors import run_shell


class JobExecutionError(RuntimeError):
    def __init__(self, result: RunResult):
        super().__init__(result.summary)
        self.result = result


def retry_count(request: JobRequest) -> int:
    return 1 if request.retryable else 0


def apply_review(
    result: RunResult,
    scientific_status: ScientificStatus,
    summary: str | None,
) -> RunResult:
    updates: dict[str, Any] = {"scientific_status": scientific_status}
    if summary is not None:
        updates["review_summary"] = summary
    return result.model_copy(update=updates)


@task(name="bogda-shell-execute")
def execute_shell_task(
    request_data: dict[str, Any],
    attempts_root: str,
    run_id: str,
) -> dict[str, Any]:
    request = JobRequest.model_validate(request_data)
    attempt = max(1, get_run_context().task_run.run_count)
    result = run_shell(request, Path(attempts_root), run_id, attempt=attempt)
    if result.execution_status is not ExecutionStatus.COMPLETED:
        raise JobExecutionError(result)
    return result.model_dump(mode="json")


@flow(name="bogda-shell-job")
def run_shell_job(
    request: dict[str, Any],
    attempts_root: str,
) -> dict[str, Any]:
    parsed = JobRequest.model_validate(request)
    run_id = str(get_run_context().flow_run.id)
    configured_task = execute_shell_task.with_options(retries=retry_count(parsed))
    try:
        result_data = configured_task(
            parsed.model_dump(mode="json"),
            attempts_root,
            run_id,
        )
        result = RunResult.model_validate(result_data)
    except JobExecutionError as error:
        save_run_result(error.result)
        raise
    save_run_result(result)
    return result.model_dump(mode="json")


@flow(name="bogda-review-result")
def review_run_result(
    run_id: str,
    scientific_status: str,
    summary: str | None = None,
) -> dict[str, Any]:
    current = load_run_result(run_id)
    if current is None:
        raise LookupError(f"run result not found: {run_id}")
    reviewed = apply_review(
        current,
        ScientificStatus(scientific_status),
        summary,
    )
    save_run_result(reviewed)
    return reviewed.model_dump(mode="json")
