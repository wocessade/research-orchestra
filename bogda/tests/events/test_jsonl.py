from datetime import datetime, timezone
import json
import importlib
import os
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
        "active_reservations_cny": "0",
        "requested_reservation_cny": "1",
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


def test_jsonl_validates_existing_lines_only_once_at_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("bogda.events.jsonl")
    original = module._validate_existing_lines
    calls = 0

    def counted(path: Path) -> None:
        nonlocal calls
        calls += 1
        original(path)

    monkeypatch.setattr(module, "_validate_existing_lines", counted)
    path = tmp_path / "events.jsonl"
    path.write_text(make_event().model_dump_json() + "\n", encoding="utf-8")
    sink = JsonlRunEventSink(path)
    sink.append(make_event(run_id="run-2"))
    sink.append(make_event(run_id="run-3"))

    assert calls == 1


@pytest.mark.parametrize("mutation", ["append", "truncate", "replace", "modify"])
def test_jsonl_rejects_external_file_changes_between_appends(
    tmp_path: Path, mutation: str
) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlRunEventSink(path)
    sink.append(make_event())

    if mutation == "append":
        with path.open("ab") as handle:
            handle.write(b"external\n")
    elif mutation == "truncate":
        path.write_bytes(b"")
    elif mutation == "replace":
        replacement = tmp_path / "replacement.jsonl"
        replacement.write_text(make_event(run_id="replacement").model_dump_json() + "\n", encoding="utf-8")
        path.unlink()
        replacement.replace(path)
    else:
        original = path.read_bytes()
        path.write_bytes(original.replace(b"run-1", b"run-9", 1))

    with pytest.raises(ValueError, match="changed"):
        sink.append(make_event(run_id="after-change"))


def _freeze_target_metadata(
    monkeypatch: pytest.MonkeyPatch, path: Path
) -> int:
    real_stat = Path.stat
    baseline = real_stat(path)

    class ControlledStat:
        def __init__(self, observed) -> None:
            self._observed = observed

        @property
        def st_dev(self):
            return baseline.st_dev

        @property
        def st_ino(self):
            return baseline.st_ino

        @property
        def st_size(self):
            return self._observed.st_size

        @property
        def st_mtime_ns(self):
            return baseline.st_mtime_ns

        def __getattr__(self, name: str):
            return getattr(self._observed, name)

    def controlled_stat(candidate: Path, *args, **kwargs):
        observed = real_stat(candidate, *args, **kwargs)
        if candidate == path:
            return ControlledStat(observed)
        return observed

    monkeypatch.setattr(Path, "stat", controlled_stat)
    return baseline.st_mtime_ns


def test_jsonl_rejects_twenty_same_size_mutations_without_mtime_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlRunEventSink(path)
    sink.append(make_event(run_id="run-000"))
    frozen_mtime_ns = _freeze_target_metadata(monkeypatch, path)

    for index in range(1, 21):
        original = path.read_bytes()
        mutated = original.replace(
            f"run-{index - 1:03d}".encode(), f"run-{index:03d}".encode(), 1
        )
        assert mutated != original
        assert len(mutated) == len(original)
        path.write_bytes(mutated)
        os.utime(path, ns=(frozen_mtime_ns, frozen_mtime_ns))

        with pytest.raises(ValueError, match="changed"):
            sink.append(make_event(run_id="after-change"))


def test_jsonl_detects_large_same_size_change_with_bounded_streaming_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("bogda.events.jsonl")
    path = tmp_path / "events.jsonl"
    event = make_event(reason="mutation-AAAA" + "x" * 131_072)
    path.write_text(event.model_dump_json() + "\n", encoding="utf-8")
    sink = JsonlRunEventSink(path)
    frozen_mtime_ns = _freeze_target_metadata(monkeypatch, path)

    original = path.read_bytes()
    mutated = original.replace(b"mutation-AAAA", b"mutation-BBBB", 1)
    assert mutated != original
    assert len(mutated) == len(original)
    path.write_bytes(mutated)
    os.utime(path, ns=(frozen_mtime_ns, frozen_mtime_ns))

    read_calls: list[tuple[int, int]] = []
    real_open = Path.open

    class TrackedHandle:
        def __init__(self, handle) -> None:
            self._handle = handle

        def __enter__(self):
            self._handle.__enter__()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return self._handle.__exit__(exc_type, exc_value, traceback)

        def read(self, size: int = -1):
            value = self._handle.read(size)
            read_calls.append((size, len(value)))
            return value

        def read1(self, size: int = -1):
            value = self._handle.read1(size)
            read_calls.append((size, len(value)))
            return value

        def readinto(self, buffer) -> int:
            count = self._handle.readinto(buffer)
            read_calls.append((len(buffer), count))
            return count

        def __getattr__(self, name: str):
            return getattr(self._handle, name)

    def tracked_open(candidate: Path, *args, **kwargs):
        handle = real_open(candidate, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if candidate == path and "r" in mode and "b" in mode:
            return TrackedHandle(handle)
        return handle

    monkeypatch.setattr(module.Path, "open", tracked_open)
    max_chunk = 64 * 1024

    with pytest.raises(ValueError, match="changed"):
        sink.append(make_event(run_id="after-change"))

    assert read_calls
    assert all(0 < requested <= max_chunk for requested, _ in read_calls)
    assert sum(returned for _, returned in read_calls) >= len(mutated)
    assert sum(returned > 1 for _, returned in read_calls) >= 2


def test_jsonl_failed_append_that_changes_size_fails_closed_on_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("bogda.events.jsonl")
    path = tmp_path / "events.jsonl"
    sink = JsonlRunEventSink(path)
    original_fsync = module.os.fsync

    def fail_fsync(fd: int) -> None:
        raise OSError("fsync failure")

    monkeypatch.setattr(module.os, "fsync", fail_fsync)
    with pytest.raises(ValueError, match="append"):
        sink.append(make_event())
    monkeypatch.setattr(module.os, "fsync", original_fsync)

    with pytest.raises(ValueError, match="changed"):
        sink.append(make_event(run_id="retry"))
