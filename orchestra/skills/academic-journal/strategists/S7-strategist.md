# Stage S7: Polish & Review [Strategist]

**Gate:** Q7 (BLOCK) — paper-audit returns PASS, no Critical or Major items remain.

**Goal:** Transform draft text into publication-quality prose that reads like a senior human expert wrote it.

### LaTeX de-AI / polish (writingFormat=latex)

IF `writingFormat == latex`:
1. Load `../academic-latex/references/style-de-ai.md` safety zones (do not rewrite math/cite/label/siunitx).
2. Prefer in-place `.tex` edits over round-trip conversion.
3. After polish batches, re-run `python ../academic-latex/scripts/verify_paper.py {paper_tex_root}` and a quick latexmk pass on touched files.
4. Figure-text consistency: captions vs `.paper/figure_inventory.md` (academic-plotting).


**Needs Composers:** paper-audit-orchestration, factual-accuracy-check, style-profile-apply, de-ai-detect, polish-protocols, literature-precheck

## Decisions

### Tool Commands (S7)

### Rewrite Matrix (P1)

IF Critical/Major items require paragraph/section rewrites:
1. Log rows in `.paper/rewrite_matrix.md` (`../academic-shared/rewrite/rewrite-matrix.md`).
2. Prefer closed-book rewrites from evidence sources (not synonym stacking).
3. Mark rows `done` before claiming Q7 pass.


- `/de-ai` → `../academic-shared/commands/de-ai.md` (standalone De-AI pass; complements composer de-ai-detect).
- IF `writingFormat=latex` → keep math/cite safety zones in `../academic-latex/references/style-de-ai.md`.


### Entry Type Routing (S7, lines 11-19)
Before execution, inspect `.pipeline_state.json` -> `axes.entry_point`:

- IF `entry_point == "existing-manuscript"` → mandatory risk acknowledgement (citations unverified, reproducibility undocumented, claim structure unchecked, design unaudited, literature gap possible). User must confirm each risk item before S7 polishing begins. IF user cannot confirm citation accuracy or replicability → recommend exiting and re-entering via `entry_point: idea-first` or `data-first`.
- IF `entry_point == "partial-manuscript"` → **gradient risk confirmation:**

  Load `passport.gap_fill_plan`, stratify by provenance:

  | Section Group | Source | Risk | De-AI Intensity | Style Check |
  |---------------|--------|------|-----------------|-------------|
  | Complete sections | Author | Lowest | Minimal/quick scan only | Used as style authority reference |
  | Partial sections (after supplement) | Mixed | Medium | Moderate scan | Checked against Complete sections |
  | Placeholder/Missing sections | AI | Higher | Aggressive scan | Must match Complete section style |

  Confirmation prompt lists:
  1. List of AI-written gap sections
  2. List of author-written Complete sections (not reviewed)
  3. Verification requirements: (a) AI content factually correct, (b) new-to-old transitions seamless, (c) terminology consistent
  4. Citation verification: verify gap-section citations only; spot-check 10% of existing citations
  5. Audit focus: structural consistency at new-old boundaries

  S7D.5 style consistency check MUST use Complete-sections-as-reference approach — AI section deviations from author style flagged as **Major** (not Minor).

- IF `entry_point == "idea-first"` or `"data-first"` → risk prompts are informational only, proceed normally.
- IF state file is missing → proactively ask user for entry type.

### Language Axis Auto-Load (S7, line 21)
- IF language == `en` → auto-load `english-de-ai-quick-ref.md` (~120 lines). Full `english-de-ai-guide.md` (~970 lines) loaded only on user request for deep De-AI scan.
- IF language == `zh` → auto-load `chinese-de-ai-quick-ref.md` (~100 lines). Full `chinese-de-ai-guide.md` loaded for deep scan on request.

### Polish Loop (S7A, lines 32-40)
Mandatory minimum 2 passes: POLISH -> AUDIT -> FIX BLOCKERS -> RE-POLISH -> RE-AUDIT.

**Correctness threshold:** IF paper-audit returns PASS with zero Critical/Major items AND De-AI check finds zero flags → output confirmation: "This manuscript reads as human-written academic prose. No structural or language edits needed." Do NOT iterate further — over-polishing degrades quality.

### Multi-Referee Review (7B-ALT, lines 53-89)
Optional enhancement — used when:
- User explicitly requests, OR
- Route A Summit Push (CNS-targeted), OR
- `paper-audit` returns borderline PASS with moderate items needing multi-angle assessment.

If triggered: Dispatch 3 referees in parallel (Technical Correctness, Novelty & Significance, Presentation & Clarity).

