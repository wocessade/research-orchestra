# Nature Figure Making (Embedded Router)

**Source:** academic-plotting + Nature profiles | **Updated:** 2026-07-27
**Pipeline usage:** S5 — high-impact / Nature-family figures

## Canonical protocol

1. Read `../../academic-plotting/SKILL.md`
2. Always load `../../academic-plotting/references/figure-contract.md` and `../../academic-plotting/references/backend-routing.md` before plotting
3. For journal sizes/export: ``../../academic-plotting/references/journal-profiles.md`, `../../academic-plotting/references/qa-checklist.md`
4. For data charts: `../../academic-plotting/references/data-charts.md` + `../../academic-plotting/references/color-palettes.md`
5. For schematics: `../../academic-plotting/references/concept-diagrams.md` (or scientific-schematics router)

## Figure Contract (Before Plotting)

1. Core conclusion — one-sentence claim
2. Evidence chain — each panel unique
3. Archetype / layout
4. Backend — deterministic vs concept (never generative numbers)
5. Export — physical width (≈89/183 mm), PDF/SVG, DPI

## Quick Start (Python)

Prefer `python ../../academic-plotting/scripts/plot_style.py --print-rcparams` and apply Okabe–Ito.

## Export Requirements

- Vector: PDF/SVG/EPS for line art
- Raster: ≥300 DPI (line art often 600 if raster-only)
- Editable text in SVG (`svg.fonttype=none`); `pdf.fonttype=42`
- Source data / script beside each panel