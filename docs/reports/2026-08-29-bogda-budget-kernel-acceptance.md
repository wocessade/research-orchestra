# Bogda Phase B budget-kernel acceptance

Date: 2026-08-29  
Worktree: `D:\pythonProject\.worktrees\bogda-budget-kernel`  
Branch: `codex/bogda-budget-kernel`  
Fork point: `08e6d35fdfc8daf1a0fcb02367779d8c8a102d99`  
Acceptance baseline/current HEAD before Task 6: `0caa27d1642009645d361613b4256eb480d4c838`

## Scope and result

Task 6 was executed, followed by the narrowly scoped JSONL audit fix described below. The authorized integration test contains five scenarios and all five passed: fresh Flash admission and JSONL round-trip; raised stale versus generic unavailable; Pro peak pricing with dynamic p90/retry/contingency ceiling; balance recovery against the same envelope; and deterministic barrier-controlled competing admissions with one winner. The follow-up changes are limited to the JSONL sink, its regression tests, and the maintainer documentation.

The original Task 6 acceptance commit carried this report, test, README, and plan checklist. The narrowly scoped JSONL fix is included in the current `fix(bogda): fingerprint JSONL audit history` commit; its exact SHA is supplied by the final `git rev-parse HEAD` handoff because a commit cannot contain its own hash. The exact Phase B history through the acceptance baseline is:

```text
003ed35ec5a51ceedb9cc8b601ade4f36c5d71d2 docs(bogda): fix Phase B test setup
59b6b9298b4f8c5aae1c748d477980c1b38d31f6 feat(bogda): add versioned DeepSeek pricing catalog
ab44295b022ebcae6d9d77607eeaeb0e7859dd3c fix(bogda): ignore weekends in pricing windows
a49a72d0cf5f697a691c7b5a95825952eef62f43 feat(bogda): add usage monitor read adapter
f67cdf12d912855d70eca640271a770f59f4c6bd fix(bogda): harden usage monitor failures
9a321f1098de4209de8371f6de1f96db28edea5b fix(bogda): classify monitor source before balance
2953246ad955ca70396930c763d583558e4d7c5e feat(bogda): estimate workload aware budgets
0b655e8dbdaf104d82a46a4341855158489ec2a9 fix(bogda): prevent underfunded workload estimates
3f96d39b7da12f7420d909a3570167a41069f0dd fix(bogda): enforce estimate contingency invariant
206fbb707f51f65ce7a4cd46cf5e032ed982d441 feat(bogda): add budget guard and reservation ledger
a30d9c6108e9f6dad864d2879f3f2190aa428a54 fix(bogda): close budget admission race gaps
9dfd19bb5f3cdc28e60bf576a1209e4f9f0244df fix(bogda): stabilize budget decision semantics
73fefc0740d3619451cd0ac5676bf6c08befb62 feat(bogda): persist budget admission events
e622cc85aaf68188fba0d4b0555f36e70f80e48c fix(bogda): make budget event delivery truthful
5a4261e62c0c3f10e913bce048fe3c1f471c11a8 fix(bogda): harden budget event integration
03c6c70c65665832310aa91af1be06ee20acf7c7 fix(bogda): bind budget audit facts
0caa27d1642009645d361613b4256eb480d4c838 fix(bogda): enforce budget event amount axes
```

## Fresh verification evidence

All commands were run from `D:\pythonProject\.worktrees\bogda-budget-kernel\bogda` unless noted:

```text
uv run --extra dev --python 3.11 pytest tests/events/test_jsonl.py -q
14 passed, 1 skipped in 0.31s

20 consecutive runs of the same-size mutation regression
modify_regression_runs=20 failures=0

uv run --extra dev --python 3.11 pytest tests/integration/test_budget_kernel.py -q
5 passed in 0.26s

uv run --extra dev --python 3.11 pytest tests/contracts tests/budget tests/events tests/integration/test_budget_kernel.py -q
262 passed, 1 skipped in 0.72s

uv run --extra dev --python 3.11 pytest -q
455 passed, 11 skipped in 33.39s

D:\pythonProject\.worktrees\bogda-budget-kernel\bogda\.venv\Scripts\python.exe -m unittest tests.test_taskfile -q
Ran 25 tests in 0.064s — OK

git diff --check
exit 0
```

The follow-up fix worktree was clean apart from the three authorized files before commit. The final handoff must re-run `git status --short --branch` and record the resulting clean branch state and exact current HEAD.

## Integration evidence

