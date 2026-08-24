# Bogda Pi Shadow Deployment Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and locally verify a repository-native Pi deployment bundle for Bogda without connecting to or modifying the Pi.

**Architecture:** Keep machine contracts in a TOML manifest, environment example, and six systemd units. Put testable SQLite backup and health-evidence logic in small Python standard-library modules; keep shell scripts limited to the future Linux installation boundary. The local dry-run validates and describes changes but never writes system paths or calls systemd.

**Tech Stack:** Python 3.11 standard library (`argparse`, `dataclasses`, `hashlib`, `json`, `sqlite3`, `tomllib`, `urllib`), Prefect 3.8.3, pytest 8, POSIX shell, systemd, uv.

**Spec:** `docs/superpowers/specs/2026-08-24-bogda-pi-shadow-bundle-design.md`

## Global Constraints

- This plan creates and tests local files only. Do not use SSH, scp, Pi credentials, `systemctl`, or writes under host `/etc`, `/opt`, or `/mnt`.
- Keep Python support at `>=3.11,<3.14` and Prefect pinned to `3.8.3`; add no dependency.
- Use `/opt/bogda`, `/etc/bogda`, `/mnt/nas/.bogda`, and `/mnt/nas/.bogda/prefect/prefect.db` exactly.
- The service account and group are `bogda`; the work pool is `pi-service`; worker concurrency is exactly `1`.
- Repository files contain only `SET_ON_PI_NOT_IN_GIT`, never a real Basic Auth value.
- SQLite is local ext4-backed storage. The bundle must not configure SMB access to the database.
- Install and rollback may manage only `bogda-*` units and must preserve `/mnt/nas/.bogda`.
- Do not import, invoke, edit, restart, or migrate Orchestra.
- Do not add Ansible, Docker, PostgreSQL, Redis, Kubernetes, Wake-on-LAN, GPU routing, or Windows power control.
- Preserve the existing unrelated working-tree changes listed in Mission 041.

## File Map

| File | Responsibility |
|---|---|
| `bogda/src/bogda/ops/bundle.py` | Parse and validate the immutable deployment contract; render dry-run output |
| `bogda/src/bogda/ops/snapshot.py` | Create, verify, and prune consistent SQLite snapshots |
| `bogda/src/bogda/ops/health.py` | Sample Pi health facts and summarize an evidence window |
| `bogda/deploy/pi/manifest.toml` | Single source of truth for paths, identity, service names, and schedules |
| `bogda/deploy/pi/bogda.env.example` | Non-secret Prefect runtime variables |
| `bogda/deploy/pi/systemd/*` | Server, worker, snapshot, and health service/timer definitions |
| `bogda/deploy/pi/install.sh` | Explicit dry-run/install boundary for a future authorized Pi window |
| `bogda/deploy/pi/rollback.sh` | Restore only prior Bogda units/config while preserving data |
| `bogda/docs/pi-shadow-runbook.md` | Human gates for future deployment, 72-hour evidence, recovery, and rollback |
| `bogda/tests/ops/*` | Contract, snapshot, health, and shell-boundary tests |

---

### Task 1: Deployment Contract and systemd Assets

**Files:**

- Create: `bogda/src/bogda/ops/__init__.py`
- Create: `bogda/src/bogda/ops/bundle.py`
- Create: `bogda/deploy/pi/manifest.toml`
- Create: `bogda/deploy/pi/bogda.env.example`
- Create: `bogda/deploy/pi/systemd/bogda-prefect-server.service`
- Create: `bogda/deploy/pi/systemd/bogda-pi-worker.service`
- Create: `bogda/deploy/pi/systemd/bogda-prefect-snapshot.service`
- Create: `bogda/deploy/pi/systemd/bogda-prefect-snapshot.timer`
- Create: `bogda/deploy/pi/systemd/bogda-shadow-health.service`
- Create: `bogda/deploy/pi/systemd/bogda-shadow-health.timer`
- Create: `bogda/tests/ops/test_bundle.py`

**Interfaces:**

