"""Path-confined, redacted reads of run stdout/stderr/event logs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bogda.model_runtime.dsh import _sanitize_diagnostic


ALLOWED_SOURCES = frozenset({"stdout", "stderr", "events"})
DEFAULT_MAX_BYTES = 65536


class SafeLogError(ValueError):
    """The requested log could not be read without leaving the artifact root."""


@dataclass(frozen=True, slots=True)
class LogSlice:
    source: str
    exists: bool
    content: str
    truncated: bool
    size_bytes: int | None


def require_safe_run_id(run_id: object) -> str:
    if not isinstance(run_id, str) or not run_id.strip():
        raise SafeLogError("run_id is invalid")
    if run_id != run_id.strip():
        raise SafeLogError("run_id is invalid")
    if any(part in run_id for part in ("/", "\\", "..")):
        raise SafeLogError("run_id is invalid")
    if run_id in {".", ".."} or run_id.startswith("."):
        raise SafeLogError("run_id is invalid")
    return run_id


class SafeLogReader:
    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise SafeLogError("root must be a Path")
        self._root = root

    def _run_dir(self, run_id: str) -> Path:
        safe = require_safe_run_id(run_id)
        root = self._root.resolve()
        candidate = (self._root / safe).resolve()
        if not candidate.is_relative_to(root):
            raise SafeLogError("run_id is invalid")
        return candidate

    def _source_path(self, run_dir: Path, source: str) -> Path | None:
        if source == "events":
            path = run_dir / "events.jsonl"
            return path if path.is_file() else None
        attempts = sorted(
            (item for item in run_dir.glob("attempt-*") if item.is_dir()),
            key=lambda item: item.name,
        )
        if not attempts:
            return None
        path = attempts[-1] / f"{source}.log"
        return path if path.is_file() else None

    def read(self, run_id: str, source: str, *, max_bytes: int = DEFAULT_MAX_BYTES) -> LogSlice:
        if source not in ALLOWED_SOURCES:
            raise SafeLogError("source is not allowed")
        if type(max_bytes) is not int or max_bytes < 1:
            raise SafeLogError("max_bytes must be a positive integer")
        run_dir = self._run_dir(run_id)
        path = self._source_path(run_dir, source) if run_dir.is_dir() else None
        if path is None:
            return LogSlice(
                source=source, exists=False, content="", truncated=False, size_bytes=None
            )
        raw = path.read_bytes()
        truncated = len(raw) > max_bytes
        text = _sanitize_diagnostic(raw[:max_bytes].decode("utf-8", errors="replace"))
        return LogSlice(
            source=source,
            exists=True,
            content=text,
            truncated=truncated,
            size_bytes=len(raw),
        )
