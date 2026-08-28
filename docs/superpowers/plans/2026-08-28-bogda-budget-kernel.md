# Bogda Phase B Budget Kernel Implementation Plan

> **Execution contract:** Luna implements one bounded task at a time with TDD. SOL reviews the fixed commit SHA, interfaces, failure semantics, and test evidence before the next task starts.

**Goal:** Build a provider-neutral, fail-closed budget kernel on top of Phase A contracts, consume the existing DeepSeek usage-monitor read-only API, estimate workload-aware peak/off-peak cost, reserve funds with a single-flight ledger, and persist structured budget events to JSONL.

**Architecture:** Keep external I/O behind ports. `UsagePort` normalizes the existing `/api/dashboard` payload into a strict snapshot; pricing and workload estimation are pure Decimal/timezone-aware services; `BudgetGuard` makes deterministic admission decisions; a ledger owns reservation state; an orchestration service emits `RunEventV1` through an append-only event sink. This phase does not call dsh, route Flash/Pro, mutate Prefect, expose frontend APIs, or enforce the guard in production flows.

**Tech stack:** Python 3.11, Pydantic v2, stdlib `urllib`, `zoneinfo`, `decimal`, `threading`, pytest.

## Scope and invariants

- Money is `Decimal` end to end and JSON money is a decimal string; floats fail closed.
- Times are timezone-aware; pricing decisions are evaluated in `Asia/Shanghai`.
- The supplied catalog is versioned as `deepseek-cn-2026-08-28`, currency `CNY`, with an explicit effective time, review deadline, and source note.
- DeepSeek peak windows are weekdays `09:00–12:00` and `14:00–18:00` Beijing time. End boundaries are off-peak.
- Unknown, missing, expired, malformed, unauthorized, wrong-currency, or older-than-120-second usage data cannot authorize a paid call.
- Bogda consumes `GET /api/dashboard` through `X-Monitor-Token`; it never imports usage-monitor internals and never receives the DeepSeek API key.
- Runtime is not billed directly. A call window that could cross a pricing boundary is conservatively costed at the more expensive applicable period.
- Budget ceilings depend on expected tokens/calls, retries, historical p90, contingency, and pricing windows; they are not a fixed small cap.
- The first ledger permits one active paid-call reservation per process. Its interface must permit a future atomic durable implementation without changing guard policy.
- Every snapshot, reservation, release, reconciliation, or budget pause decision emitted by the service is appended as a validated `RunEventV1` JSON line. Tokens and monitor credentials must never enter events.
- Existing Phase A contracts remain source-compatible. This phase may add event fields/types only when required and version-compatible.

## Program boundary

Phase B ends with a fake-provider integration acceptance test and a local read-only monitor adapter contract test. It explicitly excludes:

- dsh execution and Flash/Pro model routing (Phase C);
- prompt archive and model-call usage reconciliation from dsh responses (Phase C);
- Prefect pause/resume wiring (Phase C);
- Console windows, switches, approval endpoints, and decision center (Phase D);
- production enforcement, deployment, systemd changes, device writes, or live API calls (later gated rollout).

## Task 1 — Versioned DeepSeek pricing catalog

**Files:**

- Create: `bogda/src/bogda/budget/__init__.py`
- Create: `bogda/src/bogda/budget/pricing.py`
- Create: `bogda/tests/budget/test_pricing.py`

**Public interfaces:**

- `PricePeriod`: `off_peak | peak`
- `TokenPrices`: strict Decimal prices for cache-hit input, cache-miss input, and output
- `PricingCatalogV1`: version, currency, timezone, `effective_at`, `review_by`, source, and Flash/Pro price rows
- `DEEPSEEK_CN_2026_08_28`
- `period_at(instant) -> PricePeriod`
- `period_for_window(start, end) -> PricePeriod`
- `prices_for(tier, period, *, as_of) -> TokenPrices`
- `estimate_token_cost(...) -> Decimal`

**TDD cases:**

1. Reject naive datetimes, float money, Auto tier, unknown schema/version data, and expired catalog use.
2. Cover Monday/Friday/weekend and exact `09:00`, `12:00`, `14:00`, `18:00` boundaries in Beijing time, including a UTC input converted to Beijing time.
3. Cover all Flash/Pro × peak/off-peak × hit/miss/output price rows supplied by the owner.
4. Treat an interval touching any peak time as peak; reject non-positive or reversed windows.
5. Prove Decimal arithmetic and deterministic JSON serialization.

**Verification:**

```powershell
uv run --extra dev --python 3.11 pytest tests/budget/test_pricing.py -q
uv run --extra dev --python 3.11 pytest tests/contracts tests/budget/test_pricing.py -q
git diff --check
```

Commit: `feat(bogda): add versioned DeepSeek pricing catalog`

## Task 2 — UsagePort and read-only usage-monitor adapter

**Files:**

- Create: `bogda/src/bogda/budget/usage.py`
- Create: `bogda/tests/budget/test_usage.py`

