from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Protocol

from pydantic import ValidationError

from bogda.contracts import ModelTier
from bogda.model_runtime.contracts import (
    DshTokenUsageV1,
    ModelCallOutcome,
    ModelCallRequest,
    ModelCallResult,
    UsageReceiptPort,
)


MAX_STDERR_BYTES = 16 * 1024
_SENSITIVE_DIAGNOSTIC_PATTERNS = (
    (
        re.compile(r"(Authorization\s*:\s*Bearer\s+)[^\s]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(X-Monitor-Token\s*:\s*)[^\s]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"((?:DEEPSEEK_API_KEY|api_key|password)\s*[=:]\s*)[^\s]+",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
)


class DshCommandRunner(Protocol):
    def run(
        self,
        argv: list[str],
        *,
        cwd: Path,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        ...


class SubprocessCommandRunner:
    def run(
        self,
        argv: list[str],
        *,
        cwd: Path,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )


class JsonUsageReceiptReader:
    def read(self, attempt_dir: Path) -> DshTokenUsageV1 | None:
        receipt_path = attempt_dir / "usage.json"
        if not receipt_path.exists():
            return None
        return DshTokenUsageV1.model_validate(
            json.loads(receipt_path.read_text(encoding="utf-8"))
        )


class DshCliAdapter:
    def __init__(
        self,
        flash_patch: Path,
        pro_patch: Path,
        *,
        runner: DshCommandRunner | None = None,
        usage_reader: UsageReceiptPort | None = None,
        command: str = "dsh",
        profile: str = "headless",
    ) -> None:
        self._patches = {
            ModelTier.FLASH: Path(flash_patch),
            ModelTier.PRO: Path(pro_patch),
        }
        self._runner = runner or SubprocessCommandRunner()
        self._usage_reader = usage_reader or JsonUsageReceiptReader()
        self._command = command
        self._profile = profile

    def invoke(self, request: ModelCallRequest) -> ModelCallResult:
        patch = self._patches[request.effective_tier]
        if not patch.is_file():
            raise FileNotFoundError(f"dsh patch not found: {patch}")

        request.attempt_dir.mkdir(parents=True, exist_ok=True)
        argv = [
            self._command,
            "--profile",
            self._profile,
            "--patch",
            str(patch),
            request.prompt,
        ]

        try:
            completed = self._runner.run(
                argv,
                cwd=request.attempt_dir,
                timeout=request.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            self._write_artifacts(
                request.attempt_dir,
                _as_text(error.stdout),
                _as_text(error.stderr),
            )
            return ModelCallResult(outcome=ModelCallOutcome.USAGE_UNKNOWN)
        except OSError:
            self._write_artifacts(request.attempt_dir, "", "")
            return ModelCallResult(outcome=ModelCallOutcome.NOT_STARTED)

        stdout = _as_text(completed.stdout)
        stderr = _as_text(completed.stderr)
        self._write_artifacts(request.attempt_dir, stdout, stderr)

        if completed.returncode != 0:
            return ModelCallResult(outcome=ModelCallOutcome.USAGE_UNKNOWN)

        try:
            usage = self._usage_reader.read(request.attempt_dir)
        except Exception:
            usage = None

        if usage is None:
            return ModelCallResult(outcome=ModelCallOutcome.USAGE_UNKNOWN)
        return ModelCallResult(
            outcome=ModelCallOutcome.FINISHED,
            output=stdout,
            usage=usage,
        )

    @staticmethod
    def _write_artifacts(attempt_dir: Path, stdout: str, stderr: str) -> None:
        (attempt_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        bounded_stderr = _sanitize_diagnostic(stderr).encode("utf-8")[
            :MAX_STDERR_BYTES
        ].decode("utf-8", errors="ignore")
        (attempt_dir / "stderr.log").write_text(
            bounded_stderr,
            encoding="utf-8",
        )


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _sanitize_diagnostic(stderr: str) -> str:
    for pattern, replacement in _SENSITIVE_DIAGNOSTIC_PATTERNS:
        stderr = pattern.sub(replacement, stderr)
    return stderr


__all__ = [
    "DshCliAdapter",
    "DshCommandRunner",
    "JsonUsageReceiptReader",
    "MAX_STDERR_BYTES",
    "SubprocessCommandRunner",
]
