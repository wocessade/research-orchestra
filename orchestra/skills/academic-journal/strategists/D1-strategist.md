# Stage D1: Exploratory Data Analysis [Strategist]

**Gate:** QD1 (BLOCK) — EDA must complete before entering D2.
**Goal:** Explore data systematically to discover patterns without hypothesis testing.
**Needs Composers:** none

## Decisions

### Axis Routing
D1 is a sequential single-agent stage with dependency constraints. No axis/passport branching.

### Sub-Step Execution Order
D1A (Descriptive Statistics) → D1B (Pattern Discovery) → D1C (Alternative Explanations) → D1D (EDA Documentation)

**Dependency constraint (DP1 ref.):** D1B uses D1A's variable summaries as input. Run D1A first, then D1B. D1C runs after D1B, using D1B's patterns as the object of scrutiny. D1D compiles all prior outputs.

### Key Constraint
**NO p-values at any point.** No significance tests, no p-values, no confidence intervals for hypothesis testing, no significance stars, no asterisk annotations in figures or tables. Description and pattern discovery only.

### STOP-AND-ASK Points
- **D1A (line 38):** If distributions are extreme (bimodal, heavy-tailed, 99% zero-inflated, exponential with gap) → present pattern and let user interpret subpopulations or artifacts.
- **D1C (line 130):** For patterns where alternative explanation is plausible but cannot be resolved with available data → flag as limitation for D2. Do not assume resolution.

### Passport Update
After completing EDA, write:
- `passport.negative_results_pathway` = `"null_result_aware"` if EDA suggests likely null/negative findings (no clear patterns, weak patterns, or main patterns likely artifacts).
- Otherwise keep as `"standard"`.

## Gate

### QD1 Gate Checklist
- [ ] Descriptive statistics computed for all variables (D1A)
- [ ] Visualizations generated for key variables (D1A)
- [ ] Bivariate patterns explored (D1B) — scatter plots, grouped box plots, cross-tabulations
- [ ] Multivariate exploration completed (D1B) — correlation matrix, dimension reduction (if applicable)
- [ ] Pattern Catalog documented (D1B) — at least 3 patterns
- [ ] Alternative explanations tested for top patterns (D1C)
- [ ] NO p-values, significance tests, or inferential statistics anywhere in the stage
- [ ] `{output_dir}/D1_data_summary.md` written
- [ ] Candidate patterns for D2 identified
- [ ] Passport fields updated (including negative_results_pathway assessment)
- [ ] Stage completion log appended

### Gate Failure Route
QD1 is BLOCK — EDA must be complete to enter D2.

1. **EDA incomplete** (key variables unanalyzed, patterns unrecorded, alternative explanations unchecked) → return to the corresponding sub-step and retry gate.
2. **Data too sparse/noisy to find credible patterns** → STOP-AND-ASK: inform user data may not support a quantitative paper. Suggest: (a) find supplementary data, (b) switch to data-paper route, (c) switch to Idea-First entry.
