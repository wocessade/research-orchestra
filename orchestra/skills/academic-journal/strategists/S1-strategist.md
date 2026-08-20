# Stage S1: Research Question Formulation [Strategist]

**Gate:** Q1 (BLOCK) — question must be specific, testable, and stated in one sentence.
**Goal:** Turn a vague interest into a specific, testable, and significant research question.
**Needs Composers:** style-profile-apply (conditional — only when user provides writing samples)

## Decisions

### Research-engine handoff preload (P0/P1 align)

IF `{research_root}/.research/handoff/` exists (search: paper_dir parent, cwd, or user-stated research root):

1. Load `handoff/ready_for_writing.md` **before** brainstorming a fresh RQ from scratch.
2. Prefer verified EXP → Ci seeds from the handoff table; do not invent new strong numbers.
3. Respect **Forbidden hard-claims** (NEG list) — keep them out of Q1 one-sentence claims as asserted facts.
4. Protocol: `../academic-research-engine/references/handoff-to-writing.md` + `../academic-shared/research/schemas.md`.
5. If handoff `user_confirmed_handoff` is false → STOP-AND-ASK before treating evidence as locked.

ELSE → proceed with normal S1 flow.

### Axis Routing
S1 is the Idea-First entry point. No prior passport routing.

### Conditional Branches

**Branch 1: Style Calibration (S1, line 17)**
- IF user provides prior writing samples (published papers, coursework, etc.) → execute 1A.0 Style Calibration: extract 4-dimension style profile using style_extractor.md (sentence, vocabulary, structure, citation). Run style_analyzer.py to produce Style Profile JSON → write to passport.style_profile. Note: hedging density and register are NOT auto-extractable; flag as manual enhancement for S7 polish stage if needed.
- Then invoke composer `style-profile-apply` if profile was extracted.
- ELSE (no writing samples) → skip, `passport.style_profile` remains null.

**Branch 2: Preregistration Record (S1, line 33)**
- IF user has preregistration (OSF, ClinicalTrials.gov, AsPredicted, etc.) → execute 1A.1: extract hypotheses, outcome measures, analysis plan, sample size calculation. Compute SHA-256 first 12 chars. Write to `passport.preregistration`.
- ELSE (no preregistration) → skip, `passport.preregistration` remains null.

### Redundancy Strategy (DP25, Mode B x3)
Research question generation uses Mode B x3 redundancy (DP25, S1 lines 11-14):
- 3 agents independently generate research questions from same input (topic description + FINER criteria).
- Each outputs: one-sentence question + three-paragraph argument.
- Orchestrator compares 3 outputs:
  - High agreement → pass through directly
  - Partial agreement → merge intersection
  - Low agreement → STOP-AND-ASK: present all three to user for selection

### Question Type → Design Type Routing (S1, lines 129-140)
After FINER check passes, classify question type to determine next stage:

| Question Type | Implies | Next Stage |
|---------------|---------|------------|
| Causal / Associational | Requires identification strategy | Route to S0.5 → S1.5 (full pass) |
| Descriptive / Comparative | Observational or survey design | Route to S0.5 → S1.5 (light pass) |
| Predictive | ML validation framework | Route to S0.5 → S1.5 (light pass) |
| Literature review / Theory / Conceptual | No empirical design needed | Route to S0.5 → S2 (skip S1.5) |
| Data paper / Software/Tool / Benchmark | No empirical design needed | Route to S0.5 → S2 (skip S1.5) |

### Composer Sequence
1. composer: style-profile-apply {conditional — only when `passport.style_profile` is non-null}

### STOP-AND-ASK Points
- **S1 Mode B comparison:** If 3 agents produce low-agreement questions → present all to user for selection.
- **Q1 failure (after 2 fix attempts):** Ask user: expand scope, relax standards, or proceed-as-is.

## Gate

### Q1 Gate Checklist
- [ ] Question stated in one sentence
- [ ] All 5 FINER criteria pass
- [ ] Question type matches planned method
- [ ] Can name 3-5 papers that would appear in the Introduction

### Gate Failure Route
Q1 is BLOCK.

1. First failure → identify which FINER criteria failed → route back to corresponding sub-step for repair → re-run affected sub-steps → re-evaluate gate.
2. After 2 fix attempts still fail → STOP-AND-ASK: ask user whether to (a) expand scope, (b) relax standards, or (c) proceed-as-is.
