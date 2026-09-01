# Bogda

Bogda is the Prefect-based successor to Research Orchestra. This directory is independent from orchestra/. The local vertical slice still lives here; **production Prefect (control plane + `pi-service` worker) runs on RK3528**, not the retired Pi 4B.

## Production host (2026-09-02)

| 项 | 值 |
|---|---|
| 机器 | RK3528（hostname `rk3528`，Armbian / aarch64） |
| SSH | 优先 Tailscale `100.78.158.80` / `rk3528`；直连 `10.77.0.1` 可能 host key 失败 |
| Prefect UI / API | `http://10.77.0.1:4200`；tailnet `http://100.78.158.80:4200` |
| 数据 | `/mnt/nas/.bogda`（西数 250G，UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f`，LABEL `nas-data`） |
| 程序 | `/opt/bogda` + `/opt/bogda/.venv`；units 仍用 `deploy/pi/` 清单 |
| 工作池名 | **`pi-service`**（冻结名：控制面轻任务池，与树莓派无关；改名要动 Prefect 池、unit、`EXPECTED_VALUES`、盒子 `daemon-reload`） |
| Gate 6 | **通过**（2026-08-31，trial `20260830T154019Z`） |
| Gate 7 | **S1/S2 影子通过**（2026-09-01）。不是 3100 切换；生产科研仍禁 `pi-service` |

Do not treat Pi 4B (`192.168.0.250` / Tailscale `liuxfs`) as a scheduler. Early Gate 6 trial reports under `docs/reports/2026-08-27-bogda-pi-gate6-*` are historical. Failure-round restore notes: [`docs/reports/2026-08-30-bogda-rk3528-prefect-restore.md`](../docs/reports/2026-08-30-bogda-rk3528-prefect-restore.md). Final: [`docs/reports/2026-08-31-bogda-rk3528-gate6-final-acceptance.md`](../docs/reports/2026-08-31-bogda-rk3528-gate6-final-acceptance.md).

## Who owns what (do not mix)

| 今晚坏了什么 | 改哪边 | 不要改 |
|---|---|---|
| 雷达 / exam-watch / 任务队列 / 3100 留言 | `orchestra/`，SSH 盒子上 `orchestra-*` timer | Prefect unit、`pi-service` |
| Prefect UI、worker、`/mnt/nas/.bogda` | RK3528 `:4200`，`bogda-prefect-*` / `bogda-pi-worker` | Orchestra broker 数据根 |
| 3101 影子控制台 | `bogda-console/`，默认 mock / real-readonly | 未授权不接真 Prefect 写入 |

`deploy/pi/` 路径名是有意冻结，不是「还跑在树莓派上」。

## Requirements

- Python 3.11-3.13
- uv

Docker, CUDA, Pi deployment, WoL, Windows power control, and the 3100 console are not required for this slice.

## Install

~~~powershell
Set-Location D:\pythonProject\bogda
uv sync --python 3.11 --extra dev
~~~

## Test

~~~powershell
uv run --python 3.11 pytest -m "not integration" -v
uv run --python 3.11 pytest -m integration -v
~~~

## Run against a local Prefect server

Start the server in one terminal:

~~~powershell
uv run --python 3.11 prefect server start --host 127.0.0.1
~~~

In a second terminal:

~~~powershell
$env:PREFECT_API_URL = "http://127.0.0.1:4200/api"
uv run --python 3.11 bogda demo
~~~

The demo prints a RunResult. Use its run_id to query or review it:

~~~powershell
uv run --python 3.11 bogda result RUN_ID
uv run --python 3.11 bogda review RUN_ID accepted --summary "human accepted"
~~~

Prefect Completed means the command ran and required artifacts exist. Scientific acceptance is stored separately and starts as unreviewed.

## Current scope

Implemented: local shell flow, attempt directories, required artifact checks, versioned RunResult artifacts, separate scientific review status, and the Phase C paid-model runtime. The Phase C acceptance is local and fake-only; it does not claim Gate 6/7 or production readiness.

## Intelligent collaboration contracts

- `autonomy_mode` controls authority.
- `intent` controls cognitive behavior: execute, explore, decide, audit, or brief.
- `model_tier` controls reasoning capacity, never permissions.
- `executor` selects the adapter.
- Paid dsh requests carry a request-bound `RunBudgetEnvelope` snapshot; money uses `Decimal` values and JSON decimal strings. “Request-bound” means the resolved values are persisted with the request, not that the Pydantic object is immutable.
- Legacy Orchestra cards enter only through `bogda.compat` and become Bogda `JobRequest` objects; Bogda does not import the Orchestra runtime.
- `RunEventV1` is the versioned structured-log contract. Model-call events pair on `call_id`; ordinary events may carry prompt hashes/artifact references and never store full prompts, responses, credentials, or authorization headers.

- Core schema-v1 entry points are exported from `bogda.contracts`: `JobRequest`, `RunBudgetEnvelope`, `SchedulePolicy`, `RunEventV1`, `TaskIntent`, `ModelTier`, and `ExecutorKind`. Supporting public enums include `PricePreference`, `BudgetSource`, and `RunEventType`.
- Research worker freeze (`RunnerPacket` + `admit_runner_packet`): git+commit / staged / inbox only; `pi-service` rejects GPU/research `task_type`. Not wired to live Prefect.

## Phase B budget kernel (accepted locally)

Phase B is a provider-neutral, fail-closed kernel. The module ownership and public extension points are deliberately narrow:

- `bogda/contracts`: versioned `RunBudgetEnvelope`, `JobRequest`, and `RunEventV1` contracts.
- `bogda/budget/pricing.py`: versioned `PricingCatalogV1`, Beijing peak-window lookup, and Decimal token pricing.
- `bogda/budget/usage.py`: `UsagePort`, `UsageSnapshotV1`, freshness checks, and the walnutpi `UsageMonitorClient` (eink cache only).
- `bogda/budget/deepseek_balance.py`: official DeepSeek `GET /user/balance` adapter for admission.
- `bogda/budget/estimation.py`: `TokenWorkload`, `HistoricalUsageProfile`, and `WorkloadEstimator`.
- `bogda/budget/guard.py`: deterministic `BudgetGuard` decisions; it reads coherent ledger facts but does not mutate the ledger.
- `bogda/budget/ledger.py`: `BudgetLedger` and process-local `SingleFlightBudgetLedger`; the revision boundary is the replacement point for a durable atomic ledger.
- `bogda/budget/durable_ledger.py`: file-backed `SqliteBudgetLedger` (Stage E; not yet the Prefect worker default).
- `bogda/budget/service.py`: `BudgetAdmissionService` orchestration, reservation compensation, and terminal release/reconciliation.
- `bogda/events/jsonl.py`: caller-selected `JsonlRunEventSink`; every appended line is validated as `RunEventV1`.

Admission balance is official `GET https://api.deepseek.com/user/balance` with `Authorization: Bearer $DEEPSEEK_API_KEY` (env only; never logged). Amounts are decimal strings; Bogda selects the CNY row. `observed_at` is the local clock at a successful response. The walnutpi usage-monitor still polls the same URL every 60s for the eink panel (`GET {monitor}/api/dashboard` + `X-Monitor-Token`); that path is not Bogda's admission source.

