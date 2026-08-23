from datetime import UTC, datetime
from pathlib import Path
import subprocess

from bogda.artifacts.validation import validate_artifacts
from bogda.contracts import ExecutionStatus, JobRequest, RunResult


def run_shell(
    request: JobRequest,
    attempts_root: Path,
    run_id: str,
    attempt: int = 1,
) -> RunResult:
    attempt_dir = (
        attempts_root
        / request.job_id
        / run_id
        / f"attempt-{attempt:04d}"
    )
    attempt_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC)

    argv = request.parameters["argv"]
    completed = subprocess.run(
        argv,
        cwd=attempt_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    finished_at = datetime.now(UTC)

    (attempt_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (attempt_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    artifacts = validate_artifacts(attempt_dir, request.expected_artifacts)
    missing = [
        spec.path
        for spec, record in zip(request.expected_artifacts, artifacts, strict=True)
        if spec.required and not record.exists
    ]

    if completed.returncode != 0:
        status = ExecutionStatus.FAILED
        summary = f"command failed with exit code {completed.returncode}"
    elif missing:
        status = ExecutionStatus.FAILED
        summary = f"required artifacts missing: {', '.join(missing)}"
    else:
        status = ExecutionStatus.COMPLETED
        summary = "command completed and required artifacts exist"

    return RunResult(
        run_id=run_id,
        job_id=request.job_id,
        execution_status=status,
        started_at=started_at,
        finished_at=finished_at,
        executor="shell",
        attempt=attempt,
        declared_artifacts=artifacts,
        summary=summary,
    )
