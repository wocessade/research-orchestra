---
name: chart-type-selection
description: 19 chart types taxonomy with selection decision tree for numerical comparison, trend/convergence, model evaluation, data relationships, statistical distribution, and compound layouts. Loaded at S5 for informed figure type selection.
---

# Chart Type Selection Guide

Loaded at Stage 5A when planning figures. Select chart type BEFORE invoking `skills-embedded/nature-figure.md` or `skills-embedded/scientific-visualization.md`.

## Decision Tree

```
What is the primary evidence logic?
├── COMPARISON → Category 1 (Numerical Comparison)
│   ├── Few categories (<8), short labels → Grouped Bar
│   ├── Many categories or long labels → Horizontal Bar
│   ├── Ranked contribution (80/20 rule) → Pareto Chart
│   ├── Multi-dimensional benchmarking (3-8 axes) → Radar/Spider
│   └── Part-to-whole with time dimension → Stacked Bar
├── TREND / CONVERGENCE → Category 2 (Trend)
│   ├── Continuous trend with uncertainty → Line with CI Band
│   ├── Highlight inflection region → Zoom-in Line
│   └── Relationship with fit line → Scatter with Fit
├── MODEL EVALUATION → Category 3 (Model)
│   ├── Binary classifier comparison → ROC Curve
│   └── Imbalanced dataset → Precision-Recall Curve
├── RELATIONSHIP → Category 4 (Relationships)
│   ├── Correlation matrix or expression data → Heatmap
│   ├── Two continuous variables → Scatter
│   └── Three continuous variables → Bubble Chart
├── DISTRIBUTION → Category 5 (Statistical Distribution)
│   ├── Multi-group distribution shape → Violin Plot
│   ├── Distribution summary with outliers → Box Plot
│   └── Simple composition (3-5 parts) → Donut/Prefer Bar
└── MULTI-LOGIC → Category 6 (Compound Layouts)
    ├── Two variables with different units → Dual Y-Axis
    ├── Magnitude + trend overlay → Bar+Line Combo
    └── Multi-variable, multi-condition → Faceted Grid
```

## The 19 Chart Types

### Category 1: Numerical Comparison (5 types)

| # | Chart Type | Best For | Avoid When |
|---|-----------|----------|------------|
| 1 | Grouped Bar | Comparing values across 3-8 categories | >10 categories (unreadable) |
| 2 | Horizontal Bar | Long category labels, >8 categories | Vertical comparison needed |
| 3 | Pareto Chart | Ranked contribution, 80/20 analysis | Non-ranked data |
| 4 | Radar/Spider | Multi-attribute benchmarking (3-8 axes) | >8 dimensions, non-comparable scales |
| 5 | Stacked Bar | Part-to-whole with time series | Individual segment comparison needed |

### Category 2: Trend / Convergence (3 types)

| # | Chart Type | Best For | Avoid When |
|---|-----------|----------|------------|
| 6 | Line with CI Band | Continuous trends with uncertainty | Categorical x-axis |
| 7 | Zoom-in Line | Highlighting critical region within trend | No inflection point of interest |
| 8 | Scatter with Fit | Relationship + regression line | Non-linear relationships without fit |

### Category 3: Model Evaluation (2 types)

| # | Chart Type | Best For | Avoid When |
|---|-----------|----------|------------|
| 9 | ROC Curve | Binary classifier comparison | Multi-class (use one-vs-rest ROC) |
| 10 | Precision-Recall Curve | Imbalanced datasets | Balanced datasets (ROC sufficient) |

### Category 4: Data Relationships (3 types)

| # | Chart Type | Best For | Avoid When |
|---|-----------|----------|------------|
| 11 | Heatmap | Correlation matrix, expression data | Small matrices (<5x5) |
| 12 | Scatter | Two continuous variables | >10k points without alpha transparency |
| 13 | Bubble | Three continuous variables | Bubble size hard to read accurately |

### Category 5: Statistical Distribution (3 types)

| # | Chart Type | Best For | Avoid When |
|---|-----------|----------|------------|
| 14 | Violin Plot | Multi-group distribution shape | Small n per group (<20) |
| 15 | Box Plot | Distribution summary with outliers | Need to show bimodality |
| 16 | Donut/Pie | Simple composition (3-5 parts) | Precise comparison needed (use bar) |

### Category 6: Compound Layouts (3 types)

| # | Chart Type | Best For | Avoid When |
|---|-----------|----------|------------|
| 17 | Dual Y-Axis | Two variables with different units | Misleading axis scaling risk |
| 18 | Bar+Line Combo | Magnitude + trend overlay | >2 data series total |
| 19 | Faceted Grid | Multi-variable, multi-panel | <3 subplots (use individual charts) |

## Special Remediation Strategies

When data has extreme characteristics, apply these BEFORE selecting chart type:

| Data Situation | Remediation | When to Use |
|---------------|-------------|-------------|
| Orders-of-magnitude range | Log scale | Values span 10x+ range |
| Large gaps in axis | Broken axis | Preserve raw-value intuition |
| Cross-model magnitude comparison | Normalization | Focus on relative improvement |
| Single-experiment data | No error bars | Don't fabricate CI from single run |

## Quick Selection by Paper Type

| Paper Type | Recommended Types |
|------------|-------------------|
| Empirical research | 1, 6, 14, 12, 19 |
| Systematic review | 1, 5 (PRISMA flow), 11 |
| Methods paper | 1, 6, 17 |
| Software/tool paper | 18 (architecture), 1 (performance) |
| Benchmark paper | 1, 9, 10 |
| Theory/conceptual paper | N/A — use `skills-embedded/scientific-schematics.md` for conceptual diagrams |

## Integration with S5C Design Rules

All 19 types must follow the S5C rules:
- Colorblind-safe palette (viridis/cividis/Okabe-Ito)
- Multi-panel labeling (a), (b), (c) consistent across all figures
- Font >= 8pt at final width, axes labels 9-10pt
- Vector export for line art (PDF/SVG), 300 DPI for raster images
- No chartjunk: remove gridlines unless they convey information, use direct labels instead of legends
