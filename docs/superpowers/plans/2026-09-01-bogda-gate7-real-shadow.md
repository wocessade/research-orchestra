# Bogda Gate 7 and Real Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the accepted RK3528 Gate 6 evidence into a Gate 7 entry decision, then prove the 3101 console against live Prefect first as read-only S1 and then as exact-allowlist test-write S2.

**Architecture:** Keep Prefect as the only execution-state authority and keep the browser behind the existing BFF contracts. Strengthen `CapabilitySnapshot` so the frontend can decide action applicability for each resource without pretending that a disabled button is authorization. Run S1 locally against the RK3528 Prefect API with every mutation capability false; only after S1 passes, create uniquely named dedicated test resources and run S2 through the normal 3101 command API with exact allowlists and authoritative post-reads.

**Tech Stack:** Python 3.11, FastAPI, Prefect 3.8.3 client, Pydantic v2, React 19, TypeScript, TanStack Query, Vitest, Playwright, PowerShell, system OpenSSH.

**Spec:** `docs/superpowers/specs/2026-08-24-bogda-architecture-design.md` and `docs/superpowers/specs/2026-08-24-bogda-console-design.md`

## Global Constraints

- Gate 7 authorizes controlled integration only; it does not authorize 3100 cutover, production research writes, Orchestra deletion, dorm runner work, or paid provider calls.
- `real-readonly` performs no Prefect or RunResult mutation and exposes every mutation capability as false.
- `allowlisted-test` runs as exactly one BFF replica and accepts no wildcard; deployment, schedule, queue, and pool sets are exact.
- S2 resources use the `bogda-s2-acceptance-20260901-<suffix>` prefix and are not attached to `pi-service`, `dorm-x86`, or any existing production deployment.
- Browser code consumes only Bogda OpenAPI contracts; it never receives Prefect credentials or raw provider credentials.
- The RK3528 server uses `PREFECT_API_AUTH_STRING`; Bogda passes it only to the server-side Prefect client as `auth_string` and never serializes or logs it.
- Every successful command requires an authoritative post-read. Do not update the UI optimistically and do not retry a mutation automatically.
- Port 3100 remains reachable and unchanged before and after S1/S2. Unknown processes on 3101 are never killed.
- No secret, API key, full environment dump, or credential-bearing URL enters logs, reports, commits, or agent prompts.
- Do not add a general retry/recovery framework, alternate scheduler, second task database, or speculative high-availability layer.
- Existing main-worktree and RF PCB changes are outside this plan and must not be staged or modified.

---

### Task 1: Gate 7 entry decision and current-state reconciliation

