# Composer: paper-audit-orchestration

**Purpose:** Orchestrate paper quality audit by running paper-audit.md as the primary mechanism, with an optional 3-referee parallel enhancement for high-stakes submissions.
**Used by:** academic-journal S7 (7B structural polish), any stage requiring consolidated quality assessment
**Parameters:** `{entry_type}` (existing-manuscript/idea-first/data-first), `{use_multi_referee}` (true/false, default false)

## Instructions

### 1. Primary Audit Mechanism

Run `skills-embedded/paper-audit.md` first as the primary audit mechanism. It produces severity-rated findings:

| Severity | Meaning | Action |
|----------|---------|--------|
| Critical | Blocks Q7 gate | Must be fixed before proceeding |
| Major | Significant issue | Must be fixed before Pass 2 |
| Moderate | Notable issue | Fix what you can, acknowledge the rest |
| Minor | Advisory | Document and proceed |

Do NOT begin sentence-level polish until the structural audit passes. All Critical and Major items must be fixed before Pass 2 (language polish).

### 2. Multi-Referee Review Model (Optional Enhancement)

For high-stakes submissions (user explicitly requests, Route A Summit Push, or paper-audit returns borderline PASS with moderate items needing multi-angle assessment), upgrade the single-perspective audit to a 3-referee parallel model.

**Dispatch 3 referees in parallel:**

**Referee 1: Technical Correctness & Methodology**
Focus: Data validity, statistical methods, identification strategy, reproducibility.
- Are methods appropriate for the claims?
- Are statistical tests correct and adequately reported?
- Is sample size adequate? Any power analysis?
- Can results be reproduced from the description alone?
- Hidden flaws: confounding, selection bias, p-hacking?

**Referee 2: Novelty & Significance**
Focus: Contribution originality, literature positioning, field impact.
- Does this paper advance the field beyond published work?
- Is the novelty incremental or substantive?
- Are claims proportional to the evidence?
- Would publishing this change what researchers do?

**Referee 3: Presentation & Clarity**
Focus: Writing quality, figure clarity, structural logic, accessibility.
- Is the argument easy to follow?
- Do figures convey information without reading text?
- Is terminology consistent and defined?
- Is the paper appropriate length for its contribution?

### 3. Merge Protocol (after all 3 complete)

1. **Create a consensus matrix:** each issue rated by R1/R2/R3, flag conflicts
2. **Conflict resolution:**
   - R1+R2 agree, R3 disagrees -> prefer R1+R2 for content, R3 for presentation
   - All three disagree -> flag "needs author judgment"
   - R1 Critical + R3 Minor on same issue -> prioritize R1 (technical correctness trumps presentation)
3. **Severity calibration:**
   - A Critical from any single referee = Critical in consolidated list
   - Two Majors on same issue from different referees -> upgrade to Critical
4. **Output** consolidated list with referee source tags and conflict annotations

### 4. Execution Order

1. Run `skills-embedded/paper-audit.md` (single perspective)
2. If `use_multi_referee=true` AND (user requested OR Route A Summit Push OR borderline PASS):
   a. Run 3-referee parallel model
   b. Execute merge protocol (consensus matrix, conflict resolution, severity calibration)
   c. Produce consolidated issue list with referee source tags
3. Fix all Critical and Major items
4. Proceed to Pass 2 (language polish) only after structural audit passes

The 3-referee model runs BEFORE language polish. Structural issues must be resolved before sentence-level editing begins.

## Verification

- [ ] `skills-embedded/paper-audit.md` executed and severity-rated findings produced
- [ ] All Critical items fixed (blocks gate if any remain)
- [ ] All Major items fixed before Pass 2
- [ ] If multi-referee model used: all 3 referees dispatched
- [ ] If multi-referee model used: consensus matrix created with conflict annotations
- [ ] If multi-referee model used: severity calibrated (single Critical = Critical, two Majors on same issue = upgrade)
- [ ] If multi-referee model used: consolidated issue list with referee source tags produced
- [ ] Structural audit passes before sentence-level polish begins

## Common Pitfalls

- **Skipping the primary audit:** Going straight to multi-referee without first running paper-audit.md. The single-perspective audit is sufficient for most papers — the 3-referee model is optional.
- **Polishing before audit passes:** Running language polish while Critical structural issues remain. Structural edits may delete or rewrite polished sentences.
- **Ignoring conflict resolution:** Producing three separate referee reports without merging. Every issue must appear in the consolidated list with a single severity rating.
- **Technical correctness downgraded by presentation bias:** R3 finding something "unclear" while R1 finds it "correct" — R1's technical assessment takes priority over R3's presentation concern.
- **Upgrading without cross-referee evidence:** upgrading Moderate to Critical based on a single referee's opinion. Two Majors from different referees on the same issue is the minimum threshold for upgrade.