- Consumes: Python 3.11 `tomllib`; repository path passed by the caller.
- Produces: `BundleManifest`, `load_manifest(path: Path) -> BundleManifest`, `validate_bundle(bundle_root: Path) -> tuple[str, ...]`, and `render_dry_run(bundle_root: Path) -> tuple[str, ...]`.
- `BundleManifest` string fields: `service_user`, `service_group`, `program_root`, `config_root`, `env_file`, `data_root`, `prefect_home`, `database`, `snapshot_root`, `health_root`, `api_url`, and `work_pool`; `worker_limit: int`; `units: tuple[str, ...]`.

- [ ] **Step 1: Write failing contract tests**

Create tests that copy `bogda/deploy/pi` to `tmp_path`, then assert the clean bundle validates, the unit set is exact, and these mutations each produce a nonempty `validate_bundle()` result: `data_root = "/mnt/broker"`, `worker_limit = 2`, a missing unit, a non-`bogda-` unit, and a real-looking auth value. Separately assert malformed TOML, a missing key, or a non-integer `worker_limit` makes `load_manifest()` raise `ValueError`. Also assert `render_dry_run()` returns only descriptive lines beginning with `CHECK`, `INSTALL`, or `PRESERVE` and leaves the copied tree byte-for-byte unchanged.

```python
EXPECTED_UNITS = {
    "bogda-prefect-server.service",
    "bogda-pi-worker.service",
    "bogda-prefect-snapshot.service",
    "bogda-prefect-snapshot.timer",
    "bogda-shadow-health.service",
    "bogda-shadow-health.timer",
}

def test_clean_bundle_has_fixed_contract(bundle_copy: Path) -> None:
    manifest = load_manifest(bundle_copy / "manifest.toml")
    assert manifest.data_root == "/mnt/nas/.bogda"
    assert manifest.worker_limit == 1
    assert set(manifest.units) == EXPECTED_UNITS
    assert validate_bundle(bundle_copy) == ()

def test_dry_run_is_read_only(bundle_copy: Path) -> None:
    before = {p.relative_to(bundle_copy): p.read_bytes() for p in bundle_copy.rglob("*") if p.is_file()}
    lines = render_dry_run(bundle_copy)
    after = {p.relative_to(bundle_copy): p.read_bytes() for p in bundle_copy.rglob("*") if p.is_file()}
    assert lines
    assert all(line.startswith(("CHECK ", "INSTALL ", "PRESERVE ")) for line in lines)
    assert after == before
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run: `Set-Location bogda; uv run --python 3.11 pytest tests/ops/test_bundle.py -v`

Expected: collection fails because `bogda.ops.bundle` does not exist.

- [ ] **Step 3: Add the manifest and non-secret environment example**

Use these exact values in `manifest.toml`:

```toml
service_user = "bogda"
service_group = "bogda"
program_root = "/opt/bogda"
config_root = "/etc/bogda"
env_file = "/etc/bogda/bogda.env"
data_root = "/mnt/nas/.bogda"
prefect_home = "/mnt/nas/.bogda/prefect"
database = "/mnt/nas/.bogda/prefect/prefect.db"
snapshot_root = "/mnt/nas/.bogda/snapshots"
health_root = "/mnt/nas/.bogda/manifests/health"
api_url = "http://127.0.0.1:4200/api"
work_pool = "pi-service"
worker_limit = 1
units = [
  "bogda-prefect-server.service",
  "bogda-pi-worker.service",
  "bogda-prefect-snapshot.service",
  "bogda-prefect-snapshot.timer",
  "bogda-shadow-health.service",
  "bogda-shadow-health.timer",
]
```

Use this complete `bogda.env.example`:

```dotenv
PREFECT_HOME=/mnt/nas/.bogda/prefect
PREFECT_API_URL=http://127.0.0.1:4200/api
PREFECT_SERVER_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT
PREFECT_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT
```

- [ ] **Step 4: Add the six systemd units**

All services use `User=bogda`, `Group=bogda`, `EnvironmentFile=/etc/bogda/bogda.env`, `RequiresMountsFor=/mnt/nas/.bogda`, and `Restart=on-failure`. Use these exact commands:

```ini
# server
ExecStart=/opt/bogda/.venv/bin/prefect server start --host 0.0.0.0 --port 4200

# worker, after server and guarded by the health waiter
ExecStartPre=/opt/bogda/.venv/bin/python -m bogda.ops.health wait-api --url http://127.0.0.1:4200/api --timeout 60
ExecStart=/opt/bogda/.venv/bin/prefect worker start --pool pi-service --type process --limit 1 --create-pool-if-not-found

# snapshot oneshot
ExecStart=/opt/bogda/.venv/bin/python -m bogda.ops.snapshot create --source /mnt/nas/.bogda/prefect/prefect.db --destination /mnt/nas/.bogda/snapshots --keep 7

# health oneshot
ExecStart=/opt/bogda/.venv/bin/python -m bogda.ops.health sample --output /mnt/nas/.bogda/manifests/health/samples.jsonl
```

Set snapshot timer to daily persistence and health timer to `OnBootSec=5min`, `OnUnitActiveSec=5min`, `Persistent=true`. The worker declares `After=` and `Requires=` on `bogda-prefect-server.service`. None of the six units may mention Orchestra.

- [ ] **Step 5: Implement manifest validation and dry-run rendering**

Implement `BundleManifest` as a frozen dataclass. `load_manifest()` rejects missing keys and non-integer `worker_limit`. `validate_bundle()` returns all violations without mutating files; it checks every fixed value above, exact unit inventory, unit filename prefix, required unit fragments, both auth lines having the sentinel, and absence of `/mnt/broker` and `orchestra-` in deployable assets. Its CLI supports `check BUNDLE_ROOT` and `dry-run BUNDLE_ROOT`, prints one line per result, and exits nonzero on violations.

`render_dry_run()` lists: manifest validation, service account, target directories, env destination, each unit source/destination, daemon reload, preserved data root, and the fact that no service starts unless `--start` is supplied later.

- [ ] **Step 6: Run focused and full tests**

Run:

```powershell
Set-Location bogda
uv run --python 3.11 pytest tests/ops/test_bundle.py -v
uv run --python 3.11 pytest -m "not integration" -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 1**

```powershell
git add bogda/src/bogda/ops bogda/deploy/pi/manifest.toml bogda/deploy/pi/bogda.env.example bogda/deploy/pi/systemd bogda/tests/ops/test_bundle.py
git commit -m "feat(bogda): define Pi shadow bundle contract"
```

---

### Task 2: Consistent SQLite Snapshot and Restore Verification

**Files:**

- Create: `bogda/src/bogda/ops/snapshot.py`
- Modify: `bogda/src/bogda/ops/__init__.py`
- Create: `bogda/tests/ops/test_snapshot.py`

**Interfaces:**

- Consumes: paths from `BundleManifest`; a local SQLite file.
- Produces: `sha256_file(path: Path) -> str`, `integrity_check(path: Path) -> str`, `create_snapshot(source: Path, destination: Path, keep: int = 7, now: datetime | None = None) -> dict[str, object]`, `verify_snapshot(snapshot: Path, manifest: Path, restore_dir: Path) -> dict[str, object]`, and `prune_snapshots(destination: Path, keep: int) -> tuple[Path, ...]`.

- [ ] **Step 1: Write failing snapshot tests**

Create a source database containing a `runs(id TEXT PRIMARY KEY, result TEXT)` row. Assert that `create_snapshot()` produces `prefect-20260824T120000Z.db`, the adjacent `.json`, and atomic `latest.json`; that the database and manifest hashes match; and that `verify_snapshot()` copies to a caller-owned temporary restore directory, returns `integrity_check == "ok"`, and preserves the row.

Add two failure tests: a corrupt source must not replace a previously valid `latest.json`, and `keep=2` after three successful snapshots must retain exactly two database/manifest pairs.

```python
def test_snapshot_can_be_verified_and_read(source_db: Path, tmp_path: Path) -> None:
    report = create_snapshot(source_db, tmp_path / "snapshots", now=datetime(2026, 8, 24, 12, tzinfo=UTC))
    verified = verify_snapshot(Path(report["snapshot"]), Path(report["manifest"]), tmp_path / "restore")
    assert verified["sha256"] == report["sha256"]
    assert verified["integrity_check"] == "ok"
    with sqlite3.connect(verified["restored_path"]) as connection:
        assert connection.execute("select result from runs where id='r1'").fetchone() == ("accepted",)
```

- [ ] **Step 2: Run the tests and confirm missing symbols**

Run: `Set-Location bogda; uv run --python 3.11 pytest tests/ops/test_snapshot.py -v`

Expected: collection fails because the snapshot functions do not exist.

- [ ] **Step 3: Implement consistent snapshot creation**

Open the source read-only for validation, run `PRAGMA integrity_check`, then create a temporary database in `destination` via `sqlite3.Connection.backup()`. Run integrity check on the temporary backup, atomically rename it to the timestamped `.db`, atomically write its adjacent JSON manifest, and only then atomically replace `latest.json` with the same manifest content.

Manifest keys are `created_at`, `source`, `snapshot`, `bytes`, `sha256`, `integrity_check`, and `tool_version` (`"1"`). Reject `keep < 1`. On every exception, delete only temporary files created by the current attempt; never delete the source, prior snapshots, or prior `latest.json`.

- [ ] **Step 4: Implement restore verification and retention**

`verify_snapshot()` loads the named adjacent manifest, compares recorded and actual hash/size, copies the snapshot to `restore_dir/prefect-restored.db`, runs integrity check, and returns a report without touching the live path. `prune_snapshots()` sorts timestamped `.db` files by filename, removes the oldest database plus adjacent JSON until `keep` pairs remain, and never removes `latest.json`.

The CLI subcommands are:

```text
python -m bogda.ops.snapshot create --source PATH --destination PATH --keep 7
python -m bogda.ops.snapshot verify --snapshot PATH --manifest PATH --restore-dir PATH
```

Each prints one JSON object and returns nonzero on failure without exposing environment variables.

- [ ] **Step 5: Run focused and full tests**

Run:

```powershell
Set-Location bogda
uv run --python 3.11 pytest tests/ops/test_snapshot.py -v
uv run --python 3.11 pytest -m "not integration" -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add bogda/src/bogda/ops/__init__.py bogda/src/bogda/ops/snapshot.py bogda/tests/ops/test_snapshot.py
git commit -m "feat(bogda): snapshot and verify Prefect SQLite"
```

---

### Task 3: Health Sampling and 72-Hour Evidence Summary

**Files:**

- Create: `bogda/src/bogda/ops/health.py`
- Modify: `bogda/src/bogda/ops/__init__.py`
- Create: `bogda/tests/ops/test_health.py`

**Interfaces:**

- Consumes: `/proc/meminfo`, `/proc/vmstat`, `shutil.disk_usage`, `systemctl is-active`, the Prefect API health endpoint, and `snapshot.integrity_check` through injected callables/paths.
- Produces: `parse_meminfo(text: str) -> dict[str, int]`, `parse_vmstat(text: str) -> dict[str, int]`, `probe_api(url: str, timeout: float = 2.0) -> tuple[bool, float | None]`, `unit_states(units: tuple[str, ...], runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> dict[str, str]`, `disk_free_bytes(path: Path) -> int`, `append_sample(path: Path, sample: Mapping[str, object]) -> None`, `nearest_rank_p95(values: Sequence[float]) -> float | None`, and `summarize_samples(samples: Sequence[Mapping[str, object]], expected_interval_seconds: int = 300) -> dict[str, object]`.
- `sample_health(*, meminfo_text: str | None = None, vmstat_text: str | None = None, api_url: str = "http://127.0.0.1:4200/api", api_probe: Callable[[str], tuple[bool, float | None]] = probe_api, units: tuple[str, ...] = DEFAULT_UNITS, units_probe: Callable[[tuple[str, ...]], Mapping[str, str]] = unit_states, disk_root: Path = Path("/mnt/nas"), disk_free: Callable[[Path], int] = disk_free_bytes, database: Path = Path("/mnt/nas/.bogda/prefect/prefect.db"), now: datetime | None = None) -> dict[str, object]`.
- `wait_for_api(url: str, timeout: float, interval: float = 1.0, probe: Callable[[str], tuple[bool, float | None]] = probe_api, sleep: Callable[[float], None] = time.sleep) -> bool`.

