"""Health evidence collection and deterministic window summaries for Bogda."""

from __future__ import annotations

import argparse
import base64
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable, Mapping, Sequence
from urllib import request

from .snapshot import integrity_check


DEFAULT_UNITS = (
    "bogda-prefect-server.service",
    "bogda-pi-worker.service",
    "bogda-prefect-snapshot.service",
    "bogda-prefect-snapshot.timer",
    "bogda-shadow-health.service",
    "bogda-shadow-health.timer",
)


def parse_meminfo(text: str) -> dict[str, int]:
    """Parse ``/proc/meminfo`` values, converting kB values to bytes."""
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, raw_value = line.split(":", 1)
        fields = raw_value.strip().split()
        if not fields:
            continue
        try:
            value = int(fields[0])
        except ValueError:
            continue
        if len(fields) > 1 and fields[1].lower() == "kb":
            value *= 1024
        values[name] = value
    return values


def parse_vmstat(text: str) -> dict[str, int]:
    """Parse integer counters from ``/proc/vmstat``."""
    values: dict[str, int] = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            values[fields[0]] = int(fields[1])
        except ValueError:
            continue
    return values


def probe_api(url: str, timeout: float = 2.0) -> tuple[bool, float | None]:
    """Probe Prefect's health endpoint, returning success and latency in ms."""
    endpoint = url.rstrip("/") + "/health"
    headers: dict[str, str] = {}
    auth = os.environ.get("PREFECT_API_AUTH_STRING")
    if auth is not None:
        encoded = base64.b64encode(auth.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {encoded}"
    health_request = request.Request(endpoint, headers=headers, method="GET")
    started = time.monotonic()
    try:
        response = request.urlopen(health_request, timeout=timeout)
        close = getattr(response, "close", None)
        if close is not None:
            close()
    except Exception:
        return False, None
    return True, (time.monotonic() - started) * 1000.0


def unit_states(
    units: tuple[str, ...],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, str]:
    """Read each systemd unit state once; never mutate or restart units."""
    states: dict[str, str] = {}
    for unit in units:
        try:
            result = runner(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            state = result.stdout.strip()
            states[unit] = state or "unknown"
        except Exception:
            states[unit] = "unknown"
    return states


def disk_free_bytes(path: Path) -> int:
    return int(shutil.disk_usage(path).free)


def append_sample(path: Path, sample: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(sample), sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(encoded + "\n")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("sample timestamp must be a string")
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _format_timestamp(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def nearest_rank_p95(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _numeric_values(samples: Sequence[Mapping[str, object]], key: str) -> list[float]:
    return [float(value) for sample in samples if (value := sample.get(key)) is not None]


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _summarize_oom_counter(
    samples: Sequence[Mapping[str, object]],
) -> tuple[int | float | None, int, int]:
    """Sum known adjacent OOM increments while retaining reboot and gap evidence."""
    delta: int | float = 0
    previous: int | float | None = None
    saw_numeric = False
    unavailable_span_open = False
    resets = 0
    unavailable_spans = 0
    for sample in samples:
        current = sample.get("oom_kill_count")
        if not _is_number(current):
            if not unavailable_span_open:
                unavailable_spans += 1
                unavailable_span_open = True
            previous = None
            continue
        saw_numeric = True
        unavailable_span_open = False
        if previous is not None:
            if current >= previous:
                delta += current - previous
            else:
                resets += 1
        previous = current
    return (delta if saw_numeric else None), resets, unavailable_spans


def summarize_samples(
    samples: Sequence[Mapping[str, object]], expected_interval_seconds: int = 300
) -> dict[str, object]:
    ordered = sorted(samples, key=lambda sample: _parse_timestamp(sample["timestamp"]))
    timestamps = [_parse_timestamp(sample["timestamp"]) for sample in ordered]
    missing_intervals = 0
    for previous, current in zip(timestamps, timestamps[1:]):
        delta = (current - previous).total_seconds()
        missing_intervals += max(0, round(delta / expected_interval_seconds) - 1)

    latency = _numeric_values(ordered, "api_latency_ms")
    memory = _numeric_values(ordered, "mem_available_bytes")
    disk = _numeric_values(ordered, "disk_free_bytes")
    first_swap = ordered[0].get("swap_used_bytes") if ordered else None
    last_swap = ordered[-1].get("swap_used_bytes") if ordered else None
    oom_delta, oom_resets, oom_unavailable_spans = _summarize_oom_counter(ordered)
    return {
        "started_at": _format_timestamp(timestamps[0]) if timestamps else None,
        "ended_at": _format_timestamp(timestamps[-1]) if timestamps else None,
        "sample_count": len(ordered),
        "missing_intervals": missing_intervals,
        "api_failure_count": sum(1 for sample in ordered if sample.get("api_ok") is False),
        "api_latency_p95_ms": nearest_rank_p95(latency),
        "min_mem_available_bytes": min(memory) if memory else None,
        "swap_growth_bytes": last_swap - first_swap if _is_number(first_swap) and _is_number(last_swap) else None,
        "oom_kill_delta": oom_delta,
        "oom_kill_counter_reset_count": oom_resets,
        "oom_kill_unavailable_span_count": oom_unavailable_spans,
        "database_integrity_failure_count": sum(
            1 for sample in ordered if sample.get("database_integrity") not in (None, "ok")
        ),
        "min_disk_free_bytes": min(disk) if disk else None,
    }


def sample_health(
    *,
    meminfo_text: str | None = None,
    vmstat_text: str | None = None,
    api_url: str = "http://127.0.0.1:4200/api",
    api_probe: Callable[[str], tuple[bool, float | None]] = probe_api,
    units: tuple[str, ...] = DEFAULT_UNITS,
    units_probe: Callable[[tuple[str, ...]], Mapping[str, str]] = unit_states,
    disk_root: Path = Path("/mnt/nas"),
    disk_free: Callable[[Path], int] = disk_free_bytes,
    database: Path = Path("/mnt/nas/.bogda/prefect/prefect.db"),
    now: datetime | None = None,
) -> dict[str, object]:
    meminfo = parse_meminfo(
        meminfo_text if meminfo_text is not None else Path("/proc/meminfo").read_text(encoding="utf-8")
    )
    vmstat = parse_vmstat(
        vmstat_text if vmstat_text is not None else Path("/proc/vmstat").read_text(encoding="utf-8")
    )
    api_ok, api_latency = api_probe(api_url)
    database = Path(database)
    try:
        database_bytes: int | None = database.stat().st_size
    except OSError:
        database_bytes = None
    try:
        database_integrity = integrity_check(database)
    except Exception:
        database_integrity = "unavailable" if not database.exists() else "error"
    mem_available = meminfo.get("MemAvailable")
    swap_total = meminfo.get("SwapTotal")
    swap_free = meminfo.get("SwapFree")
    swap_used = swap_total - swap_free if swap_total is not None and swap_free is not None else None
    timestamp = _format_timestamp(_as_utc(now or datetime.now(UTC)))
    return {
        "timestamp": timestamp,
        "api_ok": api_ok,
        "api_latency_ms": api_latency,
        "mem_available_bytes": mem_available,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_used,
        "oom_kill_count": vmstat.get("oom_kill"),
        "disk_free_bytes": disk_free(Path(disk_root)),
        "database_bytes": database_bytes,
        "database_integrity": database_integrity,
        "units": dict(units_probe(units)),
    }


def wait_for_api(
    url: str,
    timeout: float,
    interval: float = 1.0,
    probe: Callable[[str], tuple[bool, float | None]] = probe_api,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    if timeout < 0 or interval <= 0:
        raise ValueError("timeout must be non-negative and interval must be positive")
    if timeout == 0:
        return False
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if probe is probe_api:
            healthy = probe(url, timeout=remaining)[0]
        else:
            healthy = probe(url)[0]
        if healthy:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        sleep(min(interval, remaining))


def _read_samples(path: Path) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("each sample must be a JSON object")
            samples.append(value)
    return samples


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bogda.ops.health")
    commands = parser.add_subparsers(dest="command", required=True)
    sample_parser = commands.add_parser("sample")
    sample_parser.add_argument("--output", required=True, type=Path)
    summary_parser = commands.add_parser("summarize")
    summary_parser.add_argument("--input", required=True, type=Path)
    wait_parser = commands.add_parser("wait-api")
    wait_parser.add_argument("--url", required=True)
    wait_parser.add_argument("--timeout", required=True, type=float)
    args = parser.parse_args(arguments)

    try:
        if args.command == "sample":
            value = sample_health()
            append_sample(args.output, value)
            report: object = value
        elif args.command == "summarize":
            report = summarize_samples(_read_samples(args.input))
        else:
            return 0 if wait_for_api(args.url, args.timeout) else 1
    except Exception as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
