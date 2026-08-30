# Bogda Price-Aware Owner Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic peak/off-peak scheduling and a durable, owner-controlled recovery path for paid calls with unknown usage, then expose that path through the existing backend-driven Decision Center.

**Architecture:** Scheduling remains a pure `bogda.budget` domain service that consumes the existing frozen `SchedulePolicy`, workload, reviewed pricing catalog, and clock. Unknown-usage recovery is a separate persistent model-runtime state machine that reconciles the existing budget ledger before it can authorize a new retry call or terminate. The console continues to depend on ports and backend-provided actions; it does not import Bogda runtime policy or DeepSeek-specific execution payloads.

**Tech Stack:** Python 3.11, Pydantic v2, SQLite, FastAPI, React 19, TypeScript, Vitest, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-bogda-intelligent-collaboration-budget-design.md`

## Global Constraints

- Do not declare Gate 6 or Gate 7 passed and do not mutate RK3528, Prefect production state, systemd, 3100, or paid provider state.
- Money is `Decimal`; all timestamps are timezone-aware; price-window evaluation is `Asia/Shanghai`.
- Exact dsh token receipts remain optional; an unknown paid-call result must stay fail-closed until an owner records an actual cost.
- The frontend renders actions and requirements supplied by the backend; scheduling and recovery policy are not copied into React.
- Preserve existing public JSON names unless this plan explicitly adds an optional backward-compatible field.
- Do not add an unpublished sibling-package runtime dependency merely to deduplicate the balance parser.
- Every behavior change follows RED → GREEN → focused regression before commit.
- No live DeepSeek call; provider spend for this plan is 0 CNY.

---

### Task 1: Deterministic peak/off-peak scheduler

**Files:**
- Create: `bogda/src/bogda/budget/scheduling.py`
- Modify: `bogda/src/bogda/budget/__init__.py`
- Create: `bogda/tests/budget/test_scheduling.py`

**Interfaces:**
- Consumes: `SchedulePolicy`, `PricePreference`, `TaskIntent`, `ModelTier`, `TokenWorkload`, `HistoricalUsageProfile`, and `WorkloadEstimator`.
- Produces: `ScheduleDisposition`, `PriceAwareSchedulePlan`, and `PriceAwareScheduler.plan`.

- [ ] **Step 1: Write failing domain tests**

Cover these exact behaviors with timezone-aware examples: off-peak starts now; weekday 10:00 Beijing waits until 12:00 when the run fits before its deadline; weekday 13:00 remains off-peak; weekday 15:00 waits until 18:00; Friday evening and weekends stay off-peak; `immediate` starts now; future `earliest_start` is respected; a deadline that cannot fit the off-peak run starts now and marks `deadline_forced=True`; cost/savings use the same `WorkloadEstimator` and reviewed catalog; naive timestamps and non-positive runtime are rejected.

- [ ] **Step 2: Run RED**

Run: `python -m pytest bogda/tests/budget/test_scheduling.py -q`

Expected: collection fails because `bogda.budget.scheduling` does not exist.

- [ ] **Step 3: Implement the scheduler**

Create:

```python
class ScheduleDisposition(StrEnum):
    START_NOW = "start_now"
    WAIT_FOR_OFF_PEAK = "wait_for_off_peak"

@dataclass(frozen=True, slots=True)
class PriceAwareSchedulePlan:
    disposition: ScheduleDisposition
    reason: str
    scheduled_start: datetime
    current_period: PricePeriod
    scheduled_period: PricePeriod
    current_estimate: WorkloadEstimate
    scheduled_estimate: WorkloadEstimate
    estimated_savings: Decimal
    deadline_forced: bool

class PriceAwareScheduler:
    def plan(
        self, *, intent: TaskIntent, tier: ModelTier,
        workload: TokenWorkload, runtime_minutes: int,
        policy: SchedulePolicy, now: datetime,
        history: HistoricalUsageProfile | None = None,
    ) -> PriceAwareSchedulePlan:
        """Return a deterministic plan without sleeping or enqueueing."""
