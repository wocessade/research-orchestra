---
name: academic-plotting
description: >
  Create, revise, and audit publication-quality academic figures: deterministic
  data charts (matplotlib/seaborn) and concept/method diagrams (image generation
  or TikZ). Use for 学术绘图, Nature/Science/IEEE figures, architecture diagrams,
  ablation plots, multi-panel layouts, figure contracts, colorblind-safe palettes,
  journal physical sizes, captions, and LaTeX \includegraphics integration.
  Complements academic-latex. Never invent numeric results in plots.
---

# Academic Plotting — Visual Arguments, Not Decoration

执行范围与授权见 [共享执行规则](../academic-shared/references/execution-policy.md)；按当前任务读取阶段细则。

Every figure is a **visual argument** with one core conclusion. Aesthetic polish
is secondary to evidence integrity and reviewer defensibility.

This skill is the canonical figure protocol for the `academic-*` family (S5 and
standalone use). Pair with `academic-latex` for manuscript inclusion.

## Non-negotiable rules

1. **Split backends.** Evidence/result figures = deterministic code only.
   Concept/method diagrams = image generation and/or TikZ/SVG. Never use image
   models to draw axes with invented numbers.
2. **Figure contract first.** Write core conclusion, panel map, evidence hierarchy,
   source path, and reviewer risk before plotting. See
   [references/figure-contract.md](references/figure-contract.md).
3. **Physical size.** Build at target journal width (e.g. Nature 89/183 mm), not
   arbitrary pixels scaled later.
4. **Colorblind-safe.** Default Okabe–Ito; redundant encoding (marker/line/hatch);
   check grayscale when color encodes categories.
5. **Reproducibility.** Ship plotting script + source data (or prompt file for
   concept diagrams). Update `.paper/figure_inventory.md`.
6. **Honest statistics.** Never invent p-values, n, or error bars.
7. **Caption contract.** What / How to read / Takeaway / Caveat — takeaway matches
   the claim ledger message.
8. **Assist, do not fabricate.** Missing data -> blocker or weakened claim, not a pretty fake plot.

## Progressive loading

| Task | Load |
|------|------|
| Any new figure | [references/figure-contract.md](references/figure-contract.md) |
| Choose backend | [references/backend-routing.md](references/backend-routing.md) |
| Data charts | [references/data-charts.md](references/data-charts.md), [references/color-palettes.md](references/color-palettes.md) |
| Concept / architecture | [references/concept-diagrams.md](references/concept-diagrams.md) |
| Journal sizes / export | [references/journal-profiles.md](references/journal-profiles.md) |
| Captions | [references/captions.md](references/captions.md) |
| LaTeX include | [references/latex-integration.md](references/latex-integration.md) |
| Pre-submit QA | [references/qa-checklist.md](references/qa-checklist.md) |

## Quick decision

| Figure has… | Backend |
|-----------|---------|
| Numeric axes, metrics, ablations, heatmaps | matplotlib / seaborn / ggplot (deterministic) |
| Boxes, arrows, pipelines, frameworks | Image gen and/or TikZ |
| Exact benchmark numbers | Prefer **table** (academic-latex) over chart |

## Workflow

1. Classify: evidence-result vs concept-method.
2. Write figure contract (YAML or markdown).
3. Choose a chart/layout from the figure contract; ask only when the choice changes the intended scientific comparison.
4. Generate asset + script/prompt under `figures/`.
5. Export PDF/SVG (+ PNG preview ≥300 DPI).
6. Caption + inventory + claim ledger link.
7. QA at final paper width ([references/qa-checklist.md](references/qa-checklist.md)).
8. Wire `\includegraphics` via academic-latex.

## Integration

| Stage | Role |
|-------|------|
| S5 | Primary figure production |
| Q5 gate | schematic + data figure minima, captions, colorblind, vector/DPI |
| S7 | figure-text consistency |
| S8 | paths exist; PDF compiles |
| Visual QA (blind) | Inspect final-width PNG with available vision tools; external vision is optional. Figure quality stays here; page floats → `academic-latex` |

Embedded routers: `nature-figure.md`, `scientific-visualization.md`,
`scientific-schematics.md` point here for the full protocol.

## Scripts

```bash
python scripts/plot_style.py --print-rcparams
python scripts/validate_figure_spec.py figures/figure_specs.yaml
```

## Federation smoke

See `../academic-shared/SMOKE-LATEX-PLOTTING.md` for end-to-end wiring checks with academic-latex.

## Claim linkage

Figure contracts should name the `Ci` from `.paper/contribution_experiment_map.md` when the figure supports a contribution.
