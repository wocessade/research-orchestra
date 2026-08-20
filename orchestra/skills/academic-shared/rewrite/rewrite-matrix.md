# Rewrite Matrix Protocol (P1)

Inspired by PaperSpine paragraph rewrite matrices.

## When required

- S7 / T6 **major** rewrites (structure, argument, evidence alignment)
- Not required for spelling, citation key fixes, or single-sentence hedges

## Workflow

1. Add rows to `.paper/rewrite_matrix.md` (from template).
2. For each open row: execute Operation against Evidence source; respect Target length.
3. If Closed-book=yes: draft new text from sources only, then compare to old.
4. Mark Status `done`; re-run audit / `verify_paper` as needed.
5. Do not “polish in place” by stacking adjectives onto a broken claim.

## Gate linkage

- Q7 / QT6: if a Critical/Major item required prose rewrite → matrix row must exist and be `done` (or user-waived).
