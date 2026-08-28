"""Append-only, secret-free persistence for validated run events."""

from __future__ import annotations

import os
from pathlib import Path
import stat
from threading import RLock
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from bogda.contracts import RunEventV1


@runtime_checkable
class RunEventSink(Protocol):
    """Destination for one already-validated v1 event at a time."""

    def append(self, event: RunEventV1) -> None:
        ...


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _lstat(path: Path, *, missing_ok: bool) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return None
        raise ValueError("event log path does not exist") from None
    except OSError:
        raise ValueError("event log path is invalid") from None


def _reject_unsafe_path(path: Path) -> None:
    parent_stat = _lstat(path.parent, missing_ok=False)
    assert parent_stat is not None
    if not stat.S_ISDIR(parent_stat.st_mode):
        raise ValueError("event log parent must be a directory")
    if stat.S_ISLNK(parent_stat.st_mode) or _is_reparse_point(parent_stat):
        raise ValueError("event log parent must not be a symlink or reparse point")

    target_stat = _lstat(path, missing_ok=True)
    if target_stat is None:
        return
    if stat.S_ISLNK(target_stat.st_mode) or _is_reparse_point(target_stat):
        raise ValueError("event log target must not be a symlink or reparse point")
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError("event log target must be a regular file")


def _validate_existing_lines(path: Path) -> None:
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for line in handle:
                RunEventV1.model_validate_json(line.rstrip("\r\n"))
    except ValidationError:
        raise ValueError("existing event log is invalid") from None
    except Exception:
        raise ValueError("existing event log is invalid") from None


def _file_state(path: Path) -> tuple[tuple[int, int] | None, int, int | None]:
    try:
        file_stat = path.stat()
    except FileNotFoundError:
        return None, 0, None
    except OSError:
        raise ValueError("event log could not be inspected safely") from None
    return (
        (file_stat.st_dev, file_stat.st_ino),
        file_stat.st_size,
        file_stat.st_mtime_ns,
    )


def _needs_line_separator(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                return False
            handle.seek(-1, os.SEEK_END)
            return handle.read(1) not in {b"\n", b"\r"}
    except OSError:
        raise ValueError("event log could not be inspected safely") from None
    except Exception:
        raise ValueError("event log could not be inspected safely") from None


class JsonlRunEventSink:
    """Persist compact v1 events using append mode and flush+fsync.

    The lock protects concurrent appends made through this sink instance in
    this process.  It is not an inter-process lock; callers needing that
    guarantee must provide a durable sink with an operating-system or
    database-level coordination mechanism.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        try:
            raw_path = os.fspath(path)
        except TypeError:
            raise ValueError("event log path is invalid") from None
        if isinstance(raw_path, bytes) or not raw_path:
            raise ValueError("event log path is invalid")
        self._path = Path(raw_path)
        self._lock = RLock()
        with self._lock:
            _reject_unsafe_path(self._path)
            _validate_existing_lines(self._path)
            self._expected_file_state = _file_state(self._path)

    def append(self, event: RunEventV1) -> None:
        if not isinstance(event, RunEventV1):
            raise TypeError("event must be a RunEventV1")
        encoded = event.model_dump_json(exclude_none=True)
        # Validate the exact line that will be written. This also keeps a
        # custom serializer or future model change from bypassing the v1 gate.
        RunEventV1.model_validate_json(encoded)
        line = encoded + "\n"

        with self._lock:
            _reject_unsafe_path(self._path)
            current_state = _file_state(self._path)
            if current_state != self._expected_file_state:
                raise ValueError("event log changed externally")
            current_size = current_state[1]
            needs_separator = current_size > 0 and _needs_line_separator(self._path)
            expected_size = current_size + (1 if needs_separator else 0) + len(
                line.encode("utf-8")
            )
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            flags |= getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(self._path, flags, 0o600)
            except (OSError, ValueError):
                raise ValueError("event log could not be opened safely") from None
            try:
                with os.fdopen(fd, "a", encoding="utf-8", newline="") as handle:
                    if needs_separator:
                        handle.write("\n")
                    handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
            except (OSError, ValueError):
                # fdopen owns the descriptor after successful construction;
                # close it explicitly only when construction itself failed.
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise ValueError("event log append failed") from None
            updated_state = _file_state(self._path)
            if updated_state[1] != expected_size:
                raise ValueError("event log changed during append")
            if current_state[0] is not None and updated_state[0] != current_state[0]:
                raise ValueError("event log changed during append")
            self._expected_file_state = updated_state


__all__ = ["JsonlRunEventSink", "RunEventSink"]
