# Data charts (deterministic)

## Publication rcParams (starting point)

```python
import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.use("Agg")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "savefig.bbox": "tight",
    "figure.dpi": 300,
    "savefig.dpi": 300,
})
```

Or: `python scripts/plot_style.py --print-rcparams`.

## Sizing

Build figsize from journal mm width (see journal-profiles.md), not random pixels.

Example single-column ~89 mm: `figsize=(3.5, 2.6)` inches.

## Method highlighting

- "Ours" / proposed method: distinct warm accent (e.g. coral `#E76F51` or vermillion).
- Baselines: cool gray.
- Consistent across all figures in the paper.

## Uncertainty

- Show CI/SD only when computed from real replicates.
- State in caption: mean+/-SD, CI level, n, single-run.
- Significance brackets only with real tests — never invent p-values.

## Multi-panel

- Shared axis limits when comparing the same metric.
- Panel labels: bold lowercase `a`, `b`, `c` top-left (unless assembling later in PPT — then label at assembly).
- Align spines; consistent legend strategy (shared legend when possible).

## Export

- Vector: PDF/SVG for line art.
- Raster preview PNG ≥300 DPI; line art often 600 DPI if raster-only venue.
- Save script as `figures/gen_fig_<name>.py`.

## Anti-patterns

Default matplotlib styling, chartjunk grids, hairlines <0.5 pt, text <5 pt at final size, `\resizebox` distortion from LaTeX side.
