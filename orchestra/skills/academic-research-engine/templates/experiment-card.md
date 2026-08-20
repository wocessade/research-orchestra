---
id: EXP-001
hypothesis_ids: [H-001]
contribution_id: null         # C1… optional until handoff
rq_id: RQ-001
status: designed              # designed | running | completed | aborted
failure_loop: null            # null | tune | redesign | rehypothesis
tournament_id: null
created: YYYY-MM-DD
updated: YYYY-MM-DD
compute_budget:
  kind: cpu                   # cpu | gpu | mixed | none
  estimate: "2 CPU-hours"
  seeds: [0, 1, 2]
---

# EXP-001 — Title

## Bound hypothesis / contribution

- H: H-001
- Future Ci: (none | C1)

## Design

| Field | Value |
|-------|-------|
| Dataset / corpus | … |
| Baseline(s) | … |
| Method under test | … |
| Metrics | … |
| Ablations | … |
| Controls | … |

## Success criteria (freeze before run)

1. …

## Failure criteria (freeze before run)

1. …

## Run log

| run_id | status | metrics path | meets_success | notes |
|--------|--------|--------------|---------------|-------|
| | | | | |

## Failure-loop notes (M4)

If failed: choose `tune` (hyperparams) → `redesign` (protocol) → `rehypothesis` (open NEG + RQ changelog). Do not post-hoc rewrite success criteria.

## Artifacts

- Code commit: …
- Config: …