- Fresh fake usage providers are used for every scenario; no live network is called.
- The Flash scenario constructs `WorkloadEstimate` and a `RunBudgetEnvelope`, preserves the envelope dump across admission, creates exactly one active reservation, and parses both JSONL lines through `RunEventV1`.
- Raised `UsageSnapshotStaleError` produces `stale_usage_snapshot` / `usage_snapshot_not_fresh`; a generic monitor error produces `usage_unavailable` / `usage_monitor_error`. Neither reserves funds.
- The Pro window overlaps Friday 11:30–12:30 Beijing time. The test observes `expected_cost=36`, `contingency_factor=1.60`, `historical_p90_cost=100`, `retry_reserve=36`, and `authorized_ceiling=136.00`; it is not a fixed `5.32` cap.
- Recovery first denies at insufficient balance, then admits after a fresh sufficient fake snapshot while the exact same envelope remains unchanged.
- A `threading.Barrier(2)` synchronizes competing admissions. Exactly one reservation wins, `active_total` equals that reservation, and all four event lines parse as `RunEventV1`.

## JSONL defect and resolution

The first fresh run of the requested relevant regression command reported one failure:

```text
tests/events/test_jsonl.py::test_jsonl_rejects_external_file_changes_between_appends[modify]
Failed: DID NOT RAISE ValueError("changed")
```

The isolated four-case event test then passed, the complete events module passed `12 passed, 1 skipped`, the relevant suite passed `260 passed, 1 skipped`, and the full suite passed `453 passed, 11 skipped`. The behavior was timing-sensitive rather than resolved by Task 6. Root-cause evidence was in the existing implementation: `_file_state()` compared device/inode, size, and `st_mtime_ns`; an in-place same-size mutation could evade that state comparison when the filesystem timestamp did not advance with sufficient resolution.

The follow-up fix extends the expected file state with a streaming SHA-256 digest. Each append compares metadata and recalculates the digest before opening the append handle; the expected state is replaced only after the existing flush+fsync succeeds and the resulting file state is checked. The deterministic regression restores the original mtime after same-size mutations and passes in 20 consecutive iterations. The fixed chunk size is 64 KiB, so the tradeoff is O(n) streaming hashing before every append; this is intentionally local and maintainable, not a general tamper-evident log. The MEDIUM defect is resolved by the follow-up commit `fix(bogda): fingerprint JSONL audit history`; its exact SHA is recorded by the final `git rev-parse HEAD` handoff.

## Maintainer contract and limitations

The public ownership, endpoint mapping, pricing procedure, dynamic formula, 120-second fail-closed semantics, process-local single-flight/revision facts, caller-selected JSONL behavior, recovery commands, and Phase C input signatures are documented in [bogda/README.md](../../bogda/README.md). In short, the monitor boundary is exact `GET /api/dashboard` with optional `X-Monitor-Token`; the DeepSeek key remains inside usage-monitor. Pricing is `deepseek-cn-2026-08-28`, reviewed by `2026-09-28`, with `Asia/Shanghai` weekday peak windows. Existing envelopes remain pinned to their catalog version.

Known limitations are explicit:

- Usage adapter is read-only and this acceptance uses fakes; no live API call occurred.
- The ledger, JSONL lock, and service replay/exactly-once bookkeeping are process-local. Cross-process safety needs a durable atomic ledger/outbox/sink.
- JSONL path is caller-selected and no production writer is wired.
- Phase B does not run dsh, route Flash/Pro, archive prompts, reconcile dsh usage, wire Prefect pause/resume, add frontend windows or switches, deploy, mutate systemd/Prefect/device state, or alter production data.
- Price catalog expiry requires a new reviewed version; runtime is priced conservatively by possible peak overlap, not billed as wall-clock time.
- The same-envelope recovery behavior never expands a ceiling automatically. Unknown usage after a future model call still requires reconciliation before retry.
- JSONL append admission performs an O(n) 64 KiB-chunk SHA-256 pass over the current file. The process-local lock does not coordinate external processes; an external mutation racing after the pre-append fingerprint and before/while the append may evade the check if it preserves identity and size, so this sink is not a cross-process security boundary. A durable high-throughput/cross-process sink remains Phase C/E work.

Phase C must consume `JobRequest`'s `intent`, `model_tier`, `budget`, `schedule_policy`, and `executor`, and use the existing boundaries:

```text
BudgetAdmissionService.admit(
    run_id: str,
    intent: TaskIntent,
    envelope: RunBudgetEnvelope,
    reservation_cny: Decimal | None = None,
) -> BudgetAdmissionResult
BudgetAdmissionService.release(
    reservation_id: str,
    *, intent: TaskIntent, requested_tier: ModelTier, pricing_version: str,
) -> Reservation
BudgetAdmissionService.reconcile(
    reservation_id: str,
    actual_cost_cny: Decimal,
    *, intent: TaskIntent, requested_tier: ModelTier, pricing_version: str,
) -> Reservation
```

## Repository safety checks

```text
rg -n -i '(^|\s)(from|import)\s+(orchestra|usage[_-]?monitor)(\.|\s|$)' bogda/src
No matching orchestra or usage-monitor imports under bogda/src

git -C D:\pythonProject status --short --branch
## main...origin/main [ahead 16]
?? docs/reports/2026-08-28-bogda-maintainability-for-sol.md
```

The main-checkout status was read-only; the user-owned maintainability report was present and untouched. No production or live external state was mutated.
