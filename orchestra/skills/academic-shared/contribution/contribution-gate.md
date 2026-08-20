# Contribution Gate (P0)

Inspired by PaperSpine contribution-first and ARS RQ clarification.
Canonical for `academic-journal` / `academic-thesis` / `academic-latex`.

## Hard rule

**No confirmed contribution → no body draft** (S4 Methods/Results/Discussion, T4 core chapters).

Outline (S3) and 开题 (T1) may draft *candidate* contributions, but advancing past Q3 / QT1 requires:

1. File `{paper_dir}/.paper/confirmed_contribution.md` (from template)
2. `user_confirmed: true` in YAML front matter (or explicit user chat confirmation recorded in the file)
3. 1–3 non-vague contribution rows (claim-first: what is new, not "we study X")

Mechanical check:

```bash
python ../academic-shared/contribution/contribution_check.py {paper_dir}/.paper/confirmed_contribution.md
```

## Mini Draft0 (conference / stem) — at S3

Before locking the outline, produce a short Draft0 packet in `.paper/draft0_intro.md`:

1. Identity sentence (who we are / what system or method)
2. Structural gap (what prior work lacks — one paragraph bullets)
3. Contribution ↔ planned experiments mapping (seed of contribution-experiment-map)
4. Page budget if venue is a CS conference

Full rhetorical path: `../conference/cs-conference-path.md`.

## Results Takeaway + map — at S4 / T4

Maintain `.paper/contribution_experiment_map.md`. Every Results subsection ends with **Takeaway** tied to a `Ci`.

## Fail closed

If user refuses to confirm contributions: stay in S3/T1; offer Socratic refinement (narrow RQ, drop vague aims). Do not invent contributions.

## Related P1 artifacts

After this gate passes, seed `.paper/issues.csv` and keep `citation_support_bank.md` in parallel (see `../issues/issues-contract.md`, `../citation/citation-support-bank.md`).
