# Stage T4: 核心章节撰写 [Strategist]

**Gate:** QT4 (BLOCK)
**Goal:** Produce full thesis body chapters with proper formatting, citations, and structure, ready for review.
**Needs Composers:** [docx-assembly, citation-anchor-format, evidence-ledger-gen, claim-to-paragraph]

## Decisions

### Tool Commands (T4)

### Contribution / Results rules (P0)

- BLOCK body chapters if contribution gate fails — return to T1/T3 to confirm 创新点.
- Maintain `.paper/contribution_experiment_map.md`; each empirical subsection ends with **Takeaway** → Ci.
- Final 绪论 rewrite after core chapters have real results (Draft0 / 开题文字 ≠ final 绪论).
- Load `../academic-shared/contribution/contribution-gate.md`.


- Bib bridge: `python ../academic-shared/literature/bib_to_bibliography.py {bib} -o {output_dir}/bibliography.json`
- `/check-refs` → `../academic-shared/commands/check-refs.md`
- IF latex: `/latex-cleanup` → `../academic-shared/commands/latex-cleanup.md` + `verify_paper.py --allow-cjk`
- Long chapters: save checkpoint via `checkpoint/state_manager.py` after each core chapter (resume-friendly).


### Axis 1: Chapter Summaries
```
if user chooses "添加本章小结":
    → selected chapters get "本章小结" section at end
    → summary length: 1 paragraph, 3-5 sentences
elif user chooses "不添加本章小结":
    → no chapter summaries in any chapter
elif user chooses "选择性添加":
    → present chapter list: [1,2,3,4,5]
    → user selects which chapters get summaries
```

### Axis 2: Writing Order — Core-First Protocol
```
priority_sequence:
    1. Core chapters (T4.3, T4.4) — results, analysis, discussion
    2. Introduction (T4.1)
    3. Conclusion (T4.5)
    4. Literature review expansion (T4.2) — expand from T2 skeleton
    5. Abstracts (CN + EN)

Rationale:
    Core chapters define the thesis contribution.
    Introduction and conclusion are written after core is stable.
    Literature review is expanded last to ensure coverage alignment.
    Abstracts are written last as they summarize the complete thesis.
```

### Axis 3: Two-Phase Writing (Scheme D)
```
Phase 1 — Write body without summaries:
    → all chapters written in full
    → "本章小结" sections omitted
    → focus on argument flow and evidence

Phase 2 — Append summaries:
    → second pass over selected chapters only
    → insert "本章小结" sections
    → verify summaries accurately reflect chapter content
    → do NOT modify chapter body in Phase 2

Activation:
    if scheme_d:
        → always activate (default for all thesis writing)
```

### Axis 4: Em Dash Constraints
```
constraints:
    max_dashes: 10 per 10,000 Chinese characters
    no_paired_inserts: true (do NOT use em dashes as paired parenthetical inserts)
    max_per_paragraph: 1

enforcement:
    if count(em_dashes) > max_dashes:
        → issue [WARNING: em-dash-overuse]
        → request reduction before gate
    if paired_insert detected:
        → flag for rewrite as parentheses or commas
```

### Axis 5: Format Routing
```
if format_preference == "latex" OR (degree == master AND no explicit preference):
    → Layout/class/GB-T: skills-embedded/latex-thesis-zh.md
    → Claim-evidence + verified cites + verify_paper: skills-embedded/latex-paper-en.md → ../../academic-latex/ (module-root: ../academic-latex/)
    → Figures via academic-plotting routers (nature-figure / scientific-visualization / scientific-schematics)
    → Before QT4/T7: python ../academic-latex/scripts/verify_paper.py {tex_root} --allow-cjk
    → composer: citation-anchor-format (LaTeX mode)

elif format_preference == "word" OR degree == bachelor:
    → Fallback: Word via generate_thesis_docx.py
    → composer: docx-assembly (Word mode)
    → composer: citation-anchor-format (Word mode)

if LaTeX fails (compilation error persists):
    → fallback to Word
    → flag [FORMAT-FALLBACK: latex-to-word]
```

### Axis 6: Page Numbering
```
front_matter: lowercase Roman numerals (i, ii, iii, ...)
    → covers: title page, abstract, ToC, list of figures/tables
body: Arabic numerals (1, 2, 3, ...)
    → covers: Chapter 1 onwards
```

