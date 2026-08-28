from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Barrier, Thread

import pytest

from bogda.contracts import RunEventV1
from bogda.events.jsonl import JsonlRunEventSink


NOW = datetime(2026, 8, 28, 20, 10, tzinfo=timezone.utc)


def make_event(run_id: str = "run-1", **updates: object) -> RunEventV1:
    values: dict[str, object] = {
        "event": "budget_snapshot",
        "run_id": run_id,
        "intent": "explore",
        "requested_tier": "flash",
        "occurred_at": NOW,
        "reason": "usage_snapshot_fresh",
        "budget_decision": "allow",
        "pricing_version": "deepseek-cn-2026-08-28",
        "balance_cny": "10",
        "reserved_cny": "0",
        "minimum_remaining_cny": "1",
        "snapshot_age_seconds": 30,
    }
    values.update(updates)
    return RunEventV1(**values)


def test_jsonl_appends_compact_validated_lines_without_truncating_existing_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(make_event().model_dump_json() + "\n", encoding="utf-8")
    sink = JsonlRunEventSink(path)

    sink.append(make_event())
    sink.append(make_event(run_id="run-2"))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert RunEventV1.model_validate_json(lines[0]).run_id == "run-1"
    assert len(lines) == 3
    for line in lines[1:]:
        parsed = RunEventV1.model_validate_json(line)
        assert parsed.run_id in {"run-1", "run-2"}
        assert " " not in line


def test_jsonl_rejects_directory_symlink_and_invalid_parent(tmp_path: Path) -> None:
    with pytest.raises((ValueError, IsADirectoryError)):
        JsonlRunEventSink(tmp_path)

    symlink = tmp_path / "symlink.jsonl"
    target = tmp_path / "target.jsonl"
    target.write_text("", encoding="utf-8")
    try:
        symlink.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this Windows account")
    with pytest.raises(ValueError, match="symlink|reparse"):
        JsonlRunEventSink(symlink)

    with pytest.raises(ValueError, match="parent"):
        JsonlRunEventSink(tmp_path / "missing" / "events.jsonl")


def test_jsonl_rejects_non_event_and_preserves_file_on_failed_append(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlRunEventSink(path)
    with pytest.raises(TypeError):
        sink.append({"event": "budget_snapshot"})  # type: ignore[arg-type]
    assert not path.exists()


def test_jsonl_rejects_an_existing_non_event_line(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"not":"a run event"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="existing event log"):
        JsonlRunEventSink(path)


def test_jsonl_separates_a_valid_existing_line_without_trailing_newline(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.jsonl"
    existing = make_event(run_id="existing").model_dump_json()
    path.write_text(existing, encoding="utf-8")

    JsonlRunEventSink(path).append(make_event(run_id="new"))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [RunEventV1.model_validate_json(line).run_id for line in lines] == [
        "existing",
        "new",
    ]


def test_jsonl_serializes_decimal_money_as_strings(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlRunEventSink(path)
    sink.append(make_event(balance_cny="1.2300"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["balance_cny"] == "1.2300"


def test_jsonl_lock_keeps_concurrent_appends_parseable(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlRunEventSink(path)
    barrier = Barrier(8)
    failures: list[BaseException] = []

    def append(index: int) -> None:
        try:
            barrier.wait()
            sink.append(make_event(run_id=f"run-{index}"))
        except BaseException as exc:  # pragma: no cover - diagnostic only
            failures.append(exc)

    threads = [Thread(target=append, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8
    for line in lines:
        RunEventV1.model_validate_json(line)
