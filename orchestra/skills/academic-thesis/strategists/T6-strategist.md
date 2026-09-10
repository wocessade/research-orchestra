# Stage T6: 修订与收敛 [Strategist]

**Gate:** QT6 (SOFT BLOCK)
**Goal:** Iteratively revise the thesis based on T5 audit findings until quality converges to acceptable threshold, then polish.
**Needs Composers:** [de-ai-detect, polish-protocols]

## Decisions

### Rewrite Matrix (P1)

For major 章节修订 (not typo fixes):

1. Maintain `{paper_dir}/.paper/rewrite_matrix.md` per `../academic-shared/rewrite/rewrite-matrix.md`.
2. Closed-book when fixing logic / evidence alignment.
3. QT6: rows blocking Critical/Major require verified fixes (`done`). A non-critical scope limitation may be explicitly accepted under convergence-loop.md; a waiver cannot close a Critical evidence defect.

### Issues / backfill (if empirical chapters still placeholder)

Follow `../academic-shared/issues/results-backfill.md` before strengthening 结论.


### Axis 1: Degeneration Detection (M3 Memory Check)
```
before each convergence round:
    run M3 memory check from attention-defense.md
    
    check: does any previously fixed issue reappear?
    - query attention-defense.md memory store for previously fixed items
    - compare current state of flagged locations
    
    if previously fixed issue reappears:
        → PAUSE — do not proceed with convergence
        → re-evaluate root cause:
            a) fix was incomplete (surface-level only)
            b) fix introduced new issue that manifests as old symptom
            c) regeneration overwrote fix (template regeneration issue)
        → document root cause
        → apply targeted fix, not blanket re-generation
        → [DEGENERATION-DETECTED] flag
```

### Axis 2: Plagiarism Integration (Conditional)
```
if user provides plagiarism report file:
    → load T6-plagiarism-check.md
    → parse report for: similarity_percentage, flagged_passages
    
    for each flagged passage:
        if passage.similarity >= 2.5 (Priority 2.5+):
            → treat as Critical issue
            → must be rewritten before convergence
        elif passage.similarity in [1.0, 2.5):
            → treat as Major issue
            → should be rewritten before convergence
        elif passage.similarity < 1.0:
            → note but no action required
    
    integration:
        → merge plagiarism findings with T5 audit findings
        → plagiarism Critical issues block convergence same as T5 Critical

elif no plagiarism report:
    → skip plagiarism check
    → no action
```

### Axis 3: Convergence Criteria

Follow `static/core/convergence-loop.md`. Track REVIEW_STABLE separately from READY: READY requires zero open Critical/Major in the cumulative register and no regression. Missing issues in the latest report remain open until the fix is checked. Maximum three rounds; at the limit deliver an unfinished draft with precise open issues, without passing QT6 or automatically advancing.

After post-expansion T5 returns, T6 repairs that revised manuscript. Record expansion_recheck_complete only after READY; do not trigger T6.7 again from keywords already handled. An additional expansion needs a new user request.

### Axis 4: T6A-Vocab — Conditional Vocabulary Polish
```
activation_conditions (OR):
    - ai_tone_score < 75  (from de-ai-detect output)
    - user explicitly mentions: "词汇单调", "用词重复", "vocabulary"

if activated:
    → run vocabulary diversity pass
    → target: frequently repeated terms (5+ occurrences within 2 pages)
    → replace with synonyms, adjust sentence structure
    → do NOT change technical terms, proper nouns, or established field terminology
    → re-check ai_tone_score after pass
    → [T6A-VOCAB-APPLIED] flag

if not activated:
    → skip vocabulary pass
```

### Axis 5: Hidden Branch — T6X Activation
```
trigger_keywords = ["注水", "降AI", "查重", "AIGC", "提交版"]

if any trigger_keyword in user_message:
    → STOP-AND-ASK
    → present: "I noticed you mentioned [keyword]. Would you like to activate the pre-submission expansion process (T6.7)?"
    → if user confirms:
        → route to T6.7-strategist.md
    → if user declines:
        → continue with T6 as normal
    → if unclear:
        → ask user to clarify intent
```

## Gate

### QT6 Gate Checklist
- [ ] Degeneration check passed (no regression)
- [ ] Plagiarism integrated (if report available)
- [ ] REVIEW_STABLE and READY recorded; all open Critical/Major resolved or non-critical limitations explicitly accepted by user
- [ ] T6A-vocab decision made
- [ ] T6X branch checked and routed
- [ ] Caveats documented (if non-converged)
- [ ] All Critical issues resolved on the current manuscript; documentation alone is not resolution

### Gate Failure Route
```
if degeneration detected 3 consecutive rounds:
    → SOFT BLOCK — switch strategy: manual fix over auto-generation
    → recommend user intervene for specific sections
if plagiarism Critical issues remain unresolved:
    → SOFT BLOCK — cannot deliver with high-similarity passages
    → must rewrite before proceeding to QT6.5/QT7
if convergence not reached within hard limit:
    → deliver unfinished draft and open issue register; keep QT6 unpassed
    → do not automatically route to final blind review or defense
```
