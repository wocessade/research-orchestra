# Backend routing

## Class 1 — Evidence / result

Use for: trends, comparisons, ablations, heatmaps, ROC, distributions, metric grids.

- Tools: matplotlib, seaborn, plotnine/ggplot2, PGFPlots with data files.
- Never image-generation models for exact numbers/axes/tables.
- Keep CSV/JSON + plotting script next to the asset.

## Class 2 — Concept / method

Use for: architecture, pipeline, framework, teaser, mechanism schematic.

- Default: built-in image generation when available (inspect for garbled text).
- High-precision labels: TikZ/SVG or hybrid (image + deterministic label overlay).
- Optional compile fallback: `\IfFileExists{generated}{...}{\input{tikz}}`.

## Rule of thumb

**Numeric axes -> code. Boxes and arrows -> diagram tools.**

## Chart selection (evidence)

| Data shape | Chart |
|------------|-------|
| time/step x metric | line (+ CI if multi-run) |
| methods x metrics | grouped bar or **table** |
| many methods, one metric | horizontal bar |
| matrix | heatmap |
| distribution | box/violin/histogram |
| two continuous vars | scatter |
| exact benchmarks | LaTeX table |

Avoid: pie/donut for ML comparisons, 3D bars, jet/rainbow, dual y-axes with unrelated units, connecting category means with lines, small-n mean bars without points.

## Hybrid

Generated diagram + SVG/LaTeX text overlay when exact terminology matters.
Generated diagrams must not create numeric evidence.
