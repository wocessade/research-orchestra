# Research Engine Schemas (canonical)

Canonical ID and field specs for `academic-research-engine`. Writing skills
(`academic-journal` / `academic-thesis` / `academic-latex`) **consume** these
IDs; they do not invent a parallel namespace.

## ID alignment (P0/P1 — mandatory)

```text
RQ-*  →  H-*  →  EXP-* / NEG-*  →  Ci  →  ISS-*  →  CLM-*
```

| ID | Meaning | Typical path |
|----|---------|--------------|
| `RQ-NNN` | Research question version | `.research/rq/RQ-001.md` |
| `H-NNN` | Hypothesis | `.research/hypotheses/H-001.md` |
| `EXP-NNN` | Experiment card + runs | `.research/experiments/EXP-001/` |
| `NEG-NNN` | Negative / null / falsified | `.research/negatives/NEG-001.md` |
| `Ci` | Confirmed contribution (`C1`…) | `.paper/confirmed_contribution.md` |
| `ISS-NNN` | Writing issue row | `.paper/issues.csv` |
| `CLM-*` | Claim ledger id | evidence ledger / citation bank |
| `S/C/F/T-*` | nature-reader block anchors | `.research/reads/{slug}.md` locator |

Join rules:

1. Every `EXP-*` binds ≥1 active `H-*` (and optionally a future `Ci`).
2. Verified run → may set `issues.csv` `evidence_status=verified` and map row → `verified`.
3. Failed / null result → open `NEG-*`; do **not** invent strong numbers in handoff.
4. `CLM-*` / citation bank `locator` may cite nature-reader `S/C/F/T` ids.
5. Handoff package **must not** contain `planned` strong quantitative claims.

## `.research/` tree

```text
.research/
  program.yaml
  rq/
  hypotheses/
  radar/
    watchlist.yaml
    inbox/
  reads/
  experiments/
    EXP-NNN/
      card.md
      runs/
        {run_id}/
          metrics.json
  negatives/
  handoff/
    ready_for_writing.md
```

## Experiment card (minimum fields)

See engine `templates/experiment-card.md`. Required YAML front-matter keys:

- `id`, `hypothesis_ids`, `status`
- `success_criteria`, `failure_criteria` (pre-registered)
- `compute_budget` (hours / GPU-hours / CPU-only)
- optional: `contribution_id`, `tournament_id`, `failure_loop`

Status machine:

`designed` → `running` → `completed` | `aborted`

Failure loops (M4): `tune` → `redesign` → `rehypothesis` (logged on NEG + RQ changelog).

## Metrics artifact

Each run writes `metrics.json` conforming to `metrics.schema.json` in this folder.

## Handoff hard rules

1. Only `verified` numeric claims may be copied into `.paper/*` as strong claims.
2. NEG ledger entries become "forbidden hard-claims" or limitation seeds.
3. Suggest journal `entry_point` and `writingFormat`; do not draft Results prose here.
