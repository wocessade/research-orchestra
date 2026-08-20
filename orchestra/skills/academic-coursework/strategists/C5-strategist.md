# Stage C5: 修订与收敛 [Strategist]

**Gate:** QC5 (BLOCK)
**Goal:** Fix all issues identified in QC4, converge to acceptable quality, and detect hidden triggers for C5.5 (注水)
**Needs Composers:** [polish-protocols]

## Decisions

### Axis Routing

#### Plagiarism Report Integration
- If user provides a plagiarism checker report file (知网/维普/PaperPass/格子达 etc.), parse it and route findings into the revision loop:
  - Similarity >= 2.0% per source → **Critical** (rewrite affected passage)
  - Similarity 1.0%-2.0% → **Major** (rephrase with synonym replacement)
  - Similarity < 1.0% → **Info** (document, no action required)
- Merge plagiarism findings with C4 review findings before entering convergence loop
- After fixes applied, re-run affected paragraphs through de-ai-detect to ensure rewrites haven't introduced new AI patterns

#### Degeneration Detection
- Run M3 memory check from `attention-defense.md`:
  - Compare current issue list against previously-fixed issue list
  - If a previously-fixed issue reappears:
    - Pause automatic fixing
    - Re-evaluate root cause: was the fix incomplete, or did regeneration reintroduce it?
    - Log `[DEGENERATION-REVIVED]` on the issue
    - Apply a different fix strategy (not the same one that failed)

#### C5-Specific Fix Method
Route to fix method based on issue type:

| Issue Type      | Fix Method                                      |
|-----------------|-------------------------------------------------|
| Content (logic, depth, structure) | Edit the python-docx generation script and regenerate .docx — ensures fixes persist across rounds |
| AI tone         | Rewrite affected paragraphs via `de-ai-detect` cleanup pass, then update script |
| Format (fonts, spacing, styles) | Modify python-docx generation script and re-run |
| Citation errors  | Fix reference entries in script, renumber by first-appearance order |

#### Convergence Loop
- Run fix → re-evaluate against QC5 checklist
- **Convergence condition:** New Critical = 0 AND New Major <= 2
- **Hard limit:** 3 rounds without convergence:
  - Deliver current draft with caveat document listing all remaining issues
  - Log `[CONVERGENCE-LIMIT-REACHED]`
  - Do NOT continue looping indefinitely

#### C5X Hidden Trigger (注水 Detection)
- Check if user has mentioned any of these keywords in conversation or task context:
  - 注水 (padding)
  - 降AI (reduce AI detectability)
  - 查重 (plagiarism check)
  - AIGC (AI-generated content bypass)
  - 提交版 (submission version)
- If triggered → STOP-AND-ASK:
  - Present: "Detected possible intent for AIGC watermarking / padding. Open C5.5 preparation module?"
  - If user confirms → route to C5.5 (注水 strategist)
  - If user declines → continue normal convergence

### Composer Sequence
1. **composer:** polish-protocols {mode: convergence_loop, draft_path: <path>, issue_list: <qc4_findings>, max_rounds: 3}

## Gate

### QC5 Gate Checklist
- [ ] All QC4 Critical issues are fixed
- [ ] Plagiarism report integrated (if provided): all similarity >= 2.0% passages rewritten, >= 1.0% passages rephrased
- [ ] Rewritten passages passed de-ai-detect recheck (no new AI patterns introduced)
- [ ] New Critical issues == 0
- [ ] New Major issues <= 2
- [ ] No degeneration detected (or diagnosed and resolved)
- [ ] Convergence within 3 rounds (or caveat delivered)
- [ ] C5X check performed (注水 trigger evaluated)

### Gate Failure Route
- Failed QC5 → route to C5A (fix remaining issues):
  - C5A collects remaining issues
  - Apply targeted fix based on issue type table
  - Re-enter convergence loop (re-evaluate)
