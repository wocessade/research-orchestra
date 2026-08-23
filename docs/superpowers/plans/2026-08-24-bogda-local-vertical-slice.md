# Bogda Local Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build an independently installable Bogda package that runs one local shell research job through Prefect, validates declared artifacts, records a versioned RunResult, and updates scientific review state separately from execution state.

**Architecture:** The first slice is deliberately local and contains no Pi deployment, WoL, Windows power control, GPU support, or Orchestra integration. Pure Pydantic contracts and a synchronous shell executor sit below thin Prefect flows; Prefect remains the only execution-state store, and a versioned Prefect Artifact is the authoritative RunResult.

**Tech Stack:** Python 3.11-3.13, uv, Prefect 3.8.3, Pydantic 2, pytest

**Spec:** docs/superpowers/specs/2026-08-24-bogda-architecture-design.md

## Global Constraints

- Create an independent project under bogda/; do not import orchestra internals.
- Pin Prefect to 3.8.3 for the first slice.
- Support Python >=3.11,<3.14; use Python 3.11 for Windows verification.
- Prefect owns execution state; do not create a second queue or status database.
- Every new RunResult starts with scientific_status=unreviewed.
- A zero exit code is not Completed when a required declared artifact is missing.
- Experiment execution retries once only when retryable=true; the default is no retry.
- Each attempt has its own directory and must not overwrite another attempt.
- Implement only deterministic checks needed by the slice; do not add repository-wide evidence scanning or general plugin infrastructure.
- Do not modify, deploy, stop, or migrate the existing Orchestra system.
- Do not add Pi, WoL, Windows Power Agent, Docker, CUDA, GPU, or 3100 console behavior in this plan.

---

## File Map

| File | Responsibility |
|---|---|
| bogda/pyproject.toml | Package metadata, pinned runtime dependencies, pytest configuration, bogda CLI entry point |
| bogda/.gitignore | Local virtual environment, pytest cache, and demo run output |
| bogda/README.md | Starts as package metadata input; becomes the operator guide in Task 4 |
| bogda/src/bogda/__init__.py | Package version |
| bogda/src/bogda/contracts/__init__.py | Public contract exports |
| bogda/src/bogda/contracts/models.py | JobRequest, RunResult, enums, and artifact models |
| bogda/src/bogda/artifacts/__init__.py | Public artifact helpers |
| bogda/src/bogda/artifacts/validation.py | Validate declared files under one attempt directory |
| bogda/src/bogda/artifacts/prefect_store.py | Save and load versioned RunResult Prefect Artifacts |
| bogda/src/bogda/executors/__init__.py | Public executor exports |
| bogda/src/bogda/executors/shell.py | Run argv without a shell, capture logs, and return RunResult |
| bogda/src/bogda/flows/__init__.py | Public flow exports |
| bogda/src/bogda/flows/shell_job.py | Prefect execution and scientific-review flows |
| bogda/src/bogda/control/__init__.py | Control package marker |
| bogda/src/bogda/control/cli.py | Local demo, result query, and scientific review commands |
| bogda/tests/contracts/test_models.py | Contract defaults and serialization |
| bogda/tests/artifacts/test_validation.py | Required/optional artifact behavior |
| bogda/tests/artifacts/test_prefect_store.py | Artifact key, serialization, latest-version loading |
| bogda/tests/executors/test_shell.py | Successful, nonzero, and missing-artifact execution |
| bogda/tests/flows/test_shell_job.py | Flow wiring and retry selection without a live server |
| bogda/tests/control/test_cli.py | CLI argument and output behavior with flow/store fakes |
| bogda/tests/integration/test_vertical_slice.py | Real temporary Prefect server end-to-end acceptance |
| bogda/README.md | Local setup, test, demo, result, review, and scope documentation |

## Task 1: Package Scaffold and Domain Contracts

**Files:**

