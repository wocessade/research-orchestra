# Issues Contract (P1)

Lightweight execution contract inspired by latex-paper-skills (not the full 18-column sheet).

## Path

`{paper_dir}/.paper/issues.csv` — copy from `issues.template.csv`.

## Columns

| Column | Meaning |
|--------|---------|
| issue_id | `ISS-NNN` |
| section | Manuscript section id (e.g. `4.1`, `method`) |
| claim_id | Ledger id `CLM-…` |
| contribution_id | `C1`… from confirmed_contribution |
| evidence_status | `planned` \| `placeholder` \| `verified` |
| artifact_path | CSV/log/figure script; empty if planned |
| notes | Short note |
| done | `true` when prose+evidence for this issue are finished |

## Rules

1. Create issues.csv at S3→S4 transition (after contribution gate). Seed one row per major claim in the outline.
2. **Results-backfill gate:** do not write *strong* result sentences for rows with `evidence_status!=verified`. Use hedging or `[CLAIM NEEDS EVIDENCE]`. See `results-backfill.md`.
3. Before Q4: every Results issue tied to a `Ci` is either `verified` or explicitly deferred in notes (user-waived).
4. Validate:

```bash
python ../academic-shared/issues/validate_issues.py {paper_dir}/.paper/issues.csv
```

5. Join keys: `claim_id` ↔ evidence ledger; `contribution_id` ↔ contribution_experiment_map.
