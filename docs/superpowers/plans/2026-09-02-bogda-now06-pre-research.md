# Bogda NOW-06 Pre-Research Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Owner already ordered execution in the same session; do not wait for a second confirmation.

**Goal:** Close the skipped Gate 7 review Important items, then wire the pre-research controls in NOW-06 without cutting 3100, touching dorm-x86, or running production research on `pi-service`.

**Architecture:** Keep console profile gates. Add a local actor/role on top. Put unforgeable >20 CNY approval, usage-unknown recovery, log reads, artifact cleanup, and peak/valley dispatch in Bogda core (SQLite + HMAC), then expose them on 3101 through fail-closed adapters. Prefect writes stay behind the existing exact allowlist.

**Tech Stack:** Python 3.11, pytest, FastAPI 3101, SQLite, HMAC-SHA256, existing `BudgetGuard` / `UsageUnknownRecoveryService` / `PriceAwareScheduler`.

## Global Constraints

- Work only in `D:\pythonProject\.worktrees\bogda-gate7-real-shadow` on branch `codex/bogda-now06-pre-research`. Do not pull/merge the dirty primary checkout.
- Never bind or write 3100. Never enable production research on `pi-service`.
- Do not implement step 5 (notebook runner, Wake Bridge, 3100 cutover).
- DEF-03 checkpoint on a dedicated worker stays deferred: no worker, do not fake it.
- DEF-20 is already closed; do not reopen the capability contract except to add identity fields.
- dsh exact `usage.json` receipt is non-blocking (owner 2026-08-31).
- Secrets stay in env/SQLite; never print HMAC keys or API keys.
- TDD: no production code without a failing test first.
- Commits only if the owner asks.

## File map

- Gate 7 hotfix: `bogda-console/src/bogda_console/services/commands.py`, `tests/backend/test_commands.py`, `tests/backend/test_config.py`, `tests/backend/test_query_service.py`
- Identity: `bogda-console/src/bogda_console/config.py`, `contracts/models.py`, `services/queries.py`, `services/commands.py`, frontend identity display
- Logs: `bogda/src/bogda/artifacts/safe_log.py`, console query/route
- Retention: `bogda/src/bogda/artifacts/lifecycle.py`
- Approval: `bogda/src/bogda/budget/approval.py`, `guard.py`, `service.py`
- Usage-unknown transport: store `list_open_cases`, `bogda-console/src/bogda_console/adapters/core_model_control.py`
- Dispatcher: `bogda/src/bogda/budget/dispatcher.py`
- Docs: deferred register NOW-06, CLAUDE.md hang, lessons-learned

---

### Task 0: Gate 7 review hotfix

**Files:**
- Modify: `bogda-console/src/bogda_console/services/commands.py`
- Test: `bogda-console/tests/backend/test_config.py`, `test_commands.py`, `test_query_service.py`

**Produces:** submit/cancel/review/checkpoint require `work_pool_name in allowed_work_pool_names`; wildcard and real-readonly mutation tests fail closed.

- [ ] **Step 1: Write the failing tests**

Add to `test_config.py`:

```python
@pytest.mark.parametrize(
    "key",
    [
        "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS",
        "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS",
        "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS",
        "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES",
    ],
)
@pytest.mark.parametrize("value", ["*", "pi-service,*"])
def test_allowlist_wildcards_fail_closed(key: str, value: str) -> None:
    with pytest.raises(ValueError, match="wildcards"):
        Settings.from_env({key: value})
```

Add to `test_commands.py`:

```python
@pytest.mark.asyncio
async def test_submit_rejects_allowlisted_deployment_on_pool_outside_allowlist(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    service.settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "bogda-s2-pool",
        }
    )
    with pytest.raises(ServiceError) as error:
        await service.submit("deployment-service", {}, "intent-pool")
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"
    assert prefect.submit_calls == []

@pytest.mark.asyncio
async def test_queue_pause_rejects_allowlisted_queue_on_pool_outside_allowlist(fixture_loader) -> None:
    service, prefect, _ = harness(fixture_loader("normal-active"))
    service.settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-cpu",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "bogda-s2-pool",
        }
    )
    before = await prefect.get_work_queue("queue-cpu")
    with pytest.raises(ServiceError) as error:
        await service.pause_queue("queue-cpu", before.command_version)
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"

@pytest.mark.asyncio
async def test_real_readonly_mutations_stop_before_adapter(fixture_loader) -> None:
    fixture = fixture_loader("normal-active")
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "real-readonly",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-dorm",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-cpu",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "dorm-x86,pi-service",
        }
    )
    prefect = MockPrefectAdapter(fixture)
    service = CommandService(
        settings=settings,
        prefect=prefect,
        results=MockRunResultAdapter(fixture),
    )
    with pytest.raises(ServiceError) as error:
        await service.submit("deployment-dorm", {}, "intent-ro")
    assert error.value.code == "RESOURCE_NOT_ALLOWLISTED"
    assert prefect.submit_calls == []
```

Extend `test_readonly_capabilities_report_configured_scope_without_enabling_commands` to assert every `can_*` flag is false.

- [ ] **Step 2: Run tests and confirm they fail for the right reason**

Run: `bogda-console/.venv/Scripts/python.exe -m pytest tests/backend/test_config.py tests/backend/test_commands.py tests/backend/test_query_service.py -q`

- [ ] **Step 3: Implement joint pool authorization**

In `commands.py` `submit` after the deployment pre-read, and in `_authorize_run`:

```python
def _authorize_pool(self, work_pool_name: str | None, resource_id: str) -> None:
    if not work_pool_name or work_pool_name not in self.settings.allowed_work_pool_names:
        self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, resource_id)
```

- [ ] **Step 4: Re-run the tests and confirm they pass**

---

### Task 1: DEF-19 identity and roles

**Files:**
- Modify: `bogda-console/src/bogda_console/config.py`, `contracts/models.py`, `services/queries.py`, `services/commands.py`
- Test: `tests/backend/test_config.py`, `test_commands.py`, `test_query_service.py`
- Frontend: show `role` / `actorId` next to the existing profile flag on `InfrastructurePage.tsx`

**Produces:** `ConsoleRole` = `owner` | `observer` | `operator`. Observer cannot POST even with a populated allowlist. Operator may run Prefect allowlisted commands but not model-control / approval. Owner is the only role that can resolve usage-unknown or issue >20 CNY credentials. Defaults: mock-all/allowlisted-test → owner, real-readonly → observer. Env: `BOGDA_CONSOLE_ROLE`, `BOGDA_CONSOLE_ACTOR`.

CapabilitySnapshot adds required `actor_id` and `role`. After API change, run `npm run generate:contracts` in `bogda-console`.

---

### Task 2: DEF-17 safe log content API

**Files:**
- Create: `bogda/src/bogda/artifacts/safe_log.py`
- Test: `bogda/tests/artifacts/test_safe_log.py`
- Console: `QueryService.run_logs`, `GET /api/v1/runs/{run_id}/logs?source=&max_bytes=`

**Produces:** `SafeLogReader(root: Path).read(run_id, source, max_bytes=65536)` for `stdout` | `stderr` | `events` only. `run_id` cannot contain `..` or path separators. Resolved path must stay under `root`. Redact with the same patterns as `dsh.py`. Truncate and set `truncated=True`. Missing file → empty content, `exists=False`, not a host-path dump.

Attempt layout: `{root}/{run_id}/attempt-1/stdout.log` (and stderr.log); events: `{root}/{run_id}/events.jsonl`.

---

### Task 3: DEF-13 artifact retention and explicit cleanup

**Files:**
- Create: `bogda/src/bogda/artifacts/lifecycle.py`
- Test: `bogda/tests/artifacts/test_lifecycle.py`