The accepted catalog is `deepseek-cn-2026-08-28`, reviewed by `2026-09-28`, in `Asia/Shanghai`: weekdays `09:00–12:00` and `14:00–18:00` are peak, with end boundaries off-peak. To update it, re-check the official price source, create a new versioned catalog with effective/review timestamps and source note, keep existing envelopes pinned to their original version, update accepted-version tests and maintainer docs, then rerun the full compatibility and acceptance suites. A catalog past `review_by` fails closed.

Dynamic estimates use total workload tokens across all expected calls (not per-call tokens):

```text
expected_cost = hit_tokens / 1_000_000 * hit_price
              + miss_tokens / 1_000_000 * miss_price
              + output_tokens / 1_000_000 * output_price
authorized_ceiling = max(expected_cost * contingency_factor, historical_p90_cost)
                    + (expected_cost / expected_calls * allowed_retries)
```

Without verifiable cache evidence, input is conservatively treated as cache-miss. A verified cache-hit ratio may reduce the effective miss partition; cache savings never become a completion prerequisite. Historical p90 and retry reserve add headroom, so the ceiling is workload- and risk-based rather than a fixed small cap. Runtime is used to determine a conservative peak/off-peak price window, not billed as wall-clock time.

New paid admissions require a fresh successful snapshot no older than 120 seconds. Missing, malformed, unauthorized, wrong-currency, unavailable, future-skewed, or stale data fails closed. `stale_usage_snapshot`, `usage_unavailable`, `insufficient_balance`, `budget_ceiling_exceeded`, and `reservation_conflict` are distinct decisions and distinct event facts; callers must not collapse them into one generic pause state.

