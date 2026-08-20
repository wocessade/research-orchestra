# Stage S8: Format & Compile [Strategist]

**Gate:** Q8 (BLOCK) — output compiles without errors (LaTeX->PDF for most venues; .docx for Chinese domestic journals), template matches venue selected at S8.5.

**Goal:** Journal-compliant output that compiles without errors.

**Needs Composers:** format-routing, docx-assembly

## Decisions

### Discipline Routing (S8, line 8)
- IF `discipline == "stem"` → load `references/discipline-stem.md`.
- Conference papers → use `\documentclass[conference]{IEEEtran}` or `acmart`. Verify page limits, font embedding, and PDF/A compliance.

### Venue Routing (S8, line 10)
- IF `venue == "chinese-domestic"` → S8.6 must run BEFORE this stage. Load `references/chinese-journal-adapter.md` after S8.5 and before S8.
- ELSE → proceed directly to format detection.

### Target Format Routing (S8, line 12)
- IF target journal requires `.docx` (common for Chinese domestic journals) → route to 8-Docx section.
- ELSE (default LaTeX->PDF) → proceed with 8-Latex path.

### Format Conversion Decision (8-Pre, lines 14-57)
Compare writingFormat (from S4) vs targetFormat (from venue/journal):

| writingFormat | Target Format | Action |
|--------------|---------------|--------|
| markdown | latex | Pandoc conversion needed |
| markdown | word | Pandoc conversion needed |
| latex | word | Pandoc conversion needed |
| word | latex | Pandoc conversion needed |
| latex | latex | No conversion — proceed to 8-Latex |
| word | word | No conversion — proceed to 8-Docx |

**STOP-AND-ASK threshold:** IF manuscript has >=2 of (5+ complex tables, 20+ equations, custom LaTeX macros, TikZ/pgfplots figures, algorithm pseudocode) → pause and ask user if they want to proceed with conversion or handle externally.

### Existing-Manuscript Format Assessment (8A-Pre, lines 59-75)
- IF entry via `existing-manuscript` (skipped S1-S6.5) → identify current format, identify target format, choose conversion path per table:
  | Current -> Target | Path |
  |-----------------|------|
  | LaTeX -> LaTeX | No conversion, proceed to 8-Latex |
  | Word -> LaTeX | Pandoc convert, manually fix tables/equations/refs |
  | Markdown -> LaTeX | Pandoc convert |
  | Word -> Word | Proceed to 8-Docx |
  | LaTeX -> Word | Pandoc convert |
- STOP-AND-ASK if manuscript has complex formatting (multi-panel figures, equation-heavy, custom tables).
- Non-existing-manuscript entries: format already determined at S4. Skip assessment.


### LaTeX verify_paper + cleanup (writingFormat=latex)

IF `writingFormat == latex` (8-Latex path):

1. Before/with compile loop, run:
   `python ../academic-latex/scripts/verify_paper.py {paper_tex_root}`
   Fix HARD failures (CJK leakage in EN papers, unresolved markers, missing bib keys, missing labels).
2. Compile with `latexmk` (or engine selected below). Save log to `{output_dir}/S8_compile_log.txt`.
3. Run command checklist `../academic-shared/commands/latex-cleanup.md` (/latex-cleanup).
3b. IF derivation-heavy STEM → optional `/verify-math` via `../academic-shared/commands/verify-math.md`.
4. Re-check figures from S5 still exist on disk and render in PDF.
5. Do **not** claim Q8 pass while verify_paper status is FAIL or cites show `??`.

### Early-LaTeX Detection (8-Latex, lines 77-83)
- IF `writingFormat == "latex"` → manuscript already in LaTeX from S4. S8 is verification only, NOT conversion. Compile-verify loop is typically 1-2 passes, not 5-10.

### Engine Selection (8B, lines 95-102)

| Condition | Engine |
|-----------|--------|
| CJK/multi-language, system fonts, modern packages | xelatex |
| Legacy templates, journal requirements | pdflatex |
| Complex font features, large documents | lualatex |

Auto-detection by skills-embedded/latex-document-skill.md — trust it unless specific journal requirement overrides.

### Docx Path (8-Docx, lines 126-143)
Three options in order of preference:
1. Pandoc conversion (`pandoc manuscript.tex -o manuscript.docx --reference-doc=journal-template.docx`) — best for structure. User must provide template.docx.
2. Manual export from Overleaf — built-in "Submit -> Word" export.
3. Format template system — YAML-driven via `format_template.py` + `StyleEngine`. After assembly, run `generate_report()` to surface defaulted/conflict items.

IF none viable → ask user to handle .docx externally. Acknowledge: "This pipeline is optimized for LaTeX->PDF."

### Preprint Auto-Route (S8, line 159)
- IF `preprint == true` → route to S8.25 automatically after S8 passes.

### Compose Verify Loop (8D, lines 115-119)
1. Run compile. 2. IF errors: fix the FIRST error only (subsequent errors are cascade), recompile. 3. When clean: visually inspect PDF (margins, figure placement, page breaks). 4. Run with PDF/A flag if venue requires archival PDF.

### Composer Sequence
1. composer: format-routing {determine conversion path, engine selection, format assessment}
2. composer: docx-assembly {conditional — only when target format is .docx}

## Gate

### Q8 Gate Checklist
- [ ] IF latex: `verify_paper.py` CLEAN (or blockers explicitly waived by user)
- [ ] Output compiles with zero errors (PDF: no LaTeX errors; .docx: opens cleanly in Word; warnings OK but review them)
- [ ] Compilation log saved to `{output_dir}/S8_compile_log.txt`
- [ ] Template matches target venue exactly (venue selected at Stage 8.5; check most recent author guidelines)
- [ ] All cross-references resolve (no "??" in output)
- [ ] Figures render at correct resolution (not pixelated)
- [ ] Page count within venue limits
- [ ] Supplementary materials separated from main text
- [ ] If .docx target (option 3): ran `generate_report()` — all styles confirmed or explicitly resolved

### Gate Failure Route
Q8 is BLOCK.

1. Inspect specific failed check item:
   - Compilation errors → route back to 8D (Compile Verify Loop), fix first error, recompile.
   - Template mismatch → route back to 8A (template check).
   - Broken cross-references → route back to 8C (common error fixes).
2. After 2 fix attempts still fail → STOP-AND-ASK: switch engine (xelatex ↔ pdflatex) or manually fix and continue.
