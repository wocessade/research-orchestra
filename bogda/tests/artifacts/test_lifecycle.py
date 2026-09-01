from pathlib import Path

import pytest

from bogda.artifacts.lifecycle import ArtifactLifecycle, ArtifactLifecycleError


def _seed(root: Path) -> None:
    attempt = root / "run-1" / "attempt-1"
    attempt.mkdir(parents=True)
    (attempt / "stdout.log").write_text("keep-ref", encoding="utf-8")
    (attempt / "stderr.log").write_text("err", encoding="utf-8")
    (root / "run-1" / "events.jsonl").write_text('{"event":"budget_reserved"}\n', encoding="utf-8")


def test_inspect_reports_existing_files_without_following_escapes(tmp_path: Path) -> None:
    _seed(tmp_path)
    records = ArtifactLifecycle(tmp_path).inspect("run-1")

    kinds = {record.kind: record for record in records}
    assert kinds["stdout"].exists is True
    assert kinds["stderr"].exists is True
    assert kinds["events"].exists is True
    assert kinds["stdout"].size_bytes == 8


def test_cleanup_requires_explicit_confirm_and_leaves_event_log(tmp_path: Path) -> None:
    _seed(tmp_path)
    lifecycle = ArtifactLifecycle(tmp_path)

    with pytest.raises(ArtifactLifecycleError, match="confirm"):
        lifecycle.cleanup("run-1", actor_id="owner-1", confirm="please")

    assert (tmp_path / "run-1" / "attempt-1" / "stdout.log").is_file()

    receipt = lifecycle.cleanup("run-1", actor_id="owner-1", confirm="delete-content")

    assert receipt.deleted_kinds == ("stdout", "stderr")
    assert not (tmp_path / "run-1" / "attempt-1" / "stdout.log").exists()
    assert (tmp_path / "run-1" / "attempt-1" / "stdout.log.tombstone").is_file()
    assert (tmp_path / "run-1" / "events.jsonl").read_text(encoding="utf-8")
    inspected = {record.kind: record for record in lifecycle.inspect("run-1")}
    assert inspected["stdout"].exists is False
    assert inspected["events"].exists is True


def test_cleanup_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(ArtifactLifecycleError, match="run_id"):
        ArtifactLifecycle(tmp_path).cleanup("../run-1", actor_id="owner-1", confirm="delete-content")
