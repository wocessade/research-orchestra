---
name: journal-style-adapter
description: Corpus-driven dynamic journal style adaptation — extract writing patterns from 5-8 target journal papers, generate a dynamic_writing_skill.md, and apply a P1-P5 priority system for section-by-section revision. Loaded at S8.5 for Route A/B international journals.
---

# Journal Style Adapter: Corpus-Driven Adaptation

Loaded at Stage 8.5 when a target journal is identified (Route A or B international journals). Generates a per-journal dynamic writing profile from actual published papers.

## When to Use

Trigger at S8.5 after a target journal is selected and S7 (Polish) has passed. Most beneficial when:
- Target journal has a distinctive house style (e.g., Nature vs. Cell vs. PNAS)
- Author is new to the target journal
- Route A submission where stylistic fit is as important as scientific merit

**NOT needed for:** Route C fast-track journals, OA mega-journals with broad scope, Chinese domestic journals (use `chinese-journal-adapter.md` instead).

## Protocol

### Step 1: Corpus Collection

Fetch 5-8 recent papers (last 2 years) from the target journal:
- Use `skills-embedded/paper-lookup.md` for DOI-based retrieval or `paper-search-cli` for multi-source search
- Use `skills-embedded/nature-reader.md` for full-text reading with figure/table awareness
- Priority: same subfield as your paper, similar methodology, published within 2 years

### Step 2: Style Pattern Extraction

Extract the following from the corpus and write to `{output_dir}/journal_style_profile.md`:

| Dimension | What to Extract | How to Apply |
|-----------|----------------|--------------|
| **Abstract structure** | Word count range, sentence count per section, presence of background vs. direct-to-finding opening | Match abstract structure template |
| **Introduction length** | Paragraph count, final-paragraph pattern (summary vs. roadmap vs. direct hypothesis) | Match intro structure |
| **Results narrative style** | Past/present tense ratio, data-first vs. interpretation-first order, hedging density | Match results narrative |
| **Discussion opening** | "Here we show..." vs. "Our results demonstrate..." vs. "These findings..." | Match discussion opener |
| **Citation density** | Citations per 1000 words, integrated vs. parenthetical ratio | Match citation style |
| **Figure/table norms** | Number of figures, multi-panel composition, caption length, statistical reporting format | Match visual norms |
| **Paragraph structure** | Mean paragraph length, topic sentence position, transition style | Match paragraph flow |

### Step 3: Priority System (P1-P5)

When applying style adaptations, follow this priority order strictly:

| Priority | Source | Description | Override Rule |
|----------|--------|-------------|---------------|
| **P1** | Scientific Facts | Your data, methods, and results | NEVER change for style |
| **P2** | Target Journal Papers | Patterns from the 5-8 corpus papers | Apply consistently |
| **P3** | Field Papers | Broader field conventions from `skills-embedded/nature-polishing.md`, `skills-embedded/scientific-writing.md` | Apply when P2 is unclear |
| **P4** | Static Rules | Pipeline DO/DON'T, De-AI rules, formatting standards | Apply when P2/P3 are silent |
| **P5** | De-AI Cleanup | Remove AI markers after P2-P4 adaptation | Apply LAST, never first |

**Critical rule:** P1 (scientific facts) is immutable. P2 (journal style) never overrides P1. P5 (De-AI) comes LAST — de-AI before style adaptation wastes work because style changes reintroduce patterns that need fresh De-AI review.

### Step 4: Generate Dynamic Writing Skill

Create `{output_dir}/dynamic_writing_skill.md` containing:
1. **Quick reference card:** One-paragraph summary of this journal's house style
2. **Section templates:** Opening/closing patterns for each IMRAD section
3. **Lexical palette:** Journal-preferred transition words, reporting verbs, hedging constructions
4. **Anti-patterns:** What this journal's editors/reviewers flag (if detectable from published rebuttals or style guides)
5. **Figure caption template:** How this journal formats captions (sentence case vs. title case, bold figure number vs. plain, terminal period vs. none)

### Step 5: Section-by-Section Revision

Apply the dynamic writing skill to each section:
1. Read the section in your manuscript
2. Read 2-3 corresponding sections from corpus papers
3. Identify mismatches (structure, tone, density, conventions)
4. Revise following P1-P5 priority
5. Record changes in revision log

**Revision log format:**
```
| Section | Original Pattern | Journal Pattern | Change Made | Priority |
|---------|-----------------|-----------------|-------------|----------|
| Abstract | 280 words, 8 sentences | 150-180 words, 5-6 sentences | Trimmed to 170 words | P2 |
| Discussion opening | "Our results demonstrate..." | "Here we show..." | Changed to match journal convention | P2 |
```