**Files:**
- Create: `docs/reports/2026-09-01-bogda-gate7-entry-decision.md`
- Modify: `docs/reports/2026-08-29-bogda-deferred-work-register.md`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/AUDIT.md`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/STATE.md`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/RUNLOG.ndjson`

**Interfaces:**
- Consumes: Gate 6 final report, remediation log, Stage D/E acceptance reports, independent Luna sentry verdict.
- Produces: a bounded Gate 7 `ACCEPT | REMEDIATE | ROLLBACK` decision and explicit S1/S2 entry conditions.

- [ ] **Step 1: Verify the evidence set is immutable and current**

Run:

```powershell
git status --short
git log --oneline -5
git diff --check
```

Expected: only this plan is tracked as new; the worktree is based on the Gate 6 acceptance commit `d05ccd6`.

- [ ] **Step 2: Integrate the independent evidence review**

Record the Luna sentry verdict verbatim by severity in `AUDIT.md`. A HIGH/BLOCKED finding stops S1; a MED finding is fixed or explicitly accepted before S1. Do not lower Gate 6 thresholds or reinterpret missing evidence.

- [ ] **Step 3: Write the Gate 7 entry report**

The report must state one of:

```text
ACCEPT: Gate 6 evidence supports controlled S1 read-only integration.
REMEDIATE: named evidence or software boundary must close before S1.
ROLLBACK: RK3528 control-plane placement is rejected and the architecture returns to the documented fallback.
```

For `ACCEPT`, list S1 as read-only and S2 as separately conditioned on resource-scoped controls, exact test-resource identity, one replica, rollback, and fresh S1 evidence.

- [ ] **Step 4: Reconcile stale current-state text**

Update NOW-03 in the deferred register so it no longer says Gate 6 failed. Keep exact dsh token receipts non-blocking per owner decision. Do not edit the concurrently modified Stage6 workboard in the main checkout.

- [ ] **Step 5: Validate and commit the decision**

Run:

```powershell
git diff --check
rg -n "Gate 6 \*\*未通过\*\*|Gate 6 未通过" docs/reports/2026-08-29-bogda-deferred-work-register.md docs/reports/2026-09-01-bogda-gate7-entry-decision.md
git add docs/reports/2026-09-01-bogda-gate7-entry-decision.md docs/reports/2026-08-29-bogda-deferred-work-register.md
git commit -m "docs: accept Bogda Gate 7 entry"
```

Expected: no stale Gate 6 failure remains in current-status rows; historical failure reports remain unchanged.

---

### Task 2: Resource-scoped command capabilities for S2

**Files:**
- Modify: `bogda-console/src/bogda_console/config.py`
- Modify: `bogda-console/src/bogda_console/app.py`
- Modify: `bogda-console/src/bogda_console/adapters/prefect_api.py`
- Modify: `bogda-console/src/bogda_console/contracts/models.py`
- Modify: `bogda-console/src/bogda_console/services/queries.py`
- Modify: `bogda-console/frontend/src/pages/InfrastructurePage.tsx`
- Modify: `bogda-console/frontend/src/pages/RunDetailPage.tsx`
- Modify: `bogda-console/tests/backend/test_config.py`
- Modify: `bogda-console/tests/backend/test_prefect_adapter_contract.py`
- Modify: `bogda-console/tests/backend/test_query_service.py`
- Modify: `bogda-console/tests/frontend/commands.test.tsx`
- Modify: `bogda-console/tests/frontend/checkpoints.test.tsx`
- Modify: `bogda-console/tests/frontend/helpers.tsx`
- Regenerate: `bogda-console/openapi.json`
- Regenerate: `bogda-console/frontend/src/api/generated.ts`

**Interfaces:**
- Consumes: `PREFECT_API_URL`, server-side `PREFECT_API_AUTH_STRING` or optional `PREFECT_API_KEY`, `Settings.allowed_*`, `RunSummary.deployment_id`, `DeploymentSummary.allowlisted`, nested pool/queue snapshots.
- Produces: `CapabilitySnapshot.canDecideCheckpoint` plus sorted `allowedDeploymentIds`, `allowedScheduleIds`, `allowedQueueIds`, and `allowedWorkPoolNames` arrays.

- [ ] **Step 1: Write failing configuration tests**

Add tests proving that `Settings.from_env` preserves `PREFECT_API_AUTH_STRING` as a server-only field and that `BOGDA_CONSOLE_PROFILE=allowlisted-test` with `BOGDA_CONSOLE_REPLICA_COUNT=2` raises:

```text
allowlisted-test requires exactly one replica
```

Retain the existing behavior that `real-readonly` disables every command.

- [ ] **Step 2: Write a failing Prefect auth-adapter test**

Monkeypatch the `PrefectClient` constructor and assert `_default_client()` passes the configured value as `auth_string`, not `api_key`, a URL parameter, or a header returned by Bogda contracts. Error assertions must not contain the credential.

- [ ] **Step 3: Write failing backend capability tests**

For `allowlisted-test`, assert the capability response includes sorted exact allowlist arrays and:

```python
assert snapshot.can_decide_checkpoint is True
assert snapshot.can_review_scientific_result is True
```

For `real-readonly`, assert both booleans are false and every allowlist array is empty unless explicitly configured; configured values may be reported but do not enable commands.

- [ ] **Step 4: Write failing frontend resource-applicability tests**

Cover these cases:

```text
deployment submit: global capability true + deployment.allowlisted true
schedule action: deployment id and schedule id both in the capability scope
queue action: pool name and queue id both in the capability scope
cancel/review/checkpoint: run deployment id in allowedDeploymentIds
checkpoint uses canDecideCheckpoint, not canReviewScientificResult
non-allowlisted resources show a visible "不在测试白名单" reason and never open a confirmation dialog
```

- [ ] **Step 5: Run the focused tests and observe failure**

Run:

```powershell
$env:PYTHONPATH = "$PWD\src"
& 'D:\pythonProject\bogda-console\.venv\Scripts\python.exe' -m pytest -q tests/backend/test_config.py tests/backend/test_prefect_adapter_contract.py tests/backend/test_query_service.py
npm run test:frontend -- --run ../tests/frontend/commands.test.tsx ../tests/frontend/checkpoints.test.tsx
```

Expected: failures identify the missing capability fields, replica fail-fast, and resource-specific UI gating.

- [ ] **Step 6: Implement the minimal server-side auth and capability contracts**

`Settings.from_env` must read `PREFECT_API_AUTH_STRING` without transforming it and reject multi-replica `allowlisted-test`. `Container.build` passes it to `PrefectApiAdapter`, whose `_default_client` passes it to `PrefectClient(auth_string=...)`. `CapabilitySnapshot` must add the five fields above. `QueryService.capabilities()` must populate booleans from existing properties and arrays from `sorted(settings.allowed_*)`; no Prefect query occurs in the capability endpoint.

- [ ] **Step 7: Implement frontend applicability without local authorization claims**

Use the capability scope only to render applicability. Backend checks remain authoritative. A disabled action explains whether the profile is read-only or the resource is outside the exact S2 allowlist. Do not cache a successful mutation as authorization for another resource.

- [ ] **Step 8: Regenerate contracts and run focused verification**

Run:

```powershell
$env:PYTHONPATH = "$PWD\src"
& 'D:\pythonProject\bogda-console\.venv\Scripts\python.exe' scripts/export_openapi.py
npm run check:contracts
& 'D:\pythonProject\bogda-console\.venv\Scripts\python.exe' -m pytest -q tests/backend/test_config.py tests/backend/test_prefect_adapter_contract.py tests/backend/test_query_service.py tests/backend/test_openapi.py
npm run test:frontend -- --run ../tests/frontend/commands.test.tsx ../tests/frontend/checkpoints.test.tsx
npm run build
```

Expected: all focused tests and generated-contract drift checks pass.

- [ ] **Step 9: Commit the resource capability change**

```powershell
git add bogda-console/src bogda-console/frontend/src bogda-console/tests bogda-console/openapi.json
git commit -m "feat(console): scope S2 controls to allowed resources"
```

---

### Task 3: Repeatable S1/S2 operator runbook

**Files:**
- Create: `bogda-console/docs/real-shadow-runbook.md`
- Modify: `bogda-console/README.md`
- Test: `bogda-console/tests/backend/test_check_contracts.py`

**Interfaces:**
- Consumes: the three profile names, exact environment variable names, local launcher ownership checks, 3100 reservation, and the capability scope from Task 2.
- Produces: a secret-safe S1/S2 sequence with evidence paths, rollback, and explicit stop conditions.

- [ ] **Step 1: Add a documentation contract test**

Assert the runbook contains all of:

```text
real-readonly
allowlisted-test
PREFECT_API_AUTH_STRING
BOGDA_CONSOLE_REPLICA_COUNT=1
BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS
BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS
BOGDA_CONSOLE_ALLOWED_QUEUE_IDS
BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES
3100
authoritative post-read
```

- [ ] **Step 2: Write the runbook**

Define six phases: ownership preflight, 3100 before-check, S1 start/read/compare, restore, S2 dedicated-resource setup, S2 command matrix/restore. Commands may read credentials from environment but must never echo them. Unknown 3101 ownership, a non-test allowlist member, a second replica, source errors, or failed post-read is a hard stop.

- [ ] **Step 3: Document evidence and rollback**

Evidence is written under `.tasks/active/052_bogda-gate7-real-shadow/evidence/` as sanitized JSON/text. Rollback stops only the launcher-owned 3101 process, restores its captured preflight profile, leaves dedicated S2 records identifiable, and never deletes Prefect records during acceptance.

- [ ] **Step 4: Link the runbook and verify**

Run:

```powershell
$env:PYTHONPATH = "$PWD\src"
& 'D:\pythonProject\bogda-console\.venv\Scripts\python.exe' -m pytest -q tests/backend/test_check_contracts.py
git diff --check
```

- [ ] **Step 5: Commit the runbook**

```powershell
git add bogda-console/docs/real-shadow-runbook.md bogda-console/README.md bogda-console/tests/backend/test_check_contracts.py
git commit -m "docs(console): add real shadow runbook"
```

---

### Task 4: Execute and record S1 real-readonly shadow

**Files:**
- Create: `docs/reports/2026-09-01-bogda-console-s1-real-shadow.md`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/RUNLOG.ndjson`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/STATE.md`
- Create ignored evidence under: `.tasks/active/052_bogda-gate7-real-shadow/evidence/s1/`

**Interfaces:**
- Consumes: `http://100.78.158.80:4200/api` after a fresh health check, local 3101 launcher state, Task 3 runbook.
- Produces: sanitized comparison of Prefect authority and 3101 projections with all command capabilities false.