- Create: bogda/pyproject.toml
- Create: bogda/.gitignore
- Create: bogda/README.md
- Create: bogda/src/bogda/__init__.py
- Create: bogda/src/bogda/contracts/__init__.py
- Create: bogda/src/bogda/contracts/models.py
- Create: bogda/tests/contracts/test_models.py

**Interfaces:**

- Consumes: Approved fields from spec section 10.
- Produces: AutonomyMode, ResourceClass, ExecutionStatus, ScientificStatus, ArtifactSpec, ArtifactRecord, JobRequest, and RunResult.

- [ ] **Step 1: Add package metadata, empty package exports, and a failing contract test**

Create bogda/pyproject.toml:

~~~toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "bogda"
version = "0.1.0"
description = "Prefect-based human-supervised research orchestration"
readme = "README.md"
requires-python = ">=3.11,<3.14"
dependencies = [
  "prefect==3.8.3",
  "pydantic>=2.11,<3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.4,<9",
]

[project.scripts]
bogda = "bogda.control.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/bogda"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "integration: starts a temporary Prefect server",
]
~~~

Create bogda/.gitignore:

~~~gitignore
.venv/
.pytest_cache/
__pycache__/
*.py[cod]
.bogda-runs/
~~~

Create bogda/README.md:

~~~markdown
# Bogda

Local vertical slice under development.
~~~

Create bogda/src/bogda/__init__.py:

~~~python
__version__ = "0.1.0"
~~~

Create bogda/src/bogda/contracts/__init__.py as an empty file, then create bogda/tests/contracts/test_models.py:

~~~python
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
~~~

- [ ] **Step 2: Install the development environment and verify the test fails**

Run:

~~~powershell
Set-Location D:\pythonProject\bogda
uv sync --python 3.11 --extra dev
uv run --python 3.11 pytest tests/contracts/test_models.py -v
~~~

Expected: collection fails because bogda.contracts.models does not exist.

- [ ] **Step 3: Implement the minimal contracts**

Create bogda/src/bogda/contracts/models.py:

~~~python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AutonomyMode(StrEnum):
    MANUAL = "manual"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class ResourceClass(StrEnum):
    PI = "pi"
    CPU = "cpu"
    GPU = "gpu"


class ExecutionStatus(StrEnum):
    SCHEDULED = "Scheduled"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CRASHED = "Crashed"
    CANCELLED = "Cancelled"


class ScientificStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ArtifactSpec(BaseModel):
    path: str
    kind: str = "file"
    required: bool = True


class ArtifactRecord(BaseModel):
    uri: str
    kind: str
    exists: bool
    size_bytes: int | None = None


class JobRequest(BaseModel):
    job_id: str
    project_id: str
    task_type: str
    resource_class: ResourceClass
    autonomy_mode: AutonomyMode
    parameters: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    expected_artifacts: tuple[ArtifactSpec, ...] = ()


class RunResult(BaseModel):
    run_id: str
    job_id: str
    execution_status: ExecutionStatus
    scientific_status: ScientificStatus = ScientificStatus.UNREVIEWED
    started_at: datetime
    finished_at: datetime
    executor: str
    attempt: int
    declared_artifacts: tuple[ArtifactRecord, ...]
    summary: str
    review_summary: str | None = None
~~~

Replace bogda/src/bogda/contracts/__init__.py with:

~~~python
from bogda.contracts.models import (
    ArtifactRecord,
    ArtifactSpec,
    AutonomyMode,
    ExecutionStatus,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
)

__all__ = [
    "ArtifactRecord",
    "ArtifactSpec",
    "AutonomyMode",
    "ExecutionStatus",
    "JobRequest",
    "ResourceClass",
    "RunResult",
    "ScientificStatus",
]
~~~

- [ ] **Step 4: Run the contract tests**

Run:

~~~powershell
uv run --python 3.11 pytest tests/contracts/test_models.py -v
~~~