**Public interfaces:**

- `UsageSourceStatus`: `up | unavailable | unauthorized | invalid`
- `UsageSnapshotV1`: provider, available, total balance, currency, observed time, source status
- `UsagePort` protocol with `get_snapshot() -> UsageSnapshotV1`
- `UsageMonitorClient`: configured with base URL, optional monitor token, timeout, and injectable transport/clock
- `snapshot_age_seconds(snapshot, *, now) -> int`
- `require_fresh_snapshot(snapshot, *, now, max_age_seconds=120) -> UsageSnapshotV1`

**Adapter mapping:**

- `balance.total` -> `total_balance`
- `balance.currency` -> `currency`
- `balance.is_available` -> `available`
- `last_updated.balance` epoch -> timezone-aware `observed_at`
- `services.deepseek_api` -> source status
- send `X-Monitor-Token` only when configured

**TDD cases:**

1. Normalize a valid dashboard response without importing usage-monitor code.
2. Reject missing fields, bool/numeric/float balance, wrong currency, invalid epoch, unavailable balance, and inconsistent source state.
3. Convert HTTP 401/403, non-2xx, timeout, invalid JSON, and transport errors into explicit fail-closed adapter errors without leaking token values.
4. Accept exactly 120 seconds old; reject older snapshots and future-skewed snapshots beyond a small explicit tolerance.
5. Assert request method/path/header/timeout using an injected fake transport; make no live network call.

**Verification:**

```powershell
uv run --extra dev --python 3.11 pytest tests/budget/test_usage.py -q
uv run --extra dev --python 3.11 pytest tests/budget -q
git diff --check
```

Commit: `feat(bogda): add usage monitor read adapter`

## Task 3 — Workload prediction and dynamic budget envelope

**Files:**

- Create: `bogda/src/bogda/budget/estimation.py`
- Create: `bogda/tests/budget/test_estimation.py`

**Public interfaces:**

- `TokenWorkload`: expected calls, hit/miss input tokens, output tokens, retry count
- `HistoricalUsageProfile`: optional p50/p90 cost and verified cache-hit ratio
- `WorkloadEstimate`: expected cost, retry reserve, contingency factor, historical p90, authorized ceiling, selected price period, pricing version
- `WorkloadEstimator.estimate(...) -> WorkloadEstimate`
- `WorkloadEstimator.to_budget_envelope(...) -> RunBudgetEnvelope`

**Formula:**

```text
expected_cost = token cost for expected calls at the conservative window price
retry_reserve = per-call expected cost * allowed retries
authorized_ceiling = max(expected_cost * contingency_factor, historical_p90_cost) + retry_reserve
```

The estimator must define documented default contingency factors by intent/tier, while allowing an injected policy table. It may use a verified cache-hit ratio only when historical evidence is supplied; otherwise all expected input is priced as cache miss.

**TDD cases:**

1. Validate tokens/calls/retries and reject floats, negatives, Auto tier, naive times, and invalid history.
2. Cover Flash execute/brief lower contingency and Pro explore/decide/audit higher contingency.
3. Prove p90 raises the ceiling, retries add reserve, cache history lowers only eligible input cost, and a peak-crossing runtime uses peak price.
4. Prove long runtime without peak overlap does not directly add money.
5. Produce a Phase A `RunBudgetEnvelope` with matching tier, source, minimum remaining, and pricing version.

**Verification:**

```powershell
uv run --extra dev --python 3.11 pytest tests/budget/test_estimation.py -q
uv run --extra dev --python 3.11 pytest tests/contracts tests/budget -q
git diff --check
```

Commit: `feat(bogda): estimate workload aware budgets`

## Task 4 — Deterministic BudgetGuard and single-flight ledger

**Files:**

- Create: `bogda/src/bogda/budget/ledger.py`
- Create: `bogda/src/bogda/budget/guard.py`
- Create: `bogda/tests/budget/test_ledger.py`
- Create: `bogda/tests/budget/test_guard.py`

**Public interfaces:**

- `Reservation`, `ReservationState`
- `BudgetLedger` protocol: active total, reserve, release, reconcile, lookup
- `SingleFlightBudgetLedger`: thread-safe process-local implementation
- `BudgetDecisionKind`: `allow | stale_usage_snapshot | usage_unavailable | insufficient_balance | budget_ceiling_exceeded | reservation_conflict | invalid_pricing`
- `BudgetDecision`: kind, allowed, reason, available-to-start, requested reservation, snapshot age
- `BudgetGuard.evaluate(...) -> BudgetDecision`

**Rules:**

- `available_to_start = total_balance - active_reservations - minimum_remaining`.
- Requested reservation cannot exceed the frozen run ceiling or available-to-start balance.
- The guard never mutates the ledger. A separate reserve operation must compare the evaluated snapshot/version and fail if another reservation wins.
- Release is idempotent only for the same terminal result; conflicting double reconciliation fails closed.
- Reconciliation records actual cost and releases the unused reserve; actual cost above reserve is visible and never expands the frozen ceiling silently.

