"""Explicit, path-confined cleanup of run artifacts. Event logs are retained."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bogda.artifacts.safe_log import require_safe_run_id, SafeLogError


CONFIRM_DELETE_CONTENT = "delete-content"
_CONTENT_FILES = (
    ("stdout", "attempt-1/stdout.log"),
    ("stderr", "attempt-1/stderr.log"),
)


class ArtifactLifecycleError(ValueError):
    """Cleanup was refused because the request was unsafe or unconfirmed."""


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
        for kind, relative in _CONTENT_FILES + (("events", "events.jsonl"),):
            path = run_dir / Path(relative)
            exists = path.is_file()
            records.append(
                ArtifactInspectRecord(
                    kind=kind,
                    exists=exists,
                    size_bytes=path.stat().st_size if exists else None,
                    relative_uri=relative,
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
        for kind, relative in _CONTENT_FILES:
            path = run_dir / Path(relative)
            if not path.is_file():
                continue
            tombstone = path.with_name(path.name + ".tombstone")
            tombstone.write_text(relative.replace("\\", "/"), encoding="utf-8")
            path.unlink()
            deleted.append(kind)
        return CleanupReceipt(
            run_id=run_id, actor_id=actor_id.strip(), deleted_kinds=tuple(deleted)
        )