### Step 6: Quality Check

After revision:
- Re-run S7 De-AI pass (minimal — focus on P5 cleanup only)
- Verify P1 facts unchanged (diff against pre-adaptation version)
- Verify no over-adaptation — the paper should still sound like YOUR work, not a pastiche of the corpus
- If adaptation changes affect >30% of sentences in any section, flag for human review

## Known Limitations

- English-language academic writing only (Chinese domestic journals use `chinese-journal-adapter.md`)
- Requires readable full-text corpus papers (Markdown/text preferred)
- The generated dynamic skill needs human review before revision begins
- Does not add facts, citations, results, or claims not already in the manuscript
- Corpus papers must be from the target journal — field papers alone are insufficient

## Route B: Corpus-Free Fallback

**Trigger:** When `corpus_status` is `unavailable` or fewer than 3 target journal full-text papers are accessible. This route sacrifices specificity but enables authors without corpus access to still produce a journal-aware final manuscript.

### B.1: Load Journal Author Guidelines

If the user can provide the target journal's "Instructions for Authors" URL or text, extract the following:

- **Word limits:** Total and per-section limits (e.g., "Introduction must not exceed 500 words")
- **Section requirements:** Required IMRAD sections and any journal-specific sections (e.g., "Graphical Abstract," "Highlights," "Author Contributions," "Data Availability Statement")
- **Reference format:** In-text citation style (numbered vs. author-year), reference list format
- **Abstract specifications:** Structured (Background/Methods/Results/Conclusions) vs. unstructured, explicit word limit
- **Heading conventions:** Numbering style, capitalization rules, font specifications if available
- **Figure/table requirements:** Number limits, resolution, caption formatting rules

If the author guidelines are unavailable or silent on a dimension, fall back to the defaults in B.2.

### B.2: Apply Generic International English Conventions

Apply the following discipline-general defaults at P3 priority level. These represent the lowest-common-denominator international English journal standard and should be overridden wherever B.1 or field-specific knowledge provides stronger guidance.

| Dimension | Default | Rationale |
|-----------|---------|-----------|
| **Abstract** | Unstructured, 150–300 words, no references | Widest compatibility across disciplines |
| **Overall structure** | IMRAD (Introduction, Methods, Results, Discussion) with optional Conclusion section | Universal in empirical sciences |
| **Verb tense** | Past tense for Methods and Results; present tense for Introduction and Discussion | Standard academic English convention |
| **Voice** | Active voice preferred; passive acceptable in Methods where agent is de-emphasized | Aligns with modern style guides (Nature, APA 7th) |
| **Reference style** | APA 7th (author-date) or Vancouver (numbered) — ask user preference | Two dominant international styles |
| **Formatting** | Times New Roman 12 pt, double-spaced, 1-inch margins | Legacy submission-neutral format |

### B.3: Generate Simplified `dynamic_writing_skill.md`

Create `{output_dir}/dynamic_writing_skill.md` with the label `[corpus-limited: P3-dominant]` at the top. The file should contain:

1. **Label:** `[corpus-limited: P3-dominant]` — signals that style guidance comes from generic conventions, not journal-specific corpus patterns
2. **Section structure:** Full section list with word limits, derived from author guidelines (B.1) or IMRAD defaults (B.2)
3. **Word budget table:** Per-section target word count, summing to the journal's total limit (or 6000 words if unspecified)
4. **Reference format specification:** In-text citation format, reference list style, and a minimal example entry
5. **Voice and tense guidance per section:** A quick-reference table mapping each IMRAD section to its expected tense and voice convention
6. **Figure caption format:** Sentence case, no terminal period (safe default) unless author guidelines specify otherwise

### B.4: Proceed with Reduced Confidence

Mark the Passport with the following metadata so downstream stages adjust expectations:

```yaml
style_profile:
  source: corpus-free-fallback
  confidence: low
  dominant_priority_level: P3
  note: "Style matching is coarser than corpus-driven profiling (Route A). Section structure and conventions come from author guidelines + generic international English defaults. Human review of style fit is strongly recommended before submission."
```

### When to Upgrade

If the user later obtains 5–8 target journal full-text papers, re-run the standard Route A profiling protocol (Steps 1–6 above). The Route B `dynamic_writing_skill.md` should be overwritten entirely by the corpus-driven version. The Passport metadata should be updated from `source: corpus-free-fallback` to `source: corpus-driven` and `confidence: low` to `confidence: high`.
