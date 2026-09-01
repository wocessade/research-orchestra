from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

INBOX_MAX_FILE_BYTES = 8 * 1024 * 1024
INBOX_MAX_FILE_BYTES_CEILING = 32 * 1024 * 1024
_TOKEN = re.compile(r"^[A-Za-z0-9._-]{1,180}$")


def inbox_max_file_bytes(env: Mapping[str, str] | None = None) -> int:
    source = os.environ if env is None else env
    raw = source.get("BOGDA_INBOX_MAX_FILE_BYTES")
    if raw is None or raw == "":
        return INBOX_MAX_FILE_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("BOGDA_INBOX_MAX_FILE_BYTES must be an integer") from exc
    if value < 1 or value > INBOX_MAX_FILE_BYTES_CEILING:
        raise ValueError(
            "BOGDA_INBOX_MAX_FILE_BYTES must be between 1 and the "
            f"{INBOX_MAX_FILE_BYTES_CEILING} byte ceiling"
        )
    return value


class InboxTooLarge(ValueError):
    """Staged file exceeds the brief-sized inbox cap."""


def stage_inbox_file(
    source: Path,
    *,
    run_id: str,
    name: str,
    inbox_root: Path,
) -> Path:
    if not _TOKEN.fullmatch(run_id) or run_id in {".", ".."} or ".." in run_id:
        raise ValueError("run_id must be inbox-safe")
    if not _TOKEN.fullmatch(name) or name in {".", ".."} or ".." in name:
        raise ValueError("name must be inbox-safe")
    size = source.stat().st_size
    cap = inbox_max_file_bytes()
    if size > cap:
        raise InboxTooLarge(f"{source} is {size} bytes; inbox cap is {cap}")
    destination = inbox_root / run_id / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination
