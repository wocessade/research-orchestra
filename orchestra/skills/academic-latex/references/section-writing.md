# Section writing (LaTeX)

## Core-First order

Default: Methods -> Results -> Discussion -> Related Work / Intro -> Abstract -> Title.

Author may override (e.g., data-ready Results first). Follow author direction.

## Per-section checklist

1. Re-read section job (style-de-ai.md).
2. Open only this section's evidence files.
3. Draft in `.tex` with real `\cite{}` / `\ref{}` as you go.
4. Update claim ledger + glossary.
5. `verify_paper.py` -> fix hard fails.
6. Compile -> inspect PDF pages.

## Findings-first Results paragraphs

Pattern: main pattern -> selective evidence (table/fig) -> mechanism or bounded synthesis.
Avoid figure-touring without a claim ("Figure 3 shows the results.").

## Partial manuscript

If academic-journal SP classified sections:

- Complete: do not rewrite
- Partial: fill gaps only; match existing terminology
- Missing/Placeholder: write from ledger + outline

## Stepping mode

When mode=stepping: stop after each subsection for author verdict (pass / minor / redo).

## Contribution gate & CS conference order

Follow `../academic-shared/contribution/contribution-gate.md` and, when applicable,
`../academic-shared/conference/cs-conference-path.md`.

1. Confirmed contributions before drafting body `.tex` sections.
2. Results: findings-first **plus Takeaway** mapped to `Ci` in `.paper/contribution_experiment_map.md`.
3. Draft0 Intro (notes) at outline time; **Final Intro** only after Methods/Results compile with real numbers.
4. Page-limit compression: use the seven cuts in cs-conference-path.md; report word/page delta.

## P1 issues / rewrite / citation bank

- Track section claims in `.paper/issues.csv` (`evidence_status`).
- Strong Results claims only if `verified` (results-backfill.md).
- Major rewrites: rewrite_matrix.md closed-book rows.
- Prefer keys from citation_support_bank.md.
