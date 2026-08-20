# Composer: Introduction Section Writing

**Purpose:** Write an Introduction using the funnel structure — broad importance to specific gap to research question to approach.
**Used by:** S4 (Journal), T4 (Thesis), C3 (Coursework)
**Parameters:** `{target_word_count}`, `{language}` (en/zh), `{section_title}` (Introduction/绪论/引言)

## Instructions

1. **Funnel structure (top-down).** Organize the Introduction as a narrowing funnel across 3-5 paragraphs:
   - **Paragraph 1:** Broad importance — why this field/topic matters (societal, scientific, or practical significance). General audience accessible.
   - **Paragraph 2:** Known landscape — what prior work has established, organized by theme. Cite 3-8 representative works.
   - **Paragraph 3:** The gap — what is not yet known, why existing approaches fall short, or what contradiction exists. This must be specific, not "little is known."
   - **Paragraph 4:** Your response — the research question or objective, the approach taken, and a high-level summary of the key finding.
   - **Paragraph 5 (optional):** Contribution statement + roadmap — 1-3 bullet points of contributions. For thesis, list 章 titles.

2. **Core-first protocol (thesis only, from T4).** For longer works (master/PhD thesis), write the Introduction AFTER the core chapters (Methods, Results, Discussion) are complete. Only then can the introduction accurately frame the gap that your actual results fill. Bachelor thesis may write introduction earlier but should revisit after core chapters.

3. **Citation discipline.**
   - Cite primary research, not reviews, when possible.
   - Do not open with a website, news article, or Wikipedia citation unless the topic is inherently about a current event.
   - Each citation should serve one of: establishing importance, mapping the landscape, or defining the gap.

4. **The gap statement must be specific.** A vague gap ("despite progress, challenges remain") does not motivate your work. A specific gap ("no prior work has tested BERT fine-tuning on code-switched medical notes") does.

5. **Avoid the "litany" structure.** Do not write paragraphs that are just "X did Y; Z did W." Each paragraph needs a topic sentence that states its role in the funnel, with citations as supporting evidence.

6. **Parameterization.**
   - `{target_word_count}`: For journal articles, typical introduction is 500-1000 words. For thesis chapters, 1500-3000 words.
   - `{language}`: If "zh", use Chinese section title and Chinese citation conventions (et al. 译为 等). If "en", use English conventions.
   - `{section_title}`: Use this as the section heading. Typically "Introduction" (English journal), "绪论" (Chinese thesis), or "引言" (shorter coursework).

## Verification

- [ ] Funnel structure is clear: broad → narrow → gap → question → approach
- [ ] The gap statement is specific enough that a reader could articulate what is missing
- [ ] No "X did Y, Z did W" litany paragraphs — each paragraph has a topic sentence with a role in the funnel
- [ ] First citation is from primary literature, not a website or news article
- [ ] Contribution / roadmap (if included) lists specific, verifiable claims
- [ ] Word count is within 10% of `{target_word_count}`
- [ ] Written after core chapters or revisited after core chapters (for thesis)

## Common Pitfalls

- **Opening with a website or news citation.** A scientific introduction opens with a scientific problem, not "According to a BBC article..." Unless the paper is about a current event, the first citation should be to primary literature.
- **Litany of "X did Y" without stating the gap.** A paragraph listing five related works tells the reader what has been done but not what has NOT been done. Always close the literature survey with a gap statement.
- **Contribution buried in paragraph 3.** The contribution should be near the end of the introduction and stated explicitly. If the reader cannot find the contribution statement within 15 seconds, it is too hidden.
- **Over-citation of self or single group.** If 6 of 8 citations are from the same lab, readers will wonder about literature coverage.
- **Introduction promises what Results does not deliver.** After writing, verify that every claim in the Introduction is actually addressed in Results. "We evaluate on 10 datasets" introduces a requirement that Results must satisfy.
