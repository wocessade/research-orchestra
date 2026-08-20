# Stage S5: Figures & Visuals [Strategist]

**Gate:** Q5 (BLOCK) — at least 1 schematic + 2 data figures, complete captions, colorblind-safe, vector format
**Goal:** Publication-quality figures that tell the paper's story without reading the text.
**Needs Composers:** none
**Canonical protocol:** `../academic-plotting/SKILL.md` (routers: nature-figure / scientific-visualization / scientific-schematics). Before any plot, load `../academic-plotting/references/figure-contract.md` + `backend-routing.md`.

## Decisions

### Discipline Routing (S5, line 8)

IF `discipline=stem` → load `references/discipline-stem.md`:
- CS figures: compact and space-efficient
- 2-4 figures, vector format mandatory
- Every figure must tell a story independently (CS reviewers scan figures before reading text)

### Paper Type Minimums (S5, lines 117-125)

| Paper Type | Minimum Figures |
|------------|----------------|
| Empirical research | 3+ (1 schematic + 2 data) |
| Systematic review | 2+ (PRISMA diagram + 1 synthesis) |
| Methods paper | 2+ (workflow + validation) |
| Data paper | Metadata tables (no data figures). 1 data inventory summary table required. |
| Software/tool paper | 2+ (architecture diagram + API/usage example) |
| Benchmark paper | 2+ outputs (leaderboard table + method comparison chart) |
| Theory/conceptual paper | 1+ conceptual diagrams (framework, causal model, or taxonomy) |

### Figure Type — Primary vs Fallback Matrix (S5, lines 19-27)

| Need | Primary | Fallback |
|------|---------|----------|
| Data plots (Python) | `skills-embedded/nature-figure.md` | `skills-embedded/scientific-visualization.md` |
| Data plots (R) | `skills-embedded/nature-figure.md` (R backend) | `skills-embedded/scientific-visualization.md` |
| Schematics/diagrams | `skills-embedded/scientific-schematics.md` | `skills-embedded/generate-image.md` |
| Graphical abstract | `skills-embedded/scientific-schematics.md` | `skills-embedded/generate-image.md` |
| Posters | `skills-embedded/latex-posters.md` | — |
| Slides from paper | `skills-embedded/nature-paper2ppt.md` | `skills-embedded/scientific-slides.md` |

`skills-embedded/nature-figure.md` requires Python or R selection first. Prompt user before proceeding.

### LaTeX manuscript figures (writingFormat=latex)

When `passport.writingFormat == latex` (or target is LaTeX):

1. Produce assets under `{paper_dir}/figures/` with reproducible scripts or prompts (academic-plotting rules).
2. Prefer PDF/SVG for data plots; include via `\includegraphics` in section `.tex` files (academic-latex `latex-integration`).
3. Update `.paper/figure_inventory.md` and claim ledger messages to match captions.
4. Evidence/result figures MUST be deterministic — never generative numbers.
5. Run academic-plotting QA checklist before declaring Q5 pass.
6. Ensure paths resolve for the S8 latexmk compile (relative to `main.tex`).


### Visual Reference Search (S5, lines 30-51) — Optional

Conditional on Tavily API key availability:
- IF user provides Tavily key → run visual reference search using query templates:
  1. "{topic} diagram architecture flowchart"
  2. "{topic} result chart data visualization"
  3. "{topic} schematic illustration figure"
- Parameters: `search_depth: "basic"`, `max_results: 5`, `include_images: true`
- Output: save image URLs and source pages to `{output_dir}/s5_visual_references.md`
- Use as style/layout inspiration only — NEVER copy or reuse

### Architecture Diagram Prompts (S5, lines 53-80)

When generating research-paper-style diagrams via `skills-embedded/scientific-schematics.md` or `skills-embedded/generate-image.md`:

Route by diagram purpose:
- `skills-embedded/scientific-schematics.md`: neural network architectures, system diagrams, biological pathways, data pipelines, schematic workflows
- `skills-embedded/generate-image.md`: conceptual illustrations, graphical abstracts, cover art

### Instrument Figure vs. Remake Boundary (S5, lines 82-113)