Expected: 2 passed.

- [ ] **Step 5: Lock dependencies and commit**

Run:

~~~powershell
uv lock --python 3.11
git add bogda/pyproject.toml bogda/uv.lock bogda/.gitignore bogda/README.md bogda/src/bogda/__init__.py bogda/src/bogda/contracts bogda/tests/contracts
git commit -m "feat(bogda): define research job contracts"
~~~

## Task 2: Artifact Validation and Shell Execution

**Files:**

- Create: bogda/src/bogda/artifacts/__init__.py
- Create: bogda/src/bogda/artifacts/validation.py
- Create: bogda/src/bogda/executors/__init__.py
- Create: bogda/src/bogda/executors/shell.py
- Create: bogda/tests/artifacts/test_validation.py
- Create: bogda/tests/executors/test_shell.py

**Interfaces:**

- Consumes: JobRequest, ArtifactSpec, ArtifactRecord, ExecutionStatus, and RunResult from Task 1.
- Produces: validate_artifacts(attempt_dir: Path, specs: tuple[ArtifactSpec, ...]) -> tuple[ArtifactRecord, ...] and run_shell(request: JobRequest, attempts_root: Path, run_id: str, attempt: int = 1) -> RunResult.

- [ ] **Step 1: Write failing artifact-validation tests**

Create bogda/tests/artifacts/test_validation.py:

~~~python
from bogda.artifacts.validation import validate_artifacts
from bogda.contracts import ArtifactSpec


def test_validate_artifacts_reports_present_and_optional_missing(tmp_path) -> None:
    (tmp_path / "result.txt").write_text("ok", encoding="utf-8")

    records = validate_artifacts(
        tmp_path,
        (
            ArtifactSpec(path="result.txt"),
            ArtifactSpec(path="optional.json", required=False),
        ),
    )

    assert records[0].exists is True
    assert records[0].size_bytes == 2
    assert records[1].exists is False
    assert records[1].size_bytes is None
~~~

- [ ] **Step 2: Write failing executor tests**

Create bogda/tests/executors/test_shell.py:

~~~python
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
~~~

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

~~~powershell
uv run --python 3.11 pytest tests/artifacts/test_validation.py tests/executors/test_shell.py -v
~~~

Expected: collection fails because validation.py and shell.py do not exist.

- [ ] **Step 4: Implement declared-artifact validation**

Create bogda/src/bogda/artifacts/validation.py:

~~~python
from pathlib import Path

from bogda.contracts import ArtifactRecord, ArtifactSpec


def validate_artifacts(
    attempt_dir: Path,
    specs: tuple[ArtifactSpec, ...],
) -> tuple[ArtifactRecord, ...]:
    records = []
    for spec in specs:
        path = attempt_dir / spec.path
        exists = path.exists()
        records.append(
            ArtifactRecord(
                uri=str(path.resolve()),
                kind=spec.kind,
                exists=exists,
                size_bytes=path.stat().st_size if exists and path.is_file() else None,
            )
        )
    return tuple(records)
~~~

Create bogda/src/bogda/artifacts/__init__.py:

~~~python
from bogda.artifacts.validation import validate_artifacts

__all__ = ["validate_artifacts"]
~~~

- [ ] **Step 5: Implement the shell executor**

Create bogda/src/bogda/executors/shell.py:

~~~python
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
~~~

Create bogda/src/bogda/executors/__init__.py:

~~~python
from bogda.executors.shell import run_shell

__all__ = ["run_shell"]
~~~

- [ ] **Step 6: Run Task 2 tests and the fast suite**

Run:

~~~powershell
uv run --python 3.11 pytest tests/artifacts/test_validation.py tests/executors/test_shell.py -v
uv run --python 3.11 pytest -m "not integration" -v
~~~

Expected: 5 Task 2 tests pass; the complete fast suite passes.

- [ ] **Step 7: Commit**

Run:

