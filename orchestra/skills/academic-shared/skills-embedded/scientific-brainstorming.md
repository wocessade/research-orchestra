# Scientific Brainstorming (Embedded)

**Source:** `scientific-brainstorming` v1.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S1 (Idea → Research Question), C1 (Topic & Arguments), T1 (选题)

## Core Principles
1. **Conversational & Collaborative** — equal thought partner, not instructor
2. **Intellectually Curious** — probing questions showing deep understanding
3. **Creatively Challenging** — push beyond obvious ideas, challenge assumptions
4. **Domain-Aware** — cross-pollination across fields
5. **Structured yet Flexible** — purpose-driven but adaptive

## Brainstorming Workflow

### Phase 0: Landscape Grounding (NEW)

When called from a pipeline stage that has already run a literature landscape scan (T1A-PRE for thesis, S1-PRE for journal papers, C1-PRE for course assignments), do NOT start brainstorming immediately. Instead:

1. Read the landscape analysis file from the calling stage:
   - Thesis (T1): `{output_dir}/t1_landscape_analysis.md`
   - Journal (S1): `{output_dir}/s1_landscape_analysis.md`
   - Course assignment (C1): `{output_dir}/c1_reference_availability.md` (lighter, just availability check)
2. Ground all subsequent phases in actual literature:
   - Phase 2 (Divergent Exploration): explicitly reference specific seed papers and gaps from the landscape
   - Phase 4 (Critical Evaluation): score novelty against the landscape scan data, not against "does this feel new?" intuition
3. Flag any candidate that has no literature grounding as `[WARNING: ungrounded]` — this candidate should either be grounded or dropped.
4. If no landscape analysis exists (e.g., standalone brainstorming, not pipeline-initiated), skip Phase 0 and proceed to Phase 1 normally.

### Phase 1: Understanding Context
- Ask open-ended questions about current research/interests/challenge
- Understand field, methodology, and constraints
- Identify implicit assumptions or unexplored angles

### Phase 2: Divergent Exploration
Techniques: **Cross-Domain Analogies**, **Assumption Reversal** ("What if opposite were true?"),
**Scale Shifting** (molecular to ecosystem), **Constraint Removal/Addition**,
**Interdisciplinary Fusion**, **Technology Speculation**

### Phase 3: Connection Making
Identify patterns, themes, unexpected connections among generated ideas.

### Phase 4: Critical Evaluation
Score promising ideas: feasibility, novelty, obstacles, resources needed.

### Phase 5: Synthesis & Next Steps
Summarize promising directions, highlight novel connections, suggest next steps.

## FINER Framework (for S1 Q1 gate)
- **F**easible — data/methods/tools exist?
- **I**nteresting — would anyone outside your lab care?
- **N**ovel — what new does this add?
- **E**thical — IRB/ethics board approvable?
- **R**elevant — connects to broader literature/problem?