- [ ] **Step 1: Write failing parser and sampler tests**

Use controlled meminfo/vmstat text and injected API/unit/disk facts. Assert `MemAvailable`, `SwapTotal - SwapFree`, `oom_kill`, API latency, disk free bytes, database bytes/integrity, and all six unit states appear in one JSON-serializable sample. Assert an unavailable API yields `api_ok=false` and `api_latency_ms=null`, not an invented success.

```python
def test_sample_records_controlled_facts(tmp_path: Path) -> None:
    sample = sample_health(
        meminfo_text="MemAvailable: 512000 kB\nSwapTotal: 102400 kB\nSwapFree: 76800 kB\n",
        vmstat_text="oom_kill 2\n",
        api_probe=lambda _: (True, 25.0),
        units_probe=lambda _: {"bogda-prefect-server.service": "active"},
        disk_free=lambda _: 10_000,
        database=make_database(tmp_path / "prefect.db"),
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )
    assert sample["mem_available_bytes"] == 512000 * 1024
    assert sample["swap_used_bytes"] == 25600 * 1024
    assert sample["oom_kill_count"] == 2
    assert sample["database_integrity"] == "ok"
```

- [ ] **Step 2: Write failing summary and wait tests**

Build four samples with one 15-minute timestamp gap, latency values `[10, 20, 30, 1000]`, decreasing memory, growing swap, one OOM counter increment, one database failure, and disk values. Assert exact sample count, missing interval count `2`, nearest-rank p95 `1000`, minimum memory, swap growth, OOM delta, integrity failure count, and minimum disk. Verify `wait_for_api()` stops after the first success and returns false after its bounded attempts.

- [ ] **Step 3: Run tests and confirm missing module failure**

Run: `Set-Location bogda; uv run --python 3.11 pytest tests/ops/test_health.py -v`

Expected: collection fails because `bogda.ops.health` does not exist.

- [ ] **Step 4: Implement parsers, probes, and one-sample collection**

Convert `kB` values to bytes. Probe `url.rstrip("/") + "/health"` with `urllib.request.urlopen`, measure with `time.monotonic`, and convert HTTP/network errors to `(False, None)`. Invoke `systemctl is-active UNIT` once per fixed unit with a five-second timeout and record stdout or `unknown`; do not restart anything.

`sample_health()` returns: `timestamp`, `api_ok`, `api_latency_ms`, `mem_available_bytes`, `swap_total_bytes`, `swap_used_bytes`, `oom_kill_count`, `disk_free_bytes`, `database_bytes`, `database_integrity`, and `units`. `append_sample()` creates only the requested parent, opens UTF-8 in append mode, and writes one compact JSON object plus newline.

- [ ] **Step 5: Implement deterministic window summary and CLI**

Sort samples by parsed UTC timestamp. Missing intervals are `max(0, round(delta / expected_interval_seconds) - 1)` summed between adjacent samples. Nearest-rank p95 uses sorted values at index `ceil(0.95 * n) - 1`; empty latency/disk inputs produce `None`. OOM delta is last minus first and swap growth is last minus first.

Summary keys are `started_at`, `ended_at`, `sample_count`, `missing_intervals`, `api_failure_count`, `api_latency_p95_ms`, `min_mem_available_bytes`, `swap_growth_bytes`, `oom_kill_delta`, `database_integrity_failure_count`, and `min_disk_free_bytes`.

Add CLI commands `sample --output PATH`, `summarize --input PATH`, and `wait-api --url URL --timeout SECONDS`. The sample command uses `/proc/meminfo`, `/proc/vmstat`, `/mnt/nas`, the fixed database path and six fixed units; summary reads nonblank JSONL lines. `wait-api` exits zero only after a successful probe.

- [ ] **Step 6: Run focused and full tests**

Run:

```powershell
Set-Location bogda
uv run --python 3.11 pytest tests/ops/test_health.py -v
uv run --python 3.11 pytest -m "not integration" -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add bogda/src/bogda/ops/__init__.py bogda/src/bogda/ops/health.py bogda/tests/ops/test_health.py
git commit -m "feat(bogda): collect Pi shadow health evidence"
```

---

### Task 4: Install/Rollback Boundary and Operations Runbook

**Files:**

- Create: `bogda/deploy/pi/install.sh`
- Create: `bogda/deploy/pi/rollback.sh`
- Create: `bogda/tests/ops/test_scripts.py`
- Create: `bogda/docs/pi-shadow-runbook.md`
- Modify: `bogda/README.md`

**Interfaces:**

- Consumes: Task 1's bundle CLI and deploy assets; Task 2/3 CLIs; a reviewed Bogda checkout.
- Produces: `install.sh --dry-run`, `install.sh --install [--start]`, `rollback.sh --dry-run`, and `rollback.sh --apply`.

- [ ] **Step 1: Write failing shell-boundary tests**

Resolve Git Bash from `BOGDA_BASH`; apply one module-level skip marker with an explicit reason when it is unset. Run `bash -n` on both scripts. Copy the bundle to `tmp_path`, hash every file, run install and rollback dry-runs, and assert hashes are unchanged. Assert output names only `bogda-*` units, says `/mnt/nas/.bogda` is preserved, and contains neither an Orchestra action nor a command that writes system paths.

```python
pytestmark = pytest.mark.skipif(not os.environ.get("BOGDA_BASH"), reason="BOGDA_BASH is required for shell checks")

def test_shell_syntax() -> None:
    bash = os.environ["BOGDA_BASH"]
    for script in (INSTALL, ROLLBACK):
        subprocess.run([bash, "-n", str(script)], check=True)

def test_install_dry_run_preserves_bundle(bundle_copy: Path) -> None:
    before = tree_hashes(bundle_copy)
    result = subprocess.run(
        [os.environ["BOGDA_BASH"], str(bundle_copy / "install.sh"), "--dry-run"],
        cwd=bundle_copy, text=True, capture_output=True, check=True,
    )
    assert tree_hashes(bundle_copy) == before
    assert "systemctl " not in result.stdout
```

- [ ] **Step 2: Run tests and confirm missing script failure**

Run:

```powershell
Set-Location bogda
$env:BOGDA_BASH = 'E:\Git\bin\bash.exe'
uv run --python 3.11 pytest tests/ops/test_scripts.py -v
```

Expected: tests fail because `install.sh` and `rollback.sh` do not exist.

- [ ] **Step 3: Implement the explicit install boundary**

Use `set -eu`; accept exactly `--dry-run` or `--install`, with optional `--start` only after `--install`. Derive `project_dir` as two parents above the script directory. Require `python3` before either mode, bind it to `python_bin`, and run bundle validation from the checkout so no installed package is required:

```sh
PYTHONPATH="$project_dir/src" "$python_bin" -m bogda.ops.bundle check "$script_dir"
```

Dry-run then calls `bogda.ops.bundle dry-run` and exits. Install mode requires UID 0 and commands `uv`, `getent`, `useradd`, `install`, `findmnt`, and `systemctl`; requires `/mnt/nas` filesystem type `ext4`; rejects the auth sentinel if `--start` is present; creates only the `bogda` account and fixed directories; and saves existing Bogda units/env under `/etc/bogda/backups/<UTC timestamp>`. Write `inventory.tsv` there with one literal target path and `present` or `absent` per line, then write the backup directory to `/etc/bogda/last-backup`. Install with:

```sh
UV_PROJECT_ENVIRONMENT=/opt/bogda/.venv uv sync --frozen --no-dev --no-editable --project "$project_dir"
```

Copy only the six manifest units, install the runtime env as `/etc/bogda/bogda.env` with mode `0640` and group `bogda`, run `systemctl daemon-reload`, and start/enable only the server, worker, snapshot timer, and health timer when `--start` was explicit. Never print auth values.

- [ ] **Step 4: Implement scoped rollback**