**TDD cases:**

1. Fresh sufficient balance allows; stale/unavailable/wrong state denies.
2. Minimum reserve line, active reservations, exact equality, ceiling breach, and Decimal precision.
3. Only one active paid reservation; simulated competing threads cannot both reserve.
4. Release, exact/under/over-reserve reconciliation, duplicate replay, and unknown reservation.
5. No policy branch depends on frontend, executor, or provider-specific payloads.

**Verification:**

```powershell
uv run --extra dev --python 3.11 pytest tests/budget/test_ledger.py tests/budget/test_guard.py -q
uv run --extra dev --python 3.11 pytest tests/budget -q
git diff --check
```

Commit: `feat(bogda): add budget guard and reservation ledger`

## Task 5 — Append-only structured budget event log and service

**Files:**

- Create: `bogda/src/bogda/events/__init__.py`
- Create: `bogda/src/bogda/events/jsonl.py`
- Create: `bogda/src/bogda/budget/service.py`
- Modify only if necessary: `bogda/src/bogda/contracts/events.py`
- Create: `bogda/tests/events/test_jsonl.py`
- Create: `bogda/tests/budget/test_service.py`

**Public interfaces:**

- `RunEventSink` protocol with `append(event: RunEventV1) -> None`
- `JsonlRunEventSink(path)`: append-only, UTF-8, one validated compact JSON object per line, flush before return
- `BudgetAdmissionService`: fetch snapshot, evaluate, reserve/release/reconcile, and emit events

**Event behavior:**

- A successful admission emits `budget_snapshot` then `budget_reserved`.
- A denial emits `budget_snapshot` then `budget_paused` with a stable reason.
- Release/reconcile emits `budget_released` with the remaining reservation facts available in schema v1.
- Event write failure prevents a reservation from being used; compensate any just-created reservation before returning failure.
- The service accepts a clock/event sink through dependency injection. It never logs transport headers, tokens, raw dashboard payloads, prompts, or arbitrary exceptions.

**TDD cases:**

1. JSONL remains parseable across multiple appends; each line round-trips through `RunEventV1`.
2. Reject directories, unsafe replacement behavior, and invalid event objects; never truncate an existing log.
3. Assert event order and fields for allow, stale, unavailable, insufficient, release, and reconcile.
4. Assert event-sink failure compensates reservation and surfaces a typed failure.
5. Scan persisted output to prove a configured sentinel token is absent.

**Verification:**

```powershell
uv run --extra dev --python 3.11 pytest tests/events/test_jsonl.py tests/budget/test_service.py -q
uv run --extra dev --python 3.11 pytest tests/contracts tests/budget tests/events -q
git diff --check
```

Commit: `feat(bogda): persist budget admission events`

## Task 6 — Fake-provider integration acceptance and maintainer docs

**Files:**

- Create: `bogda/tests/integration/test_budget_kernel.py`
- Modify: `bogda/README.md`
- Create: `docs/reports/2026-08-28-bogda-budget-kernel-acceptance.md`
- Modify: `docs/superpowers/plans/2026-08-28-bogda-budget-kernel.md`

**Acceptance scenarios:**

1. A fake fresh usage provider + Flash estimate + single-flight ledger creates a reservation and two ordered JSONL events.
2. A stale snapshot prevents reservation and writes a distinct pause reason.
3. A Pro workload crossing a peak boundary uses peak prices and a non-tight dynamic ceiling.
4. Balance recovery can be re-evaluated against the same frozen envelope without expanding it.
5. Competing admission cannot over-reserve; released funds become available to a later run.

**Documentation must state:**

- exact module ownership and extension ports;
- usage-monitor endpoint/header mapping and secret boundary;
- pricing version, review deadline, peak rules, and update procedure;
- dynamic-budget formula and single-flight limitation;
- JSONL location is caller-selected and no production writer is wired yet;
- recovery commands and Phase C input contracts;
- no live network, dsh, Prefect, frontend, deployment, or device mutation occurred.

**Final verification:**

```powershell
uv run --extra dev --python 3.11 pytest -q
D:\pythonProject\bogda\.venv\Scripts\python.exe -m unittest tests.test_taskfile -q
git diff --check
git status --short --branch
```

SOL performs a whole-branch review from the Phase B fork point, verifies no `orchestra` or usage-monitor imports under `bogda/src`, and records exact pass counts and commit SHAs in the acceptance report.

Commit: `docs(bogda): accept budget kernel phase`

## Review and stop gate

Each task requires focused red/green evidence, relevant regression tests, `git diff --check`, an isolated commit, and SOL review before the next task. Luna's report is implementation input, not acceptance evidence.

Phase B is complete only when Tasks 1–6 pass, the full Bogda and Orchestra compatibility suites remain green, the event log is demonstrably append-only and secret-safe, and the acceptance report names every limitation. Stop before Phase C and present the owner with local merge / push-PR / preserve-worktree options. No production integration is authorized by this plan.
