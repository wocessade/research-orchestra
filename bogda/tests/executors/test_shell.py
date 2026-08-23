import sys

from bogda.contracts import (
    ArtifactSpec,
    AutonomyMode,
    ExecutionStatus,
    JobRequest,
    ResourceClass,
)
from bogda.executors.shell import run_shell


def request_for(argv: list[str], artifact: str = "result.txt") -> JobRequest:
    return JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="shell",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        parameters={"argv": argv},
        expected_artifacts=(ArtifactSpec(path=artifact),),
    )


def test_shell_executor_completes_when_required_artifact_exists(tmp_path) -> None:
    request = request_for(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('result.txt').write_text('ok', encoding='utf-8')",
        ]
    )

    result = run_shell(request, tmp_path, "run-1")

    attempt_dir = tmp_path / "job-1" / "run-1" / "attempt-0001"
    assert result.execution_status is ExecutionStatus.COMPLETED
    assert result.scientific_status.value == "unreviewed"
    assert (attempt_dir / "stdout.log").exists()
    assert result.declared_artifacts[0].exists is True


def test_shell_executor_fails_on_nonzero_exit(tmp_path) -> None:
    request = request_for([sys.executable, "-c", "raise SystemExit(7)"])

    result = run_shell(request, tmp_path, "run-2")

    assert result.execution_status is ExecutionStatus.FAILED
    assert "exit code 7" in result.summary


def test_shell_executor_fails_when_required_artifact_is_missing(tmp_path) -> None:
    request = request_for([sys.executable, "-c", "print('no artifact')"])

    result = run_shell(request, tmp_path, "run-3")

    assert result.execution_status is ExecutionStatus.FAILED
    assert "result.txt" in result.summary


def test_attempt_directories_do_not_overwrite_each_other(tmp_path) -> None:
    request = request_for(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('result.txt').write_text('ok', encoding='utf-8')",
        ]
    )

    run_shell(request, tmp_path, "run-4", attempt=1)
    run_shell(request, tmp_path, "run-4", attempt=2)

    assert (tmp_path / "job-1" / "run-4" / "attempt-0001" / "result.txt").exists()
    assert (tmp_path / "job-1" / "run-4" / "attempt-0002" / "result.txt").exists()