- [ ] **Step 1: Confirm target and local ownership without mutation**

Run strict read-only checks:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3100/ -TimeoutSec 5
Invoke-RestMethod http://100.78.158.80:4200/api/health -TimeoutSec 10
powershell -ExecutionPolicy Bypass -File bogda-console/scripts/local-console.ps1 status
```

Do not stop 3101 unless the launcher status proves it owns the process.

- [ ] **Step 2: Capture pre-state and start `real-readonly`**

Set only the documented profile, Prefect URL, loopback host, ports, and optional server-side credential. Start the built console at 3101. Do not set any allowlist or DeepSeek key for S1.

- [ ] **Step 3: Query both authority and projection**

Capture `/api/v1/capabilities`, `/overview`, `/runs`, `/deployments`, and `/infrastructure`. Compare deployment, run, pool, queue, worker, state type/name, and RunResult identifiers against direct Prefect reads. Every capability beginning with `can` must be false except pure read capability fields, if any are later introduced.

- [ ] **Step 4: Verify frontend behavior**

Open the 3101 UI and verify the Infrastructure and Run Detail pages show live Prefect source state while all write controls are disabled with a read-only reason. Capture browser console/network errors and screenshots without secrets.

- [ ] **Step 5: Restore pre-state and verify 3100**

Stop only the launcher-owned S1 process, restore the captured launcher state if one existed, and recheck 3100. No Prefect object count or command-version field may change because of S1.

- [ ] **Step 6: Write and commit the S1 report**

The report records target, timestamps, source freshness, compared IDs/counts, frontend result, 3100 before/after, zero mutation evidence, discrepancies, and the S2 go/no-go decision.

```powershell
git add docs/reports/2026-09-01-bogda-console-s1-real-shadow.md
git commit -m "docs(console): record S1 real shadow"
```

---

### Task 5: Execute and record exact-allowlist S2

**Files:**
- Create: `docs/reports/2026-09-01-bogda-console-s2-allowlisted-shadow.md`
- Modify: `docs/reports/2026-08-29-bogda-deferred-work-register.md`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/RUNLOG.ndjson`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/STATE.md`
- Create ignored evidence under: `.tasks/active/052_bogda-gate7-real-shadow/evidence/s2/`

**Interfaces:**
- Consumes: S1 PASS, Task 2 resource capability scope, Task 3 runbook.
- Produces: exact test-resource IDs and command receipts for submit, cancel, schedule pause/resume, queue pause/resume, review, and checkpoint applicability.

- [ ] **Step 1: Create dedicated inert test resources**

Using the Prefect client, create a uniquely suffixed flow, process work pool, queue, deployment, and inactive interval schedule whose names begin with `bogda-s2-acceptance-20260901-`. The pool has concurrency limit 1 and no worker. Persist only the returned IDs and non-secret names to ignored evidence.

- [ ] **Step 2: Prove isolation before enabling writes**

Reject the stage if any returned object belongs to `pi-service`, `dorm-x86`, an existing deployment, or a non-prefixed resource. Capture 3100 and the existing production object inventory before S2.

- [ ] **Step 3: Start one `allowlisted-test` replica**

Populate all four exact allowlist variables from the newly returned IDs/names and set `BOGDA_CONSOLE_REPLICA_COUNT=1`. Start on loopback 3101. Query `/capabilities` and confirm the browser enables controls only for the dedicated resources.

- [ ] **Step 4: Exercise the command matrix through 3101**

Execute each applicable command once: submit, cancel the submitted test run, pause/resume the dedicated schedule, and pause/resume the dedicated queue. Seed a test-only RunResult Artifact and append one scientific review through 3101. For checkpoint, either seed the existing documented checkpoint artifact/input form and decide it through 3101, or record `inapplicable` with the exact missing runtime precondition; do not fake success or use a production run.

- [ ] **Step 5: Verify negative paths and authoritative receipts**

Attempt one non-allowlisted production-safe read resource command only if it can be rejected before mutation; expect `403 RESOURCE_NOT_ALLOWLISTED`. Confirm every successful receipt matches a direct Prefect post-read. Do not automatically retry any command.

- [ ] **Step 6: Restore safe state without deleting evidence**

Leave the dedicated schedule and queue resumed or paused exactly as the report states, cancel any remaining dedicated run, stop only the launcher-owned S2 process, and restore the prior 3101 profile. Do not delete test records during acceptance. Recheck 3100 and production object state.

- [ ] **Step 7: Write and commit the S2 report**

The report lists exact non-secret test IDs, command receipts, post-read states, negative-path result, frontend applicability, rollback state, 3100 before/after, and any deferred checkpoint limitation. Update DEF-20 only if backend authorization and frontend applicability are both proven.

```powershell
git add docs/reports/2026-09-01-bogda-console-s2-allowlisted-shadow.md docs/reports/2026-08-29-bogda-deferred-work-register.md
git commit -m "docs(console): record S2 allowlisted shadow"
```

---

### Task 6: Full verification, maintainability audit, and integration

**Files:**
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/AUDIT.md`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/STATE.md`
- Modify: `.tasks/active/052_bogda-gate7-real-shadow/RUNLOG.ndjson`
- Create: `.tasks/active/052_bogda-gate7-real-shadow/BRIEF.md`

**Interfaces:**
- Consumes: all prior commits, live S1/S2 evidence, deferred findings.
- Produces: final branch review, clean merge candidate, and recoverable handoff.

- [ ] **Step 1: Run full local verification**

```powershell
$env:PYTHONPATH = "$PWD\bogda-console\src"
& 'D:\pythonProject\bogda-console\.venv\Scripts\python.exe' -m pytest -q bogda-console/tests
npm --prefix bogda-console run test:frontend
npm --prefix bogda-console run build
npm --prefix bogda-console run test:browser
git diff --check origin/main...HEAD
```

- [ ] **Step 2: Run compatibility and maintainability review**

Check that Prefect remains the only execution-state authority, mock profiles still pass, generated OpenAPI matches, no frontend imports Prefect/provider types, allowlist logic exists once per layer, no secret-like values are tracked, and no mission-scoped dead code or abandoned evidence is present.

- [ ] **Step 3: Independent whole-branch review**

Use the complete `origin/main...HEAD` review package. HIGH/MED findings are fixed and re-reviewed or explicitly surfaced; no silent dismissal.

- [ ] **Step 4: Complete mission records**

Record exact verification output, live side effects, final provider spend of 0 CNY, unresolved deferred items, rulings, and rollback state. Move mission metadata to completed only after evidence is sufficient.

- [ ] **Step 5: Integrate under existing owner authorization**

Fetch `origin/main`, verify the branch is based on the current remote, rebase only if conflict-free, push the reviewed commits to `main`, and verify remote equality. Do not stage, reset, or modify the dirty main checkout.
