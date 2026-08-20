# Stage S12: Revise & Resubmit [Strategist]

**Gate:** Q12 (BLOCK) — all reviewer comments addressed, response letter complete, manuscript changes verified against response, paper-audit (fatal-only) passes.

**Goal:** Convert reviewer feedback into a structured, collegial response with verified manuscript changes.

**Needs Composers:** paper-audit-orchestration (fatal-only mode)

## Decisions

### Entry Condition (S12, line 8)
- ONLY execute when post-submission status = R&R (major revision or minor revision), routed from S11.
- ELSE → do not enter this stage.

### Reviewer Comment Parsing (S12A, lines 13-26)
For each reviewer comment:
1. Extract every individual request (one paragraph may contain 2-3 distinct requests).
2. Classify each by type:
   - **Revise text** — change wording, add clarification, restructure section.
   - **Add analysis** — run additional statistical test, provide supplementary data.
   - **Add experiment** — collect new data, run new simulation.
   - **Argue/defend** — reviewer concern addressable with existing evidence.
   - **Clarify** — reviewer misunderstood; resolvable with better explanation.
   - **Reject politely** — request is unreasonable, out of scope, or would change contribution.
3. Number every request: R1-1, R1-2, ..., R2-1, R2-2, ...

### Classification & Feasibility Assessment (S12B, lines 28-40)
For each request, determine strategy and response format:

| Request Type | Strategy | Response Format |
|-------------|----------|-----------------|
| Revise text | Accept and do | "We have revised [location] to [change]." |
| Add analysis | If data exists -> accept; if not -> explain infeasibility | "We have added [analysis] in [section]." or "This analysis requires [data] which is not available because [reason]." |
| Add experiment | If lab/field access -> accept; if constrained -> explain | "We have conducted [experiment] (see new Figure SX)." or "We acknowledge this limitation. Conducting [experiment] is beyond the scope of this revision because [reason]." |
| Argue/defend | Present evidence concisely | "We respectfully disagree. [Evidence] demonstrates that [reasoning]." |
| Clarify | Accept and rewrite | "We apologize for the lack of clarity. We have revised [section] to explain that [clarification]." |
| Reject politely | Limited to 1 out of 15+ requests max | "We appreciate this suggestion. However, [polite reason with evidence why this would not improve the paper]." |

**STOP-AND-ASK:** Present classified request list with proposed strategy for each. Ask user: "Do you agree with the classification? Any request you'd handle differently? Are there any requests you consider infeasible that I should mark as 'reject politely'?"

### Paper-Audit on Revised Manuscript (S12E, lines 70-76)
Run paper-audit in fatal-only mode (S9-Lite mode):
- 1 round only, no 4 reviewer personas.
- Check that revisions didn't introduce new structural problems.
- Check that added text matches paper's style and quality.
- IF fatal flaw found -> fix and re-run once.
- IF fatal flaws persist after 2 rounds -> STOP-AND-ASK with explicit diagnosis.

### Cross-Verification (S12F, lines 78-88)
For every "We have revised/changed/modified/added/removed" claim from response letter:
1. Locate the corresponding change in revised manuscript.
2. Verify claim matches reality.
3. IF any claim cannot be verified -> flag as `[UNVERIFIED CLAIM]` and fix before gate.

### Composer Sequence
1. composer: paper-audit-orchestration {fatal-only mode, 1 round}

## Gate

### Q12 Gate Checklist
- [ ] All reviewer comments parsed and numbered (S12A)
- [ ] Every comment classified with a response strategy (S12B)
- [ ] User confirmed response strategy (S12B STOP-AND-ASK)
- [ ] All revisions applied to manuscript source (S12C)
- [ ] Response letter drafted with change locations documented (S12C)
- [ ] Response letter audit passed: all responses aligned, located, collegial, complete (S12D)
- [ ] Revised manuscript audit passed — fatal-only (S12E)
- [ ] Cross-verification complete: every response claim confirmed in manuscript (S12F)
- [ ] Cross-verification report saved to `{output_dir}/S12_cross_verify.md`
- [ ] Revised manuscript compiles (.pdf/.docx opens without errors)
- [ ] No unresolved [UNVERIFIED CLAIM] flags

### Gate Failure Route
Q12 is BLOCK.

1. Inspect specific failed check item:
   - Reviewer comments not fully parsed -> S12A.
   - Response incomplete -> S12C.
   - Letter audit failed -> S12D.
   - Cross-verification failed (claimed change doesn't exist) -> S12F.
   - Revised manuscript audit failed -> S12E.
2. Fix, re-run affected sub-step, re-evaluate gate.
3. After 2 fix attempts still fail -> STOP-AND-ASK: whether additional data/experiments are needed, or whether to contact editor for clarification.