```

The scheduler scans only real pricing boundaries from `pricing.py`; it does not sleep or enqueue. A candidate off-peak start is valid only when the complete runtime window ends no later than `deadline`. `estimated_savings` is `max(current.authorized_ceiling - scheduled.authorized_ceiling, Decimal("0"))`.

- [ ] **Step 4: Run GREEN and focused regressions**

Run: `python -m pytest bogda/tests/budget/test_scheduling.py bogda/tests/budget/test_pricing.py bogda/tests/budget/test_estimation.py -q`

Expected: all pass.

- [ ] **Step 5: Commit**

Commit only the three task files with message `feat(budget): plan paid calls around price windows`.

### Task 2: Durable unknown-usage recovery state machine

**Files:**
- Create: `bogda/src/bogda/model_runtime/recovery.py`
- Modify: `bogda/src/bogda/model_runtime/service.py`
- Modify: `bogda/src/bogda/model_runtime/__init__.py`
- Create: `bogda/tests/model_runtime/test_recovery.py`
- Modify: `bogda/tests/model_runtime/test_paid_call_service.py`

**Interfaces:**
- Consumes: `BudgetAdmissionService.reconcile`, `RunEventSink`, `RunEventV1`, and the reservation/run/call context already known by `PaidModelCallService`.
- Produces: `UsageUnknownState`, immutable `UsageUnknownCase`, `SqliteUsageUnknownStore`, and `UsageUnknownRecoveryService`.

- [ ] **Step 1: Write failing recovery tests**

Test: opening a case survives store reopen; duplicate open is idempotent only for identical context; stale revision rejects; retry/terminate are impossible before reconciliation; reconciliation requires finite non-negative `Decimal`; repeated identical reconciliation is idempotent; conflicting actual cost rejects; after reconciliation owner may approve exactly one new retry or terminate; retry approval refers to a new call rather than reusing the paid call id; terminal decisions survive reopen.

- [ ] **Step 2: Run RED**

Run: `python -m pytest bogda/tests/model_runtime/test_recovery.py -q`

Expected: collection fails because `bogda.model_runtime.recovery` does not exist.

- [ ] **Step 3: Implement persistent recovery**

Use SQLite `BEGIN IMMEDIATE`, Decimal strings, UTC-aware timestamps, and monotonically increasing per-case revisions. States are exactly:

```python
class UsageUnknownState(StrEnum):
    AWAITING_RECONCILIATION = "awaiting_reconciliation"
    AWAITING_RETRY_DECISION = "awaiting_retry_decision"
    RETRY_APPROVED = "retry_approved"
    TERMINATED = "terminated"
