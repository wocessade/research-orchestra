from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from bogda.contracts import ModelTier
from bogda.model_runtime import (
    DshCliAdapter,
    DshTokenUsageV1,
    JsonUsageReceiptReader,
    ModelCallOutcome,
    ModelCallRequest,
    MAX_STDERR_BYTES,
)


class FakeRunner:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "answer",
        stderr: str = "",
        error: BaseException | None = None,
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.calls: list[tuple[list[str], Path, float]] = []

    def run(self, argv: list[str], *, cwd: Path, timeout: float):
        self.calls.append((argv, cwd, timeout))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def call_request(attempt_dir: Path, tier: ModelTier, timeout: float = 7.5):
    return ModelCallRequest(
        run_id="run-1",
        call_id="call-1",
        effective_tier=tier,
        attempt_dir=attempt_dir,
        timeout_seconds=timeout,
        prompt="secret-free prompt",
    )


def adapter_for(tmp_path: Path, runner: FakeRunner, **kwargs) -> DshCliAdapter:
    flash_patch = tmp_path / "flash.yml"
    pro_patch = tmp_path / "pro.yml"
    flash_patch.write_text("flash", encoding="utf-8")
    pro_patch.write_text("pro", encoding="utf-8")
    return DshCliAdapter(
        flash_patch=flash_patch,
        pro_patch=pro_patch,
        runner=runner,
        **kwargs,
    )


def write_usage(attempt_dir: Path, **overrides: object) -> DshTokenUsageV1:
    usage = DshTokenUsageV1(
        input_tokens=12,
        cache_read_tokens=3,
        output_tokens=8,
        actual_cost_cny="0.25",
        reference="dsh-receipt-1",
    ).model_dump(mode="json")
    usage.update(overrides)
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "usage.json").write_text(
        json.dumps(usage),
        encoding="utf-8",
    )
    return DshTokenUsageV1.model_validate(usage)


def test_flash_invocation_uses_owned_patch_and_list_argv(tmp_path: Path) -> None:
    runner = FakeRunner()
    adapter = adapter_for(tmp_path, runner)
    request = call_request(tmp_path / "attempt", ModelTier.FLASH)
    write_usage(request.attempt_dir)

    result = adapter.invoke(request)

    argv, cwd, timeout = runner.calls[0]
    assert argv == [
        "dsh",
        "--profile",
        "headless",
        "--patch",
        str(tmp_path / "flash.yml"),
        "secret-free prompt",
    ]
    assert cwd == request.attempt_dir
    assert timeout == 7.5
    assert result.outcome is ModelCallOutcome.FINISHED


def test_pro_invocation_selects_owned_pro_patch(tmp_path: Path) -> None:
    runner = FakeRunner()
    adapter = adapter_for(tmp_path, runner)
    request = call_request(tmp_path / "attempt", ModelTier.PRO)
    write_usage(request.attempt_dir)

    adapter.invoke(request)

    assert runner.calls[0][0][3:5] == ["--patch", str(tmp_path / "pro.yml")]


def test_missing_selected_patch_fails_before_runner_and_attempt_creation(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    adapter = DshCliAdapter(
        flash_patch=tmp_path / "missing-flash.yml",
        pro_patch=tmp_path / "pro.yml",
        runner=runner,
    )
    request = call_request(tmp_path / "attempt", ModelTier.FLASH)

    with pytest.raises(FileNotFoundError, match="dsh patch not found"):
        adapter.invoke(request)

    assert runner.calls == []
    assert not request.attempt_dir.exists()


def test_missing_executable_is_not_started(tmp_path: Path) -> None:
    runner = FakeRunner(error=FileNotFoundError("dsh missing"))
    adapter = adapter_for(tmp_path, runner)

    result = adapter.invoke(call_request(tmp_path / "attempt", ModelTier.FLASH))

    assert result.outcome is ModelCallOutcome.NOT_STARTED


def test_timeout_after_spawn_is_usage_unknown_and_preserves_partial_output(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        error=subprocess.TimeoutExpired(
            cmd=["dsh"],
            timeout=7.5,
            output="partial answer",
            stderr="partial stderr",
        )
    )
    adapter = adapter_for(tmp_path, runner)
    request = call_request(tmp_path / "attempt", ModelTier.FLASH)

    result = adapter.invoke(request)

    assert result.outcome is ModelCallOutcome.USAGE_UNKNOWN
    assert (request.attempt_dir / "stdout.log").read_text(encoding="utf-8") == (
        "partial answer"
    )
    assert (request.attempt_dir / "stderr.log").read_text(encoding="utf-8") == (
        "partial stderr"
    )


def test_nonzero_after_spawn_is_usage_unknown(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=2)
    adapter = adapter_for(tmp_path, runner)

    result = adapter.invoke(call_request(tmp_path / "attempt", ModelTier.FLASH))

    assert result.outcome is ModelCallOutcome.USAGE_UNKNOWN


def test_stdout_is_exact_and_stderr_is_bounded_attempt_artifact(
    tmp_path: Path,
) -> None:
    stdout = "answer\nwith exact spacing"
    stderr = "e" * (MAX_STDERR_BYTES + 17)
    runner = FakeRunner(returncode=2, stdout=stdout, stderr=stderr)
    adapter = adapter_for(tmp_path, runner)
    request = call_request(tmp_path / "attempt", ModelTier.FLASH)

    adapter.invoke(request)

    assert (request.attempt_dir / "stdout.log").read_text(encoding="utf-8") == stdout
    bounded_stderr = (request.attempt_dir / "stderr.log").read_text(encoding="utf-8")
    assert bounded_stderr == stderr[:MAX_STDERR_BYTES]
    assert len(bounded_stderr) == MAX_STDERR_BYTES


def test_zero_exit_without_receipt_is_usage_unknown(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=0, stdout="answer")
    adapter = adapter_for(tmp_path, runner)

    result = adapter.invoke(call_request(tmp_path / "attempt", ModelTier.FLASH))

    assert result.outcome is ModelCallOutcome.USAGE_UNKNOWN
    assert result.usage is None


def test_valid_usage_receipt_round_trip_finishes_call(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=0, stdout="answer")
    adapter = adapter_for(tmp_path, runner)
    request = call_request(tmp_path / "attempt", ModelTier.FLASH)
    expected_usage = write_usage(request.attempt_dir)

    result = adapter.invoke(request)

    assert result.outcome is ModelCallOutcome.FINISHED
    assert result.output == "answer"
    assert result.usage == expected_usage


def test_json_usage_reader_validates_present_receipt(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    (attempt_dir / "usage.json").write_text('{"input_tokens": "free"}', encoding="utf-8")

    with pytest.raises(ValidationError):
        JsonUsageReceiptReader().read(attempt_dir)


def test_malformed_receipt_is_unknown_not_free_success(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=0, stdout="answer")
    adapter = adapter_for(tmp_path, runner)
    request = call_request(tmp_path / "attempt", ModelTier.FLASH)
    request.attempt_dir.mkdir()
    (request.attempt_dir / "usage.json").write_text("not json", encoding="utf-8")

    result = adapter.invoke(request)

    assert result.outcome is ModelCallOutcome.USAGE_UNKNOWN
    assert result.usage is None
