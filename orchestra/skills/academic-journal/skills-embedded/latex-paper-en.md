# LaTeX Paper English (Embedded Router)

**Source:** academic-latex (canonical) | **Updated:** 2026-07-27
**Pipeline usage:** S4 / S7 / S8 when writingFormat=latex

## Canonical protocol

Load and follow the full skill (progressive disclosure):

- `../../academic-latex/SKILL.md`
- On demand under `../../academic-latex/references/` — especially `workflow.md`, `citations.md`, `verification.md`, `style-de-ai.md`, `compile-debug.md`

Chinese thesis layout still uses `latex-thesis-zh.md`, but inherits claim/citation/verify rules from academic-latex.

## Capabilities

- Scaffold LaTeX projects with claim-evidence engineering
- Section drafting (Core-First) with mechanical verification
- Verified BibTeX only (no memory citations)
- Compile/diagnose (pdflatex, xelatex, latexmk, tectonic)
- De-AI polish with math/cite safety zones
- Pre-submit `/latex-cleanup` + `scripts/verify_paper.py`

## Common Commands

```bash
latexmk -pdf main.tex
python ../../academic-latex/scripts/verify_paper.py /path/to/paper
# Chinese thesis/body:
python ../../academic-latex/scripts/verify_paper.py /path/to/paper --allow-cjk
python ../../academic-shared/literature/bib_to_bibliography.py refs.bib -o bibliography.json
python ../../academic-shared/literature/verify_citations.py --input bibliography.json --output-dir ./verification/
```

## Do Not Use For

- Planning-from-scratch without S3 outline / user approval
- Deep literature search (S2)
- Inventing results or citations
- Figures (use academic-plotting / nature-figure / scientific-visualization routers)

## Hard rules (summary)

1. No artifact → `[CLAIM NEEDS EVIDENCE]`
2. No BibTeX from memory
3. Compile before judging layout
4. verify_paper hard fails block section completion
5. Figures: deterministic for numbers; see academic-plotting

## Pre-Compile Checklist

- [ ] Venue class matches target
- [ ] Full compile chain clean (or accepted soft warnings)
- [ ] verify_paper.py CLEAN (or blockers reported)
- [ ] Figures vector/PDF preferred; ≥300 DPI raster
- [ ] All `\cite` / `\ref` resolve