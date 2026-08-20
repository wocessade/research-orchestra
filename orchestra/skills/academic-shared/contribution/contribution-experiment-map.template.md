# Contribution ↔ Experiment / Section Map

> Path default: `{paper_dir}/.paper/contribution_experiment_map.md`
> Required before locking Results prose (S4 / T4). Join with claim ledger via `contribution_id`.

| Contribution ID | Experiment / ablation / theorem | Results subsection | Figure / Table | Takeaway (one sentence) | Evidence status |
|-----------------|----------------------------------|--------------------|-------------|-------------------------|-----------------|
| C1 | … | §4.1 | Fig.1 / Tab.1 | … | planned |
| C2 | … | §4.2 | Fig.2 | … | planned |

Evidence status: `planned` | `placeholder` | `verified`

## Rules

1. Every `Ci` in `confirmed_contribution.md` appears in ≥1 row.
2. Results paragraphs must end with a **Takeaway** that maps to a row.
3. Do not write strong conclusion sentences for rows still `planned`/`placeholder` (use hedging or `[CLAIM NEEDS EVIDENCE]`).
4. After experiments finish → set `verified` and run results-backfill before Final Intro / Abstract.
