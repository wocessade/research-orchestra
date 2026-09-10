# Bogda Runner 开工包（本地准入）Implementation Plan

<!-- campus-runner-status:2026-09-10 -->
> 2026-09-10 现状更新：Orchestra/3100 已停用；Y7000 已接入 WSL2、NAS 和 dorm-x86，并发 1，自主 smoke 与 WSL 重启恢复通过。checkpoint key 本地修复已测、尚未部署，DEF-03 未通过现网验收。3101 仍为只读 observer。下文历史设计/操作步骤不代表已经部署；“runner 未到手/未联网/仅雷达停用”等旧状态以[最新交接](../../reports/2026-09-10-bogda-runner-handoff.md)为准。共享 SQLite 和日志发布接线仍待完成。
<!-- /campus-runner-status -->

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode spec §5.3 / §5.7 as a versioned `RunnerPacket` plus `admit_runner_packet`, so a research JobRequest cannot be treated as runnable without frozen git/staged/inbox attachments, a runbook, and a non-`pi-service` pool.

**Architecture:** Keep `JobRequest` extra-forbid and unchanged as the Prefect/payload header. Put the worker-facing freeze in `bogda.contracts.runner_packet`. Admission is a pure function: no Prefect client, no SSH, no dsh. Live `dorm-x86` and 3101 writes stay out.

**Tech Stack:** Python 3.11, pydantic v2, pytest, existing `bogda.contracts`.

## Global Constraints

- Do not declare Gate 6 or Gate 7 passed.
- Do not submit research Flow Runs to RK3528 `pi-service`.
- Do not import `orchestra`.
- Do not print or commit secrets.
- Commit only if the owner asks.
- TDD: failing test before production code.

---

## File map

| File | Role |
|---|---|
| `bogda/tests/contracts/test_runner_packet.py` | Admit matrix: missing commit, `D:\` path, `pi-service` research, happy git |
| `bogda/src/bogda/contracts/runner_packet.py` | `AttachmentRef`, `RunnerPacket`, `AdmitDecision`, `admit_runner_packet` |
| `bogda/src/bogda/contracts/__init__.py` | Export the new types |
| `docs/superpowers/specs/2026-08-30-bogda-runner-dsh-design.md` | Point §5.7 at this module once it exists |

Constants (copy verbatim in code):

- `PI_SERVICE_POOL = "pi-service"`
- `RESEARCH_POOL = "dorm-x86"`
- Research `task_type` values that may not use `pi-service`: `paper_reproduce`, `paper_reproduce_slice`, `research`

---

### Task 1: Admit runner packets locally

**Files:**
- Create: `bogda/tests/contracts/test_runner_packet.py`
- Create: `bogda/src/bogda/contracts/runner_packet.py`
- Modify: `bogda/src/bogda/contracts/__init__.py`

**Interfaces:**
- Consumes: `JobRequest`, `ResourceClass`
- Produces: `admit_runner_packet(request: JobRequest, packet: RunnerPacket) -> AdmitDecision` with `status` in `{admitted, blocked_missing_inputs, pool_forbidden}`

- [x] **Step 1: Write the failing tests** (file contents in `test_runner_packet.py` as implemented this session)

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run --python 3.11 pytest tests/contracts/test_runner_packet.py -v` from `bogda/`

Expected: `ImportError` or collection failure for `bogda.contracts.runner_packet`

- [x] **Step 3: Implement `runner_packet.py` and exports**

- [x] **Step 4: Re-run tests**

Expected: PASS (6 passed). Related suites 358 passed.

- [x] **Step 5: Commit**

Skip unless owner asks.

## Out of this plan

Wake Bridge, `dorm-x86` worker unit, 3101 hosting on RK3528, wiring admit into Prefect worker, live clone of prefix-sliding, `usage.json` bridge.

## Spec coverage

| Spec | Task |
|---|---|
| §5.3 attachments must be runner-resolvable | Task 1 |
| §5.3 reject `D:\` only | Task 1 |
| §5.7 packet minimum | Task 1 (runbook + commands + criteria required on model) |
| Research never `pi-service` | Task 1 |
| A/B live paths | Explicitly out |
