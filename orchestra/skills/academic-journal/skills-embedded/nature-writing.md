# Nature-Style Writing (Embedded)

**Source:** `nature-writing` v1.0.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S3, S4, S7 — high-impact writing for Nature-family venues

## Core Process

### Step 1: Intake
Surface missing: What is the one-sentence claim? What is the key evidence?
What are the boundaries? Don't draft until all three are clear.

### Step 2: Paper-Type Playbook
- **Research:** Claim → Key result → Evidence chain → Context → Implications
- **Methods/Metrics:** Problem → Why existing fails → New approach → Validation
- **Hypothesis:** Observation → Existing models → Competing predictions → Test
- **Algorithmic:** Setup → Limitation of prior → Key insight → Empirical proof
- **Review:** Scope → Method → Thematic sections → Synthesis → Future

### Step 3: Section Drafting
**Abstract:** Four-sentence structure: what is known → what is unknown → what we did → what we found
**Introduction:** 3-paragraph funnel: broad context → specific gap → this paper's solution
**Results:** Claim-first paragraphs. Each starts with the finding, then evidence, then statistics.
**Discussion:** Answer first, then interpret, contextualize, limitations, implications.

### Step 4: Journal-Specific Framing
- **Nature/Science:** Broad significance framing, minimal jargon, general audience
- **Nature Communications:** Field-accessible but more technical
- **Generic:** Standard academic prose, field-standard terminology

## Key Rules
- Write the one-sentence argument before any paragraph
- If essential evidence is missing, write a placeholder and list it under "Assumptions or missing inputs"
- Never invent content — flag missing data instead

## Examples

### Before/After: Introduction Opening

**Before (placeholder-intro):**
> "In recent years, there has been growing interest in machine learning applications in healthcare. Many studies have explored various approaches to this problem. However, challenges remain..."

→ Flagged: no specific context, no numbers, no gap. The reader has no reason to continue.

**After (content-first):**
> "Sepsis affects 49 million patients annually and kills 11 million (WHO 2020). Early detection from EHR data could prevent 30% of these deaths, yet existing warning scores (SOFA, MEWS) miss 40% of cases in the first 6 hours. We test whether a transformer model trained on irregularly-sampled vital signs can reduce time-to-detection by 2+ hours compared to SOFA."

### Anti-Pattern: Placeholder Introduction
**Symptoms:** Opens with "In recent years..." or "With the rapid development of..."; defers the specific problem to paragraph 3; uses "many studies have shown" without naming any. **Fix:** Move the specific gap/contribution to sentence 1 or 2. Cut the warm-up.

### Pre-Submission Checklist
- [ ] One-sentence claim stated and traceable through every section
- [ ] Introduction opens with specific context (numbers, named studies, concrete problem), not warm-up phrases
- [ ] Results paragraphs lead with the finding, not the method
- [ ] Discussion opens with the answer, not a summary
- [ ] No placeholders remain; every flagged gap has a documented reason
