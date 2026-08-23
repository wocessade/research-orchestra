# Bogda Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Approved

**Goal:** Build the approved Bogda Console V1 on public port 3101: authoritative Prefect monitoring, allowlisted registered-Deployment commands, append-only scientific review, and source-separated infrastructure/power visibility.

**Architecture:** A stateless FastAPI BFF exposes closed V1 DTOs over thin Prefect, RunResult, Power, and ProjectContext ports. A React/Vite client presents four responsive, accessible research-console surfaces; deterministic in-memory mock adapters drive development and browser acceptance while real Prefect remains read-only by default.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, HTTPX, Prefect 3.8.3 adapter boundary, pytest; React 19, TypeScript, Vite, React Router, TanStack Query, Vitest, Testing Library; Playwright and axe-core.

**Spec:** `docs/superpowers/specs/2026-08-24-bogda-console-design.md`

## Global Constraints

- Put every product, test, fixture, build, screenshot, and acceptance file under `bogda-console/`; only this plan and the approved spec live under `docs/superpowers/`.
- Do not import or modify `bogda/`, `orchestra/console/`, Orchestra data, Pi, or a real dorm machine.
- Prefect remains the only current execution authority; do not add a task table, command outbox, offline mutation queue, scheduler, or execution state machine.
- The newest `bogda-run-{flowRunId}` / `bogda.run-result` Artifact is the scientific authority, even when invalid; review appends a new version.
- Keep Prefect execution state and scientific status separate in models, copy, filters, and presentation. Completed copy is exactly “执行完成，且声明的必要产物存在；这不代表科研结论已被接受。”
- V1 profiles are only `mock-all`, `real-readonly`, and `allowlisted-test`; Power is mock-only, and Prefect plus RunResult share one workspace.
- Development uses public Vite port 3101 and loopback BFF port 3102. Production uses one FastAPI public port 3101. Every entry point must reject port 3100.
- Real Prefect shadow is read-only. Command tests use mock or disposable/local exact allowlists only.
- `dorm-x86` CPU/GPU queues share Prefect Work Pool capacity one; do not implement a local semaphore or scheduler.
- Do not add a full-text evidence scanner, Hermes/OpenClaw integration, generic plugin/action registry, or an autonomy-policy store/editor.
- Focus degradation logic on API unavailable, Worker offline, missing/invalid RunResult, and stale data; do not add speculative recovery machinery.
- Use the approved light “Bogda mountain observatory” design, bundled fonts, no gradients, no default dark theme, and no generic card wall.
- Acceptance covers 1440, 1280, 768, 390, 360, and 320 CSS-pixel reflow, plus 200% zoom, keyboard, focus, reduced motion, and axe serious/critical violations.
- Browser acceptance may read 3100 reachability before and after; it must not stop, cover, bind, mutate, or switch 3100.

## File Map

```text
bogda-console/
├── README.md                         # isolated setup, profiles, ports, safety, test commands
├── pyproject.toml                    # Python runtime and test dependencies
├── package.json                     # frontend and browser scripts
├── tsconfig.json
├── vite.config.ts                    # 3101 public dev server, 3102 loopback proxy, port guard
├── playwright.config.ts
├── openapi.json                      # generated FastAPI contract snapshot
├── scripts/
│   ├── export_openapi.py             # deterministic OpenAPI export
│   └── check_contracts.py            # temp regeneration and drift failure
├── frontend/
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── app/App.tsx
│       ├── api/client.ts
│       ├── api/generated.ts           # openapi-typescript output
│       ├── api/types.ts
│       ├── components/AppShell.tsx
│       ├── components/BrandMark.tsx
│       ├── components/Dialogs.tsx
│       ├── components/RunLedger.tsx
│       ├── components/SourceNotice.tsx
│       ├── components/StatusMark.tsx
│       ├── pages/InfrastructurePage.tsx
│       ├── pages/OverviewPage.tsx
│       ├── pages/ReviewsPage.tsx
│       ├── pages/RunDetailPage.tsx
│       ├── pages/RunsPage.tsx
│       ├── styles/fonts.css
│       ├── styles/global.css
│       └── styles/tokens.css
├── fixtures/
│   ├── normal-active.json
│   ├── sleep-queued.json
│   ├── gaming-paused.json
│   ├── degraded-stale.json
│   ├── result-missing-invalid-conflict.json
│   └── mobile-dense.json
├── src/bogda_console/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── config.py
│   ├── api/routes.py
│   ├── contracts/models.py
│   ├── contracts/ports.py
│   ├── adapters/mock_prefect.py
│   ├── adapters/mock_power.py
│   ├── adapters/mock_run_results.py
│   ├── adapters/prefect_api.py
│   ├── services/commands.py
│   ├── services/queries.py
│   └── services/snapshots.py
├── tests/
│   ├── backend/
│   │   └── conftest.py                # deterministic clocks, fixtures, clients, service harnesses
│   ├── integration/
│   │   └── test_local_prefect.py      # disposable loopback Prefect 3.8.3 contract
│   ├── frontend/
│   │   ├── setup.ts                   # jsdom, MSW, jest-dom, cleanup
│   │   └── helpers.tsx                # router/query render helpers and request log
│   └── browser/
└── docs/acceptance/                  # generated screenshots and final evidence index
```

---

### Task 1: Safe Project Scaffold and Port Isolation

**Files:**
- Create: `bogda-console/pyproject.toml`
- Create: `bogda-console/package.json`
- Create: `bogda-console/tsconfig.json`
- Create: `bogda-console/vite.config.ts`
- Create: `bogda-console/src/bogda_console/__init__.py`
- Create: `bogda-console/src/bogda_console/config.py`
- Create: `bogda-console/tests/backend/test_config.py`
- Create: `bogda-console/tests/frontend/vite-config.test.ts`

**Interfaces:**
- Produces: `Settings.from_env(env: Mapping[str, str]) -> Settings`, `assert_safe_port(port: int, purpose: str) -> int`, and Vite `resolveDevPorts(env) -> {publicPort, bffPort}`.
- Guarantees: only three named profiles; new public/internal ports reject 3100; BFF host is loopback in development.

- [ ] **Step 1: Write failing Python configuration tests**

```python
import pytest

from bogda_console.config import Settings, assert_safe_port


def test_default_mock_profile_uses_3101_and_loopback_3102() -> None:
    settings = Settings.from_env({})
    assert settings.profile == "mock-all"
    assert settings.public_port == 3101
    assert settings.bff_host == "127.0.0.1"
    assert settings.bff_port == 3102


@pytest.mark.parametrize("purpose", ["public", "bff", "test"])
def test_every_new_console_entry_point_rejects_3100(purpose: str) -> None:
    with pytest.raises(ValueError, match="3100 is reserved"):
        assert_safe_port(3100, purpose)


def test_unsupported_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported BOGDA_CONSOLE_PROFILE"):
        Settings.from_env({"BOGDA_CONSOLE_PROFILE": "real-prefect-mock-results"})
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_config.py -v`

