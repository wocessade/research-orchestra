# Stage S4: Writing [Strategist]

**Gate:** Q4 (BLOCK) — complete draft exists, every section has prose, no placeholder text
**Goal:** Produce complete manuscript text with flowing prose.
**Needs Composers:** [methods-writing, results-writing, discussion-writing, introduction-writing, abstract-title-writing, claim-to-paragraph, citation-anchor-format, evidence-ledger-gen, style-profile-apply, format-routing]

### Entry Type Routing — Partial-Manuscript Fill Mode

Check `passport.gap_fill_plan`:
- If null/missing → standard S4 behavior (write all sections from scratch)
- If present (partial-manuscript) → **fill mode**:

**Section dispatch** (iterates in `gap_fill_plan.core_first_order`):

| Status | Behavior |
|--------|----------|
| **Complete** | Skip. Do not modify existing prose. Do not generate evidence ledger entries. |
| **Partial** | Load existing content. Write ONLY missing parts (`missing_parts`). Preserve existing paragraphs untouched. Output merged section. |
| **Placeholder** | Write from scratch (standard S4 behavior). |
| **Missing** | Write from scratch (standard S4 behavior). |

**Style matching** (when `has_any_complete_sections == true`):
- Use `complete_sections_for_style_reference` sections as style templates
- Before writing Partial/Missing sections, analyze Complete sections for: terminology preferences, sentence length, paragraph structure, citation integration style, hedging density, register
- Apply patterns to new prose to maintain a unified authorial voice across the manuscript
- If no Complete sections exist → fall back to default academic style

