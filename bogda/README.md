# Bogda

Bogda is the Prefect-based successor to Research Orchestra. This directory is independent from orchestra/ and currently implements only the local vertical slice.

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

## Pi shadow operations

The fixed Pi deployment inventory is in [deploy/pi/manifest.toml](deploy/pi/manifest.toml). Future deployment, acceptance, and rollback are gated by the [Pi shadow operations runbook](docs/pi-shadow-runbook.md); local checks do not authorize a Pi install.

## Deferred

- Actual Pi deployment and 72-hour acceptance
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
