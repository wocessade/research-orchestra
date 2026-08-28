# Bogda Contract Foundation Acceptance

Date: 2026-08-28

Branch: `codex/bogda-contract-foundation`
Scope: Phase A contract foundation only

## Outcome

Phase A is accepted for planning Phase B. It does not authorize live DeepSeek usage, balance API calls, dsh model execution, production Prefect writes, Console writes, RK3528 changes, systemd changes, pricing enforcement, reservations, or production gate transitions.

## Task commits

| Task | Commit(s) | Result |
|---|---|---|
| 1 — task axes and schedule policy | `8d1dc62`, `e1f764f` | Approved after fail-closed fix |
| 2 — Decimal budget contracts | `696cc60` | Approved |
| 3 — versioned `JobRequest` | `c743757`, `25e012c` | Approved after strict-version/budget fix |
| 4 — Orchestra compatibility | `173daaf`, `f430969` | Approved after structural/path-safety fix |
| 5 — structured run events | `1bdb165` | Approved |
| 6 — documentation and acceptance | Commit containing this report, subject `docs(bogda): accept contract foundation` | Self-referential commit SHA is recorded by Git and the final handoff ledger |

## Public schema-v1 contracts

- `JobRequest`
- `RunBudgetEnvelope`
- `SchedulePolicy`
- `RunEventV1`
- `TaskIntent`
- `ModelTier`
- `ExecutorKind`
- `PricePreference`
- `BudgetSource`
- `RunEventType`

`autonomy_mode`, `intent`, `model_tier`, and `executor` are orthogonal. A Pro tier increases reasoning capacity but never grants authority, tools, or permissions. Existing shell requests retain execute + auto + shell + no-budget defaults. Dsh requests require a budget; explicit Flash/Pro must match the budget tier.

## Legacy Orchestra mapping

| Orchestra card | Bogda request |
|---|---|
| `mode` | `intent` |
| omitted `model` | `model_tier=auto` |
| `model=flash\|pro` | matching `model_tier` |
| `executor` | `executor` |
| `required_outputs` | `expected_artifacts` |
| body and remaining execution metadata | `parameters["legacy_orchestra"]` |

The adapter is one-way. `bogda.compat` contains a structurally independent local parser and imports no `orchestra` package, Broker database, scan loop, executor, or runtime. It rejects unknown/duplicate fields, unsafe POSIX and Windows paths, malformed CSV, invalid dependencies, and inconsistent output contracts.

## Money and logging invariants

- CNY values use `Decimal`; float input is rejected at migrated boundaries.
- JSON monetary fields serialize as decimal strings, preserving values such as `"5.00"`.
- `RunEventV1` is strict schema v1 with timezone-aware timestamps.
- Model-call start/finish events require `call_id`; route and tier-change events require requested/effective tiers.
- Ordinary event records reject arbitrary fields and secret-bearing prompt/response/header/API-key/authorization fields. Full prompts and outputs belong in controlled artifacts referenced by hash/ref.

## Verification evidence

From `bogda/`:

```powershell
uv run --python 3.11 pytest tests/contracts -q
# 54 passed in 0.19s

uv run --python 3.11 pytest -m "not integration" -q
# 242 passed, 10 skipped, 1 deselected in 6.47s

uv run --python 3.11 pytest -m integration -v
# 1 passed, 252 deselected in 20.26s
```

From `orchestra/broker/`, using the Bogda Python 3.11 virtual environment because the Windows `python` alias is unavailable:

```powershell
& 'D:\pythonProject\.worktrees\bogda-contract-foundation\bogda\.venv\Scripts\python.exe' -m unittest tests.test_taskfile -v
# Ran 25 tests — OK
```

Repository hygiene:

```powershell
git diff --check
git status --short
```

No whitespace errors were present and only intended Phase-A files were committed. The user-owned untracked `docs/reports/2026-08-28-bogda-maintainability-for-sol.md` in the main checkout was not added or modified.

## Production safety confirmation

This work made no writes to RK3528, production Prefect, systemd, production `prefect.db`, `bogda.env`, work pools, Console, production concurrency, or external APIs. The integration suite used only ephemeral local `prefect_test_harness` state and local test artifacts. It did not call DeepSeek or query/consume a live balance.

## Phase B handoff

Phase B may consume these stable signatures:

- `JobRequest`
- `RunBudgetEnvelope`
- `SchedulePolicy`
- `RunEventV1`

The next plan should implement `UsagePort`, a versioned DeepSeek pricing catalog, workload estimation, `BudgetGuard`, and reservation/release semantics. It must retain stale-balance fail-closed behavior, peak/off-peak pricing in Asia/Shanghai, workload/runtime-aware budgets, and mandatory structured event emission. Phase B requires a new plan based on these actual interfaces; it is not started by this acceptance.

## Non-blocking hardening backlog

- Reject whitespace-only `call_id` values before the runtime writer is introduced.
- Add per-event smoke tests for the remaining ordinary budget lifecycle event types.
