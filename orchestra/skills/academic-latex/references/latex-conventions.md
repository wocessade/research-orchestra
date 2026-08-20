# LaTeX conventions and layout

## Document setup

- Match venue class; do not switch to two-column casually if frontmatter/tables need single-column.
- `booktabs` tables; `siunitx` for numbers/units.
- Float control: `\usepackage[section]{placeins}` + `\FloatBarrier` beats scattering `[H]`.

## Layout fixes (compile PDF first)

- Loose/sparse page or stranded heading: check float placement before rewriting prose.
- Figure split / "Float too large": regenerate at correct aspect ratio (`figsize`); do not `\resizebox` distort.
- Wide multi-panel: regenerate taller at source rather than shrinking to illegibility.
- Widows/orphans: reword before `\enlargethispage`.

## Density (single-column reports)

When a compiled PDF looks sparse:

1. Modest `geometry` margins or KOMA `DIV`.
2. `microtype`.
3. Tighten chapter title skips (KOMA) if needed.
4. Optional chapter-flow gate (advanced) — only with user opt-in; verify patch in log.

Two-column conference density is a separate user decision when using report/thesis classes.

## Cross-references

- One `\label` after caption/title; never reuse keys.
- Prefer `cleveref` if the template allows; else `Fig.~\ref{...}`, `Table~\ref{...}`, `Eq.~(\ref{...})`.
- Run full compile chain so refs resolve (latexmk or pdflatex+bib+pdflatex×2).

## Math and algorithms

- Prefer `amsmath` environments; keep equation labels stable across revisions.
- Pseudocode: template's algorithm package; wrap as float with caption when venue expects it.

## Figures in LaTeX

- Owned by academic-plotting; this skill only includes and references them.
- Caption: What / How to read / Takeaway / Caveat (see plotting caption contract).
- Every figure referenced in text near first appearance.

## Glossary

Maintain `.paper/glossary.md`: one term -> one English (or Chinese) rendering for the whole manuscript.
