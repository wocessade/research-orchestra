# Writing Handoff

## Goal

Materialize writing-side P0/P1 artifacts from **verified** research evidence only.

## Command

```bash
py -3 academic-research-engine/scripts/handoff_sync.py \
  --research-root .research \
  --paper-dir {paper_dir} \
  --module academic-journal
```

Without verified runs, sync exits non-zero unless `--allow-empty-verified` (scaffolds only).

## Outputs

| Artifact | Rule |
|----------|------|
| `.research/handoff/ready_for_writing.md` | verified table + forbidden claims |
| `.paper/confirmed_contribution.md` | seed only; `user_confirmed` stays false until user OK |
| `.paper/contribution_experiment_map.md` | seed / update |
| `.paper/issues.csv` | verified rows get artifacts |
| `.paper/citation_support_bank.md` | seed from reads pointers |

## Hard rules

1. No `planned` strong numbers in handoff package.
2. Suggest `entry_point` + `writingFormat`; do not draft Results prose here.
3. Journal/thesis: if `.research/handoff` exists, **preload** at S1/S3 (and T1).

## After handoff

Continue in `academic-journal` or `academic-thesis` with contribution gate + issues contract.
