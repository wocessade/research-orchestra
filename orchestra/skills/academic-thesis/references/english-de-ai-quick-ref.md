---
name: english-de-ai-quick-ref
description: Quick-reference De-AI checklist for English academic prose — surface markers, common fixes, and NNES caveats. For deep scans, load english-de-ai-guide.md on demand.
---

# English De-AI Quick Reference

Auto-loaded at Stage 7 for English manuscripts. This file covers the highest-signal surface markers (~70% detection coverage). For the full 17-dimension deep guide with field-specific appendices, composite scoring, and automation matrices, load `references/english-de-ai-guide.md` on demand.

---

## Core Principle: 宁缺毋滥 (Don't Fix What Isn't Broken)

The correctness threshold for De-AI editing: if a passage already reads like competent human academic prose, do NOT force changes just to lower a De-AI score. Over-editing introduces new problems — degraded clarity, stripped discourse markers, unnaturally terse prose.

**Leave text alone when:** no Tier 1-4 lexical items detected, sentence length varies naturally (SD ≥ 10), no "not only...but also" or roadmap paragraph, hedge density is within normal range.

**Output a positive confirmation when text passes:** "This section reads as human-written academic English. No De-AI edits needed." Do not invent marginal changes to satisfy an editing quota. If the 60-second check finds zero flags, output PASS and stop iterating.

---

## Surface Marker Quick Detection (D1-D8)

### D1: Lexical Over-Representation (CRITICAL — highest single-word signal)

**Tier 1 (delete all instances):** delve/delves/delved, underscores/underscoring, pivotal, realm, foster/fostering, intricate/intricately
**Tier 2 (high suspicion):** multifaceted, testament to, landscape (non-geographic), tapestry (NEVER use in academic prose), crucial
**Tier 3 (moderate suspicion):** robust (non-statistical), comprehensive, paradigm/paradigm shift, nuanced

**Thresholds:** Tier 1 >1 per 5,000 words = flag. Tier 2 >1 per 2,000 words = flag. Tier 3 >1 per 1,000 words = flag.

### Tier 4: Extended AI Vocabulary (from awesome-ai-research-writing)

Density >3 from this list per 1,000 words = high suspicion. Cross-reference with composite score (Dimension 16 in english-de-ai-guide.md).

**Category A — Rhetorical Intensifiers (delete or simplify):**
Accentuate, Amplify, Augment, Bolster, Cement, Constitute, Culminate, Elevate, Embody, Engender, Entrench, Exemplify, Garner, Gravitate, Illuminate, Invigorate, Manifest, Pioneer, Solidify
→ Replace with plain verbs: "Accentuate" → "highlight", "Elucidate" → "explain", "Manifest" → "show".

**Category B — Abstract Nominalizations (replace with concrete language):**
Amelioration, Commensurate, Confluence, Conundrum, Dichotomy, Disparity, Epitome, Facet, Genesis, Juxtaposition, Mosaic, Nexus, Paradigm, Ramification, Salience, Synergy, Trajectory, Zenith
→ "Juxtaposition" → "contrast", "Nexus" → "connection", "Ramification" → "consequence".

**Category C — Pretentious Modifiers (downgrade):**
Commendable, Conspicuous, Contentious, Copious, Erudite, Esoteric, Exhaustive, Imperative, Indelible, Inextricable, Myriad, Pertinent, Plausible, Ubiquitous, Unprecedented
→ "Myriad" → "many", "Ubiquitous" → "common", "Unprecedented" → "new" or "previously unreported".

**Category D — Overused Transition/Connective Verbs:**
Adumbrate, Buttress, Corroborate, Delineate, Demarcate, Elucidate, Emphasize, Enumerate, Explicate, Juxtapose, Posit, Propound, Substantiate, Underscore

**Category E — Grandiosity Signals (delete or reduce):**
Burgeoning, Exponential (non-mathematical), Inexorable, Instrumental, Monumental, Nascent, Profound, Seminal, Tectonic (metaphorical), Transformative, Watershed, Zeitgeist
→ "Profound implications" → "implications", "Transformative impact" → specify what transformed.

### D2: Discourse Marker Over-Density (CRITICAL)

**"Moreover" = 0 instances in any paper under 6,000 words.**
**"Notably" + "Importantly" + "Interestingly" = 0-2 combined in any paper.**

Acceptable marker budget: 12-18 (3k words), 20-35 (6k words), 35-55 (10k words). LLM text typically 2-4x these numbers.