`BudgetAdmissionService.admit(run_id, intent, envelope, reservation_cny=None)` evaluates the same frozen `RunBudgetEnvelope` and reserves atomically using the ledger revision. `release(reservation_id, *, intent, requested_tier, pricing_version)` and `reconcile(reservation_id, actual_cost_cny, *, intent, requested_tier, pricing_version)` close the reservation. The current single-flight ledger and its facts/revision are process-local and permit one active paid reservation per process. A future concurrent implementation must provide durable atomic reserve/release semantics; reading balance and then reserving independently is insufficient.

Event storage is caller-selected, for example `JsonlRunEventSink(Path("events.jsonl"))`. The sink uses a process-local lock, append mode, flush/fsync, exact validated lines, and a streaming SHA-256 fingerprint of the file to detect same-size in-place changes that metadata alone can miss. The fingerprint is recalculated before each append in fixed 64 KiB chunks, so append admission is O(n) in the current log size and adds a full-file read; a durable high-throughput/cross-process sink remains Phase C/E work. The check/hash/write sequence is not an OS transaction: an external same-size mutation racing during that sequence can still evade detection. It does not provide inter-process locking or durable cross-process exactly-once delivery; service replay/idempotence tracking is also process-local. No production writer is wired by Phase B.

Recovery is intentionally explicit and local:

```powershell
Set-Location D:\pythonProject\.worktrees\bogda-budget-kernel\bogda
uv run --extra dev --python 3.11 pytest tests/integration/test_budget_kernel.py -q
git status --short --branch
```

On stale or insufficient balance, preserve the artifacts and event log, obtain a new monitor snapshot, and re-run admission against the original envelope. Recovery may admit only if that unchanged envelope now fits; it never expands the ceiling automatically. If a model call later has unknown usage, Phase C must reconcile before retrying.

Phase C consumes the existing `JobRequest` fields `intent`, `model_tier`, `budget`, `schedule_policy`, and `executor`, and calls the admission boundary above before a paid dsh call. The local Phase C slice adds the dsh adapter, model routing, prompt archive, actual usage reconciliation, and Prefect pause/resume wiring without changing the envelope semantics. Real provider/deployment wiring remains deferred as documented below.

Phase B acceptance used fake usage providers and local JSONL only. It did not run dsh, archive prompts, wire Prefect pause/resume, add frontend windows or switches, deploy, call a live API, change systemd/Prefect/device state, or mutate production data.

## Phase C paid-model runtime (accepted locally)

The runtime keeps policy, persistence, execution, budget admission, and Prefect orchestration separate:

- `bogda.model_runtime.contracts` owns `ModelCallRequest`, `ModelCallResult`, `DshTokenUsageV1`, and the provider-neutral execution, receipt, and archive ports.
- `bogda.model_runtime.archive` owns `FilePromptArchive`, which writes `{archive_root}/{run_id}/{call_id}.prompt.md` as a UTF-8 research artifact and returns its SHA-256 reference.
- `bogda.model_runtime.routing` owns the frozen Flash/Pro policy. `auto` consumes the concrete tier already frozen in `RunBudgetEnvelope`; `decide` and `audit` never silently downgrade, while an explicit frozen Flash fallback is limited to `execute`, `brief`, and `explore`.
- `bogda.model_runtime.dsh` owns the concrete `dsh --profile headless --patch ... <prompt>` adapter and the optional `attempt_dir/usage.json` receipt. Its Bogda-owned overlays are `config/dsh-patches/flash.yml` and `pro.yml`; stdout and bounded stderr are written to the attempt directory.
- `bogda.model_runtime.service` owns the one-call state machine and event-safe reservation lifecycle. It uses the Phase B `BudgetAdmissionService` and emits `RunEventV1` through the caller-selected sink.
- `bogda.flows.paid_model_call` is the thin Prefect boundary. It uses `suspend_flow_run` for recoverable budget pauses and re-evaluates the same parsed request after resume.

