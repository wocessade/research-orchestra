# LaTeX Document Skill (Embedded)

**Source:** `latex-document-skill` | **Snapshot:** 2026-06-06
**Pipeline usage:** S8 (LaTeX Compilation), T7 (Final Thesis Output — T7A)

## Capabilities (Pipeline-Relevant)
- Compile LaTeX projects: pdflatex, xelatex, lualatex with auto-detection
- LaTeX build failure diagnosis
- Bibliography compilation (bibtex, biber, biblatex)
- PDF/A output
- Multi-language/CJK support (auto XeLaTeX)
- Word count in LaTeX documents
- Document statistics (figures, tables, citations)
- LaTeX lint/check for common issues

## Common Build Sequences
```bash
# Simple
pdflatex main.tex

# With bibliography
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex

# XeLaTeX (Chinese/CJK)
xelatex main.tex && biber main && xelatex main.tex && xelatex main.tex

# latexmk (auto)
latexmk -pdf main.tex
latexmk -xelatex main.tex

# latexmk continuous mode
latexmk -pvc -pdf main.tex
```
