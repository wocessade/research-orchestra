# Results Backfill Gate (P1)

When experiments finish after a draft with placeholders:

## Procedure

1. Open `.paper/issues.csv` and `.paper/contribution_experiment_map.md`.
2. For each row with new artifacts:
   - Set `evidence_status=verified`
   - Fill `artifact_path`
   - Update map Takeaway with real numbers (no invention)
3. Patch Results `.tex`/prose: replace placeholders / soft hedges with verified claims only where status is `verified`.
4. Re-run `verify_paper.py` (latex) and update claim ledger `audit_status`.
5. Only then rewrite **Final Intro / Abstract** numbers.

## Hard rule

`evidence_status` in {planned, placeholder} → no definitive superiority / SOTA / exact % claims in body.

## Trigger stages

- Journal: late S4 / pre-Q4 / after S5 figure refresh
- Thesis: T4 empirical chapters
- Standalone latex: before framing sections