~~~powershell
git add bogda/src/bogda/artifacts bogda/src/bogda/executors bogda/tests/artifacts/test_validation.py bogda/tests/executors/test_shell.py
git commit -m "feat(bogda): execute shell jobs with artifact checks"
~~~

## Task 3: Prefect Flow and Versioned RunResult Store

**Files:**

- Create: bogda/src/bogda/artifacts/prefect_store.py
- Modify: bogda/src/bogda/artifacts/__init__.py
- Create: bogda/src/bogda/flows/__init__.py
- Create: bogda/src/bogda/flows/shell_job.py
- Create: bogda/tests/artifacts/test_prefect_store.py
- Create: bogda/tests/flows/test_shell_job.py

**Interfaces:**

- Consumes: RunResult and run_shell from Tasks 1-2; Prefect Artifact, flow, task, and get_run_context.
- Produces: artifact_key(run_id: str) -> str, save_run_result(result: RunResult) -> None, load_run_result(run_id: str) -> RunResult | None, run_shell_job(request: dict[str, Any], attempts_root: str) -> dict[str, Any], and review_run_result(run_id: str, scientific_status: str, summary: str | None = None) -> dict[str, Any].

- [ ] **Step 1: Write failing Prefect-store tests using a small fake**

Create bogda/tests/artifacts/test_prefect_store.py:

~~~python
import json
from types import SimpleNamespace

from bogda.artifacts import prefect_store
from bogda.contracts import ExecutionStatus, RunResult, ScientificStatus


