from __future__ import annotations

import re
import shutil
from pathlib import Path

INBOX_MAX_FILE_BYTES = 8 * 1024 * 1024
_TOKEN = re.compile(r"^[A-Za-z0-9._-]{1,180}$")


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
    if size > INBOX_MAX_FILE_BYTES:
        raise InboxTooLarge(
            f"{source} is {size} bytes; inbox cap is {INBOX_MAX_FILE_BYTES}"
        )
    destination = inbox_root / run_id / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination
