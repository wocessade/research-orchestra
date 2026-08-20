# Composer: claim-to-paragraph

**Purpose:** Expand outline claims from S3/T3 into full body paragraphs using the topic-sentence + evidence + bridge pattern.
**Used by:** academic-journal S4, academic-thesis T4
**Parameters:** `{language}` (en/zh), `{section_structure}` (IMRAD/章-节)

## Instructions

Each claim from the outline expands into one full paragraph using the following three-element structure:

### 1. Topic Sentence
State the claim directly. For English (IMRAD), the topic sentence comes from the S3 claim outline. For Chinese (章-节), the opening paragraph of each chapter states the chapter's purpose and what question it answers.

### 2. Evidence
Provide supporting material for the claim:
- Data, statistics, or quantitative results
- Figure/table references (e.g., "as shown in Fig. 2" or "如表 3-1 所示")
- Literature citations for attribution claims
- Methodological details for method claims

Every claim backed by evidence. If the evidence is weak or absent, do NOT fabricate — downgrade or remove the claim instead.

### 3. Bridge
Connect this claim to the next one in the logical chain:
- English: natural transition sentence that sets up the following claim without forced segues
- Chinese (两阶段方案D): write the body without a chapter summary (本章小结); instead, let the final paragraph naturally transition to the next chapter's topic. Append `### 本章小结` (3-5 sentences) in a second pass only for chapters confirmed at T4A.

### Scope Control
- **Never** introduce new claims not present in the S3/T3 outline — scope creep is the most common cause of unfocused writing
- If you cannot write a paragraph for a claim because evidence is weak or missing — **downgrade or remove the claim**. This is a feature, not a bug: writing reveals gaps the outline concealed.

### Writing Order
Regardless of section_structure, write body/core sections first, then front matter, then back matter:
1. Core sections/chapters (results, analysis, discussion) — the contribution
2. Introduction / 第1章 绪论
3. Conclusion / 第N+1章 结论与展望
4. Literature review / 第2章 文献综述
5. Abstract / 摘要 (written last)

## Verification
- [ ] Every paragraph has exactly one claim (topic sentence)
- [ ] Every claim has supporting evidence (data, citation, figure/table reference)
- [ ] No claims appear that were not in the S3/T3 outline
- [ ] Weak evidence → claim downgraded or removed (not padded)
- [ ] Bridge sentences connect claims without forced transitions
- [ ] Chinese thesis: 本章小结 only appended for chapters confirmed at T4A

## Common Pitfalls
- **Litany citations:** "Smith et al. did X, Jones et al. did Y" without stating the gap or your position — always frame cited work relative to your claim
- **Fabricated evidence:** never invent supporting data; if evidence is weak, mark the claim for removal
- **Hidden new claims:** a new claim smuggled in as a "bridge sentence" — bridges connect claims, they don't introduce them
- **Empty chapter summaries (Chinese):** 本章小结 must be substantive (3-5 sentences) and echo actual chapter content, not generic boilerplate
- **Introduction takes 50% of abstract:** abstract is 150-250 words, problem+method+result+implication only