Decision rule for every figure:

```
Can I produce this figure myself from the data I have?
├── YES → Produce it. Apply S5C design rules.
└── NO → What exactly needs to change?
    ├── Needs replot from raw data → STOP AND ASK: specific replot instructions + why
    ├── Needs re-export from instrument software → STOP AND ASK: resolution/format/crop specs
    └── Needs modification in specialized software → STOP AND ASK: step-by-step instructions
```

Per-figure-type boundary:

| Figure Type | Agent Can | Agent Cannot → STOP AND ASK |
|-------------|-----------|------------------------------|
| Data plots from tabular data | Remake from CSV/Excel | — |
| XRD, FTIR, NMR spectra | Remake from raw xy-text | Processed in Origin/PeakFit; ask for raw xy |
| SEM/TEM micrographs | Annotate, labels, multi-panel | Change magnification, contrast, scale bar |
| Western blot / gel | Crop, annotate lanes | Adjust brightness, quantify bands |
| Confocal microscopy | Merge channels, add scale bar | Change channel colors, adjust intensity |
| Flow cytometry | Remake from FCS CSV export | Gating strategy; ask for percentages |
| XPS survey/scans | Remake from exported xy data | Peak fitting/deconvolution; ask for assignments |
| Chemical structures | `skills-embedded/scientific-schematics.md` | Complex stereochemistry; ask for ChemDraw/CDX |
| Instrument screenshots | Use as-is (high-res PNG/TIFF) | Re-export at 300+ DPI |

**Never:**
- Screenshot a figure from a paper/PDF and pass off as original
- Draw over an instrument figure to misrepresent data
- Accept low-resolution instrument screenshot when journal requires 300 DPI
- Guess what a figure shows and make claims based on the guess

### Figure Design Rules (S5, lines 128-135)

- **Colorblind-safe palette:** viridis/cividis for continuous, Okabe-Ito for categorical. Never red-green alone.
- **Multi-panel labeling:** (a), (b), (c) bottom-left or top-left, consistent
- **Font size:** No smaller than 8pt at final width. Axes labels 9-10pt.
- **Export:** Vector (PDF/SVG) for line art, 300+ DPI TIFF for images with gradients
- **Dimension:** Target journal column width. Nature = 89mm (single) / 183mm (double). Check `skills-embedded/venue-templates.md`.
- **No chartjunk:** Remove gridlines unless informative, remove borders, direct labels over legends

### Figure Caption Template (S5, lines 137-143)

Every figure caption must answer:
1. **What** is being shown (type of plot, variables, sample)
2. **How** was it measured/computed (key methods, statistical tests)
3. **What** is the takeaway (one sentence of interpretation)

### Figure Planning Protocol — Pre-Plot Checklist (S5, lines 11-17)

Before opening any plotting tool, define for each figure:
1. What conclusion does this figure prove?
2. What evidence logic (comparison, trend, distribution, relationship)?
3. What chart type best expresses this? Use `references/chart-type-selection.md` (19-type taxonomy + decision tree).
4. What export specs (width, format, dpi, color space)?
5. What review risks (visual misinterpretation, colorblindness, overplotting)?

### STOP-AND-ASK Points
- Agent cannot remake instrument figure → ask user for raw data or re-export with specific instructions
- Figure minimum not met after fix attempts → ask user: expand scope, relax standards, or proceed-as-is

## Gate

### Q5 Gate Checklist
- [ ] At least 1 schematic + 2 data figures (or type-appropriate minimums)
- [ ] All figures have complete captions following the What/How/What template
- [ ] Colorblind-safe palette used
- [ ] Axes labels readable, no default matplotlib styling
- [ ] Figure-text consistency: every number in figures matches text (cross-check manually)
- [ ] Vector format for line art, 300 DPI minimum for raster images

### Gate Failure Route
Q5 is BLOCK.

1. First failure → identify which check items failed → route back to corresponding sub-step (S5A figure planning) → re-run → re-evaluate gate.
2. After 2 fix attempts still fail → **STOP-AND-ASK** user: expand scope, relax standards, or proceed with current state. Route back to S5A, redesign or supplement missing figures.
