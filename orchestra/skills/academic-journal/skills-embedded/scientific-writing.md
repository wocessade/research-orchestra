# Scientific Writing (Embedded)

**Source:** `scientific-writing` v1.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S3 (Research Design), S4 (Writing), S7 (revise)

## Core Principle
Write in full paragraphs with flowing prose. Never submit bullet points.
Use two-stage process: outline → flowing prose.

## IMRAD Structure
- **Introduction:** Background → Gap → Question → Approach → Preview findings
- **Methods:** Design → Sample → Measures → Procedure → Analysis
- **Results:** Descriptive → Primary analysis → Secondary/sensitivity → Figures/Tables
- **Discussion:** Summary → Interpret → Contextualize → Limitations → Implications

## Section Writing Guide
**Abstract (structured):** Background (2-3 sentences), Methods (2-3), Results (3-4), Conclusions (2-3)
**Introduction:** Broad → narrow funnel. 3-4 paragraphs: general context → specific gap → your approach → preview
**Methods:** Enough detail to replicate. Subheadings by procedure type.
**Results:** Claim → evidence → statistics → interpretation. Lead with the finding.
**Discussion:** Top-down: answer → contextualize → implications → limitations → future

## Citation Format Support
APA, AMA, Vancouver, Chicago, IEEE, Nature-style. Use consistent format throughout.

## Reporting Guidelines
- CONSORT for RCTs
- STROBE for observational studies
- PRISMA for systematic reviews
- STREGA for genetic association studies

## Examples

### Before/After: Results Paragraph

**Before (data-dump):**
> "The mean response time in the treatment group was 234 ms (SD = 45) and in the control group was 312 ms (SD = 52). A t-test showed t(58) = 5.43, p < 0.001. The effect size was Cohen's d = 1.6."

→ The numbers are there but the paragraph reads like a lab notebook. No claim, no interpretation.

**After (claim-first):**
> "The treatment reduced response time by 78 ms (95% CI [49, 107], p < 0.001), a large effect (Cohen's d = 1.6). This reduction was consistent across all three task blocks (Block 1: -72 ms; Block 2: -81 ms; Block 3: -80 ms), ruling out a simple practice effect."

### Anti-Pattern: Data Dump Without Claims
**Symptoms:** Paragraph opens with a statistic or test result without stating what the finding means. Every result is reported but none is interpreted. **Fix:** Open every Results paragraph with a one-sentence claim. The statistics support the claim — they are not the claim itself.

### IMRAD Pre-Submission Checklist

**Introduction (3 items):**
- [ ] Opens with specific context (not "In recent years...")
- [ ] Gap stated as a testable question or specific unknown
- [ ] Contribution previewed in the final paragraph

**Methods (3 items):**
- [ ] Sample size justified (power analysis or equivalent rationale)
- [ ] Every measure has a citation or validation reference
- [ ] Analysis plan matches the research question (no fishing)

**Results (3 items):**
- [ ] Each paragraph opens with a claim, not a statistic
- [ ] Effect sizes reported alongside p-values
- [ ] Tables and figures are referenced in text and appear in order

**Discussion (3 items):**
- [ ] Opens with the answer to the research question
- [ ] Limitations are specific (not "more research is needed")
- [ ] Implications are proportional to the evidence strength