def sample_result() -> RunResult:
    return RunResult.model_validate(
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


def test_save_and_load_run_result_uses_one_versioned_key(monkeypatch) -> None:
    stored = {}

    class FakeArtifact:
        def __init__(self, **values):
            self.values = values

        def create(self):
            stored[self.values["key"]] = json.dumps(self.values["data"])
            return SimpleNamespace()

        @classmethod
        def get(cls, key):
            data = stored.get(key)
            return None if data is None else SimpleNamespace(data=data)

    monkeypatch.setattr(prefect_store, "Artifact", FakeArtifact)
    result = sample_result()

    prefect_store.save_run_result(result)
    loaded = prefect_store.load_run_result(result.run_id)

    assert prefect_store.artifact_key(result.run_id) == f"bogda-run-{result.run_id}"
    assert loaded == result
    assert loaded.execution_status is ExecutionStatus.COMPLETED
    assert loaded.scientific_status is ScientificStatus.UNREVIEWED
~~~

- [ ] **Step 2: Write failing flow-wiring tests without starting a server**

Create bogda/tests/flows/test_shell_job.py:

~~~python
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
~~~

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

~~~powershell
uv run --python 3.11 pytest tests/artifacts/test_prefect_store.py tests/flows/test_shell_job.py -v
~~~

Expected: collection fails because prefect_store.py and flows/shell_job.py do not exist.

- [ ] **Step 4: Implement the Prefect Artifact store**

Create bogda/src/bogda/artifacts/prefect_store.py:

~~~python
import json
from uuid import UUID

from prefect.artifacts import Artifact

from bogda.contracts import RunResult


def artifact_key(run_id: str) -> str:
    return f"bogda-run-{UUID(run_id)}"


def save_run_result(result: RunResult) -> None:
    Artifact(
        key=artifact_key(result.run_id),
        type="bogda.run-result",
        description=f"Bogda result for {result.job_id}",
        data=result.model_dump(mode="json"),
        flow_run_id=UUID(result.run_id),
    ).create()


def load_run_result(run_id: str) -> RunResult | None:
    artifact = Artifact.get(key=artifact_key(run_id))
    if artifact is None:
        return None
    data = json.loads(artifact.data) if isinstance(artifact.data, str) else artifact.data
    return RunResult.model_validate(data)
~~~

Update bogda/src/bogda/artifacts/__init__.py:

~~~python
from bogda.artifacts.prefect_store import (
    artifact_key,
    load_run_result,
    save_run_result,
)
from bogda.artifacts.validation import validate_artifacts

__all__ = [
    "artifact_key",
    "load_run_result",
    "save_run_result",
    "validate_artifacts",
]
~~~

- [ ] **Step 5: Implement execution and review flows**

Create bogda/src/bogda/flows/shell_job.py:

~~~python
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
~~~

Create bogda/src/bogda/flows/__init__.py:

~~~python
from bogda.flows.shell_job import review_run_result, run_shell_job

__all__ = ["review_run_result", "run_shell_job"]
~~~

- [ ] **Step 6: Run Task 3 tests and the fast suite**

Run:

~~~powershell
uv run --python 3.11 pytest tests/artifacts/test_prefect_store.py tests/flows/test_shell_job.py -v
uv run --python 3.11 pytest -m "not integration" -v
~~~

Expected: 3 Task 3 tests pass; the complete fast suite passes.

- [ ] **Step 7: Commit**

Run:

~~~powershell
git add bogda/src/bogda/artifacts bogda/src/bogda/flows bogda/tests/artifacts/test_prefect_store.py bogda/tests/flows/test_shell_job.py
git commit -m "feat(bogda): orchestrate jobs with Prefect"
~~~

## Task 4: CLI, Real Prefect Acceptance, and Operator Documentation

**Files:**

- Create: bogda/src/bogda/control/__init__.py
- Create: bogda/src/bogda/control/cli.py
- Create: bogda/tests/control/test_cli.py
- Create: bogda/tests/integration/test_vertical_slice.py
- Modify: bogda/README.md

**Interfaces:**

- Consumes: run_shell_job, review_run_result, load_run_result, JobRequest, and the Prefect API selected through PREFECT_API_URL.
- Produces: main(argv: Sequence[str] | None = None) -> int and the installed bogda command.

- [ ] **Step 1: Write failing CLI tests**

Create bogda/tests/control/test_cli.py:

~~~python
import json

from bogda.control import cli


def test_result_command_prints_stored_result(monkeypatch, capsys) -> None:
    stored = {
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
    monkeypatch.setattr(
        cli,
        "load_run_result",
        lambda run_id: cli.RunResult.model_validate(stored),
    )

    exit_code = cli.main(["result", stored["run_id"]])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["scientific_status"] == "unreviewed"


def test_result_command_returns_one_when_result_is_absent(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_run_result", lambda run_id: None)

    exit_code = cli.main(
        ["result", "36c86e99-d0a1-4399-a30c-4d6c5044444c"]
    )

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err
~~~

- [ ] **Step 2: Write the real Prefect integration test**

Create bogda/tests/integration/test_vertical_slice.py:

~~~python
import sys

import pytest
from prefect.testing.utilities import prefect_test_harness

from bogda.artifacts import load_run_result
from bogda.contracts import (
    ArtifactSpec,
    AutonomyMode,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
)
from bogda.flows import review_run_result, run_shell_job


@pytest.mark.integration
def test_local_vertical_slice(tmp_path) -> None:
    with prefect_test_harness(server_startup_timeout=60):
        request = JobRequest(
            job_id="integration-job",
            project_id="bogda",
            task_type="shell",
            resource_class=ResourceClass.CPU,
            autonomy_mode=AutonomyMode.SUPERVISED,
            parameters={
                "argv": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('result.txt').write_text('bogda ok', encoding='utf-8')",
                ]
            },
            expected_artifacts=(ArtifactSpec(path="result.txt"),),
        )

        returned = RunResult.model_validate(
            run_shell_job(
                request.model_dump(mode="json"),
                str(tmp_path),
            )
        )
        stored = load_run_result(returned.run_id)

        assert returned.execution_status.value == "Completed"
        assert stored is not None
        assert stored.scientific_status is ScientificStatus.UNREVIEWED

        reviewed = RunResult.model_validate(
            review_run_result(
                returned.run_id,
                ScientificStatus.ACCEPTED.value,
                "human accepted",
            )
        )
        latest = load_run_result(returned.run_id)

        assert reviewed.execution_status == returned.execution_status
        assert latest is not None
        assert latest.scientific_status is ScientificStatus.ACCEPTED
        assert latest.summary == returned.summary
        assert latest.review_summary == "human accepted"

        missing_request = request.model_copy(
            update={
                "job_id": "integration-missing",
                "parameters": {
                    "argv": [sys.executable, "-c", "print('no artifact')"]
                },
            }
        )
        failed_state = run_shell_job(
            missing_request.model_dump(mode="json"),
            str(tmp_path),
            return_state=True,
        )
        failed_run_id = str(failed_state.state_details.flow_run_id)
        failed_result = load_run_result(failed_run_id)

        assert failed_state.name == "Failed"
        assert failed_result is not None
        assert failed_result.execution_status.value == "Failed"
        assert "result.txt" in failed_result.summary
~~~

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

~~~powershell
uv run --python 3.11 pytest tests/control/test_cli.py -v
uv run --python 3.11 pytest tests/integration/test_vertical_slice.py -v
~~~

Expected: CLI test collection fails because control/cli.py does not exist. The integration test may collect but must not be treated as accepted until the CLI and final flow wiring are complete.

- [ ] **Step 4: Implement the control CLI**

Create bogda/src/bogda/control/cli.py:

~~~python
import argparse
import json
from pathlib import Path
import sys
from typing import Sequence
from uuid import uuid4

from bogda.artifacts import load_run_result
from bogda.contracts import (
    ArtifactSpec,
    AutonomyMode,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
)
from bogda.flows import review_run_result, run_shell_job


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="bogda")
    commands = root.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo")
    demo.add_argument("--attempts-root", default=".bogda-runs")

    result = commands.add_parser("result")
    result.add_argument("run_id")

    review = commands.add_parser("review")
    review.add_argument("run_id")
    review.add_argument(
        "status",
        choices=[
            ScientificStatus.ACCEPTED.value,
            ScientificStatus.REJECTED.value,
            ScientificStatus.INCONCLUSIVE.value,
        ],
    )
    review.add_argument("--summary")
    return root


def print_result(result: RunResult) -> None:
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


def demo_request() -> JobRequest:
    return JobRequest(
        job_id=f"demo-{uuid4()}",
        project_id="bogda",
        task_type="shell",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        parameters={
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('result.txt').write_text('bogda ok', encoding='utf-8')",
            ]
        },
        expected_artifacts=(ArtifactSpec(path="result.txt"),),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "demo":
        result = RunResult.model_validate(
            run_shell_job(
                demo_request().model_dump(mode="json"),
                str(Path(args.attempts_root).resolve()),
            )
        )
        print_result(result)
        return 0
    if args.command == "result":
        result = load_run_result(args.run_id)
        if result is None:
            print(f"run result not found: {args.run_id}", file=sys.stderr)
            return 1
        print_result(result)
        return 0

    reviewed = RunResult.model_validate(
        review_run_result(args.run_id, args.status, args.summary)
    )
    print_result(reviewed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
~~~

Create bogda/src/bogda/control/__init__.py as an empty file.

- [ ] **Step 5: Run the CLI tests**

Run:

~~~powershell
uv run --python 3.11 pytest tests/control/test_cli.py -v
~~~

Expected: 2 passed.

- [ ] **Step 6: Write the operator README**

Create bogda/README.md with these exact sections and commands:

~~~~markdown
# Bogda

Bogda is the Prefect-based successor to Research Orchestra. This directory is independent from orchestra/ and currently implements only the local vertical slice.

## Requirements

- Python 3.11-3.13
- uv

Docker, CUDA, Pi deployment, WoL, Windows power control, and the 3100 console are not required for this slice.

## Install

~~~powershell
Set-Location D:\pythonProject\bogda
uv sync --python 3.11 --extra dev
~~~

## Test

~~~powershell
uv run --python 3.11 pytest -m "not integration" -v
uv run --python 3.11 pytest -m integration -v
~~~

## Run against a local Prefect server

Start the server in one terminal:

~~~powershell
uv run --python 3.11 prefect server start --host 127.0.0.1
~~~

In a second terminal:

~~~powershell
$env:PREFECT_API_URL = "http://127.0.0.1:4200/api"
uv run --python 3.11 bogda demo
~~~

The demo prints a RunResult. Use its run_id to query or review it:

~~~powershell
uv run --python 3.11 bogda result RUN_ID
uv run --python 3.11 bogda review RUN_ID accepted --summary "human accepted"
~~~

Prefect Completed means the command ran and required artifacts exist. Scientific acceptance is stored separately and starts as unreviewed.

## Current scope

Implemented: local shell flow, attempt directories, required artifact checks, versioned RunResult artifacts, and separate scientific review status.

Deferred: Pi deployment, Wake Bridge, Windows Power Agent, CPU/GPU work queues, autonomous planning, SLC SD purchase, higher concurrency, and 3100 migration.
~~~~

- [ ] **Step 7: Run the real integration test**

Run:

~~~powershell
uv run --python 3.11 pytest tests/integration/test_vertical_slice.py -v
~~~

Expected: 1 passed. The temporary Prefect server starts, one shell Flow Run completes, the required artifact exists, the latest RunResult version changes from unreviewed to accepted without changing execution_status, and a second Flow Run with a missing required artifact ends in Prefect Failed with a stored Failed RunResult.

- [ ] **Step 8: Run the full verification suite**

Run:

~~~powershell
uv run --python 3.11 pytest -v
uv run --python 3.11 bogda --help
git diff --check
~~~

Expected: all tests pass; the CLI lists demo, result, and review; git diff reports no whitespace errors.

- [ ] **Step 9: Commit**

Run:

~~~powershell
git add bogda/src/bogda/control bogda/tests/control bogda/tests/integration bogda/README.md
git commit -m "feat(bogda): complete local Prefect vertical slice"
~~~

## Final Verification

- [ ] Confirm the implementation changed only bogda/ plus its approved plan and task-tracking files.
- [ ] Confirm no code imports from orchestra.
- [ ] Confirm the fast test suite passes on Python 3.11.
- [ ] Confirm the real temporary-server integration test passes.
- [ ] Confirm a missing required artifact produces execution_status=Failed.
- [ ] Confirm a successful run begins with scientific_status=unreviewed.
- [ ] Confirm review creates a new artifact version with accepted, rejected, or inconclusive while preserving execution_status.
- [ ] Confirm attempts 1 and 2 use different directories.
- [ ] Confirm no Pi, WoL, Windows power, Docker, CUDA, GPU, or 3100 implementation entered this slice.

## Spec Coverage Check

| Spec area | This plan |
|---|---|
| Independent bogda/ boundary | Task 1 package scaffold and final import check |
| Minimal JobRequest and RunResult | Task 1 |
| Required artifact semantics and separate attempts | Task 2 |
| Prefect as execution authority and versioned RunResult | Task 3 |
| Explicit experiment retry only | Task 3 |
| Scientific review independent of execution | Tasks 3-4 |
| Local stage 0 vertical slice | Task 4 integration test |
| Pi B-lite deployment and 72-hour test | Deliberately deferred to the next plan |
| Wake Bridge and Windows Power Agent | Deliberately deferred until the local slice passes |
| Dorm CPU/GPU queues and total concurrency 1 | Deliberately deferred until a remote worker exists |
| 3100 cutover and Orchestra retirement | Deliberately deferred until Bogda is stable |