For an admitted call, the observable event order is `route_selected` (or `tier_downgraded`) → prompt archive → `budget_snapshot` → `budget_reserved` → `model_call_started` → `model_call_finished` or `model_call_usage_unknown` → `budget_released` (the last event carries reconciliation facts when applicable). A Pro-required route emits `tier_upgrade_requested` before any archive or reservation. A budget pause emits `budget_paused`; a real Prefect resume is recorded as `budget_resumed` before the unchanged request is evaluated again. Ordinary events carry only prompt hashes/artifact paths and usage references, never full prompts, model output, credentials, or authorization headers.

If a call may have started but usage is absent, the result is `usage_unknown`: the reservation remains active and the same `run_id`/`call_id` is blocked with `reconciliation_required`. It is not zero usage and must be manually reconciled before retry. `not_started` is the separate safe path that releases its reservation. The current `SingleFlightBudgetLedger`, paid-call claim, terminal-event delivery tracking, and JSONL sink are process-local; they do not provide cross-process exactly-once recovery.

Local recovery and verification use the frozen request and fake ports:

~~~powershell
Set-Location D:\pythonProject\.worktrees\bogda-paid-model-runtime\bogda
uv run --extra dev --python 3.11 pytest tests/integration/test_paid_model_runtime.py -q
uv run --extra dev --python 3.11 pytest --import-mode=importlib tests/integration tests/flows tests/model_runtime tests/budget tests/events tests/contracts -q
~~~

The real Prefect boundary additionally requires a registered deployment, a worker able to resume suspended runs, durable result/event/artifact storage, and a fresh usage/balance source. Those prerequisites are intentionally not configured or exercised here.

## Phase D/E and Gate 6 handoff

Stage D owns the owner-facing decision center and runtime windows: requested/effective tier, budget and price window, pause reason, recovery action, prompt/artifact references, and the non-disableable safety constraints. Stage E owns read-only usage wiring, constrained dsh/DeepSeek smoke, Prefect deployment/resume verification, durable accounting/outbox work, runtime artifact lifecycle, and production operations. Gate 6 read-only closeout may proceed in parallel with Stage D/E; state-changing Stage E and cutover actions wait for owner-approved prerequisites, shadow/production checks, and rollback evidence. The Phase C handoff is documented in [`docs/reports/2026-08-29-bogda-paid-model-runtime-acceptance.md`](../docs/reports/2026-08-29-bogda-paid-model-runtime-acceptance.md) and the required follow-up register in [`docs/reports/2026-08-29-bogda-deferred-work-register.md`](../docs/reports/2026-08-29-bogda-deferred-work-register.md).

Explicit exclusions for this phase: no live dsh or DeepSeek call, no deployment or Prefect server mutation, no frontend, no production writer, no secrets or production credentials, no cross-process exactly-once ledger/outbox, no 3100/3101 cutover, no Gate 6/7 declaration, and no push, merge, or cleanup.

## Pi-bundle operations

The fixed ARM64 deployment inventory is in [deploy/pi/manifest.toml](deploy/pi/manifest.toml) (paths and unit names stay Pi-compatible). Day-to-day ops on RK3528: [docs/pi-shadow-runbook.md](docs/pi-shadow-runbook.md) (banner: current host). After a USB drop, server/worker follow `mnt-nas.mount`; health timers do not. Local pytest does not authorize a reinstall. Hot-patching two unit files must not go through `install.sh --install`.

## Deferred

- Gate 6 **已通过**（2026-08-31）；Gate 7 S1/S2 影子 **已通过**。生产科研仍禁 `pi-service`
- Wake Bridge/WoL（宿舍塔停购；第二台笔记本暂代 runner，仍未接线）
- Laptop `dorm-x86` pool（控制台契约有名；真机未接）
- Windows Power Agent/game mode
- Task migration
- CPU/GPU worker and higher concurrency
- SLC/pSLC purchase
- 3100 cutover
- CLI error polish
- Streaming logs
- Review, merge, and regression of `bogda-console`
