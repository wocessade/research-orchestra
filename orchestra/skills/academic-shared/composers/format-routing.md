# Composer: format-routing

**Purpose:** Select writing tool by format axis and convert between formats when source differs from target venue requirements.
**Used by:** academic-journal S4, S8
**Parameters:** `{writing_format}`, `{target_format}`, `{manuscript_path}`

## Instructions

### S4 Writing Tool Selection

The `{writing_format}` parameter determines which tool and approach to use for writing:

| writingFormat | Writing Tool | Notes |
|---------------|-------------|-------|
| **latex** | `skills-embedded/latex-paper-en.md` → **`../../academic-latex/SKILL.md`** | Write directly in LaTeX. Cross-refs (`\ref{}`), citations (`\cite{}`), and figure references are native. Compile after each section to catch errors early — a broken `\ref{}` found at S4 costs 30 seconds; the same error at S8 costs 30 minutes. |
| **word** | `skills-embedded/scientific-writing.md` | Write in standard prose. S8 will convert to .docx via Pandoc or manual transcription. |
| **markdown** | `skills-embedded/scientific-writing.md` | Write in Markdown with Pandoc-ready structure. Pandoc converts to target format at S8. |
| **typst** | `skills-embedded/typst-paper.md` | Write directly in Typst. Native cross-refs and citation support. |
| **auto-detect** | `skills-embedded/scientific-writing.md` (default) | Default to prose format. User can override at any point. |

If `writingFormat=latex` **and** deliverable is a **Chinese thesis / GB/T layout**:
use `skills-embedded/latex-thesis-zh.md` for class/layout, and still load academic-latex via `latex-paper-en` for claim/cite/verify with `verify_paper.py --allow-cjk`. Do not override university 封面/cls requirements.
If `writingFormat=latex`: the primary writing tool is `skills-embedded/latex-paper-en.md` which **must load** `../../academic-latex/SKILL.md` (full protocol), not `skills-embedded/scientific-writing.md`. Cross-references and citations accumulate incrementally during writing rather than being inserted as a batch at S6/S8. The S8 compile-verify loop is typically 1-2 passes instead of 5-10.

### Format Conversion (Hard Switch)

When the writing format used in S4 differs from the target format required by the venue, convert before entering the compile-verify loop.

**Detection matrix:**

| Source Format | Target Format | Action |
|---------------|---------------|--------|
| markdown | latex | `pandoc manuscript.md -o manuscript.tex --standalone --biblatex` |
| markdown | word | `pandoc manuscript.md -o manuscript.docx --reference-doc=template.docx` |
| latex | word | `pandoc manuscript.tex -o manuscript.docx --reference-doc=template.docx` |
| word | latex | `pandoc manuscript.docx -o manuscript.tex --standalone` |
| latex | latex | No conversion needed |
| word | word | No conversion needed |

For **existing-manuscript entry**, assess current format (Word, Google Docs, plain text, Markdown, Overleaf) vs. target format using the same matrix.

### Conversion Report

After conversion, produce a loss assessment:

```markdown
## Format Conversion: {source} -> {target}
**Method:** Pandoc {command used}
**Known Losses:**
- Cross-references: Pandoc may drop `\ref{}` -> manual re-link required
- Complex tables: multi-row/col spans may break -> verify each table
- Equations: inline `$...$` usually survive; display math may need `\begin{equation}` wrapper
- Citations: `[@key]` -> `\cite{key}` usually works; check BibTeX compatibility
- Figures: `![]()` -> `\includegraphics{}` usually works; check path separators
**Items to Manually Verify (in priority order):**
1. Cross-references (most fragile)
2. Tables (layout may shift)
3. Equations (rendering)
4. Special characters / Unicode
5. Page breaks / section breaks
```

### STOP-AND-ASK Threshold

If the manuscript has **2 or more** of the following, pause and ask the user if they want to proceed with conversion or handle it externally:
- 5+ complex tables (multirow, multicol, spanning cells)
- 20+ displayed equations
- Custom LaTeX macros or environments
- TikZ/pgfplots figures
- Algorithm pseudocode environments

For **existing-manuscript entry**, also STOP-AND-ASK if the manuscript has complex formatting (multi-panel figures, equation-heavy, custom tables).

## Verification
- [ ] Writing tool selected matches `{writing_format}` parameter
- [ ] If `{writing_format}` != `{target_format}`: Pandoc conversion command identified and run
- [ ] Conversion report produced with known losses documented
- [ ] All cross-references, tables, and equations manually verified after conversion
- [ ] STOP-AND-ASK triggered if threshold met (2+ complex features)
- [ ] If `writingFormat=latex`: compile-verify expected in 1-2 passes (not 5-10)

## Common Pitfalls
- **Incremental latex compilation skipped:** failing to compile each section as written in LaTeX defers errors to S8, turning 30-second fixes into 30-minute debugging sessions
- **Pandoc as black box:** assuming Pandoc handles everything perfectly — always verify cross-references and tables manually after conversion
- **Skipping conversion report:** going straight to compile without assessing known losses means fragile items (cross-refs, tables) are not prioritized for manual verification
- **Converting without asking when threshold is met:** complex manuscripts (20+ equations, TikZ, custom macros) WILL break during conversion — always STOP-AND-ASK first
