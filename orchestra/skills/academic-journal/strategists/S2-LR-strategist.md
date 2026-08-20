# Stage 2-LR: Systematic Literature Review [Strategist]

**Gate:** Q2-LR (BLOCK) — PRISMA flow diagram generated, search strategy documented, inclusion/exclusion criteria defined, quality assessment method stated, synthesis approach described
**Goal:** Conduct a systematic, reproducible literature search with full PRISMA documentation.
**Needs Composers:** none

## Decisions

### Review Type Routing
- **Systematic review** → full protocol registration (2LR-A), standard screening depth, full quality assessment with discipline-appropriate RoB tool
- **Narrative/scoping review** → adapt screening depth, use PRISMA-ScR as lighter alternative; protocol registration is **optional** (skip 2LR-A)

### Synthesis Method Selection (2LR-F)
Based on nature of included studies, select ONE:
- **Narrative synthesis** — heterogeneous studies, mixed designs → textual summary structured by themes
- **Thematic synthesis** — qualitative studies → analytical + descriptive themes
- **Meta-analysis** — homogeneous interventions, comparable outcomes → forest plot, I², pooled effect
- **Meta-regression** — heterogeneous but sufficient N → identify effect modifiers
- **SWiM (Synthesis Without Meta-analysis)** — quant data unsuitable for pooling → vote-counting by direction of effect
- **Scoping synthesis** — mapping evidence, not answering quantitative question → charted evidence map

### Redundant Scheduling (DP26)
Gap identification uses Mode B x2: two agents independently produce gap statements from the same literature set and PRISMA screening results.
- High agreement → proceed directly
- Partial agreement → take intersection, merge
- Low agreement → **STOP-AND-ASK**: present both gap statements, let user choose or merge

### STOP-AND-ASK Triggers
- **PRISMA screening completion** (2LR-G): "PRISMA 筛选完成。{N} 篇论文通过纳入标准。其中经过质量评估的优秀论文 {A} 篇。需要扩大搜索范围补充还是接受当前结果？"

### Gate Failure Route
If Q2-LR check fails → review specific failure items → route to corresponding sub-step (2LR-A through 2LR-G) → fix → re-run affected sub-steps → re-evaluate gate. If still failing after 2 fix attempts → **STOP-AND-ASK** user: expand scope / relax criteria / proceed with current state. — Route back to 2LR-A (PRISMA screening), adjust inclusion/exclusion criteria and re-screen.

## Gate

The 11-item checklist below maps to the authoritative PRISMA 2020 27-item checklist
(loaded as reference `prisma-2020`). This gate confirms the minimum journal-submission subset.

### Q2-LR Gate Checklist
- [ ] Search strategy documented for ALL databases (strings, coverage dates — reproducible)
- [ ] Inclusion/exclusion criteria defined as structured table
- [ ] PRISMA 2020 flow diagram generated with all 4 tiers quantified (N₁ through N₆)
- [ ] Full-text exclusion log produced (each excluded study with reason)
- [ ] Quality assessment completed with appropriate tool per study design
- [ ] Data extraction table populated for all included studies
- [ ] Synthesis method selected and justified
- [ ] Gap analysis produced (consistent findings + contradictions + gaps + where fits)
- [ ] All DOIs in BibTeX library verified
- [ ] For systematic reviews: protocol registration number documented
- [ ] For meta-analyses: forest plot generated and heterogeneity assessed
