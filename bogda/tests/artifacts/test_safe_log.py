from pathlib import Path

import pytest

from bogda.artifacts.safe_log import SafeLogError, SafeLogReader


def _seed(root: Path, run_id: str = "run-1") -> Path:
    attempt = root / run_id / "attempt-1"
    attempt.mkdir(parents=True)
    (attempt / "stdout.log").write_text("hello stdout\nAuthorization: Bearer secret-token\n", encoding="utf-8")
    (attempt / "stderr.log").write_text("DEEPSEEK_API_KEY=sk-live\nwarn\n", encoding="utf-8")
    (root / run_id / "events.jsonl").write_text('{"event":"budget_snapshot"}\n', encoding="utf-8")
    return attempt


def test_reads_stdout_from_attempt_dir_and_redacts_secrets(tmp_path: Path) -> None:
    _seed(tmp_path)
    slice_ = SafeLogReader(tmp_path).read("run-1", "stdout")

    assert slice_.exists is True
    assert "hello stdout" in slice_.content
    assert "secret-token" not in slice_.content
    assert "[REDACTED]" in slice_.content
    assert slice_.truncated is False
    assert slice_.source == "stdout"


def test_unknown_source_and_path_escape_fail_closed(tmp_path: Path) -> None:
    _seed(tmp_path)
    reader = SafeLogReader(tmp_path)

    with pytest.raises(SafeLogError, match="source"):
        reader.read("run-1", "host-path")
    with pytest.raises(SafeLogError, match="run_id"):
        reader.read("../etc", "stdout")
    with pytest.raises(SafeLogError, match="run_id"):
        reader.read("run-1/../../secret", "stdout")


def test_missing_log_is_empty_not_a_host_dump(tmp_path: Path) -> None:
    slice_ = SafeLogReader(tmp_path).read("missing-run", "stderr")

    assert slice_.exists is False
    assert slice_.content == ""
    assert slice_.truncated is False


def test_truncation_sets_flag_and_keeps_prefix(tmp_path: Path) -> None:
    attempt = tmp_path / "run-1" / "attempt-1"
    attempt.mkdir(parents=True)
    (attempt / "stdout.log").write_text("abcdefghij", encoding="utf-8")

    slice_ = SafeLogReader(tmp_path).read("run-1", "stdout", max_bytes=4)

    assert slice_.content == "abcd"
    assert slice_.truncated is True
