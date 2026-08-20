# Incremental Update Protocol

When the user needs to change something in an earlier stage after later stages have already been completed, use this protocol to minimize rework.

## Dependency Graph (DAG)

```
# ── Idea-First ──────────────────────────────────────
S1 ──→ S0.5 ──→ S1.5 ──→ S2 ──→ S2.5 ──→ S3 ──→ S4 ──┬─→ S5 ──┬─→ S7 ──→ S8.5 ──┬─→ S8 ──→ S9 ──→ S9.5 ──→ S10 ──→ S11 ──→ S12
                                                         ├─→ S6 ──┤             │                        │
                                                         └─→ S6.5─┘             ├─→ S8.6 ──→ S8         └─→ null
                                                                                │  (venue=chinese-domestic)
                                                                                └─→ S8

# ── Idea-First (with Preprint Option) ─────────────
S1 ──→ ... ──→ S8 ──→ S8.25 ──→ S9  (when paperType=empirical/lit-review/data-paper/software-tool/benchmark)
S1 ──→ ... ──→ S8 ──→ S9         (when paperType=theory/registered-report)

# ── Idea-First: Literature Review ───────────────────
S1 ──→ S0.5 ──→ S2-LR ──→ S2.5 ──→ S3 ──→ ... (same as Idea-First from S2.5)

# ── Data-First ──────────────────────────────────────
D0 ──→ D1 ──→ D2 ──→ S0.5 ──→ ... (merges into Idea-First after S0.5)

# ── Existing-Manuscript ─────────────────────────────
S7 ──→ S8.5 ──→ ... (same as Idea-First from S8.5)

# ── Course-Assignment ───────────────────────────────
C1 ──→ C2 ──→ C3 ──→ C4 ──→ C5

# ── Thesis ──────────────────────────────────────────
T1 ──┬─→ T1.5 ──→ T2 ──→ T3 ──→ T4 ──→ T5 ──→ T6 ──┬─→ T6.5 ──→ T7
     │  (hasData=true)                                     │  (degree=master)
     └─→ T2                                              └─→ T7
```

## Stage Dependency Table

For each stage, what downstream stages it affects:

| Stage Changed | Stages Affected (must re-run or audit) | Partially Reusable |
|---------------|---------------------------------------|-------------------|
| S1 / C1 / T1 (topic) | All subsequent stages | Nothing — topic change invalidates everything |
| D0-D2 (data analysis) | S0.5 onward | Data inventory (D0) may be reusable |
| S0.5 (feasibility) | S1.5 onward | — |
| S1.5 (research design) | S2 onward | — |
| S2 / C2 / T2 (lit review) | S2.5 → S3 → S4 → S7 (citations need re-verification) | Individual figures in S5 unaffected if claims unchanged |
| S2-LR (systematic lit review) | S2.5 → S3 → S4 → S7 (PRISMA diagram, screening log, quality scores need update) | Data extraction table partially reusable if claims unchanged |
| S2.5 (novelty) | S3 → S4 (Introduction gap framing) | Discussion and Methods mostly unaffected |
| S3 (outline) | S4 (full rewrite of affected sections) | — |
| S4 (writing) | S7 (polish), S8 (compile), S9 (audit) | S5 figures, S6 citations (if citations didn't change) |
| S5 (figures) | S7 (figure-text consistency check), S8 | Other figures, S6 citations |
| S6 (citations) | S7, S8 | S5 figures |
| S6.5 (reproducibility) | S7 (methods section only) | Everything else |
| S7 (polish) | S8 (compile), S9 (audit) | — |
| S8.5 (venue) | S8 (formatting), S8.6 (if Chinese) | S7 content |
| S8 (compile) | S9 (audit) | — |
| S8.25 (preprint) | S9 (preprint DOI available for submission letter) | Everything except cover letter mention |
| T2 (lit review) | T3 → T4 → T5 → T6 (review re-run) | — |
| T3 (methodology) | T4 (methods chapter), T5 | Core chapter content unaffected |
| T4 (writing) | T5 → T6 (review loop re-run) | — |
| T5-T6 (review) | T7 (must update defense script) | PPT slides mostly reusable |
| T6.5 (blind review) | T7 (defense materials) | PPT slides mostly reusable — re-anonymize if T5-T6 changes require new citations |

## Rerun Protocol

When the user says "go back to stage N":

### Step 1: Identify Impact
1. Look up stage N in the dependency table above
2. List all stages that must be re-run
3. List outputs that are partially reusable

### Step 2: Mark Stale
1. Mark stage N and all downstream stages as `[STALE]` in the output directory
2. Move stale outputs to `{output_dir}/.stale/` (don't delete — they may contain reusable fragments)
3. Preserve reusable outputs in place

### Step 3: User Confirmation
Present before executing:

"Going back to {stage N} will invalidate: {list of affected stages}. 
Partially reusable: {list of outputs that can be preserved}.
Proceed?"

### Step 4: Re-execute
1. Start from stage N
2. All gates are enforced normally — don't skip because "it passed before"
3. For partially reusable outputs: audit before accepting (don't blindly trust stale output)
4. After each downstream stage completes, remove its `[STALE]` marker

## Critical Rule

**Gate enforcement never weakens during rerun.** If gate Q2 required 10+ verified citations the first time, it requires 10+ verified citations the second time — even if the S6 citation count previously passed with the old literature. Each gate re-evaluates against the current state of all inputs, not the historical state.

---

## Backtracking Calculator

When S7 (paper-audit) finds Critical/Major issues, use this protocol to determine the minimal set of stages that must be re-executed.

### Issue-to-Stage Mapping

Classify each S7 issue by its root cause stage:

| Issue Pattern | Root Stage | Rerun From |
|---------------|-----------|------------|
| Research question not testable / too vague / scope mismatch | S1 | S1 |
| Literature gap not clearly established / key papers missing / search incomplete | S2 | S2 |
| PRISMA flow chart incomplete / screening undocumented / quality assessment missing | S2-LR | S2-LR |
| Missing identification strategy / weak causal design / insufficient power | S1.5 | S1.5 |
| IMRAD structure broken / missing sections / contribution unclear | S3 | S3 |
| Claims unsupported / writing quality / prose issues / placeholder text | S4 | S4 |
| Figures missing / wrong type / poor quality / caption inadequate | S5 | S5 |
| Citations unverified / wrong DOIs / reference count mismatch | S6 | S6 |
| Reproducibility gaps / data not backed up / seeds not set | S6.5 | S6.5 |
| Cross-chapter inconsistency / terminology drift / data-text mismatch | T5 / C4 specific | T4 / C3 |
| Preprint not posted / license wrong / author metadata missing | S8.25 | S8.25 (re-run) |

### Minimal Rerun Algorithm

Execute these steps in order:

**Step 1: Collect.** Gather all Critical and Major issues from the S7 paper-audit report.

**Step 2: Classify.** For each issue, find the matching pattern in the Issue-to-Stage Mapping table. Record the root stage. If an issue doesn't match any pattern, default to S4 (writing — the most common root cause).

**Step 3: Map to DAG.** For each root stage found, use the Dependency Graph (above) to list ALL downstream stages that depend on it. Take the union of all affected stages across all root stages.

**Step 4: Find earliest start.** Among all root stages, pick the one that appears earliest in the pipeline sequence. This is the minimal re-execution start point.

**Step 5: Present to user:**
```
S7 paper-audit found {N} issues classified to {M} root stages:
  Root stage(s): {list}
  Minimal rerun: start from {earliest stage}, re-execute through S7
  Stages affected: {list}
  Partially reusable: {list from dependency table}

Proceed with rerun from {earliest stage}?
```
- **Option A ("Rerun from start"):** Re-execute from the earliest root stage through S7. All gates enforced normally.
- **Option B ("Targeted fix"):** Only re-execute root stages + their direct dependents. Faster but may miss cascading issues. Only recommended when the affected set is small (≤3 stages) and has no cross-stage dependencies.

### Example

S7 audit produces 3 issues:
1. "Literature gap does not clearly position the paper" → root: S2
2. "Methods section missing power analysis" → root: S1.5
3. "Figure 2 caption incomplete" → root: S5

DAG lookup:
- S2 affects: S2.5 → S3 → S4 → S7
- S1.5 affects: S2 → S2.5 → S3 → S4 → S7
- S5 affects: S7 (figure-text check), S8

Earliest start: S1.5. Union of affected stages: S1.5 → S2 → S2.5 → S3 → S4 → S5 → S7.

Presentation: "Minimal rerun: start from S1.5, re-execute through S7. Partially reusable: S6 citations, S6.5 reproducibility (if citations didn't change)."
