# RQ / Hypothesis Store

## Templates

- `templates/rq.md` → `.research/rq/RQ-NNN.md`
- `templates/hypothesis.md` → `.research/hypotheses/H-NNN.md`

## RQ requirements

- One falsifiable sentence
- Scope + non-goals
- Version changelog
- Links to reads / H / EXP / NEG

## Hypothesis card

- Prediction, dependencies, required evidence type
- Draft success/failure (frozen on EXP card)

## Gate before EXP

1. User confirms an **active** RQ (`program.yaml` `active_rq`).
2. At least one `H-*` in `active` or `candidate` linked to that RQ.
3. Pre-writing stage may have RQ without `Ci`; contribution gate merges later at handoff/S3/T1.

## Deep read implication

After nature-reader, fill `templates/read-bridge.md`:

`supports` | `threatens` | `orthogonal`

- `threatens` → propose NEG or RQ version bump (never auto-rewrite contribution prose).

## Grill / stress-test (optional)

For explorer / high-stakes H: optionally invoke `grill-me` skill to pressure-test assumptions before EXP.
