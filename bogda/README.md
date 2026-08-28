# Bogda

Bogda is the Prefect-based successor to Research Orchestra. This directory is independent from orchestra/. The local vertical slice still lives here; **production Prefect (control plane + `pi-service` worker) runs on RK3528**, not the retired Pi 4B.

## Production host (2026-08-28)

| 项 | 值 |
|---|---|
| 机器 | RK3528（hostname `rk3528`，Armbian / aarch64） |
| SSH | `liuxfs@10.77.0.1`（直连 `/30`）；Tailscale `100.78.158.80` |
| Prefect UI / API | `http://10.77.0.1:4200`；tailnet `http://100.78.158.80:4200` |
| 数据 | `/mnt/nas/.bogda`（西数 250G，UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f`，LABEL `nas-data`） |
| 程序 | `/opt/bogda` + `/opt/bogda/.venv`；units 仍用 `deploy/pi/` 清单 |
| 工作池名 | **`pi-service`**（不改名；host 已换） |

Do not treat Pi 4B (`192.168.0.250` / Tailscale `liuxfs`) as a scheduler. Gate trial reports under `docs/reports/2026-08-27-bogda-pi-gate6-*` are historical.

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

Implemented: local shell flow, attempt directories, required artifact checks, versioned RunResult artifacts, and separate scientific review status.

## Intelligent collaboration contracts

- `autonomy_mode` controls authority.
- `intent` controls cognitive behavior: execute, explore, decide, audit, or brief.
- `model_tier` controls reasoning capacity, never permissions.
- `executor` selects the adapter.
- Paid dsh requests carry a request-bound `RunBudgetEnvelope` snapshot; money uses `Decimal` values and JSON decimal strings. “Request-bound” means the resolved values are persisted with the request, not that the Pydantic object is immutable.
- Legacy Orchestra cards enter only through `bogda.compat` and become Bogda `JobRequest` objects; Bogda does not import the Orchestra runtime.
- `RunEventV1` is the versioned structured-log contract. Model-call events pair on `call_id`; ordinary events may carry prompt hashes/artifact references and never store full prompts, responses, credentials, or authorization headers.

Core schema-v1 entry points are exported from `bogda.contracts`: `JobRequest`, `RunBudgetEnvelope`, `SchedulePolicy`, `RunEventV1`, `TaskIntent`, `ModelTier`, and `ExecutorKind`. Supporting public enums include `PricePreference`, `BudgetSource`, and `RunEventType`.

## Pi-bundle operations

The fixed ARM64 deployment inventory is in [deploy/pi/manifest.toml](deploy/pi/manifest.toml) (paths and unit names stay Pi-compatible). Day-to-day ops on RK3528: [docs/pi-shadow-runbook.md](docs/pi-shadow-runbook.md) (banner: current host). Local pytest does not authorize a reinstall.

## Deferred

- Gate 7 and remaining 24-hour acceptance on RK3528 (4B Gate 6 did not pass; owner shortened the window from 72h on 2026-08-28)
- Wake Bridge/WoL
- Laptop `dorm-x86`
- Windows Power Agent/game mode
- Task migration
- CPU/GPU worker and higher concurrency
- SLC/pSLC purchase
- 3100 cutover
- CLI error polish
- Streaming logs
- Review, merge, and regression of `bogda-console`
