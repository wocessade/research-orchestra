# Negative Results Ledger

## Purpose

Honest registry of failed, null, or falsified predictions — fuel for limitations and for **forbidden hard-claim** lists at handoff.

## Template

`templates/negative.md` → `.research/negatives/NEG-NNN.md`

## Fields

- Prediction vs actual
- Likely causes (tentative)
- Impact: `weakens` | `falsifies` | `narrows_scope` | `inconclusive`
- `public_in_paper`: limitation / omit / dedicated null section

## Writing alignment

- Matches P1 `null_result_aware` / results-backfill: do not prop Ci with failed EXP.
- Handoff must list forbidden hard-claims from open NEGs.

## Auto-open

`ingest_run.py --open-neg-on-fail` creates a stub NEG when success criteria fail.