**Evidence ledger handling:**
- Complete sections: no regeneration (trust author's original content)
- Partial sections: generate ledger entries ONLY for newly added content
- Placeholder/Missing sections: generate full ledger entries (standard behavior)

**Length targets:**
- Total word count target accounts for existing Complete section lengths; new content fills the remainder
- If Complete sections already exceed journal upper bound → warn user before writing

## Decisions

### Tool Commands (S4)

- IF STEM with multi-step derivations → `/verify-math` (`../academic-shared/commands/verify-math.md`) before locking equations into the draft.
- IF `writingFormat=latex` → section-end `verify_paper.py` (see latex-paper-en router).


### Composer Sequence

Composers are dispatched per-section in the writing order below. The orchestrator calls each composer sequentially, passing the S3 claim outline as input.

### Writing Order — Core-First Protocol (S4, lines 22-37)

### Preflight — Contribution Gate (BLOCK)

### Issues Contract + Results Backfill (P1)

1. Ensure `{paper_dir}/.paper/issues.csv` exists (from `../academic-shared/issues/issues.template.csv`); seed from S3 claims.
2. Load `../academic-shared/issues/issues-contract.md` and `../academic-shared/issues/results-backfill.md`.
3. While writing Results: update `evidence_status`; **no strong claims** unless `verified`.
4. Before Q4: `python ../academic-shared/issues/validate_issues.py {paper_dir}/.paper/issues.csv` (add `--require-verified-results` when experiments are done).
5. After new runs: execute results-backfill, then Final Intro/Abstract numbers.


IF `contribution_check.py` would fail on `.paper/confirmed_contribution.md` → **do not draft body**; return to S3.
Load `../academic-shared/contribution/contribution-gate.md` and keep `contribution_experiment_map.md` updated while writing Results.

### CS Conference / STEM path (P0)

IF `discipline=stem` OR CS conference venue:
1. Load `../academic-shared/conference/cs-conference-path.md`
2. Prefer order: Method → Experiments/Results (Takeaway each subsection) → Related Work → **Final Intro** (rewrite Draft0) → Abstract → Title
3. Enforce page budget; use compression list in cs-conference-path when over limit
4. Claim-first paragraph openers; no textbook padding in Intro

### Results Takeaway rule (all empirical / eval sections)

Every Results subsection ends with a bold **Takeaway** sentence mapped to a `Ci` row in `contribution_experiment_map.md`.
Do not write strong conclusions for rows with evidence status `planned` or `placeholder`.


**Default order.** The orchestrator follows this sequence unless the author redirects to a different section.

Introduction and Abstract must be written LAST — after Methods, Results, and Discussion are complete. This is fundamental writing discipline: you cannot properly introduce or summarize what you haven't yet written.

For IMRAD/empirical papers (Nature convention):
1. Methods (easiest, builds momentum)
2. Results (data-driven)
3. Discussion (interpretation)
4. Introduction (now you know what you're introducing)
5. Abstract (last — summarizes the whole)
6. Title

For non-IMRAD paper types, use structure from S3 outline:
- **Data paper:** Methods → Data Records → Technical Validation → Usage Notes
- **Software/tool:** Architecture → Implementation → Validation → Usage
- **Benchmark:** Task Definition → Benchmark Design → Results → Analysis
- **Theory:** Problem Statement → Framework/Model → Implications
- **Registered report:** Stage 1 (Hypotheses → Methods → Analysis Plan → Pilot Data). Stage 2 (full paper after in-principle acceptance)
- **Literature review:** Background → Methods (inclusion/exclusion) → Results (thematic synthesis) → Discussion (gaps, future directions)

Authors may adjust the order for a specific reason (e.g., figures are already done → write Results before Methods). The AI follows the author's direction without correcting them back to the default.

### Discipline Routing (S4, line 11)

IF `discipline=stem` → load `references/discipline-stem.md`:
- Use non-IMRAD structures (System Design → Implementation → Evaluation or Algorithm → Analysis → Experiments)
- Related Work placed after main technical content
- Writing concise and figure-driven; page limits constrain every sentence

### Language & Format Routing (S4, lines 13-20)

Inspect `passport.writingFormat` and `passport.language`.

**Precedence (writingFormat wins first):**
1. IF `writingFormat == latex` → use latex-paper-en + `../academic-latex/` (ignore nature-writing/scientific-writing as primary writer).
2. ELSE route by language/venue table below.

| Condition | Primary Skill | Fallback |
|-----------|--------------|----------|
| English journal | `skills-embedded/nature-writing.md` | `skills-embedded/scientific-writing.md` |
| English template | `references/english-paper-template.md` | — |
| English LaTeX | `skills-embedded/latex-paper-en.md` + `../academic-latex/SKILL.md` | Full claim-evidence + verify_paper protocol |
| Chinese thesis | `skills-embedded/latex-thesis-zh.md` | — |
| Chinese journal paper | `skills-embedded/scientific-writing.md` (zh mode), style-match from sample paper | `skills-embedded/nature-reader.md` then `skills-embedded/scientific-writing.md` (zh mode) |
| Typst | `skills-embedded/typst-paper.md` | — |

### WritingFormat Axis — Format-Aware Writing (S4, lines 219-229)

| writingFormat | Tool | Behavior |
|---------------|------|----------|
| latex | `skills-embedded/latex-paper-en.md` → `../academic-latex/` | Write directly in LaTeX with claim ledger, verified cites, per-section verify_paper + compile. Figures via `../academic-plotting/`. |
| word | `skills-embedded/scientific-writing.md` | Standard prose. S8 converts to .docx via Pandoc. |
| markdown | `skills-embedded/scientific-writing.md` | Pandoc-ready structure. |
| typst | `skills-embedded/typst-paper.md` | Native cross-refs and citations. |
| auto-detect | `skills-embedded/scientific-writing.md` (default) | Default to prose. User can override. |

### Style Profile Conditional (S4, lines 67-89)

Check `passport.style_profile`:
- IF profile exists (not null) → apply soft constraints during writing:
  1. Sentence length deviation ≤ 20% from profile
  2. If integral citation style >60% → use "Author (Year) found..." format
  3. If high hedge density → increase cautiously worded conclusions in Discussion
  4. Paragraph length deviation ≤ 30% from profile
- **Priority:** Journal conventions (HARD) > Disciplinary norms (STRONG) > Author personal style (SOFT)
- IF style_profile is null → **skip this step**

### Citation Anchor Format (S4, lines 91-133) — All Sections Mandatory

Every citation must carry:
```
IF latex: `Smith (2024) demonstrated X~\cite{smith2024}.`  (never HTML comments)
IF word/markdown: Smith (2024) demonstrated... <!--ref:smith2024--><!--anchor:page:14-->
```

Anchor kind enumeration:
| kind | Usage |
|------|-------|
| `quote` | Verbatim quote (≤25 words) |
| `page` | Page number |
| `section` | Section name |
| `paragraph` | Paragraph number |
| `none` | Explicitly no locator (triggers warning) |

Rules:
1. Every `<!--ref:...-->` must have a corresponding `<!--anchor:...-->`
2. `anchor:quote` ≤ 25 English words / 40 Chinese characters
3. No orphan anchor tags
4. `anchor:none:claimed` requires attached reason comment

### S3-Claim to S4-Paragraph Conversion (S4, lines 172-180)

Each S3 claim → one paragraph:
1. Topic sentence (state claim directly)
2. Evidence (data, statistics, figure/table reference)
3. Bridge (connect to next claim)
4. **Never** introduce new claims not in S3 outline

IF evidence is weak for a claim → downgrade or remove the claim (not the paragraph).

### Evidence Ledger Generation (S4, lines 182-208)

After writing each section → generate evidence ledger entries:

```
claim_id, section, paragraph_index, claim_text, source_ref, source_excerpt, confidence, claim_type, audit_status
```

- Each cited claim → one entry in `{output_dir}/evidence_ledger.jsonl`
- `confidence` = `high` (direct excerpt) / `low` (memory-based)
- `claim_type` = factual / attribution / method / result / interpretation
- Skip uncited factual statements (common knowledge)

### Length Targets (S4, lines 40-64)

| Section | Target | Upper Bound |
|---------|--------|-------------|
| Abstract | 150-300 words | 350 |
| Introduction | 500-1200 | 1500 |
| Methods | 800-2000 | 2500 |
| Results | 800-2000 | 2500 |
| Discussion | 800-2000 | 2500 |
| Conclusion | 100-300 | 400 |
| **Total** | **3,500-7,500** | **9,000** |

- IF total exceeds upper bound → trim Introduction or Discussion first
- IF total below target → check Methods completeness and Discussion depth
- Title: ≤ 20 words, no colons unless necessary
- Journal-specific limits from `references/journal-style-adapter.md` take priority

### STOP-AND-ASK Points
- If evidence for a claim is too weak to write a paragraph → flag to user: downgrade or remove claim
- If word count targets cannot be met with available data → ask user whether to expand scope or accept shorter draft

## Gate

### Q4 Gate Checklist
- [ ] Contribution gate still green (`user_confirmed: true`)
- [ ] `contribution_experiment_map.md` covers every Ci; Results Takeaways present
- [ ] Final Introduction rewritten after Methods/Results (not Draft0 paste)
- [ ] Methods section written (past tense, reproducible detail)
- [ ] Results section written (data-driven, no interpretation)
- [ ] Discussion section written (interpretation, limitations, implications)
- [ ] Introduction section written (gap → question → approach)
- [ ] Abstract and Title written
- [ ] No bullet points anywhere in the manuscript
- [ ] No placeholder text ("[TBD]", "[add more here]", etc.)
### Q4 latex checklist

IF `writingFormat == latex`:
- [ ] Body is `.tex` with native `\cite`/`\citep`/`\autocite` (NO HTML `<!--ref-->` anchors)
- [ ] `python ../academic-latex/scripts/verify_paper.py {tex_root}` CLEAN (or blockers listed)
- [ ] Claim ledger updated for new claims
- Then skip the HTML ref/anchor checklist items below.

IF not latex, apply HTML anchor checks:
- [ ] **Every `<!--ref:...-->` has a corresponding `<!--anchor:...-->`** — no orphan refs
- [ ] **No uncited references** — every `<!--ref:...-->` maps to a real bibliography entry, and vice versa
- [ ] **No isolated anchor tags** — every `<!--anchor:...-->` follows a `<!--ref:...-->`
- [ ] **`anchor:quote` values ≤ 25 words** — no oversized quotes
- [ ] **`anchor:none:claimed` used only when location truly unavailable** — with documented reason

### Gate Failure Route
Q4 is BLOCK.

1. First failure → identify which check items failed → route back to corresponding missing section (S4A.x) → re-run affected sub-steps → re-evaluate gate.
2. After 2 fix attempts still fail → **STOP-AND-ASK** user: expand scope, relax criteria, or proceed with current state. Route back to S4A, complete missing body paragraphs, then re-check.
