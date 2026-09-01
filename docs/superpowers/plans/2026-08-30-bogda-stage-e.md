# Bogda Stage E Implementation Plan

> **历史计划。** Gate 6 已于 2026-08-31 通过；Gate 7 S1/S2 影子已于 2026-09-01 合入 `origin/main`。下文「不要宣布 Gate 6/7 通过 / 观察窗内禁研究 Flow」只约束当时执行，不再当现网状态。下一跳见根 `CLAUDE.md` 挂账，不是重跑本计划 Task 1–4。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Stage E runtime pieces that Gate 6 does not block: durable budget ledger, fail-closed real usage client already in-tree, then local dsh/Prefect smokes — without declaring Gate 6/7 pass, cutting 3100, or running research Flow on the live Gate 6 RK3528 trial.

**Architecture:** Keep `BudgetLedger` / `UsagePort` / dsh argv contracts. Replace process-local `SingleFlightBudgetLedger` with a SQLite file that survives process restart. Admission balance is official `GET https://api.deepseek.com/user/balance` (`DeepSeekBalanceClient`); the walnutpi usage-monitor dashboard stays an eink cache, not Bogda's source. Live DeepSeek and live Prefect resume wait for the Gate 6 box not to be in an observation window (or a separate local Prefect). Auto-admit ≤ 20 CNY.

**Tech Stack:** Python 3.11, sqlite3, existing `bogda.budget` / `bogda.model_runtime`, pytest.

## Global Constraints

- Do not declare Gate 6 or Gate 7 passed.
- Do not import `orchestra` or usage-monitor runtime into `bogda/src`.
- Do not print, commit, or log API keys, `PREFECT_*_AUTH`, or `X-Monitor-Token`.
- Do not submit research Flow Runs to RK3528 `pi-service` while trial `20260830T034154Z` is collecting health samples.
- Live DeepSeek: auto-admit estimated cost **≤ 20 CNY**; above 20 CNY must wait for owner console approval. **Test/smoke spend ≤ 10 CNY** does not need a further ask. Do not run paid Flow on RK3528 `pi-service` during trial `20260830T034154Z`.
- 3100 cutover, Orchestra migration, `dorm-x86` worker, and Wake Bridge are out of Stage E Task 1–3.
- TDD: failing test before production code. Commit only if the owner asks.

---

## File map

| File | Role |
|---|---|
| `bogda/src/bogda/budget/durable_ledger.py` | SQLite `BudgetLedger`; one active reservation; crash-reopen |
| `bogda/src/bogda/budget/ledger.py` | Protocol stays; process-local impl unchanged |
| `bogda/src/bogda/budget/__init__.py` | Export durable ledger |
| `bogda/tests/budget/test_durable_ledger.py` | Reopen, conflict, idempotent release/reconcile |
| `bogda/src/bogda/budget/deepseek_balance.py` | Official `GET /user/balance` → `UsageSnapshotV1` |
| `bogda/tests/budget/test_deepseek_balance.py` | Fail-closed CNY client; secret-safe errors |
| `docs/reports/2026-08-30-bogda-stage-e-start.md` | Owner auth, caps, env names, what is not live yet |

## Task 1: Durable SQLite ledger (DEF-05 slice)

**Files:** `tests/budget/test_durable_ledger.py`, `src/bogda/budget/durable_ledger.py`, `__init__.py`

- [x] Write failing tests: reopen sees ACTIVE reservation; second opener cannot reserve; revision CAS; release/reconcile parity with process-local errors.
- [x] Run pytest on that file; confirm ImportError/fail.
- [x] Implement `SqliteBudgetLedger(path)` with `BEGIN IMMEDIATE`, Decimal as strings, aware UTC timestamps.
- [x] Re-run tests green. Do not wire it into Prefect yet.

## Task 2: Paid-call service can take a durable ledger

**Files:** `tests/model_runtime/test_paid_call_service.py`

- [x] `PaidModelCallService` already takes `BudgetAdmissionService`/`BudgetLedger`. Added `test_finished_call_reconciles_on_sqlite_ledger_and_survives_reopen` with fake executor (no network).
- [x] No live provider.

## Task 3: Official DeepSeek balance client (DEF-01)

Owner 2026-08-30: admission reads DeepSeek `GET /user/balance`, not walnutpi `GET /api/dashboard`. Base URL is public `https://api.deepseek.com` (does not change on 2026-09-08 school cutover; campus may still block outbound HTTPS).

- [x] TDD `DeepSeekBalanceClient`: Bearer `DEEPSEEK_API_KEY`, pick CNY from `balance_infos`, `is_available=false` / USD-only / non-string totals fail closed, errors never include the key.
- [x] Document env names (no values) in the Stage E start report.
- [x] Live `GET /user/balance` from this Windows laptop (2026-08-30): CNY available, snapshot `up`. Key from dsh credentials store (not User env). Never printed.
- [ ] 3101 real profile still not wired.

## Task 4: Constrained dsh smoke (DEF-02)

Owner 2026-08-30: test spend **≤ 10 CNY** needs no extra ask.

- [x] Local Flash then Pro, `dsh --profile headless --patch config/dsh-patches/{flash,pro}.yml`, prompt “reply pong”. Both stdout `pong`. Not on RK3528 `pi-service`.
- [x] Windows: `SubprocessCommandRunner` now `shutil.which` so `dsh.cmd` resolves (bare `dsh` FileNotFoundError).
- [x] Gap: dsh does **not** write Bogda `attempt_dir/usage.json`. Adapter correctly returns `usage_unknown`. Account balance still `41.81` (delta `0.00`); conservative catalog charge for both calls `0.084` CNY, under the 10 CNY test cap.
- [ ] Exact provider cost receipt still missing; do not treat this smoke as DEF-02 closed.

## Task 5: Prefect suspend/resume (DEF-03) — later

- [ ] Local or post-trial RK3528 only. Not on the live 24h health worker during `20260830T034154Z`.

## Task 6: Artifact retention policy (DEF-13) — later

- [ ] Explicit cleanup command; do not auto-delete referenced receipts.
