# LaTeX Posters (Embedded)

**Source:** `latex-posters` | **Snapshot:** 2026-06-06
**Pipeline usage:** S5 — academic poster output

## Purpose
Create academic conference posters using LaTeX (tikzposter, beamerposter, baposter).
Used when the pipeline needs to produce a poster version of the paper.

## Common Classes
```latex
\documentclass[orientation=portrait, size=a0]{tikzposter}
% or
\documentclass[orientation=landscape, size=a0]{tikzposter}
```

## Standard Poster Sections
1. Title + Authors + Affiliations
2. Introduction/Background
3. Methods
4. Key Results (figures + brief text)
5. Conclusions
6. References (selective)
7. Acknowledgments + QR code
