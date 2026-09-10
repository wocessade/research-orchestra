from datetime import UTC, datetime
from pathlib import Path
import subprocess

from bogda.artifacts.validation import validate_artifacts
from bogda.contracts import ExecutorKind, ExecutionStatus, JobRequest, RunResult


def run_shell(
    request: JobRequest,
    attempts_root: Path,
    run_id: str,
    attempt: int = 1,
) -> RunResult:
    if request.executor is not ExecutorKind.SHELL:
        raise ValueError("shell executor requires executor=shell")

    resolved_attempts_root = attempts_root.resolve()
    attempt_dir = (
        resolved_attempts_root
        / run_id
        / f"attempt-{attempt:04d}"
    ).resolve()
    try:
        attempt_dir.relative_to(resolved_attempts_root)
    except ValueError as error:
        raise ValueError(
            "attempt directory must be inside attempts root"
        ) from error
    attempt_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC)

    argv = request.parameters["argv"]
    launch_error = None
    try:
        completed = subprocess.run(
            argv,
            cwd=attempt_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
    except OSError as error:
        launch_error = error
        stdout = ""
        stderr = (
            f"{type(error).__name__}: {error}\n"
            f"command: {' '.join(str(argument) for argument in argv)}\n"
        )
    finished_at = datetime.now(UTC)

    (attempt_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (attempt_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    artifacts = validate_artifacts(attempt_dir, request.expected_artifacts)
    missing = [
        spec.path
        for spec, record in zip(request.expected_artifacts, artifacts, strict=True)
        if spec.required and not record.exists
    ]

    if launch_error is not None:
        status = ExecutionStatus.FAILED
        summary = f"command launch failed: {launch_error}"
    elif completed.returncode != 0:
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