Key overused markers: Moreover, Furthermore, Additionally, However (repeated), Therefore, Thus, Hence, Indeed, In fact, Notably, Importantly, It is worth noting that.

### D3: Syntactic Uniformity / Low Burstiness (CRITICAL — most robust surface signal)

Sentence-length SD < 8 = AI-like. SD > 12 = human-like.
Inject ultra-short sentences (under 8 words) after long ones. Break repeated syntactic templates (3+ sentences with same opening structure in a paragraph = AI fingerprint).

### D4: "Not Only...But Also..." (MAJOR)

**Zero tolerance.** Any instance flags AI. Split into two sentences or use compound predicate.

### D5: Signposting Over-Density (MAJOR)

Delete: roadmap paragraphs (95% of papers), "In this section we will discuss...", "As discussed above...", "The remainder of this paper is organized as follows...", "It is important to note that...", "It should be emphasized that...".

### D6: Hedge Quality (MAJOR)

**Problem is hedge STACKING, not hedging itself.** Fix: "may potentially suggest" → "suggests". "could possibly indicate" → "could indicate". Target: 0.5-1.0 hedges per claim. One hedge per verb, vary construction type. Overclaiming is also an AI trait.

### D7: Bullet-to-Prose Artifacts (MAJOR)

Detectable when each sentence reads as an independent unit with no flow between them. Merge related points, establish hierarchy, use anaphora.

### D8: Sandwich Paragraph (MAJOR)

General → Specific → General structure exceeding 50% of paragraphs = AI signal. Vary structures: inverted pyramid, question-driven, narrative, fragment/transition.

---

## Quick Fix Rules

1. **"Delve" → "examine", "investigate", "explore"** (or delete)
2. **"Pivotal" → "central", "key", "critical"** (or delete if role already described)
3. **"Tapestry" → DELETE.** The single most AI-diagnostic metaphor in academic writing.
4. **"Moreover" → DELETE.** Always replaceable with content transition or sentence merging.
5. **"Not only...but also..." → DELETE.** Split into two sentences or use compound predicate.
6. **Roadmap paragraph → DELETE.** Human academics stopped writing them around 2010.
7. **"In the context of" / "in terms of" / "with respect to" → DELETE.** Apply the deletion test: remove the phrase. If meaning survives, delete permanently.
8. **Stacked hedges → SINGLE HEDGE.** "may potentially suggest" → "suggests".
9. **Generic conclusion → SPECIFIC.** "More research is needed" → state exactly what and why.
10. **Every claim has a number.** Effect sizes, CIs, exact N, software versions, dates.

---

## NNES (Non-Native English Speaker) Caveat

GPT detectors misclassify NNES writing as AI-generated at 50-70% false positive rates (Liang et al., 2023). Every "AI pattern" rule also flags common NNES writing: lower burstiness, formulaic discourse markers, restricted lexical variety, higher hedging density.

**For NNES manuscripts:** raise D2/D5 thresholds by ~30%. Deep features (D12 methodological narrative, D13 stance variation, D15 concrete specificity) are safer diagnostics than surface lexical features. The goal for NNES authors is to remove genuine AI artifacts while preserving the scaffolding that supports their argument — do not strip out discourse markers and hedges that are legitimate English-proficiency features.

---

## Section Risk Weights (for composite scoring)

| Section | AI Risk | Weight |
|---------|---------|--------|
| Methods | LOW (formulaic by convention) | 0.10 |
| Results | MODERATE (specificity matters) | 0.20 |
| Introduction | MODERATE-HIGH | 0.25 |
| Discussion | HIGH (cognitive depth is key) | 0.30 |
| Abstract | HIGH (visibility) | 0.15 |

**Rule of thumb:** If the Discussion passes but Methods fails, probably human. If Methods passes but Discussion fails, probably AI.

---

## Minimum De-AI Pass (60-second check)

1. Grep for: `delve|pivotal|tapestry|realm|foster|intricate|multifaceted|Moreover|not only.*but also|accentuate|ameliorate|bolster|conundrum|delineate|elucidate|exacerbate|garner|juxtapose|manifest|myriad|nexus|paradigm|profound|ramification|salient|synerg|trajector|ubiquitous|underscore|unprecedented|zeitgeist`
2. Count discourse markers. Over threshold → fix.
3. Read one paragraph aloud. Metronome rhythm → vary sentence length.
4. Check conclusion: "more research is needed" → rewrite.

For the full 17-dimension deep guide, load `references/english-de-ai-guide.md` (on-demand only).