### Axis 7: Reference Numbering
```
if reference_style == "first-appearance":
    → default: sequential numbering by first citation order
    → format: [1], [2], ...
elif reference_style == "author-year":
    → per university requirement (some humanities departments)
    → format: (Author, 2023)

Default: first-appearance
Override: user specifies author-year at T4 entry
```

### Axis 8: Validation Max Attempts
```
max_attempts = 3
for attempt in 1..max_attempts:
    run validation (citation check, format check, structure check)
    if pass:
        → proceed to gate
    elif fail:
        → save checkpoint via state_manager.py (preserves paragraph-level progress)
        → report issues, fix, retry
        if attempt == max_attempts:
            → STOP-AND-ASK
            → user decides: accept with caveats or manual override
```

### Axis 9: Advisor Feedback Severity
```
feedback classification:
    - Critical: argument flaw, missing chapter, data misinterpretation
      → blocks T5, must be resolved before proceeding
    - Major: structural reorganization, significant rewriting
      → should be resolved before T5, but user may escalate
    - Minor: wording, formatting, citation style
      → can be deferred to T6

Action:
    if any Critical:
        → [QT4-CRITICAL-FLAG] → resolve before T5 gate
    if all Major resolved OR user acknowledges:
        → proceed to QT4 gate
```

### T4F-VALIDATE: Post-Generation Automated Validation

After generating the thesis document, run automated validation:

```
for attempt in 1..3:
    1. Chapter Presence Check:
       - Verify all required chapters exist in the document
       - Check front matter (title page, abstract CN, abstract EN, ToC)
       - Check body chapters (introduction, core chapters, conclusion)
       - Check back matter (references, appendices, acknowledgements, declarations)
    2. Placeholder Scan:
       - Search for [TODO], [add], [XX], [placeholder], [TBD] patterns
       - Any match → FAIL, list offending locations
    3. Character Count Check:
       - Bachelor: 15,000+ Chinese characters
       - Master: 30,000+ Chinese characters
       - Count via python-docx or text extraction
    4. Margin & Font Check:
       - Page margins: 2.54cm top/bottom, 3.18cm left/right (or GB/T 7713.1)
       - Body font: 宋体 12pt (小四), Headings: 黑体
       - Line spacing: 1.5×
    5. Reference Format Check:
       - GB/T 7714 format compliance
       - References numbered by first-appearance order
       - No uncited references in bibliography

    if all pass:
        → proceed to gate
    elif fail:
        → save checkpoint
        → fix reported issues
        → regenerate document
        if attempt == 3:
            → STOP-AND-ASK: user decides accept with caveats or manual override
```

### T4-ADVISOR: 送审导师 (Advisor Review)

After validation passes, optionally route to advisor review:

```
1. Package for advisor:
   - Complete thesis .docx or PDF
   - Feedback tracking table (see below)

2. Advisor feedback collection:
   | # | Chapter | Page | Issue | Severity | Advisor Comment |
   |---|---------|------|-------|----------|-----------------|
   | 1 | Ch.3    | p.15 | ...   | Critical | ...             |

3. Severity classification (same as Axis 9):
   - Critical → blocks T5
   - Major → should resolve before T5
   - Minor → can defer to T6

4. Revision rounds: max 3 rounds of advisor review
   - After each round: apply fixes, re-generate, re-submit
   - After 3 rounds: proceed with remaining issues documented
```

## Gate

### QT4 Gate Checklist
- [ ] Core chapters written first per protocol
- [ ] Two-phase writing completed (body → summaries)
- [ ] Em dash constraints satisfied
- [ ] Format routing resolved (LaTeX or Word)
- [ ] Page numbering applied correctly
- [ ] Reference numbering style set
- [ ] Post-generation validation (T4F-VALIDATE) passed (or STOP-AND-ASK resolved)
- [ ] Advisor review (T4-ADVISOR) completed (if applicable) — no Critical feedback pending
- [ ] No Critical issues remaining
- [ ] All composers (docx-assembly, citation-anchor-format, evidence-ledger-gen, claim-to-paragraph) executed

### Gate Failure Route
```
if validation fails after 3 attempts:
    → BLOCK — user must accept or override
if Critical feedback unresolved:
    → BLOCK — cannot proceed to T5
if format fallback fails (Word also fails):
    → BLOCK — document must be deliverable
if em dash constraints violated:
    → SOFT BLOCK — recommend reduction
    → user may override for critical passages
```
