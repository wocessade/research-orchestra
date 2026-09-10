# Composer: factual-accuracy-check

**Purpose:** Run a standalone factual accuracy audit on the polished manuscript across 6 dimensions, dispatching a subagent via stage_agents.md.
**Used by:** academic-journal S7 (7G), any stage requiring factual accuracy verification before gate
**Parameters:** `{output_dir}`, `{pipeline_root}`, `{has_source_documents}` (true/false)

## Instructions

### 1. Launch Procedure

1. Load the agent prompt from `{pipeline_root}/evaluate/stage_agents.md`
2. Dispatch the `factual_accuracy` agent via `stage_agents.md` routing
3. Provide the polished manuscript text to the agent
4. The agent checks 6 dimensions (see Section 2)
5. Agent writes results to `{output_dir}/agent_reports/factual_accuracy_review.md`
6. The report follows a 3-part format: annotated text / explanation / change log

### 2. Six Audit Dimensions

| # | Dimension | What It Checks | Always Runs? |
|---|-----------|----------------|-------------|
| 1 | Structure-data consistency | Do stated chapter/section counts match the actual document? | Yes |
| 2 | Cross-reference validity | Do referenced items (Figure X, Table Y) actually exist? | Yes |
| 3 | Numerical consistency | Is the same data point reported consistently throughout? | Yes |
| 4 | Terminology consistency | Is the same concept referred to with the same term throughout? | Yes |
| 5 | Internal contradiction | Does the paper contradict itself anywhere? | Yes |
| 6 | Source-document alignment | Does the manuscript match the source documents? | Only when source docs exist |

**If no source documents are provided:** Run dimensions 1-5 plus the ledger coverage audit; record unavailable source support and classify core evidence gaps by impact.

### 3. Severity Classification

| Severity | Meaning | Action |
|----------|---------|--------|
| Critical | Blocks Q7 gate | Must be fixed — same severity as paper-audit Critical items |
| Major | Must be addressed | Resolved or explicitly accepted as a non-critical scope limitation under convergence-loop.md; evidence defects remain open |
| Minor | Advisory | Can be acknowledged without action |

### 4. Documenting Results

The agent writes results to `{output_dir}/agent_reports/factual_accuracy_review.md` following the 3-part format:

1. **Annotated text** — the manuscript text with inline annotations showing each finding
2. **Explanation** — detailed explanation of each finding, including severity
3. **Change log** — what was changed (or deferred) and why

### 5. Execution Summary

```
1. Load agent prompt from {pipeline_root}/evaluate/stage_agents.md
2. Dispatch factual_accuracy subagent with manuscript text
3. Agent runs internal/source checks plus current-manuscript ledger coverage; unavailable sources remain unverified
4. Results written to {output_dir}/agent_reports/factual_accuracy_review.md
5. All Critical errors resolved before gate
6. Major errors resolved under convergence-loop.md; no waiver of evidence defects
7. Minor errors documented as advisory
```

## Verification

- [ ] `factual_accuracy` agent prompt loaded from `{pipeline_root}/evaluate/stage_agents.md`
- [ ] Agent dispatched with complete polished manuscript text
- [ ] Internal/source checks and ledger coverage completed; unavailable support recorded explicitly
- [ ] Report written to `{output_dir}/agent_reports/factual_accuracy_review.md`
- [ ] Report follows 3-part format (annotated text / explanation / change log)
- [ ] No Critical factual errors remain (blocks Q7 gate)
- [ ] All Major errors resolved under convergence-loop.md; accepted scope limitations recorded separately
- [ ] Minor errors documented as advisory

## Common Pitfalls

- **Skipping the agent prompt:** Running the check without loading `stage_agents.md` means the agent lacks the domain-specific factual accuracy rubric. Always load the prompt.
- **Failing to distinguish source-document alignment from internal consistency:** When no source documents exist, dimension 6 is not applicable. Do not invent an error in an unavailable source. Still record concrete unsupported core claims and the evidence needed to verify them.
- **Treating Minor findings as blockers:** Minor factual issues are advisory. Spending time fixing every comma or phrasing inconsistency in the accuracy pass distracts from real Critical/Major issues.
- **Overlapping with paper-audit:** Factual accuracy focuses on objective truth (numbers, cross-references, contradictions), while paper-audit focuses on writing quality and argument strength. Keep the audits separate — do not merge them.
- **Deferring without documentation:** Only a non-critical scope limitation may be explicitly accepted under convergence-loop.md. Missing core evidence remains open; a deferred label cannot pass the gate.
