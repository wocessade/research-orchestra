# Composer: polish-protocols

**Purpose:** Execute the structural and language polish loop on a completed manuscript draft, with correctness threshold for early exit.
**Used by:** academic-journal S7
**Parameters:** `{language}`, `{entry_type}` (existing-manuscript/idea-first/data-first)

## Instructions

### The Polish Loop (MANDATORY — minimum 2 passes)

```
POLISH -> AUDIT -> FIX BLOCKERS -> RE-POLISH -> RE-AUDIT
```

Never do one pass and call it done. The first audit WILL find problems. That's expected. Fix them, then re-polish.

**Correctness Threshold:** If `skills-embedded/paper-audit.md` returns PASS with zero Critical/Major items and the De-AI check finds zero flags, output: "This manuscript reads as human-written academic prose. No structural or language edits needed." Do NOT iterate the polish loop just to meet a pass-count quota. Over-polishing degrades prose quality.

### Pass 1: Structural Polish (whole-paper level)

| Check | Tool |
|-------|------|
| IMRAD section completeness | `skills-embedded/paper-audit.md` |
| Logical flow between sections | `skills-embedded/scientific-critical-thinking.md` |
| Claim-evidence alignment (every claim backed) | `skills-embedded/nature-polishing.md` |
| Figure-text consistency (what figures show = what text says) | Manual cross-check |

**Run `skills-embedded/paper-audit.md` first.** It produces severity-rated findings (major/moderate/minor). Do NOT polish sentences until the structure passes. All major items must be fixed before Pass 2.

**Existing-manuscript entry risks to address during structural polish:**
- Reproducibility undocumented -> ask user: "Can someone else reproduce your results from the files you have?"
- Claim structure never verified -> extra attention to logical flow between sections
- Research design not audited -> if causal claims, flag: "Causal claims without verified identification strategy — high rejection risk"
- Literature gap not searched -> ask user: "When did you last do a comprehensive literature search?"
- These risks do NOT block the pipeline, but the user must acknowledge them

### Pass 2: Language Polish (sentence level)

| Need | Primary | Fallback |
|------|---------|----------|
| Nature/high-impact English | `skills-embedded/nature-polishing.md` | -- |
| General academic English | `skills-embedded/scientific-writing.md` (revise mode) | -- |
| Chinese -> English translation | `skills-embedded/nature-polishing.md` (zh-to-en axis) | -- |
| Chinese thesis polish | `skills-embedded/latex-thesis-zh.md` (de-AI mode) | -- |

**Section-specific polish targets:**

| Section | Focus |
|---------|-------|
| **Abstract** | Every word counts. 150-250 words max. State problem, method, key result, implication. No background fluff. |
| **Introduction** | Funnel structure: broad context -> specific gap -> your question -> your approach. End with a clear contribution statement. |
| **Methods** | Past tense, passive voice acceptable. Reproducibility is the goal — another researcher should be able to replicate from this text alone. |
| **Results** | Past tense. Report effect sizes AND p-values. Never just "significant". Lead with data, not interpretation. |
| **Discussion** | Start with answer to research question. Then: compare to literature, explain unexpected results, acknowledge limitations, state implications. Don't just repeat results. |
| **Conclusion** | No new information. Summarize contribution + one forward-looking sentence. |

**Statistical reporting checklist:**
- Effect sizes with confidence intervals (not just p-values)
- Exact p-values to 2-3 decimals (not "p<0.05" unless truly marginal)
- Sample sizes and degrees of freedom
- Test statistics (t, F, chi-squared) with values
- Software + version + package for all analyses

### Terminology & Consistency Scan

- Scan all sections for term variants (e.g., "machine learning" vs "ML" vs "deep learning" used interchangeably)
- Pick one term per concept, use it everywhere
- Tense consistency: Methods=Past, Results=Past, Discussion=Present/Past mix, Introduction=Present
- Abbreviation audit: define on first use, use consistently after

### Entry-Type Adjustments

- **existing-manuscript**: The first structural pass must also cover entry-type risks (see Pass 1 above). Skip factual accuracy check (7G) only if user confirms no fabricated references.
- **idea-first / data-first**: Standard flow. Structural pass focuses on IMRAD completeness and claim-evidence alignment. Factual accuracy check runs as normal.

## Verification
- [ ] Minimum 2 passes completed (POLISH -> AUDIT -> FIX -> RE-POLISH -> RE-AUDIT)
- [ ] Pass 1: all Critical/Major structural items fixed before proceeding to Pass 2
- [ ] Pass 2: section-specific polish applied per targets table
- [ ] Statistical reporting checklist verified (effect sizes, CI, exact p-values, sample sizes, test stats, software)
- [ ] Terminology scan complete — one term per concept, consistent tense, all abbreviations defined
- [ ] Correctness threshold applied: PASS with zero Critical/Major -> confirmed and stopped (no over-polishing)
- [ ] Existing-manuscript entry risks acknowledged by user

## Common Pitfalls
- **Polishing before fixing structure:** running Pass 2 language polish while Critical structural issues exist wastes effort — sentences you polish may be deleted or rewritten at the structural level
- **Over-polishing:** iterating the loop beyond the correctness threshold. PASS with zero Critical/Major means "done" — further passes degrade prose quality
- **"p < 0.05" as the only statistic:** reporting only p-values without effect sizes, confidence intervals, or test statistics is the most common statistical reporting gap
- **Term variants in different sections:** "machine learning" in Introduction, "ML" in Methods, "deep learning" in Discussion — all referring to the same concept. Standardize early.
- **Statistical reporting incomplete:** software version, package name, and exact p-values are required, not optional
