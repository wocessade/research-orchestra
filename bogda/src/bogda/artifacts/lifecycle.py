"""Explicit, path-confined cleanup of run artifacts. Event logs are retained."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bogda.artifacts.safe_log import require_safe_run_id, SafeLogError


CONFIRM_DELETE_CONTENT = "delete-content"


class ArtifactLifecycleError(ValueError):
    """Cleanup was refused because the request was unsafe or unconfirmed."""


def _latest_attempt_dir(run_dir: Path) -> Path | None:
    attempts = sorted(
        (item for item in run_dir.glob("attempt-*") if item.is_dir()),
        key=lambda item: item.name,
    )
    return attempts[-1] if attempts else None


def _content_files(run_dir: Path) -> tuple[tuple[str, Path, str], ...]:
    attempt = _latest_attempt_dir(run_dir)
    if attempt is None:
        return ()
    return (
        ("stdout", attempt / "stdout.log", f"{attempt.name}/stdout.log"),
        ("stderr", attempt / "stderr.log", f"{attempt.name}/stderr.log"),
    )


@dataclass(frozen=True, slots=True)
class ArtifactInspectRecord:
    kind: str
    exists: bool
    size_bytes: int | None
    relative_uri: str


@dataclass(frozen=True, slots=True)
class CleanupReceipt:
    run_id: str
    actor_id: str
    deleted_kinds: tuple[str, ...]


class ArtifactLifecycle:
    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise ArtifactLifecycleError("root must be a Path")
        self._root = root

    def _run_dir(self, run_id: str) -> Path:
        try:
            safe = require_safe_run_id(run_id)
        except SafeLogError as exc:
            raise ArtifactLifecycleError("run_id is invalid") from exc
        root = self._root.resolve()
        candidate = (self._root / safe).resolve()
        if not candidate.is_relative_to(root):
            raise ArtifactLifecycleError("run_id is invalid")
        return candidate

    def inspect(self, run_id: str) -> tuple[ArtifactInspectRecord, ...]:
        run_dir = self._run_dir(run_id)
        records: list[ArtifactInspectRecord] = []
        files = _content_files(run_dir)
        if not files:
            for kind in ("stdout", "stderr"):
                records.append(
                    ArtifactInspectRecord(
                        kind=kind,
                        exists=False,
                        size_bytes=None,
                        relative_uri=f"{kind}.log",
                    )
                )
        else:
            for kind, path, relative in files:
                exists = path.is_file()
                records.append(
                    ArtifactInspectRecord(
                        kind=kind,
                        exists=exists,
                        size_bytes=path.stat().st_size if exists else None,
                        relative_uri=relative,
                    )
                )
        events = run_dir / "events.jsonl"
        records.append(
            ArtifactInspectRecord(
                kind="events",
                exists=events.is_file(),
                size_bytes=events.stat().st_size if events.is_file() else None,
                relative_uri="events.jsonl",
            )
        )
        return tuple(records)

    def cleanup(
        self,
        run_id: str,
        *,
        actor_id: str,
        confirm: str,
    ) -> CleanupReceipt:
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ArtifactLifecycleError("actor_id is invalid")
        if confirm != CONFIRM_DELETE_CONTENT:
            raise ArtifactLifecycleError("confirm token is invalid")
        run_dir = self._run_dir(run_id)
        deleted: list[str] = []
        for kind, path, relative in _content_files(run_dir):
            if not path.is_file():
                continue
            tombstone = path.with_name(path.name + ".tombstone")
            tombstone.write_text(relative, encoding="utf-8")
            path.unlink()
            deleted.append(kind)
        return CleanupReceipt(
            run_id=run_id, actor_id=actor_id.strip(), deleted_kinds=tuple(deleted)
        )