Use `set -eu`; accept exactly `--dry-run` or `--apply`. Dry-run describes the six unit actions, whether `/etc/bogda/last-backup` exists, daemon reload, and explicit preservation of `/mnt/nas/.bogda`; it executes no system command that changes state.

Apply mode requires UID 0, stops/disables only the four startable `bogda-*` units, reads the literal path/status rows from `inventory.tsv`, restores files marked `present`, removes deployed files marked `absent`, and runs daemon reload. Reject a backup path outside `/etc/bogda/backups/`, an inventory target outside `/etc/bogda/bogda.env` plus the six `/etc/systemd/system/bogda-*` paths, duplicate rows, and unknown statuses. Do not remove program/data directories or inspect Orchestra units.

- [ ] **Step 5: Run script tests and fix only observed failures**

Run:

```powershell
Set-Location bogda
$env:BOGDA_BASH = 'E:\Git\bin\bash.exe'
uv run --python 3.11 pytest tests/ops/test_scripts.py -v
```

Expected: syntax and dry-run tests pass without any system mutation.

- [ ] **Step 6: Write the future deployment runbook and README pointer**

The runbook must have seven ordered gates: local verification; manual Pi preflight; install without start; auth/Tailscale exposure check; shadow start; 72-hour collection plus reboot/snapshot/restore drill; accept, return to Orchestra-only operation, or rollback. State that local success does not prove ARM64, systemd, SSD mount, Tailscale, reboot persistence, or 72-hour stability.

Include exact future checks: `findmnt -no FSTYPE /mnt/nas` equals `ext4`; `systemd-analyze verify` on all six units; env file mode/owner; API inaccessible from public internet; `systemctl status` for Bogda units; health summary JSON; OOM delta zero; no database-integrity failures; restored snapshot integrity `ok`; queued/history state present after reboot. Treat 400 MB available memory as an observation threshold, while OOM, missing SSD, corrupt database, and unrestorable snapshot are hard failures.

Add a short README section linking the manifest and runbook. List as deferred: actual Pi deployment/72-hour acceptance, Wake Bridge/WoL, laptop `dorm-x86`, Windows Power Agent/game mode, task migration, CPU/GPU worker and higher concurrency, SLC/pSLC purchase, 3100 cutover, CLI error polish, streaming logs, and review/merge/regression of `bogda-console`.

- [ ] **Step 7: Run complete local verification**

Run:

```powershell
Set-Location bogda
$env:BOGDA_BASH = 'E:\Git\bin\bash.exe'
uv run --python 3.11 pytest -v
uv run --python 3.11 python -m bogda.ops.bundle check deploy/pi
& $env:BOGDA_BASH -n deploy/pi/install.sh
& $env:BOGDA_BASH -n deploy/pi/rollback.sh
Set-Location ..
git diff --check
rg -n "from orchestra|import orchestra" bogda/src bogda/tests
rg -n "/mnt/broker|orchestra-" bogda/deploy/pi/manifest.toml bogda/deploy/pi/bogda.env.example bogda/deploy/pi/systemd bogda/deploy/pi/install.sh bogda/deploy/pi/rollback.sh
git status --short
```

Expected: pytest, bundle validation, shell syntax, and diff checks pass; both `rg` commands return no matches; status contains only planned Bogda changes plus the pre-existing user-owned changes. Do not claim Pi deployment or 72-hour acceptance.

- [ ] **Step 8: Commit Task 4**

```powershell
git add bogda/deploy/pi/install.sh bogda/deploy/pi/rollback.sh bogda/tests/ops/test_scripts.py bogda/docs/pi-shadow-runbook.md bogda/README.md
git commit -m "docs(bogda): add Pi shadow operations runbook"
```

---

## Execution Checkpoints

After every task, review the task diff against its interface and run its focused test plus the non-integration suite. After Task 4, run the complete verification block once from a clean implementation worktree. Do not merge to `main` until all checks pass and a final review confirms that no Pi or Orchestra operation occurred.

The implementation worktree should be created only after the user selects an execution mode. The independent `codex/bogda-console` worktree remains outside this plan; when its owner reports completion, review and merge it in a separate gate with post-merge regression.
