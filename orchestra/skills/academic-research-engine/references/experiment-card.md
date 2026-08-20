# Experiment Registry

## Heart of the engine

Design + register + ingest artifacts. **Default: do not run GPU jobs for the user.**

## Card location

`.research/experiments/EXP-NNN/card.md` ← `templates/experiment-card.md`

## Required content

- Bind `H-*` (+ optional future `Ci`)
- Dataset, baselines, metrics, ablations, compute budget, seeds
- **Success criteria / failure criteria frozen before run**
- Status: `designed` → `running` → `completed` | `aborted`

## Validate

```bash
py -3 academic-research-engine/scripts/validate_experiment_card.py .research/experiments/EXP-001/card.md
```

## Ingest

```bash
py -3 academic-research-engine/scripts/ingest_run.py path/to/metrics.json \
  --research-root .research \
  --paper-dir {paper_dir} \
  --open-neg-on-fail
```

`metrics.json` must conform to `academic-shared/research/metrics.schema.json`.

## Failure loops (M4)

On fail, set `failure_loop` on the card:

| Loop | Meaning | Also |
|------|---------|------|
| `tune` | hyperparams / seeds / epochs | keep H |
| `redesign` | protocol / data / baseline change | keep H, new EXP version or child EXP |
| `rehypothesis` | H wrong | open NEG + RQ changelog |

Do **not** silently rewrite success criteria after seeing results.

## Tournament mode (optional)

If `program.yaml` `tournament.enabled`:

- Cap parallel H by `max_parallel_hypotheses`
- Each H needs EXP card with budget + pre-registered criteria
- Abort when compute budget exhausted
- Still human-executed unless `compute_budget.mode: ci_cpu`

## CI / CPU optional runner note

`ci_cpu` may document a small CPU job script for the user/CI to run. **No default GPU runner** ships with this skill.