Expected: FAIL because `bogda_console.config` does not exist.

- [ ] **Step 3: Add minimal Python packaging and configuration**

`pyproject.toml` starts with this bounded runtime:

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "bogda-console"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.116,<1",
  "httpx>=0.28,<1",
  "prefect==3.8.3",
  "pydantic>=2.11,<3",
  "uvicorn[standard]>=0.35,<1",
]

[project.optional-dependencies]
dev = ["pytest>=8.4,<9", "pytest-asyncio>=1,<2"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
```

```python
SAFE_PROFILES = {"mock-all", "real-readonly", "allowlisted-test"}


def assert_safe_port(port: int, purpose: str) -> int:
    if port == 3100:
        raise ValueError(f"3100 is reserved for the legacy console ({purpose})")
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid {purpose} port: {port}")
    return port
```

`Settings.from_env` must parse public port, BFF loopback host/port, profile, fixture scenario, API URL/key, replica count, and four exact S2 sets: `allowed_deployment_ids`, `allowed_schedule_ids`, `allowed_queue_ids`, and `allowed_work_pool_names`. There is no client-asserted parent or wildcard. `real-readonly` forces all command capabilities false, and review capability is false when replica count is not one.

- [ ] **Step 4: Write and pass the Vite port-guard test**

`package.json` defines React 19 and bounded major-version tooling with scripts `dev`, `build`, `test:frontend`, and `test:browser`; Vite root is `frontend`, build output is `frontend/dist`, and Vitest loads `tests/frontend/setup.ts` under jsdom. Runtime dependencies are `react@^19`, `react-dom@^19`, `react-router-dom@^7`, and `@tanstack/react-query@^5`; dev dependencies include TypeScript 5, Vite 7, Vitest 3, Testing Library, MSW 2, Playwright, axe-core, `openapi-typescript`, and the two Fontsource packages.

```ts
import { describe, expect, it } from "vitest";
import { resolveDevPorts } from "../../vite.config";

describe("resolveDevPorts", () => {
  it("uses public 3101 and loopback BFF 3102", () => {
    expect(resolveDevPorts({})).toEqual({ publicPort: 3101, bffPort: 3102 });
  });
  it("rejects either port when it is 3100", () => {
    expect(() => resolveDevPorts({ BOGDA_CONSOLE_PUBLIC_PORT: "3100" })).toThrow(/reserved/);
    expect(() => resolveDevPorts({ BOGDA_CONSOLE_BFF_PORT: "3100" })).toThrow(/reserved/);
  });
});
```

Run: `cd bogda-console; npm install; npm run test:frontend -- vite-config.test.ts`

Expected: PASS after `vite.config.ts` exports `resolveDevPorts` and defaults `server.host = "127.0.0.1"`, `server.port = 3101`, `server.strictPort = true`, with `/api` proxied only to `http://127.0.0.1:3102`. `BOGDA_CONSOLE_PUBLIC_HOST` may explicitly select an approved Tailnet/interface bind while retaining port 3101; it never changes the BFF loopback bind.

- [ ] **Step 5: Run both scaffold suites and commit**

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_config.py -v; npm run test:frontend -- vite-config.test.ts`

Expected: both suites PASS.

Commit: `git add bogda-console; git commit -m "chore(console): scaffold isolated 3101 application"`

---

### Task 2: Closed Wire Contracts and Deterministic Fixtures

**Files:**
- Create: `bogda-console/src/bogda_console/contracts/models.py`
- Create: `bogda-console/src/bogda_console/contracts/ports.py`
- Create: all six `bogda-console/fixtures/*.json`
- Create: `bogda-console/tests/backend/test_contracts.py`
- Create: `bogda-console/tests/backend/test_fixtures.py`
- Create: `bogda-console/tests/backend/conftest.py`

**Interfaces:**
- Produces: the exact spec DTOs, `ApiEnvelope[T]`, closed `ApiErrorCode`, `command_version(resource) -> str`, `validate_run_result(payload) -> ValidRunResult`, and five runtime-checkable Protocols.
- Consumes: `Settings` from Task 1.

- [ ] **Step 1: Write failing contract tests for authority separation and closed enums**

```python
from bogda_console.contracts.models import (
    ApiErrorCode,
    PrefectStateSnapshot,
    ProjectContext,
    RunSummary,
    ScientificSummary,
)


def test_completed_and_unreviewed_are_separate_fields() -> None:
    run = RunSummary.model_validate({
        "runId": "run-1", "name": "alpine assay", "state": {
            "type": "COMPLETED", "name": "Completed", "timestamp": "2026-08-24T01:00:00Z", "terminal": True,
        },
        "scientific": {"availability": "available", "artifactId": "artifact-1", "artifactCreatedAt": "2026-08-24T01:01:00Z", "scientificStatus": "unreviewed", "reviewSummary": None, "validationIssues": []},
        "commandVersion": "opaque",
    })
    assert run.state.type == "COMPLETED"
    assert run.scientific.scientific_status == "unreviewed"


def test_unavailable_project_mode_has_one_wire_shape() -> None:
    context = ProjectContext(projectId="p1", effectiveAutonomyMode=None, modeSource="unavailable", writable=False)
    assert context.effective_autonomy_mode is None


def test_error_codes_are_closed() -> None:
    assert ApiErrorCode("COMMAND_OUTCOME_UNKNOWN").value == "COMMAND_OUTCOME_UNKNOWN"
```

- [ ] **Step 2: Run and confirm failure, then implement the exact Pydantic models**

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_contracts.py -v`

Expected: FAIL on missing models.

Implementation requirements: use camelCase aliases on the wire, `extra="forbid"` for wire DTOs, UTC-aware datetimes, exact scientific/autonomy/power/profile enums, raw Prefect `type` and `name`, nullable source-owned aggregate components, and the complete `ApiErrorCode` set from spec §14.3.

- [ ] **Step 3: Write failing RunResult validation tests**

```python
from pydantic import ValidationError
import pytest

from bogda_console.contracts.models import ValidRunResult


def valid_payload() -> dict[str, object]:
    return {"run_id": "run-1", "job_id": "job-1", "execution_status": "Completed", "scientific_status": "unreviewed", "started_at": "2026-08-24T00:00:00Z", "finished_at": "2026-08-24T00:02:00Z", "executor": "shell", "attempt": 1, "declared_artifacts": [], "summary": "done", "review_summary": None, "future_core_field": "preserve me"}


def test_valid_result_keeps_unknown_core_fields() -> None:
    result = ValidRunResult.model_validate(valid_payload())
    assert result.model_extra == {"future_core_field": "preserve me"}


def test_invalid_newest_result_does_not_parse() -> None:
    payload = valid_payload()
    payload["scientific_status"] = "proven"
    with pytest.raises(ValidationError):
        ValidRunResult.model_validate(payload)
```

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_contracts.py -v`

Expected: PASS after implementing `ValidRunResult` with `extra="allow"` while wire wrappers remain closed.

- [ ] **Step 4: Add deterministic scenario fixtures and parity tests**

Each JSON fixture must contain `clock`, `prefect`, `runResults`, and `power`. The six files must collectively include all raw/intermediate Prefect names, every scientific status, missing and newest-invalid RunResult, Worker OFFLINE, stale/unavailable sources, both pools, CPU/GPU shared capacity, all four Power modes, an allowlisted deployment, and a review-conflict setup.

```python
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("name", ["normal-active", "sleep-queued", "gaming-paused", "degraded-stale", "result-missing-invalid-conflict", "mobile-dense"])
def test_fixture_has_all_source_sections(name: str) -> None:
    data = json.loads((Path("fixtures") / f"{name}.json").read_text(encoding="utf-8"))
    assert set(data) == {"clock", "prefect", "runResults", "power"}


def test_power_modes_are_collectively_complete() -> None:
    modes = {json.loads(path.read_text(encoding="utf-8"))["power"]["mode"] for path in Path("fixtures").glob("*.json")}
    assert modes == {"sleep", "compute", "gaming", "maintenance"}
```

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_contracts.py tests/backend/test_fixtures.py -v`

Expected: PASS.

`tests/backend/conftest.py` provides `fixture_loader(name)`, an injected `FixtureClock`, fresh adapter factories, an ASGI `client`, and isolated `services` / `command_harness` fixtures. Every factory deep-copies JSON before mutation and closes the HTTPX client after each test; no fixture talks to a network or shared database.

- [ ] **Step 5: Define the five Protocols and commit**

```python
class PrefectQueryPort(Protocol):
    async def list_runs(self, filters: RunFilters, cursor: str | None, limit: int) -> Page[RunSummary]:
        raise NotImplementedError

    async def get_run(self, run_id: str) -> RunDetail:
        raise NotImplementedError


class RunResultPort(Protocol):
    async def get_latest(self, run_id: str) -> RunResultView:
        raise NotImplementedError

    async def append_review(self, run_id: str, base_artifact_id: str, scientific_status: ScientificStatus, review_summary: str | None) -> RunResultView:
        raise NotImplementedError
```

Also define all methods in spec §8 for `PrefectCommandPort`, `PowerStatusPort`, and `ProjectContextPort`; do not add a generic action method.

Commit: `git add bogda-console; git commit -m "feat(console): define authority-preserving contracts"`

---

### Task 3: Mock Adapters, Source Freshness, and Last-Good Reads

**Files:**
- Create: `bogda-console/src/bogda_console/adapters/mock_prefect.py`
- Create: `bogda-console/src/bogda_console/adapters/mock_power.py`
- Create: `bogda-console/src/bogda_console/adapters/mock_run_results.py`
- Create: `bogda-console/src/bogda_console/services/snapshots.py`
- Create: `bogda-console/tests/backend/test_mock_adapters.py`
- Create: `bogda-console/tests/backend/test_snapshots.py`

**Interfaces:**
- Produces: `FixtureClock`, `MockPrefectAdapter`, `MockRunResultAdapter`, `MockPowerAdapter`, and `LastGoodReader[T].read(fetch) -> SourceRead[T]`.
- Guarantees: process-memory mutation/reset, no silent mock fallback, newest invalid Artifact stays invalid, independent source freshness.

- [ ] **Step 1: Write failing freshness tests**

```python
from datetime import UTC, datetime
import pytest

from bogda_console.services.snapshots import LastGoodReader


@pytest.mark.asyncio
async def test_failed_refresh_returns_stale_last_good_without_changing_observed_at() -> None:
    reader = LastGoodReader(source="prefect", source_mode="mock", stale_after_seconds=30, now=lambda: datetime(2026, 8, 24, 2, tzinfo=UTC))

    async def success():
        return {"runs": ["run-1"]}, datetime(2026, 8, 24, 1, 59, 50, tzinfo=UTC)

    async def failure():
        raise ConnectionError("offline")

    first = await reader.read(success)
    second = await reader.read(failure)
    assert first.meta.freshness == "fresh"
    assert second.data == {"runs": ["run-1"]}
    assert second.meta.freshness == "stale"
    assert second.meta.observed_at == first.meta.observed_at
```

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_snapshots.py -v`

Expected: FAIL, then PASS after `LastGoodReader` keeps only process-local memory and returns unavailable when no snapshot exists.

- [ ] **Step 2: Write failing adapter authority tests**

```python
@pytest.mark.asyncio
async def test_newest_invalid_artifact_never_falls_back(fixture_loader) -> None:
    adapter = MockRunResultAdapter(fixture_loader("result-missing-invalid-conflict"))
    result = await adapter.get_latest("run-invalid")
    assert result.availability == "invalid"
    assert result.artifact_id == "artifact-invalid-newest"
    assert result.result is None


@pytest.mark.asyncio
async def test_dorm_capacity_comes_from_one_pool(fixture_loader) -> None:
    adapter = MockPrefectAdapter(fixture_loader("normal-active"))
    pools = await adapter.list_work_pools()
    dorm = next(pool for pool in pools if pool.name == "dorm-x86")
    assert dorm.concurrency_limit == 1
    assert {queue.name for queue in dorm.queues} == {"cpu", "gpu"}
```

- [ ] **Step 3: Implement fixture-backed reads and process-memory commands**

`MockPrefectAdapter` must expose exact query and command methods, recompute raw state timestamps from the fixture clock, and mutate only its copied fixture dictionary. `MockRunResultAdapter.append_review` must lock per run, re-read newest, compare `baseArtifactId`, preserve unknown payload fields, append a monotonically timestamped Artifact, and raise a typed `ReviewConflict` on mismatch. `MockPowerAdapter` is read-only.

- [ ] **Step 4: Test reset and source independence**

```python
@pytest.mark.asyncio
async def test_mock_state_resets_with_new_adapter_instance(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    changed = MockPrefectAdapter(fixture)
    await changed.pause_work_queue("queue-cpu")
    reset = MockPrefectAdapter(fixture)
    queue = await reset.get_work_queue("queue-cpu")
    assert queue.is_paused is False


def test_power_fixture_is_always_labeled_mock(fixture_loader) -> None:
    adapter = MockPowerAdapter(fixture_loader("normal-active"))
    assert adapter.source_mode == "mock"
```

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_mock_adapters.py tests/backend/test_snapshots.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add bogda-console; git commit -m "feat(console): add deterministic source adapters"`

---

### Task 4: Query Service and Closed HTTP API

**Files:**
- Create: `bogda-console/src/bogda_console/services/queries.py`
- Create: `bogda-console/src/bogda_console/api/routes.py`
- Create: `bogda-console/src/bogda_console/app.py`
- Create: `bogda-console/tests/backend/test_query_service.py`
- Create: `bogda-console/tests/backend/test_query_api.py`

**Interfaces:**
- Produces: `QueryService` methods for every GET route and `create_app(settings: Settings | None = None) -> FastAPI`.
- Consumes: closed contracts, ports, adapters, and `LastGoodReader`.

- [ ] **Step 1: Write failing query-service tests for partial authority**

```python
@pytest.mark.asyncio
async def test_infrastructure_keeps_power_when_prefect_has_no_snapshot(services) -> None:
    services.prefect.fail_without_snapshot()
    response = await services.queries.infrastructure()
    assert response.data.pools is None
    assert response.data.dorm_power.mode == "compute"
    assert response.sources["prefect"].freshness == "unavailable"
    assert response.sources["power"].freshness == "fresh"


@pytest.mark.asyncio
async def test_run_list_never_fabricates_empty_when_prefect_unavailable(services) -> None:
    services.prefect.fail_without_snapshot()
    with pytest.raises(SourceUnavailable) as error:
        await services.queries.runs(RunFilters(), None, 50)
    assert error.value.code == "PREFECT_UNAVAILABLE"
```

- [ ] **Step 2: Implement aggregation without cross-source erasure**

`QueryService` must gather independent source reads concurrently, attach each `SourceMeta` in the envelope, return partial aggregate data, use exact filters, and calculate `commandVersion` from current Prefect fields only. It must not persist query results beyond `LastGoodReader` memory.

- [ ] **Step 3: Write failing HTTP contract tests**

```python
@pytest.mark.asyncio
async def test_get_runs_uses_closed_envelope(client) -> None:
    response = await client.get("/api/v1/runs?executionType=COMPLETED&limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data", "sources", "errors"}
    assert payload["data"]["items"][0]["state"]["type"] == "COMPLETED"
    assert payload["data"]["items"][0]["scientific"]["scientificStatus"] == "unreviewed"


@pytest.mark.asyncio
async def test_deployments_without_snapshot_is_503(client, scenario_control) -> None:
    scenario_control.prefect_unavailable_without_snapshot()
    response = await client.get("/api/v1/deployments")
    assert response.status_code == 503
    assert response.json()["data"] is None
    assert response.json()["errors"][0]["code"] == "PREFECT_UNAVAILABLE"
```

- [ ] **Step 4: Implement all GET routes and exception mapping**

Register `/api/v1/capabilities`, `/overview`, `/runs`, `/runs/{runId}`, `/runs/{runId}/result`, `/runs/{runId}/result/versions`, `/deployments`, and `/infrastructure`. Validation is `422 VALIDATION_ERROR`; unknown IDs are `404 NOT_FOUND`; unavailable direct sources are `503`; aggregate partial responses remain `200`.

Also register `POST /api/v1/test/scenario` only when both profile is `mock-all` and `BOGDA_CONSOLE_TEST_MODE=1`. Its closed body is `{scenario: <one of the six fixture names>}`; it reconstructs all adapters from a deep copy and clears last-good memory. The route must return `404` in `real-readonly`, `allowlisted-test`, or non-test mode. This endpoint is only browser-test control, not a product capability.

- [ ] **Step 5: Run backend contract suite and commit**

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_contracts.py tests/backend/test_fixtures.py tests/backend/test_snapshots.py tests/backend/test_mock_adapters.py tests/backend/test_query_service.py tests/backend/test_query_api.py -v`

Expected: PASS.

Commit: `git add bogda-console; git commit -m "feat(console): expose source-aware query API"`

---

### Task 5: Authoritative Commands and Append-Only Review

**Files:**
- Create: `bogda-console/src/bogda_console/services/commands.py`
- Modify: `bogda-console/src/bogda_console/api/routes.py`
- Create: `bogda-console/tests/backend/test_commands.py`
- Create: `bogda-console/tests/backend/test_command_api.py`

**Interfaces:**
- Produces: `CommandService.submit`, `cancel`, `pause_schedule`, `resume_schedule`, `pause_queue`, `resume_queue`, and `review`; HTTP returns `CommandReceipt[T]`.
- Guarantees: fresh pre-read, allowlist, exact precondition, adapter call, mandatory authoritative post-read; no last-good write decisions or optimistic receipt.

Authorization is server-derived and exact:

- submission requires the exact Deployment ID in `allowed_deployment_ids`;
- schedule pause/resume requires both the exact schedule ID and exact parent Deployment ID in their sets, plus a fresh Deployment read proving that schedule currently belongs to that Deployment;
- Queue pause/resume requires the exact Queue ID and Work Pool name in their sets, plus a fresh Queue read proving current membership;
- cancel and review do not use a client-supplied or static Run ID list. A fresh Prefect Flow Run read must show a non-null `deploymentId` in `allowed_deployment_ids`; standalone runs are never mutable;
- a newly submitted Flow Run becomes eligible because its authoritative post-read contains that allowlisted Deployment ID. The console does not add it to local state;
- review performs the same fresh Prefect ownership read before the Artifact read, so a forged client `deploymentId` or Artifact alone cannot authorize it.

- [ ] **Step 1: Write failing stale-intent and non-idempotent precondition tests**

```python
@pytest.mark.asyncio
async def test_stale_cancel_intent_stops_before_adapter_call(command_harness) -> None:
    with pytest.raises(ResourceChanged):
        await command_harness.service.cancel("run-1", "old-command-version")
    assert command_harness.prefect.cancel_calls == []


@pytest.mark.asyncio
async def test_pause_already_paused_is_not_a_silent_success(command_harness) -> None:
    current = command_harness.prefect.queue("queue-gpu", paused=True)
    with pytest.raises(CommandNotApplicable):
        await command_harness.service.pause_queue("queue-gpu", current.command_version)


@pytest.mark.asyncio
async def test_cancel_authorization_comes_from_fresh_run_deployment(command_harness) -> None:
    command_harness.prefect.set_run_deployment("run-1", "deployment-not-allowed")
    current = command_harness.prefect.run("run-1")
    with pytest.raises(ResourceNotAllowlisted):
        await command_harness.service.cancel("run-1", current.command_version)
    assert command_harness.prefect.cancel_calls == []


@pytest.mark.asyncio
async def test_schedule_must_belong_to_allowed_parent(command_harness) -> None:
    command_harness.prefect.move_schedule("schedule-1", "deployment-other")
    with pytest.raises(ResourceNotAllowlisted):
        await command_harness.service.pause_schedule("deployment-allowed", "schedule-1", "version-1")


@pytest.mark.asyncio
async def test_queue_must_still_belong_to_allowed_pool(command_harness) -> None:
    command_harness.prefect.move_queue("queue-cpu", "pool-other")
    current = command_harness.prefect.queue("queue-cpu")
    with pytest.raises(ResourceNotAllowlisted):
        await command_harness.service.pause_queue("queue-cpu", current.command_version)
```

- [ ] **Step 2: Write failing dorm limit and post-read tests**

```python
@pytest.mark.asyncio
async def test_dorm_submission_requires_prefect_pool_limit_one(command_harness) -> None:
    command_harness.prefect.set_pool_limit("dorm-x86", 2)
    with pytest.raises(InfrastructureMisconfigured):
        await command_harness.service.submit("deployment-dorm", {}, "intent-1")
    assert command_harness.prefect.submit_calls == []


@pytest.mark.asyncio
async def test_cancel_accepts_authoritative_cancelling_receipt(command_harness) -> None:
    current = command_harness.prefect.run("run-1")
    receipt = await command_harness.service.cancel("run-1", current.command_version)
    assert receipt.snapshot.state.name == "Cancelling"
```

- [ ] **Step 3: Implement the command pipeline and typed errors**

Use per-resource `asyncio.Lock` objects only to enforce the documented single-process test invariant. `RESOURCE_CHANGED` applies only to the pre-read digest mismatch. Pause/resume requires the target boolean in the post-read. Cancel accepts `Cancelling` or `Cancelled`. A failed post-read raises `COMMAND_OUTCOME_UNKNOWN` and never retries automatically.

Resolve every relationship through the fresh Prefect pre-read. Do not accept `deploymentId`, schedule parentage, Queue pool name, or ownership facts from a command body beyond the resource IDs present in the URL.

- [ ] **Step 4: Write and pass append-only review tests**

```python
@pytest.mark.asyncio
async def test_review_appends_and_preserves_unknown_fields(command_harness) -> None:
    before = await command_harness.results.get_latest("run-review")
    receipt = await command_harness.service.review("run-review", before.artifact_id, "accepted", "evidence checked")
    assert receipt.snapshot.artifact_id != before.artifact_id
    assert receipt.snapshot.result.scientific_status == "accepted"
    assert receipt.snapshot.result.model_extra["future_core_field"] == "kept"


@pytest.mark.asyncio
async def test_review_conflict_returns_current_newest_version(command_harness) -> None:
    with pytest.raises(ReviewConflict) as error:
        await command_harness.service.review("run-review", "artifact-old", "rejected", "stale form")
    assert error.value.current_resource.artifact_id == "artifact-newest"


@pytest.mark.asyncio
async def test_review_rejects_standalone_run_before_artifact_write(command_harness) -> None:
    command_harness.prefect.set_run_deployment("run-review", None)
    with pytest.raises(ResourceNotAllowlisted):
        await command_harness.service.review("run-review", "artifact-newest", "accepted", None)
    assert command_harness.results.append_calls == []


@pytest.mark.asyncio
async def test_submitted_run_inherits_authorization_from_prefect_receipt(command_harness) -> None:
    submitted = await command_harness.service.submit("deployment-allowed", {}, "intent-new")
    receipt = await command_harness.service.cancel(submitted.snapshot.run_id, submitted.snapshot.command_version)
    assert receipt.snapshot.deployment_id == "deployment-allowed"
```

- [ ] **Step 5: Add POST routes, test the closed envelopes, and commit**

Test every route for success, `403 RESOURCE_NOT_ALLOWLISTED`, `409` conflict/precondition/mismatch, `422`, `503` pre-read, and `503 COMMAND_OUTCOME_UNKNOWN`. Verify `real-readonly` capability fields are false and routes reject before an adapter mutation.

Run: `cd bogda-console; py -3.11 -m pytest tests/backend -v`

Expected: PASS.

Commit: `git add bogda-console; git commit -m "feat(console): add authoritative Prefect commands and review"`

---

### Task 6: Frontend API Client, App Shell, and Visual Foundation

**Files:**
- Create: `bogda-console/frontend/index.html`
- Create: `bogda-console/frontend/src/main.tsx`
- Create: `bogda-console/frontend/src/app/App.tsx`
- Create: `bogda-console/frontend/src/api/generated.ts`
- Create: `bogda-console/frontend/src/api/types.ts`
- Create: `bogda-console/frontend/src/api/client.ts`
- Create: `bogda-console/frontend/src/components/AppShell.tsx`
- Create: `bogda-console/frontend/src/components/BrandMark.tsx`
- Create: `bogda-console/frontend/src/components/SourceNotice.tsx`
- Create: `bogda-console/frontend/src/components/StatusMark.tsx`
- Create: `bogda-console/frontend/src/styles/fonts.css`
- Create: `bogda-console/frontend/src/styles/tokens.css`
- Create: `bogda-console/frontend/src/styles/global.css`
- Create: `bogda-console/tests/frontend/app-shell.test.tsx`
- Create: `bogda-console/tests/frontend/api-client.test.ts`
- Create: `bogda-console/tests/frontend/setup.ts`
- Create: `bogda-console/tests/frontend/helpers.tsx`
- Create: `bogda-console/scripts/export_openapi.py`
- Create: `bogda-console/scripts/check_contracts.py`
- Generate: `bogda-console/openapi.json`

**Interfaces:**
- Produces: `api.get<T>()`, `api.command<T>()`, generated OpenAPI wire types, `AppShell`, `BrandMark`, `SourceNotice`, `ExecutionMark`, and `ScientificMark`.
- Consumes: exact FastAPI/Pydantic OpenAPI from Tasks 2–5; TypeScript wire types are generated, not manually duplicated.

- [ ] **Step 1: Write failing app-shell accessibility test**

```tsx
it("renders four primary destinations and a skip link", () => {
  render(<AppShell><p>content</p></AppShell>, { wrapper: MemoryRouter });
  expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute("href", "#main-content");
  for (const name of ["总览", "运行", "评审", "基础设施"]) {
    expect(screen.getByRole("link", { name })).toBeVisible();
  }
  expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
});
```

- [ ] **Step 2: Implement the observatory shell and tokens**

Use the exact spec color tokens, 12-column desktop grid, left rail, mobile bottom navigation, 44px targets, visible `:focus-visible`, no gradient declarations, and an inline SVG mountain ridge whose decorative contour is `aria-hidden="true"`. Install `@fontsource-variable/manrope` and `@fontsource/ibm-plex-mono`; import their packaged font files through `fonts.css` so Vite bundles them without a public CDN. System CJK fallbacks remain usable if fonts fail.

- [ ] **Step 3: Write failing API client error test**

```ts
it("throws the closed envelope without treating a 503 as success", async () => {
  server.use(http.get("/api/v1/runs", () => HttpResponse.json({ data: null, sources: { prefect: unavailableMeta }, errors: [{ code: "PREFECT_UNAVAILABLE", message: "offline", source: "prefect", retryable: true }] }, { status: 503 })));
  await expect(api.get("/api/v1/runs")).rejects.toMatchObject({ status: 503, errors: [{ code: "PREFECT_UNAVAILABLE" }] });
});
```

- [ ] **Step 4: Generate typed API envelopes and enforce zero drift**

`scripts/export_openapi.py` imports `create_app(Settings.from_env({"BOGDA_CONSOLE_PROFILE": "mock-all"}))`, writes deterministic sorted OpenAPI JSON, and strips no schemas. `npm run generate:contracts` runs that script followed by `openapi-typescript openapi.json -o frontend/src/api/generated.ts`. `scripts/check_contracts.py` exports and generates into a temporary directory, byte-compares both files with the committed copies, and exits nonzero with the exact regeneration command on drift. `npm run check:contracts` invokes it, and `npm run build` runs `check:contracts` before TypeScript/Vite.

`frontend/src/api/types.ts` may define view-only helper aliases but must import every wire DTO/enum from `generated.ts`. `api.command` never updates cached state optimistically; on success it invalidates and re-fetches relevant queries, and on conflict it exposes `details.currentResource` to the dialog.

`tests/frontend/setup.ts` starts and resets one MSW server, installs jest-dom matchers, and fails tests on unexpected `console.error`. `tests/frontend/helpers.tsx` exports `renderAppAt(path)`, `user`, `server`, `http`, `HttpResponse`, `unavailableMeta`, `requestLog`, `useScenario(name)`, and `useReviewConflictOnce()` with deterministic envelope fixtures matching the backend JSON.

- [ ] **Step 5: Run, inspect, and commit**

Run: `cd bogda-console; npm run generate:contracts; npm run check:contracts; npm run test:frontend -- app-shell.test.tsx api-client.test.ts`

Expected: generated files are unchanged on a second run, drift check passes, and tests PASS with no React warnings.

Commit: `git add bogda-console; git commit -m "feat(console): establish observatory interface system"`

---

### Task 7: Overview, Runs, Detail, and Review Surfaces

**Files:**
- Create: `bogda-console/frontend/src/components/RunLedger.tsx`
- Create: `bogda-console/frontend/src/pages/OverviewPage.tsx`
- Create: `bogda-console/frontend/src/pages/RunsPage.tsx`
- Create: `bogda-console/frontend/src/pages/RunDetailPage.tsx`
- Create: `bogda-console/frontend/src/pages/ReviewsPage.tsx`
- Modify: `bogda-console/frontend/src/app/App.tsx`
- Create: `bogda-console/tests/frontend/overview.test.tsx`
- Create: `bogda-console/tests/frontend/runs.test.tsx`
- Create: `bogda-console/tests/frontend/reviews.test.tsx`

**Interfaces:**
- Produces: `/`, `/runs`, `/runs/:runId`, and `/reviews` routes.
- Guarantees: dual status vocabulary, exact raw Prefect names, invalid/missing semantics, source degradation, desktop table/mobile records.

- [ ] **Step 1: Write failing dual-status and Completed-copy tests**

```tsx
it("shows Completed and unreviewed together without claiming science succeeded", async () => {
  renderAppAt("/runs/run-completed-unreviewed");
  expect(await screen.findByText("Completed")).toBeVisible();
  expect(screen.getByText("待评审")).toBeVisible();
  expect(screen.getByText("执行完成，且声明的必要产物存在；这不代表科研结论已被接受。")).toBeVisible();
  expect(screen.queryByText(/研究成功|结论成立|验证通过/)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Implement attention-led overview and run ledger**

Overview order is attention, active runs, awaiting review, dorm capacity/power, then recent outcomes. `RunLedger` uses a semantic table from 768px upward and labeled `<article>` records below 768px. Every status uses visible text plus an SVG/icon shape, with exact Prefect `name` primary and `type` secondary.

- [ ] **Step 3: Write failing filter and degradation tests**

```tsx
it("sends exact execution and scientific filters", async () => {
  renderAppAt("/runs");
  await user.selectOptions(screen.getByLabelText("执行状态"), "COMPLETED");
  await user.selectOptions(screen.getByLabelText("科研状态"), "unreviewed");
  await waitFor(() => expect(requestLog.last()).toContain("executionType=COMPLETED&scientificStatus=unreviewed"));
});

it("renders stale Prefect data with absolute time instead of zero runs", async () => {
  useScenario("degraded-stale");
  renderAppAt("/runs");
  expect(await screen.findByText(/陈旧数据/)).toBeVisible();
  expect(screen.getByText(/2026-08-24/)).toBeVisible();
  expect(screen.queryByText("0 个运行")).not.toBeInTheDocument();
});
```

- [ ] **Step 4: Implement run detail and review queue**

Run detail renders separate execution and scientific bands, ProjectContext with read-only mode source, declared Artifact records without scanning, version history, and explicit missing/invalid panels. Reviews uses `/runs?scientificStatus=unreviewed`; a terminal non-Completed run with valid result retains both the execution warning and review controls.

- [ ] **Step 5: Run frontend surface tests and commit**

Run: `cd bogda-console; npm run test:frontend -- overview.test.tsx runs.test.tsx reviews.test.tsx`

Expected: PASS, including raw `Late`, `Retrying`, `Paused`, newest-invalid Artifact, and Worker/source attention fixtures.

Commit: `git add bogda-console; git commit -m "feat(console): add run and scientific review surfaces"`

---

### Task 8: Infrastructure and Safe Mutation Dialogs

**Files:**
- Create: `bogda-console/frontend/src/components/Dialogs.tsx`
- Create: `bogda-console/frontend/src/pages/InfrastructurePage.tsx`
- Modify: `bogda-console/frontend/src/pages/RunDetailPage.tsx`
- Modify: `bogda-console/frontend/src/pages/ReviewsPage.tsx`
- Modify: `bogda-console/frontend/src/components/AppShell.tsx`
- Create: `bogda-console/tests/frontend/infrastructure.test.tsx`
- Create: `bogda-console/tests/frontend/commands.test.tsx`
- Create: `bogda-console/tests/frontend/dialogs.test.tsx`

**Interfaces:**
- Produces: registered Deployment drawer, cancel confirmation, schedule/queue pause/resume confirmation, and append-only review form.
- Guarantees: no arbitrary Deployment editor, no optimistic state, 409 input preservation, source/time disclosure, keyboard dialog behavior.

- [ ] **Step 1: Write failing infrastructure truth tests**

```tsx
it("shows one dorm capacity rather than two queue capacities", async () => {
  renderAppAt("/infrastructure");
  expect(await screen.findByText("dorm-x86")).toBeVisible();
  expect(screen.getByText("共享并发 1 / 1")).toBeVisible();
  expect(screen.getByText("cpu")).toBeVisible();
  expect(screen.getByText("gpu")).toBeVisible();
  expect(screen.queryByText("CPU 1/1")).not.toBeInTheDocument();
  expect(screen.queryByText("GPU 0/1")).not.toBeInTheDocument();
});

it("keeps Worker OFFLINE separate from sleep and API unavailable", async () => {
  useScenario("sleep-queued");
  renderAppAt("/infrastructure");
  expect(await screen.findByText("OFFLINE")).toBeVisible();
  expect(screen.getByText("sleep")).toBeVisible();
  expect(screen.getByText("模拟数据")).toBeVisible();
});
```

- [ ] **Step 2: Implement infrastructure and Power presentation**

Render `pi-service` and `dorm-x86` as distinct ledgers; include pools, queues, workers, last heartbeats, shared slots, and an explicit misconfiguration banner. Show Power `sleep`, `compute`, `gaming`, `maintenance`, reachability, sleep inhibition, last transition, absolute time, and “模拟数据.” Never infer one source from another.

- [ ] **Step 3: Write failing mutation and conflict tests**

```tsx
it("keeps review text and shows newest artifact on conflict", async () => {
  useReviewConflictOnce();
  renderAppAt("/runs/run-review");
  await user.type(screen.getByLabelText("评审说明"), "证据链不完整");
  await user.click(screen.getByRole("button", { name: "提交评审" }));
  expect(await screen.findByText(/结果已被其他评审更新/)).toBeVisible();
  expect(screen.getByLabelText("评审说明")).toHaveValue("证据链不完整");
  expect(screen.getByText("artifact-newest")).toBeVisible();
});

it("waits for authoritative cancel receipt", async () => {
  renderAppAt("/runs/run-active");
  await user.click(screen.getByRole("button", { name: "取消运行" }));
  await user.click(screen.getByRole("button", { name: "确认取消" }));
  expect(screen.getByRole("button", { name: "确认取消" })).toBeDisabled();
  expect(await screen.findByText("Cancelling")).toBeVisible();
});
```

- [ ] **Step 4: Implement dialogs and commands**

All dialogs use native `<dialog>` or an equivalent tested focus trap, Escape close, initial focus, destructive labels, and opener focus restoration. Submit only an allowlisted registered Deployment with server-provided parameter schema. Mutation success invalidates queries after the authoritative receipt; conflict renders `currentResource`; outcome unknown remains a persistent warning and never auto-retries.

- [ ] **Step 5: Run interaction tests and commit**

Run: `cd bogda-console; npm run test:frontend -- infrastructure.test.tsx commands.test.tsx dialogs.test.tsx`

Expected: PASS for submit, cancel, schedule pause/resume, queue pause/resume, review append/conflict, `real-readonly` disabled controls, and focus restoration.

Commit: `git add bogda-console; git commit -m "feat(console): add infrastructure and guarded controls"`

---

### Task 9: Production Serving, Safety Documentation, and Full Unit Verification

**Files:**
- Create: `bogda-console/src/bogda_console/__main__.py`
- Modify: `bogda-console/src/bogda_console/app.py`
- Create: `bogda-console/src/bogda_console/adapters/prefect_api.py`
- Create: `bogda-console/README.md`
- Create: `bogda-console/tests/backend/test_app_serving.py`
- Create: `bogda-console/tests/backend/test_prefect_adapter_contract.py`
- Create: `bogda-console/tests/integration/test_local_prefect.py`

**Interfaces:**
- Produces: `python -m bogda_console` public 3101 entry point, built-asset serving with SPA fallback, and a thin read-only-capable Prefect 3.8.3 API adapter.
- Guarantees: no browser Prefect credentials, no implicit mock fallback, no 3100 bind, no real commands unless exact S2 configuration passes.

- [ ] **Step 1: Write failing entry-point and static-serving tests**

```python
def test_cli_refuses_reserved_port(monkeypatch) -> None:
    monkeypatch.setenv("BOGDA_CONSOLE_PUBLIC_PORT", "3100")
    with pytest.raises(ValueError, match="reserved"):
        main()


@pytest.mark.asyncio
async def test_spa_fallback_serves_built_index(app_with_build, client) -> None:
    response = await client.get("/runs/run-1")
    assert response.status_code == 200
    assert "Bogda Console" in response.text
```

- [ ] **Step 2: Implement production asset serving and safe CLI**

`python -m bogda_console` validates profile/ports before constructing adapters and runs Uvicorn on configured public port 3101. `/api` is registered before static fallback. Missing frontend build returns a clear startup error in production mode.

- [ ] **Step 3: Write failing fake-client and disposable Prefect integration tests**

Fake-client unit tests verify each public client method, request model, pagination cursor translation, and raw state mapping. The integration module uses Prefect 3.8.3's official `prefect_test_harness(server_startup_timeout=60)`, which launches a loopback subprocess server with an isolated temporary SQLite database and a random 8000–9000 port. The fixture asserts the chosen port is not 3100.

Inside that disposable workspace, seed through Prefect's public client: one flow, a `dorm-x86` Work Pool with `concurrency_limit=1`, `cpu` and `gpu` queues, one registered Deployment with an interval schedule, and two same-key `Artifact(type="bogda.run-result", key=f"bogda-run-{run_id}")` versions. No Worker or real execution is needed. The integration assertions are:

```python
@pytest.mark.asyncio
async def test_real_prefect_adapter_round_trip(local_prefect_seed) -> None:
    adapter, command_service, ids = local_prefect_seed
    assert {pool.name for pool in await adapter.list_work_pools()} == {"dorm-x86"}
    assert (await adapter.get_work_pool_concurrency("dorm-x86")).concurrency_limit == 1
    assert {queue.name for queue in await adapter.list_work_queues("dorm-x86")} == {"cpu", "gpu"}
    before = await adapter.get_latest(ids.run_id)
    assert before.artifact_id == ids.latest_artifact_id
    assert len((await adapter.list_versions(ids.run_id, None, 20)).items) == 2

    reviewed = await command_service.review(ids.run_id, before.artifact_id, "accepted", "local Prefect evidence checked")
    after = await adapter.get_latest(ids.run_id)
    versions = await adapter.list_versions(ids.run_id, None, 20)
    assert reviewed.snapshot.artifact_id == after.artifact_id
    assert after.artifact_id != before.artifact_id
    assert len(versions.items) == 3
    assert after.result.scientific_status == "accepted"
    assert after.result.execution_status == before.result.execution_status
    assert after.result.model_extra["future_core_field"] == "preserved"

    submitted = await adapter.submit_registered_deployment(ids.deployment_id, {}, "local-intent")
    await adapter.cancel_run(submitted.run_id)
    await adapter.pause_schedule(ids.deployment_id, ids.schedule_id)
    await adapter.resume_schedule(ids.deployment_id, ids.schedule_id)
    await adapter.pause_work_queue(ids.cpu_queue_id)
    await adapter.resume_work_queue(ids.cpu_queue_id)
```

The seeded `ids.run_id` is created from the allowlisted Deployment, not as a standalone run. `command_service` uses the same real Prefect query and RunResult adapters and exact S2 sets, so the review call must first fresh-read `run.deploymentId`, pass the derived authorization chain, and then execute the real append-only Artifact path. This test is the integration proof for review lineage; a direct mock/fake append does not satisfy it.

Run: `cd bogda-console; py -3.11 -m pytest tests/backend/test_prefect_adapter_contract.py tests/integration/test_local_prefect.py -v`

Expected: FAIL before the adapter exists; the integration never reads configured production credentials.

- [ ] **Step 4: Implement and pass the Prefect 3.8.3 adapter contract**

Use Prefect client calls only inside `adapters/prefect_api.py`; map raw types/names/timestamps without rewriting state. Query methods and Artifact reads share one API URL/workspace. Real command methods require `allowlisted-test` and the server-derived authorization chain from Task 5; `real-readonly` raises `RESOURCE_NOT_ALLOWLISTED` before a network mutation. Keep fake-client unit tests for edge cases, and require the disposable server integration above to pass for SDK/API compatibility.

- [ ] **Step 5: Write the operator README**

Document isolated installation, `.venv`, `npm install`, mock dev commands, production build, all environment variables, profile matrix, public/internal ports, 3100 reservation, fixture scenarios, tests, screenshot location, real-shadow read-only rule, exact S2 allowlists, single-replica review/command invariant, and explicit non-goals. Include no 3100 switch procedure.

- [ ] **Step 6: Build and run all non-browser tests**

Run:

```powershell
cd bogda-console
py -3.11 -m pytest tests/backend -v
py -3.11 -m pytest tests/integration/test_local_prefect.py -v
npm run test:frontend -- --run
npm run build
```

Expected: backend, disposable local Prefect integration, and frontend tests PASS; contract drift check and TypeScript pass; `frontend/dist/index.html` exists.

Commit: `git add bogda-console; git commit -m "feat(console): package safe standalone console"`

---

### Task 10: Playwright Accessibility, Responsive, and Shadow Acceptance

**Files:**
- Create: `bogda-console/playwright.config.ts`
- Create: `bogda-console/tests/browser/console.spec.ts`
- Create: `bogda-console/tests/browser/accessibility.spec.ts`
- Create: `bogda-console/tests/browser/degradation.spec.ts`
- Create: `bogda-console/tests/browser/port-safety.spec.ts`
- Create: `bogda-console/docs/acceptance/README.md`
- Generate: `bogda-console/docs/acceptance/overview-desktop.png`
- Generate: `bogda-console/docs/acceptance/run-detail-desktop.png`
- Generate: `bogda-console/docs/acceptance/scientific-review-phone.png`
- Generate: `bogda-console/docs/acceptance/infrastructure-degraded-phone.png`

**Interfaces:**
- Produces: reproducible browser evidence package for Stage S3 on 3101.
- Consumes: built product and deterministic mock scenarios.

- [ ] **Step 1: Write failing browser navigation and interaction tests**

```ts
test("four-page workflow keeps execution and science separate", async ({ page }) => {
  await page.goto("http://127.0.0.1:3101/");
  await page.getByRole("link", { name: "运行" }).click();
  await page.getByRole("link", { name: "alpine assay" }).click();
  await expect(page.getByText("Completed")).toBeVisible();
  await expect(page.getByText("待评审")).toBeVisible();
  await expect(page.getByText("这不代表科研结论已被接受", { exact: false })).toBeVisible();
});
```

Add scenarios for Deployment submit, cancel, exact schedule pause/resume, queue pause/resume, append review, preserved conflict form, Prefect unavailable with/without last-good, Worker OFFLINE, missing/invalid RunResult, stale Power, and all four mock Power modes.

- [ ] **Step 2: Add viewport, reflow, keyboard, and axe assertions**

Run projects at 1440x900, 1280x800, 768x1024, 390x844, 360x800, and 320x800. Assert `document.documentElement.scrollWidth <= window.innerWidth`, repeat at 200% browser zoom, test skip link/dialog focus/Escape/focus restoration, emulate reduced motion, and run axe on all four pages, run detail, review form, infrastructure detail, and a degraded state. Fail on serious or critical violations.

- [ ] **Step 3: Add strict browser error collection**

```ts
const unexpected: string[] = [];
page.on("pageerror", error => unexpected.push(`pageerror:${error.message}`));
page.on("console", message => {
  if (message.type() === "error") unexpected.push(`console:${message.text()}`);
});
page.on("response", response => {
  if (response.status() >= 400 && !expectedScenarioResponses.has(`${response.request().method()} ${new URL(response.url()).pathname} ${response.status()}`)) {
    unexpected.push(`http:${response.status()} ${response.url()}`);
  }
});
```

Each test asserts `unexpected` is empty; scenario-injected `503` responses are allowlisted narrowly by method/path/status and must still render the expected error state.

- [ ] **Step 4: Run on 3101 without touching 3100 and capture screenshots**

Before starting the new app, perform only `Invoke-WebRequest http://127.0.0.1:3100/ -UseBasicParsing` and record reachable/unreachable without changing it. Start the built Bogda Console on 3101 in mock mode, run Playwright, save the four required named screenshots, then stop only the process whose PID was launched by this task. Repeat the same read-only 3100 reachability check afterward.

Run:

```powershell
cd bogda-console
npm run test:browser
```

Expected: all browser projects PASS; four PNGs exist; no unexpected JS/React/network/static-resource error; no new process ever binds 3100.

- [ ] **Step 5: Write the evidence index and run the complete verification matrix**

`docs/acceptance/README.md` records commit hash, fixture/profile, commands, test counts, axe results, viewport matrix, screenshot links, before/after 3100 reachability, and the explicit untouched list: Pi, dorm machine, `bogda/`, `orchestra/console/`, Orchestra data, real Prefect mutations, and 3100 routing.

Run:

```powershell
cd bogda-console
py -3.11 -m pytest tests/backend -v
py -3.11 -m pytest tests/integration/test_local_prefect.py -v
npm run check:contracts
npm run test:frontend -- --run
npm run build
npm run test:browser
cd ..\orchestra\console
py -3.11 -m unittest discover -v
```

Expected: all new tests pass, build succeeds, browser acceptance passes, and the preserved old console still reports its baseline suite passing.

Commit: `git add bogda-console; git commit -m "test(console): add 3101 shadow acceptance evidence"`

---

## Final Review Gate

- [ ] Run `git status --short` and confirm changes are limited to `bogda-console/` plus the approved spec and plan commits.
- [ ] Run `git diff --check HEAD~1..HEAD` and the complete verification matrix from Task 10.
- [ ] Search the product for forbidden claims and boundaries: `rg -n "研究成功|结论成立|验证通过|localhost:3100|127\.0\.0\.1:3100|pause_run|Hermes|OpenClaw" bogda-console` and explain every intentional README/test match.
- [ ] Request an independent code/spec/visual evidence review; fix every blocking finding and rerun affected plus full verification.
- [ ] Stop at the Stage S3 evidence package. Do not add or execute any 3100 cutover procedure without a new explicit user approval.
