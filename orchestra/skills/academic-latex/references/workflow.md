# LaTeX paper workflow (gated)

## Principles

1. Framework before prose (story / claims / evidence map).
2. Execution contract before long drafting (outline + section jobs + figure plan).
3. Evidence before definitive claims (`planned` -> `placeholder` -> `verified`).
4. Audit + compile before "done".

Aligns with gated LaTeX skill patterns and academic-journal Core-First.

## Stage map

```text
Intake (metadata, venue, artifacts)
  -> Story + contribution boundaries + claims-to-avoid
  -> Claim-evidence map (+ numeric sources)
  -> Outline contract (user approval gate)
  -> Scaffold paper/ + .paper/
  -> Core sections (Methods -> Results -> Discussion)
  -> Framing (Intro -> Abstract -> Title)
  -> Figures via academic-plotting
  -> Citation lock + verify_citations.py
  -> De-AI / polish (safety zones)
  -> latexmk + verify_paper.py + /latex-cleanup
  -> Submission package notes
```

## Approval gate

Do not fill `main.tex` body with full prose until:

- Metadata frozen
- Outline approved (including existing explicit authorization to proceed; do not ask again)
- Claim-evidence map exists for every major contribution claim
- Venue template / document class chosen

Skeleton-only `main.tex` is OK before approval.

## Two-pass drafting

**Pass A — evidence core:** Methods -> Results -> Discussion

**Pass B — framing:** Related Work -> Introduction -> Abstract / Title

Empirical papers: keep result cells as placeholder until real CSVs exist; then backfill (do not invent).

Survey papers: literature snapshot + issue list before section prose.

## Issue / section contract (recommended)

Maintain `issues/sections.csv` or `.paper/section_contract.md`:

| id | section | acceptance | evidence | status |
|----|---------|------------|----------|--------|
| I1 | sec:method | Named modules match repo | README, code paths | DONE |
| I2 | sec:exp | All numbers from results CSV | scripts/make_tables.py | WIP |

Mark DONE only when acceptance criteria hold.

## Session handoff

When context saturates (rising hard-fail counts, drifting numbers), write:

```markdown
## Handoff
- paper_dir:
- venue / engine:
- completed sections:
- open blockers:
- next section + evidence files:
- verify_paper last result:
```

## Done definition

For a completed draft/revision batch:

1. verify_paper hard fails = 0 for that section
2. Relevant checks pass under [verification.md](verification.md); final delivery requires a successful full compile
3. Changed PDF pages visually checked when layout is affected, using available render/vision tools; record any unavailable visual check
4. Ledger updated for new claims
5. Unresolved markers reported as blockers

Never say "paper finished" while blockers remain unless explicitly reporting them.

## P1 — Issues contract & results backfill

1. After outline approval: copy `../academic-shared/issues/issues.template.csv` → `.paper/issues.csv`.
2. Draft only to the contract; run `validate_issues.py`.
3. When experiments land: `../academic-shared/issues/results-backfill.md` before Final Intro numbers.
4. Major polish passes: `.paper/rewrite_matrix.md`.
5. Citations: `.paper/citation_support_bank.md` + bib bridge / verify_citations.
