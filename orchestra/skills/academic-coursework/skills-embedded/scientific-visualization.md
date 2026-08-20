# Scientific Visualization (Embedded Router)

**Source:** academic-plotting | **Updated:** 2026-07-27
**Pipeline usage:** S5 data figures; D0 exploration plots

## Canonical protocol

Follow `../../academic-plotting/SKILL.md` with emphasis on:

- `../../academic-plotting/references/data-charts.md`
- `../../academic-plotting/references/color-palettes.md`
- `../../academic-plotting/references/journal-profiles.md`
- `../../academic-plotting/references/qa-checklist.md`

## Core Principles

1. Resolution & format: vector preferred; raster 300–600+ DPI
2. Colorblind-safe (Okabe–Ito default) + redundant encoding
3. Multi-panel consistency (limits, colors, legends)
4. No chartjunk / 3D / jet colormaps
5. Reproducible scripts + source data — never hand-invent plotted numbers

## Chart chooser

See academic-plotting `backend-routing.md` table (line / grouped bar / heatmap / table…).

## Export

```bash
python ../../academic-plotting/scripts/plot_style.py --print-rcparams
# save fig as PDF + PNG preview
```