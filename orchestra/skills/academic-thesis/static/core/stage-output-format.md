# Stage Output Format

Every stage must produce a standardized output block when its gate passes. This ensures consistency across stages, makes session persistence captures useful, and gives the user a clear picture of progress.

## Standard Output Block

```markdown
## Stage {N} Complete: {Stage Name}
**Gate Status:** Q{N} ✓ PASS
**Output Files:**
- `{output_dir}/S{N}_{name}.md` — {description}
- `{output_dir}/S{N}_{name}.csv` — {description} (if applicable)
**Decisions Made:**
- {decision 1}
- {decision 2}
**To Next Stage:** {what was passed downstream — key artifacts, unresolved warnings, deferred decisions}
```

## Stage-Specific Examples

### S2 (Literature Review)
```markdown
## Stage 2 Complete: Literature Review & Gap Analysis
**Gate Status:** Q2 ✓ PASS
**Output Files:**
- `output/S2_lit_review.md` — Thematic literature synthesis (4 themes, 32 papers)
- `output/S2_gap_analysis.md` — Identified research gap with supporting evidence
- `output/S2_bibliography.bib` — Cleaned BibTeX (32 entries, DOI-verified)
**Decisions Made:**
- Research gap: {one-line description}
- Theoretical framework: {framework name or "grounded/inductive"}
**To Next Stage:** Bibliography (32 refs), gap statement, competing papers table → S2.5 Novelty Audit
```

### S4 (Writing)
```markdown
## Stage 4 Complete: First Draft
**Gate Status:** Q4 ✓ PASS
**Output Files:**
- `output/S4_draft.md` — Complete first draft (~6,200 words)
- `output/S4_figure_placeholders.md` — 3 figure placeholders with captions
**Decisions Made:**
- Structure: IMRAD (standard)
- Target length: ~6,000 words (journal-dependent, adjust at S8)
**To Next Stage:** Draft manuscript + figure specs → S5+S6+S6.5 (parallel group)
```

### S7 (Polish)
```markdown
## Stage 7 Complete: Polish & De-AI
**Gate Status:** Q7 ✓ PASS
**Output Files:**
- `output/S7_polished.md` — Polished manuscript
- `output/S7_audit_report.md` — paper-audit report (0 Critical, 0 Major, 3 Minor)
**Decisions Made:**
- De-AI pass: 1 round (language=zh, chinese-de-ai-quick-ref applied)
- paper-audit: all Critical/Major resolved, 3 Minor deferred to S9
**To Next Stage:** Polished manuscript + audit baseline → S8.5 Venue Selection
```

### T4 (Thesis Writing)
```markdown
## Stage 4 Complete: 核心章节撰写
**Gate Status:** QT4 ✓ PASS
**Output Files:**
- `output/T4_thesis.tex` — Complete thesis (~32,000 words, master)
- `output/T4_封面.tex` — Cover page
- `output/T4_摘要.tex` — Chinese + English abstracts
**Decisions Made:**
- Chapter order: 绪论 → 文献综述 → 研究方法 → {core chapters} → 结论
- Writing format: LaTeX (ctexbook)
**To Next Stage:** Complete thesis draft → T5 四线并行审查
```

## Failure Output

When a gate fails, the output format changes:

```markdown
## Stage {N} Blocked: {Stage Name}
**Gate Status:** Q{N} ✗ BLOCK
**Failed Items:**
- {item 1} — {why it failed}
- {item 2} — {why it failed}
**Action Required:** {what to fix and where to return}
**Salvageable Output:** {what was produced before the block — don't discard}
```

## Rules

1. Output the block immediately after gate evaluation — don't bury it in narrative
2. File paths must be relative to `output_dir` — the session persistence system reads these
3. "Decisions Made" captures irreversible choices — things downstream stages must respect
4. "To Next Stage" is the handoff — it tells the next stage what to expect and what to use
5. Never include speculative future-stage decisions in the output block