**Produces:** `ArtifactLifecycle.inspect(run_id)` returns records with `exists`, `size_bytes`, `kind`. `cleanup(run_id, *, actor_id, confirm="delete-content")` deletes file bytes, writes `{name}.tombstone` containing the original relative URI, and does not delete event log rows. Wrong confirm token is a no-op error. Path confinement same as Task 2.

---

### Task 4: DEF-16 unforgeable >20 CNY approval credential

**Files:**
- Create: `bogda/src/bogda/budget/approval.py`
- Modify: `bogda/src/bogda/budget/guard.py`, `service.py`
- Test: `bogda/tests/budget/test_approval.py` plus one guard/service case

**Produces:**

```python
@dataclass(frozen=True, slots=True)
class OwnerApprovalCredential:
    credential_id: str
    run_id: str
    envelope_digest: str
    pricing_version: str
    authorized_ceiling_cny: Decimal
    actor_id: str
    issued_at: datetime
    expires_at: datetime
    nonce: str
    mac: str
```

`SqliteApprovalStore.issue` / `consume` with HMAC-SHA256 over the canonical fields. `BudgetGuard.evaluate(..., approval=None)` still fail-closes above 20 CNY without a valid credential; with a valid unconsumed credential matching run/envelope/pricing, it may `allow` with reason `owner_approval_consumed`. `BudgetAdmissionService.admit(..., approval=None)` consumes inside the same path as reserve: forged/expired/wrong run/wrong envelope/replay → deny, no reservation. Emit `BUDGET_OVERRIDE_APPROVED` once.

HMAC key from constructor bytes, never logged.

---

### Task 5: DEF-04 usage_unknown core → console transport

**Files:**
- Modify: `bogda/src/bogda/model_runtime/recovery.py` add `list_open_cases`
- Create: `bogda-console/src/bogda_console/adapters/core_model_control.py`
- Modify: `app.py` Container for `allowlisted-test` when `BOGDA_USAGE_UNKNOWN_DB` is set
- Test: `bogda/tests/model_runtime/test_recovery.py`, `bogda-console/tests/backend/test_core_model_control.py`

**Produces:** Real adapter maps open cases to `DecisionKind.USAGE_UNKNOWN` with the existing reconcile → approve-retry / terminate actions and revision CAS. Same call id cannot be retried. `preview_run` / policy writes stay unwired (503) on real profiles. Observer 403. Do not enable the mock model-control store on real profiles.

---

### Task 6: DEF-06 peak/valley dispatcher

**Files:**
- Create: `bogda/src/bogda/budget/dispatcher.py`
- Test: `bogda/tests/budget/test_dispatcher.py`

**Produces:** `PriceAwareDispatcher.dispatch(plan, command, *, envelope, approval=None)` with commands `wait_for_off_peak` | `start_now` | `cancel`. It records a frozen plan and calls a `PaidStartPort` only for `start_now`. Peak `start_now` must pass `BudgetGuard` (and Task 4 credential if >20 CNY). It does not call live Prefect or `pi-service`.

---

### Task 7: Docs and hang

Update `docs/reports/2026-08-29-bogda-deferred-work-register.md` NOW-06 / DEF-04/13/16/17/19/06. CLAUDE.md hang: Gate 7 review Important items closed in this branch; pre-research wiring local; still no 3100/dorm; DEF-03 still needs a worker. Append lessons 56+ about joint pool allowlist and HMAC credentials.

Write `docs/reports/2026-09-02-bogda-now06-pre-research.md` with what is local-tested vs still not production research.

---

## Explicitly out of scope

- DEF-03 live checkpoint (no worker)
- Step 5 notebook/Wake Bridge/3100
- Deleting leftover S2 Prefect resources (ask owner)
- Live dsh `usage.json` exact receipt
- Push to origin unless owner asks
