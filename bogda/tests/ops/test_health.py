from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3

import pytest

from bogda.ops import health
from bogda.ops.health import (
    DEFAULT_UNITS,
    append_sample,
    nearest_rank_p95,
    parse_meminfo,
    parse_vmstat,
    sample_health,
    summarize_samples,
    wait_for_api,
)


def make_database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute("create table runs (id text primary key)")
    return path


def test_parsers_convert_memory_and_vmstat_facts() -> None:
    assert parse_meminfo("MemAvailable: 512000 kB\nSwapTotal: 102400 kB\nSwapFree: 76800 kB\n") == {
        "MemAvailable": 512000 * 1024,
        "SwapTotal": 102400 * 1024,
        "SwapFree": 76800 * 1024,
    }
    assert parse_vmstat("oom_kill 2\npgfault 99\n") == {"oom_kill": 2, "pgfault": 99}


def test_sample_records_controlled_facts(tmp_path: Path) -> None:
    units = {unit: "active" for unit in DEFAULT_UNITS}
    database = make_database(tmp_path / "prefect.db")
    sample = sample_health(
        meminfo_text="MemAvailable: 512000 kB\nSwapTotal: 102400 kB\nSwapFree: 76800 kB\n",
        vmstat_text="oom_kill 2\n",
        api_probe=lambda _: (True, 25.0),
        units_probe=lambda _: units,
        disk_free=lambda _: 10_000,
        database=database,
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )

    assert sample["timestamp"] == "2026-08-24T12:00:00Z"
    assert sample["api_ok"] is True
    assert sample["api_latency_ms"] == 25.0
    assert sample["mem_available_bytes"] == 512000 * 1024
    assert sample["swap_total_bytes"] == 102400 * 1024
    assert sample["swap_used_bytes"] == 25600 * 1024
    assert sample["oom_kill_count"] == 2
    assert sample["disk_free_bytes"] == 10_000
    assert sample["database_bytes"] == database.stat().st_size
    assert sample["database_integrity"] == "ok"
    assert sample["units"] == units
    json.dumps(sample)


def test_sample_records_unavailable_api_without_inventing_latency(tmp_path: Path) -> None:
    sample = sample_health(
        meminfo_text="MemAvailable: 1 kB\nSwapTotal: 2 kB\nSwapFree: 1 kB\n",
        vmstat_text="oom_kill 0\n",
        api_probe=lambda _: (False, None),
        units_probe=lambda _: {},
        disk_free=lambda _: 1,
        database=make_database(tmp_path / "prefect.db"),
    )

    assert sample["api_ok"] is False
    assert sample["api_latency_ms"] is None


def test_probe_api_adds_basic_auth_without_returning_or_logging_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def controlled_urlopen(request: object, timeout: float) -> Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("PREFECT_API_AUTH_STRING", "alice:secret")
    monkeypatch.setattr(health.request, "urlopen", controlled_urlopen)

    result = health.probe_api("http://127.0.0.1:4200/api", timeout=1.25)

    expected = "Basic " + base64.b64encode(b"alice:secret").decode("ascii")
    request = captured["request"]
    assert isinstance(request, health.request.Request)
    assert request.full_url == "http://127.0.0.1:4200/api/health"
    assert request.get_header("Authorization") == expected
    assert captured["timeout"] == 1.25
    assert result[0] is True
    assert "secret" not in repr(result)
    assert "secret" not in repr(captured)


def test_probe_api_omits_auth_header_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[object] = []

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.delenv("PREFECT_API_AUTH_STRING", raising=False)
    monkeypatch.setattr(health.request, "urlopen", lambda request, timeout: (captured.append(request) or Response()))

    assert health.probe_api("http://example.test/api")[0] is True
    assert isinstance(captured[0], health.request.Request)
    assert captured[0].get_header("Authorization") is None


def test_append_sample_writes_one_compact_json_line(tmp_path: Path) -> None:
    path = tmp_path / "evidence" / "health.jsonl"
    append_sample(path, {"timestamp": "2026-08-24T12:00:00Z", "api_ok": True})

    assert path.read_text(encoding="utf-8") == '{"api_ok":true,"timestamp":"2026-08-24T12:00:00Z"}\n'


def test_summary_reports_72_hour_window_evidence() -> None:
    started = datetime(2026, 8, 21, tzinfo=UTC)
    timestamps = [started, started + timedelta(minutes=5), started + timedelta(minutes=10), started + timedelta(minutes=25)]
    samples = [
        {
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "api_ok": index != 2,
            "api_latency_ms": latency,
            "mem_available_bytes": memory,
            "swap_used_bytes": swap,
            "oom_kill_count": oom,
            "database_integrity": integrity,
            "disk_free_bytes": disk,
        }
        for index, (timestamp, latency, memory, swap, oom, integrity, disk) in enumerate(
            zip(timestamps, [10, 20, 30, 1000], [400, 300, 200, 100], [10, 20, 30, 50], [2, 2, 3, 3], ["ok", "ok", "failed", "ok"], [1000, 900, 800, 700])
        )
    ]

    summary = summarize_samples(samples)

    assert summary == {
        "started_at": "2026-08-21T00:00:00Z",
        "ended_at": "2026-08-21T00:25:00Z",
        "sample_count": 4,
        "missing_intervals": 2,
        "api_failure_count": 1,
        "api_latency_p95_ms": 1000,
        "min_mem_available_bytes": 100,
        "swap_growth_bytes": 40,
        "oom_kill_delta": 1,
        "database_integrity_failure_count": 1,
        "min_disk_free_bytes": 700,
    }


def test_summary_sorts_samples_and_handles_empty_metrics() -> None:
    samples = [
        {"timestamp": "2026-08-24T00:10:00Z", "api_ok": True, "api_latency_ms": None, "disk_free_bytes": None},
        {"timestamp": "2026-08-24T00:00:00Z", "api_ok": False, "api_latency_ms": None, "disk_free_bytes": None},
    ]
    summary = summarize_samples(samples)

    assert summary["started_at"] == "2026-08-24T00:00:00Z"
    assert summary["ended_at"] == "2026-08-24T00:10:00Z"
    assert summary["api_latency_p95_ms"] is None
    assert summary["min_disk_free_bytes"] is None
    assert nearest_rank_p95([]) is None


def test_wait_for_api_stops_after_first_success() -> None:
    results = iter([(False, None), (True, 12.0), (True, 8.0)])
    sleeps: list[float] = []

    assert wait_for_api("http://api", timeout=3.0, interval=0.25, probe=lambda _: next(results), sleep=sleeps.append)
    assert sleeps == [0.25]


def test_wait_for_api_returns_false_after_bounded_attempts() -> None:
    calls: list[str] = []

    def probe(url: str) -> tuple[bool, float | None]:
        calls.append(url)
        return False, None

    assert not wait_for_api("http://api", timeout=2.0, interval=0.5, probe=probe, sleep=lambda _: None)
    assert len(calls) == 4


def test_health_cli_summarize_reads_nonblank_jsonl(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "health.jsonl"
    input_path.write_text(
        "\n" + json.dumps({"timestamp": "2026-08-24T00:00:00Z", "api_ok": True}) + "\n",
        encoding="utf-8",
    )

    assert health.main(["summarize", "--input", str(input_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["sample_count"] == 1