**Conflict resolution:**
- R1+R2 agree, R3 disagrees → prefer R1+R2 for content, R3 for presentation.
- All three disagree → flag "needs author judgment."
- R1 Critical + R3 Minor on same issue → prioritize R1 (technical correctness trumps presentation).
- Two Majors on same issue from different referees → upgrade to Critical.

Multi-referee model runs BEFORE S7C (language polish). Structural issues must resolve before sentence-level editing.

### Polish Pass Routing (S7C, lines 91-109)

| Section | Pass Focus |
|---------|-----------|
| Abstract | 150-250 words max. State problem, method, key result, implication. |
| Introduction | Funnel structure: broad context -> specific gap -> your question -> approach. End with clear contribution statement. |
| Methods | Past tense, passive voice acceptable. Reproducibility goal. |
| Results | Past tense. Report effect sizes AND p-values. Lead with data. |
| Discussion | Start with answer. Then compare, explain unexpected, acknowledge limits, state implications. |
| Conclusion | No new info. Summarize contribution + one forward-looking sentence. |

### Style Consistency Check (7D.5, lines 142-159) — Conditional
- IF `passport.style_profile` exists in `.pipeline_state.json` -> compare manuscript against profile across 6 dimensions. Unacceptable deviations → record as Minor items.
- IF `passport.style_profile` is null → skip this step entirely.

### De-AI Language Routing (7D/7D-zh)
- English: load english-de-ai-guide.md for 16-dimension detection. Use dimension-specific rules per section.
- Chinese: load chinese-de-ai-guide.md for 19-dimension detection. Dual abstract mismatch -> Major item at Q7 gate.
- **NNES caveat:** Raise thresholds by 30% for D2/D5. Deep features (D12, D13, D15) are safer diagnostics than surface lexical features.

### Factual Accuracy Check (7G, lines 193-218)
Run standalone factual accuracy audit BEFORE Q7 gate.

**Conditional source-document handling:**
- IF source documents exist → run all 6 dimensions (structure-data consistency, cross-reference validity, numerical consistency, terminology consistency, internal contradiction, source-document alignment).
- IF no source documents provided → run dimensions 1-5 only (internal consistency). Agent notes the limitation.

### Composer Sequence
1. composer: literature-precheck {batch-verify all DOIs via OpenAlex API; then spot-check 5 random citations for claim-to-citation alignment}
2. composer: paper-audit-orchestration {first pass — structural/severity audit}
3. composer: polish-protocols {section-specific polish per S7C routing}
4. composer: de-ai-detect {language-specific De-AI scan}
5. composer: style-profile-apply {conditional — only when `passport.style_profile` is non-null}
6. composer: factual-accuracy-check {standalone factual accuracy audit}
7. composer: paper-audit-orchestration {re-audit after fixes — verify no Critical/Major remain}

## Gate

### Q7 Gate Checklist
- [ ] Literature verification pre-check complete — all DOIs passed existence checks (existing-manuscript: verify ALL; normal: spot-check at least 20%)
- [ ] No fabricated/fictional references (Critical item)
- [ ] Cited papers' titles/authors/sources/years match API results (Major items fixed)
- [ ] Spot-check: verify 5 random citations for claim-to-citation alignment
- [ ] paper-audit returns PASS (or PASS with only moderate/minor advisory items). All Critical and Major items fixed. (If Major items remain: go back to relevant stage — don't polish past structural problems. Moderate/minor only: fix what you can, acknowledge the rest. If moderate/minor items persist after 2 polish passes with no improvement → go back to S3 or re-examine outline structure.)
- [ ] If multi-referee model used: cross-review synthesis complete, conflicts resolved, consolidated issue list with referee source tags
- [ ] De-AI pass complete — no AI rhythm patterns detected
- [ ] Factual accuracy check complete — no Critical factual errors. All Major factual errors fixed or deferred.
- [ ] Terminology consistent across all sections (one term per concept)
- [ ] Style consistency checked (if profile in passport) — style_profile deviations reviewed
- [ ] Tense consistency: Methods/Results past, Intro present, Discussion mixed
- [ ] All abbreviations defined on first use
- [ ] Paragraph length varied; prose reads aloud without monotone
- [ ] If PASS with no Critical or Major items → proceed to Stage 8.5 (Publication Strategy) before formatting

### Gate Failure Route
Q7 is BLOCK.

1. Inspect specific failed items:
   - IF Critical/Major issues → route back to S7A (polish loop), fix, re-verify.
   - IF factual accuracy errors → route back to S7G (factual accuracy check), fix, re-run paper-audit.
2. After 2 repair attempts still fail → STOP-AND-ASK: accept a degraded pass with known limitations documented, or return to S3 to restructure.