```

`UsageUnknownRecoveryService.reconcile` calls the existing budget reconciliation once and appends a `model_call_finished` event whose reason is `manual_usage_reconciliation`, with stable non-secret `usage_reference="manual-reconciliation:<case-id>"` so the existing v1 event contract remains valid. `approve_retry` appends `budget_resumed` and stores a required non-empty `new_call_id`; `terminate` never releases an unknown reservation before reconciliation. Idempotency is required for owner commands and persisted business state; the existing JSONL sink remains at-least-once across a process crash until DEF-05 supplies a persistent outbox.

- [ ] **Step 4: Integrate the paid-call service**

Add an optional recovery port to `PaidModelCallService`. When execution returns `USAGE_UNKNOWN`, open the durable case after the usage-unknown event is safely appended. Existing callers without the port retain current fail-closed behavior. Never auto-call `approve_retry` and never reuse the original `call_id`.

- [ ] **Step 5: Run GREEN and focused regressions**

Run: `python -m pytest bogda/tests/model_runtime/test_recovery.py bogda/tests/model_runtime/test_paid_call_service.py bogda/tests/budget/test_durable_ledger.py -q`

Expected: all pass.

- [ ] **Step 6: Commit**

Commit task files with message `feat(runtime): persist unknown usage recovery`.

### Task 3: Backend decision contract and mock lifecycle

**Files:**
- Modify: `bogda-console/src/bogda_console/contracts/models.py`
- Modify: `bogda-console/src/bogda_console/contracts/ports.py`
- Modify: `bogda-console/src/bogda_console/api/routes.py`
- Modify: `bogda-console/src/bogda_console/services/commands.py`
- Modify: `bogda-console/src/bogda_console/adapters/mock_model_control.py`
- Modify: `bogda-console/tests/backend/test_contracts.py`
- Modify: `bogda-console/tests/backend/test_model_control_adapters.py`
- Modify: `bogda-console/tests/backend/test_commands.py`
- Modify: `bogda-console/openapi.json`

**Interfaces:**
- Consumes: the existing `DecisionItem`/`DecisionAction` revision model and Decision Center route.
- Produces: optional `DecisionAction.actual_cost_required: bool = False`, optional `DecisionAction.new_call_id_required: bool = False`, optional matching request fields, and the sequential reconcile → retry/terminate mock lifecycle.

- [ ] **Step 1: Write failing contract and command tests**

Assert old decision payloads remain valid without the new fields. For a usage-unknown item, `reconcile` advertises and requires finite non-negative CNY plus the current revision; success updates the run budget cost/event and replaces actions with `approve-retry` (advertising `newCallIdRequired=true`) and `terminate`; either terminal action removes the item; `approve-retry` requires a non-empty `newCallId`; stale revisions, missing required input, repeated terminal actions, and unknown actions return existing conflict/not-applicable envelopes rather than 500.

- [ ] **Step 2: Run RED**

Run: `python -m pytest bogda-console/tests/backend/test_contracts.py bogda-console/tests/backend/test_model_control_adapters.py bogda-console/tests/backend/test_commands.py -q`

Expected: new assertions fail because action metadata and request fields are absent.

- [ ] **Step 3: Implement the additive contract**

Extend the request/port signature with keyword-only optional `actual_cost_cny: Decimal | None = None` and `new_call_id: str | None = None`. Keep backend action interpretation in `MockModelControlAdapter`; the frontend must not infer which action needs which field. Add `TERMINATED = "terminated"` to `BudgetState` for the terminal mock snapshot. Reuse existing structured event types and put manual reconciliation detail in the event summary rather than creating a second log taxonomy.

- [ ] **Step 4: Regenerate and validate OpenAPI**

Run the repository's existing OpenAPI generation/check command from `bogda-console`; do not hand-edit generated schema content.

- [ ] **Step 5: Run GREEN**

Run the three focused backend files, then `python -m pytest bogda-console/tests/backend -q`.

- [ ] **Step 6: Commit**

Commit task files with message `feat(console): expose unknown usage decisions`.

### Task 4: Owner-facing Decision Center inputs

**Files:**
- Modify: `bogda-console/frontend/src/api/generated.ts`
- Modify: `bogda-console/frontend/src/pages/DecisionsPage.tsx`
- Modify: `bogda-console/frontend/src/styles.css`
- Modify: `bogda-console/tests/frontend/decisions.test.tsx`
- Create: `bogda-console/tests/browser/decision-center.spec.ts`

**Interfaces:**
- Consumes: backend `DecisionAction.actualCostRequired`, `DecisionAction.newCallIdRequired`, and revisioned decision response.
- Produces: accessible actual-cost and new-call-id fields shown only for the selected action that requires them; unchanged backend-driven decision rendering.

- [ ] **Step 1: Write failing frontend tests**

Test the full sequence: open usage-unknown decision; select reconcile; confirm is disabled until a valid non-negative CNY amount is entered; payload includes `actualCostCny`; refreshed item presents approve-retry/terminate; approve-retry requires a non-blank new call id; terminate does not request a new call id; stale 409 replaces the snapshot and requires a fresh click; ordinary peak-override actions show neither field.

- [ ] **Step 2: Run RED**

Run: `npm --prefix bogda-console run test:frontend -- decisions.test.tsx`

Expected: tests fail because conditional owner inputs are absent.

- [ ] **Step 3: Implement accessible conditional inputs**

Keep the existing dialog, focus management, evidence list, cost/quality impact, irreversible consequence, and rationale behavior. Add labels, inline validation, and field clearing when action or decision changes. Send only fields required by the selected backend action.

- [ ] **Step 4: Run GREEN, typecheck, and browser coverage**

Run: `npm --prefix bogda-console run test:frontend -- decisions.test.tsx`; `npm --prefix bogda-console run build`; then `npm --prefix bogda-console run test:browser -- decision-center.spec.ts` at desktop and 320px widths.

Expected: all pass with no horizontal overflow, console error, or keyboard trap.

- [ ] **Step 5: Commit**

Commit task files with message `feat(console-ui): guide unknown usage recovery`.

### Task 5: Provider conformance, audit, and durable handoff

**Files:**
- Create: `contracts/fixtures/deepseek-balance-v1.json`
- Modify: `bogda/tests/budget/test_deepseek_balance.py`
- Modify: `bogda-console/tests/backend/test_usage_balance_api.py`
- Modify: `docs/reports/2026-08-29-bogda-deferred-work-register.md`
- Create: `docs/reports/2026-08-31-bogda-price-aware-owner-control-acceptance.md`
- Modify: mission records under `.tasks/active/049_bogda-price-aware-owner-control/`

**Interfaces:**
- Consumes: both existing DeepSeek balance adapters.
- Produces: one versioned set of success and failure payload cases used by both test suites; final acceptance evidence and precise deferred triggers.

- [ ] **Step 1: Add shared conformance cases**

The fixture must cover: valid CNY string amount; `is_available=false`; USD-only; malformed `balance_infos`; numeric rather than string amount; negative, NaN, and Infinity strings; duplicate CNY entries. Define duplicate CNY as invalid so both parsers fail closed.

- [ ] **Step 2: Run both adapter suites**

Run core and console DeepSeek balance tests. They must consume the same fixture and agree on every case without importing each other's runtime package.

- [ ] **Step 3: Run full verification**

Run Bogda full pytest, console backend full pytest, frontend Vitest, OpenAPI/typecheck/build, and the full Playwright matrix. Record exact counts and skipped tests.

- [ ] **Step 4: Independent Luna audit**

Review mission consistency, time-window boundaries, persistent-state idempotency, event ordering, secret safety, frontend/backend action completeness, compatibility, and unnecessary defensive complexity. Fix all HIGH/MEDIUM findings and rerun affected evidence.

- [ ] **Step 5: Update durable records and commit**

Close only work proven by commits/tests. Keep real model-control transport, production RBAC, true adapter consolidation, and exact dsh receipts deferred with activation triggers. Commit with message `docs(bogda): accept price-aware owner controls`.
