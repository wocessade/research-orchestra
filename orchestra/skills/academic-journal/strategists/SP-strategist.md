# Stage SP: Partial Manuscript Assessment [Strategist]

**Gate:** QSP (SOFT BLOCK) — all sections assessed, paper type detected, gap-fill plan confirmed by user, Complete sections locked, gap_fill_plan written to passport.
**Goal:** Classify every section of a partially-written manuscript, generate a gap-fill plan in Core-First order, and produce an S3-format outline for S4 consumption.
**References:** `static/core/partial-manuscript-assessment.md`, `static/core/paper-types.md`

## Decisions

### Decision Chain (9 steps)

#### Step 1: Receive Manuscript
Prompt user to paste/upload the partial manuscript. Validate:
- Non-empty content
- Has recognizable section structure (numbered headings, IMRAD-like sections, etc.)
- Is NOT a completed manuscript (if all sections have ≥80% complete prose → suggest routing to existing-manuscript instead)

**STOP-AND-ASK:** If manuscript appears already complete → "This looks like a completed manuscript. Routing to existing-manuscript (S7→polish→publish) would be more efficient. Switch?"

#### Step 2: Detect Paper Type
Analyze manuscript content to detect `paperType`. Use the same detection rules from `manifest.yaml` axes.paperType.detect:
- Empirical study with data collection/analysis → `empirical`
- Systematic review, meta-analysis, or literature survey → `literature-review`
- Theoretical, conceptual, or framework paper → `theory`
- Registered report or pre-registration mention → `registered-report`
- Data descriptor or data resource → `data-paper`
- Software tool, package, or library → `software-tool`
- Benchmark or comparative evaluation → `benchmark`

**STOP-AND-ASK:** If ambiguous → "I can't confidently determine the paper type. Is this: [empirical / literature-review / theory / registered-report / data-paper / software-tool / benchmark]?"

#### Step 3: Map Expected Section Structure
Based on detected `paperType`, map the expected section structure:
- **empirical (IMRAD):** Introduction → Methods → Results → Discussion → Conclusion → Abstract → Title
- **literature-review:** Background → Methods (inclusion/exclusion) → Results (thematic synthesis) → Discussion (gaps, future directions)
- **theory:** Problem Statement → Framework/Model → Implications
- **registered-report:** Stage 1 (Hypotheses → Methods → Analysis Plan → Pilot Data)
- **data-paper:** Methods → Data Records → Technical Validation → Usage Notes
- **software-tool:** Architecture → Implementation → Validation → Usage
- **benchmark:** Task Definition → Benchmark Design → Results → Analysis

Reuse S3's structure routing table for consistency.

#### Step 4: Classify Each Section
For each expected section, classify its status per the assessment methodology:

| Status | Criteria | Action |
|--------|----------|--------|
| **Complete** | Full prose, no placeholders, arguments have evidence support | Preserve untouched |
| **Partial** | Content exists but insufficient: missing evidence, logical gaps, some subsections are outlines | Supplement incrementally, don't rewrite |
| **Placeholder** | Only `[TBD]`/`[To be written]`/empty heading markers | Write from scratch |
| **Missing** | Entire section doesn't exist in the manuscript | Write from scratch |

Provide evidence for each classification (e.g., "§2.1-2.2 have full prose, §2.3 is only a heading with one bullet point").

#### Step 5: Conflict Marking
If Complete sections contain statements that logically or empirically conflict with what needs to be written in gap sections:
- Mark the conflict location
- When writing gaps, prioritize data/evidence over existing claims
- If necessary, plan minimal edits to Complete sections (only to resolve factual contradictions)

Output format:
```
⚠ Conflicts detected:
- Discussion §4.3 claims N=200; Methods §2.2 describes N=150
- Introduction §1.2 states "first study to..." but literature review shows prior work (Smith 2022)
```

#### Step 6: Generate Assessment + Gap-Fill Plan
Produce output in the format specified by `partial-manuscript-assessment.md`:

```markdown
## Manuscript Assessment: {paper_title}

### Section Status
| § | Section | Status | Notes |
|----|---------|--------|-------|

### Gap-Fill Plan (Core-First order)
1. §X.Y — [action]
2. ...
```

**Core-First order** for gap filling:
1. Methods (easiest, builds momentum)
2. Results (data-driven)
3. Discussion (interpretation)
4. Introduction (now you know what you're introducing)
5. Abstract (last — summarizes the whole)
6. Title

Non-IMRAD types adapt accordingly per Step 3 structure.

#### Step 7: User Confirmation [STOP-AND-ASK]
Display the assessment table. User must confirm:
- Section classifications are correct
- Gap-fill order is acceptable
- Complete sections will NOT be modified
- Any conflicts are acknowledged

User may:
- Reclassify sections (e.g., "§3 is actually Complete, not Partial")
- Reorder the gap-fill plan
- Add notes or constraints

If user rejects → incorporate corrections and re-display.

#### Step 8: Write Passport
Write `gap_fill_plan` to `.pipeline_state.json` passport:

```json
{
  "gap_fill_plan": {
    "entry_type": "partial-manuscript",
    "assessed_at": "{ISO timestamp}",
    "paper_type": "{detected paperType}",
    "detected_structure": "{IMRAD or detected structure name}",
    "sections": [
      {
        "section": "Methods",
        "section_id": "2",
        "status": "Partial",
        "action": "supplement",
        "missing_parts": ["§2.3 实验设置", "§2.5 统计方法"],
        "existing_parts": ["§2.1 材料", "§2.2 样本准备", "§2.4 表征"],
        "existing_content_approx_words": 1200
      }
    ],
    "core_first_order": ["Methods", "Results", "Discussion", "Introduction", "Abstract", "Title"],
    "complete_sections_for_style_reference": ["Discussion"],
    "has_any_complete_sections": true,
    "conflicts": []
  }
}
```

Also pre-initialize `stepping_state.json`:
- Mark all `status: "Complete"` sections as pre-approved
- Set `recommended_next` to the first gap section in Core-First order

#### Step 9: Mode Recommendation
Default recommendation: **stepping mode** (gap-filling needs per-section author verification for consistency with existing content).

If user insists on standard mode → warn: "Without per-section review, AI-written sections may diverge in style from your existing prose. I'll still attempt style matching, but you'll only catch drift at the end."

Respect user's final choice.

### Reverse-S3: Extract Claims from Complete Sections
For Complete sections, perform "reverse-S3": extract the key claims from existing prose so the S3-format outline is comprehensive. This ensures S4's claim-to-paragraph conversion has a complete claim map, even for sections it won't rewrite.

For gap sections, perform "forward-S3": generate claims from the research question and detected gap type.

Unified output: write to `output/S3_outline.md` in standard S3 format. S4 consumes this without needing to know which claims came from which source.

## Gate

### QSP Gate Checklist
- [ ] Manuscript received and non-empty
- [ ] Paper type detected or user-confirmed
- [ ] Expected section structure mapped
- [ ] Every section classified with evidence
- [ ] Conflicts marked
- [ ] Gap-fill plan generated in Core-First order
- [ ] **User confirmed assessment** (or adjustments applied)
- [ ] `gap_fill_plan` written to passport
- [ ] Mode recommendation presented

### Gate Failure Route
QSP is SOFT BLOCK.

1. User rejects classification → re-assess per user corrections, re-display.
2. Paper type cannot be determined → ask user to specify explicitly.
3. Manuscript is too fragmented (no Complete sections, all Missing/Placeholder) → warn and suggest idea-first. If user insists → proceed but mark `has_any_complete_sections: false` and `complete_sections_for_style_reference: []`.
4. After 2 failed attempts → degrade: route directly to S7 (existing-manuscript fallback — treat the whole thing as a complete draft and let S7's audit find issues).
