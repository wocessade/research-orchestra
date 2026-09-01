from __future__ import annotations

from pathlib import Path

import pytest

from bogda.ops.inbox import (
    INBOX_MAX_FILE_BYTES,
    InboxTooLarge,
    stage_inbox_file,
)


def test_stage_inbox_file_copies_under_run_id(tmp_path: Path) -> None:
    src = tmp_path / "note.md"
    src.write_text("brief only", encoding="utf-8")
    root = tmp_path / "inbox"
    dest = stage_inbox_file(src, run_id="jr-packet-1", name="note.md", inbox_root=root)
    assert dest == root / "jr-packet-1" / "note.md"
    assert dest.read_text(encoding="utf-8") == "brief only"


def test_stage_inbox_file_rejects_oversize(tmp_path: Path) -> None:
    src = tmp_path / "fat.bin"
    src.write_bytes(b"x" * (INBOX_MAX_FILE_BYTES + 1))
    with pytest.raises(InboxTooLarge):
        stage_inbox_file(src, run_id="jr-packet-1", name="fat.bin", inbox_root=tmp_path / "inbox")
