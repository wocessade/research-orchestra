# English Academic Prose De-AI Detection Framework

## Version: 1.0 | 2026-05-30
## Scope: English-language academic manuscripts, all disciplines
## Integrates with: Academic Paper Pipeline Stage 7 (Polish & De-AI)

---

> **~93 KB reference file.** Prefer on-demand partial reads.
> **Sections:** `## Version: 1.0 | 2026-05-30` · `## Scope: English-language academic manuscripts, all discipl...` · `## Integrates with: Academic Paper Pipeline Stage 7 (Polish ...` · `### Critical Caveat: Non-Native English Speaker (NNES) False ...` · `## Dimension 1: Lexical Over-Representation (CRITICAL)` · `### Detection Rule` · `### High-Confidence Marker List` · `### Robustness Note` · `### Fix Strategy` · `### Example` · `### Automation Potential` · `## Dimension 2: Discourse Marker Over-Density (CRITICAL)` · `### Detection Rule` · `### Target Discourse Markers` · `### Thresholds` · `### Fix Strategy` · `### The "Moreover" Rule` · `### The "Notably / Importantly / Interestingly" Rule` · `### Example` · `### Automation Potential` · `## Dimension 3: Syntactic Uniformity and Low Burstiness (CRI...` · `### Detection Rule` · `### What to Measure` · `### Syntactic Template Repetition Detection` · `### Fix Strategy` · `### Example` · `### Automation Potential` · `## Dimension 4: The "Not Only... But Also..." Tic (MAJOR)` · `### Detection Rule` · `### Data` · `### Threshold` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 5: Signposting Over-Density (MAJOR)` · `### Detection Rule` · `### Signposting Phrases to Audit` · `### The Roadmap Paragraph Problem` · `### Acceptable Signposting Budget` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 6: Hedge Quality and Calibration (MAJOR)` · `### Detection Rule` · `### Hedge Inventory` · `### Hedge Stacking Detection` · `### Hedge Density Threshold` · `### Fix Strategy` · `### Example` · `### Automation Potential` · `## Dimension 7: Bullet-to-Prose Conversion Artifacts (MAJOR)` · `### Detection Rule` · `### Artifact Patterns` · `### Fix Strategy` · `### Example` · `### Automation Potential` · `## Dimension 8: The Generic-to-Specific-to-Generic "Sandwich...` · `### Detection Rule` · `### Detection Metric` · `### Fix Strategy` · `### Example` · `### Automation Potential` · `## Dimension 9: Citation Integration Patterns (MAJOR)` · `### Detection Rule` · `### Detection Metrics` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 10: "In the Context of" and Other Preposition-P...` · `### Detection Rule` · `### High-Frequency Padding Phrases` · `### Fix Strategy` · `### Example`
> `### Automation Potential` · `## Dimension 11: Abstract and Title Formulaicism (MAJOR)` · `### Detection Rule` · `### Abstract Structural Rigidity` · `### Detection Metrics` · `### Title Patterns Overused by LLMs` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 12: Lack of Methodological Narrative (MAJOR)` · `### Detection Rule` · `### Signs of Missing Methodological Narrative` · `### Fix Strategy` · `### Example` · `### Automation Potential` · `## Dimension 13: Voice and Epistemic Stance Monotonicity (MA...` · `### Detection Rule` · `### Voice Dimensions That Should Vary` · `### Important: Passive Voice Is NOT an AI Signal` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 14: Adjectival Over-Modification (MINOR)` · `### Detection Rule` · `### Over-Modification Patterns` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 15: Lack of Concrete Specificity (MINOR)` · `### Detection Rule` · `### Specificity Gap Indicators` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 17: Light-Verb & Collocation Literalness (P0 — ...` · `### Detection Rule` · `### High-Confidence Light-Verb List` · `### Detection Metrics` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 18: Clause-Opening Monotony (P1)` · `### Detection Rule` · `### Sentence-Opening Families` · `### Detection Metrics` · `### Section Sensitivity` · `### Fix Strategy` · `### Automation Potential` · `## Dimension 15B: Section-Specific Diagnostics` · `### Detection Rule` · `### Section Risk Weights` · `### Composite Score Re-weighting (for D16)` · `## Dimension 16: Composite De-AI Scoring Checklist` · `### Purpose` · `### Scoring Rubric` · `### Composite Scoring` · `### Q7 Gate Integration` · `## Field-Specific AI Markers` · `### Computer Science / Engineering` · `### Biomedical / Life Sciences` · `### Social Sciences / Economics` · `### Humanities` · `## Field-Adjusted Thresholds` · `### Automation Priority` · `## What English Needs That Chinese Doesn't` · `## What Chinese Needs That English Doesn't` · `## Shared Concerns (Both Languages)` · `## Research Findings on LLM Academic English` · `## Journal Positions on AI Writing (as of 2025-2026)` · `### Practical Conclusion from Journal Positions` · `## Tier 1: Immediately Implement (Catches ~70% of AI text)` · `## Tier 2: Implement Next (Catches ~85% combined with Tier 1)` · `## Tier 3: Human-Guided (the remaining ~15%)` · `### Surface vs. Deep Feature Classification` · `## Integration with Pipeline Stage 7` · `## References (for the De-AI guide itself)`

# Part 0: Why English De-AI Is Harder Than Chinese De-AI

Chinese AI detection benefits from a sharp signal: LLMs trained predominantly on English data produce Chinese text with distinctive translationese artifacts, collocation errors, and register mismatches that are relatively easy to spot. English AI detection has no such luxury. The LLM was trained on the same native-English academic prose you are trying to emulate. The signal-to-noise ratio is fundamentally worse.

This means English De-AI must rely on **distributional patterns** (what is statistically overrepresented) rather than **error patterns** (what is grammatically wrong). It also means that no single dimension is dispositive -- only the composite pattern across multiple dimensions provides reliable detection.

**Core principle**: The goal is not to remove every trace of AI involvement. The goal is to make the text indistinguishable from skilled-human academic prose by eliminating the statistical fingerprints that current and future detectors exploit.

### Critical Caveat: Non-Native English Speaker (NNES) False Positive Risk

Liang et al. (2023) demonstrated that GPT detectors systematically misclassify non-native English writing as AI-generated, with false positive rates of 50-70% for some detector-tool combinations. Every "this pattern = AI" rule in this guide also flags common NNES writing patterns: lower burstiness, more formulaic discourse markers, restricted lexical variety, and higher hedging density are all features of NNES academic English as well as LLM output.

This means:

1. **No single dimension is dispositive for NNES authors.** A high D2 (discourse marker) or D5 (signposting) score in an NNES manuscript may reflect English proficiency, not AI use.
2. **The composite score thresholds (D16) assume native-speaker baselines.** For NNES manuscripts, raise the PASS threshold by 0.05-0.10 OR exempt D2 and D5 from the composite if the author's first language is not English.
3. **Deep features (D12, D13, D15) are safer diagnostics for NNES text.** Methodological narrative, stance variation, and concrete specificity are less confounded with English proficiency than surface lexical features.
4. **NNES authors should be EXPLICITLY warned** that common De-AI advice ("remove discourse markers," "vary sentence length," "reduce hedging") may degrade their prose by removing structures that make their writing clear. The goal for NNES authors is to remove GENUINE AI artifacts while preserving the scaffolding that supports their argument.

---

# Part 1: The 19 Dimensions

Dimensions are ordered by severity: Critical dimensions are high-confidence LLM fingerprints; Major dimensions are strong signals; Minor dimensions are subtle but cumulatively important.

---

## Dimension 1: Lexical Over-Representation (CRITICAL)

### Detection Rule

Scan the manuscript for words and phrases that appear at anomalously high frequency in LLM-generated academic English compared to human-written academic English. This is the single highest-signal dimension because it exploits the LLM's training distribution bias: certain words were overrepresented in the RLHF-preferred completions and the model learned to deploy them as "sounds academic" markers.

### High-Confidence Marker List

The following words and phrases are **strongly diagnostic** when they appear at elevated frequency. A single occurrence is meaningless; density matters.

| Tier | Words/Phrases | Typical LLM Rate | Human Baseline | Action |
|------|--------------|------------------|----------------|--------|
| **Tier 1 (immediate removal)** | delve into, delve deeper, delve | ~1 per 500 words | ~1 per 50,000 words | Delete all instances; replace with "examine", "investigate", "explore", or cut entirely |
| **Tier 1** | underscores, underscoring | ~1 per 800 words | ~1 per 20,000 words | Replace with "highlights", "reveals", "demonstrates", or restructure sentence |
| **Tier 1** | pivotal, plays a pivotal role | ~1 per 600 words | ~1 per 15,000 words | Replace with "central", "key", "critical", "essential" -- or delete if the role was already described |
| **Tier 1** | realm, in the realm of | ~1 per 700 words | ~1 per 25,000 words | Replace with "domain", "area", "field", "context" -- or cut entirely |
| **Tier 1** | foster, fostering | ~1 per 900 words | ~1 per 12,000 words | Replace with "encourage", "promote", "support", "enable" |
| **Tier 1** | intricate, intricately | ~1 per 1,000 words | ~1 per 18,000 words | Replace with "complex", "detailed", "fine-grained". Only keep if describing literal physical intricacy. |
| **Tier 2 (high suspicion)** | multifaceted | ~1 per 1,200 words | ~1 per 20,000 words | Replace with "multi-dimensional", "complex", "many-sided", or enumerate the facets instead of naming the abstraction |
| **Tier 2** | testament to, a testament to | ~1 per 1,500 words | ~1 per 30,000 words | Replace with "demonstrates", "reflects", "provides evidence of" |
| **Tier 2** | landscape, the landscape of | ~1 per 800 words | ~1 per 8,000 words | Replace with "field", "area", "domain", "literature" -- or cut |
| **Tier 2** | tapestry, rich tapestry | ~1 per 10,000 words | ~1 per 200,000 words | Delete. This is the single most AI-diagnostic metaphor in academic writing. Never use "tapestry" in academic prose. |
| **Tier 2** | crucial, plays a crucial role | ~1 per 400 words | ~1 per 3,000 words | Replace with "important", "critical", "key", "essential". PREFER deleting "plays a [modifier] role" construction entirely -- describe what it does, not that it plays a role. |
| **Tier 3 (moderate suspicion)** | robust (non-statistical use) | ~1 per 500 words | ~1 per 2,500 words | If not describing a statistical procedure (robust standard errors, robust regression), replace with "strong", "reliable", "consistent", "substantial" |
| **Tier 3** | comprehensive | ~1 per 600 words | ~1 per 2,000 words | Replace with "thorough", "extensive", "detailed", or delete (often redundant) |
| **Tier 3** | paradigm, paradigm shift | ~1 per 2,000 words | ~1 per 15,000 words | Replace with "framework", "approach", "model". Reserve "paradigm shift" for Kuhn-level changes; your paper almost certainly isn't one. |
| **Tier 3** | nuanced | ~1 per 1,500 words | ~1 per 10,000 words | Replace with "subtle", "fine-grained", "detailed", or demonstrate nuance instead of claiming it |

### Robustness Note

Lexical over-representation is a **degrading surface feature.** As LLMs improve, the specific words on this list will change. "Delve" was the #1 ChatGPT-4 shibboleth in 2023-2025; future models may favor different markers. The detection principle (excess word frequency) is robust; the specific word list requires periodic recalibration against the current LLM generation distribution. See Kobak et al. (2024) for the excess-word-frequency methodology.

### Fix Strategy

1. Run a frequency count of all Tier 1-3 words in the manuscript.
2. Flag any Tier 1 word appearing more than once per 5,000 words.
3. Flag any Tier 2 word appearing more than once per 2,000 words.
4. Flag any Tier 3 word appearing more than once per 1,000 words.
5. For each flagged instance: (a) delete if redundant, (b) replace with the most specific plain-English alternative, or (c) if the word is genuinely the best choice, keep it -- but only one instance per paper.

### Example

**AI text:**
> This study delves into the intricate landscape of gut-brain interactions, underscoring the pivotal role that the microbiome plays in fostering a multifaceted tapestry of metabolic regulation.

**De-AI fix:**
> This study examines how gut microbiota influence metabolic regulation through gut-brain signaling pathways.

**What changed**: "delves into" → "examines"; "intricate landscape of" → deleted (described concretely as "signaling pathways"); "underscoring the pivotal role that the microbiome plays in fostering a multifaceted tapestry of" → "influence". Seven AI markers replaced with one specific verb.

### Automation Potential

**Fully automatable.** A script can count Tier 1-3 word frequencies against manuscript length and flag over-threshold instances. Replacement requires human judgment on the best alternative word, but detection is mechanical.

---

## Dimension 2: Discourse Marker Over-Density (CRITICAL)

### Detection Rule

Count discourse markers per 1,000 words. LLM-generated text uses them at 2-4x the rate of human academic writing because the model was RLHF'd to produce "well-structured" output, and discourse markers are the cheapest way to create the appearance of logical flow.

### Target Discourse Markers

| Category | Markers |
|----------|---------|
| **Additive** | Moreover, Furthermore, Additionally, In addition, Also, Besides, What is more |
| **Adversative** | However, Nevertheless, Nonetheless, On the other hand, In contrast, Conversely, That said, Having said that |
| **Causal** | Therefore, Thus, Hence, Consequently, As a result, Accordingly, For this reason |
| **Sequential/temporal** | First, Second, Third, Finally, Lastly, Subsequently, Meanwhile, Simultaneously |
| **Emphatic** | Indeed, In fact, Notably, Importantly, Significantly, It is worth noting that, It should be noted that, It is important to emphasize that |
| **Concessive** | Although, Even though, While, Whereas, Despite, In spite of |
| **Summarizing** | In summary, To summarize, In conclusion, Overall, Taken together, In brief |

### Thresholds

| Manuscript Length | Max Acceptable Discourse Markers | LLM-Generated Typical |
|------------------|----------------------------------|----------------------|
| 3,000 words (letter/report) | 12-18 | 30-50 |
| 6,000 words (standard article) | 20-35 | 60-100 |
| 10,000 words (comprehensive) | 35-55 | 100-160 |

### Fix Strategy

The problem is not discourse markers per se -- it is (a) over-density relative to human baselines and (b) limited variety in marker choice and placement. The goal is to reduce to the human baseline rate for your field while increasing variety.

1. **Reduce to the human baseline**: Count your markers per 1,000 words. If you exceed the maximum in the threshold table above, remove markers until you are within the acceptable range. Start with the weakest ones -- markers that can be deleted without losing logical coherence.
2. **Vary position**: Instead of sentence-initial placement every time, try medial ("The results, however, suggest that...") or sentence-final placement. LLMs place markers sentence-initially >80% of the time; human writers use initial placement ~50-60% of the time.
3. **Vary marker choice**: If you use "However" 5 times in 6,000 words, replace 3 instances with "But" (underused by LLMs), "That said," or restructure to eliminate the connector. Repetition of the same marker is itself an AI signal.
4. **Replace with content transitions**: Instead of "Furthermore, X affects Y", write "X affects Y through at least three pathways." The content itself signals the structure.
5. **Sentence merging (the highest-quality fix)**: Instead of "X is important. However, Y is also important." → "While X has received the most attention, Y may matter more for [reason]."

**Note on NNES authors**: If English is not your first language, discourse markers are legitimate scaffolding for argument clarity. Reduce to the field baseline rather than below it. The "Moreover = 0" rule still applies -- there are always better alternatives.

### The "Moreover" Rule

**"Moreover" should appear 0 times in any paper under 6,000 words, and at most once in longer papers.** It is the single most overused AI discourse marker in English academic prose. Human academics almost never write "Moreover" in drafts -- it is a word added by copyeditors, not by writers. This is a distributional claim grounded in the excess-word-frequency method (Kobak et al., 2024): "Moreover" appears at ~10-30x the human baseline rate in LLM-generated academic text, making it one of the strongest single-word diagnostics available.

### The "Notably / Importantly / Interestingly" Rule

**Combined, these three words should appear 0-2 times in any paper.** LLMs use them as cheap emphasis -- every third finding is "notably" or "interestingly." In human writing, these words signal genuine surprise or emphasis. If everything is notable, nothing is.

### Example

**AI text:**
> Moreover, the results indicate that treatment significantly reduced symptoms. Furthermore, the effect was sustained at follow-up. Additionally, subgroup analysis revealed that younger participants benefited more. Interestingly, this pattern was reversed in the placebo group. However, this finding should be interpreted cautiously. Nevertheless, the overall pattern is consistent with our hypothesis.

**De-AI fix:**
> Treatment reduced symptoms (d = 0.45, 95% CI [0.31, 0.59]) and the effect persisted at 6-month follow-up (d = 0.38). The benefit was larger in participants under 40 (d = 0.61 vs. 0.28 in older participants). In the placebo group, the age pattern reversed, though the interaction was imprecise (p = 0.08).

**What changed**: Seven discourse markers eliminated. Content becomes the transition. Specific numbers replace vague summaries. The paragraph reads like a researcher reporting findings, not a language model assembling connectors.

### Automation Potential

**Fully automatable.** Count occurrences of marker words divided by word count. Flag when above threshold.

---

## Dimension 3: Syntactic Uniformity and Low Burstiness (CRITICAL)

**This is the #1 most robust surface-level differentiator between human and LLM academic text.** While lexical markers (D1) degrade as models improve and discourse-marker rules (D2) depend on specific word lists, sentence-length burstiness is a statistical signature that is extremely difficult for LLMs to suppress because it emerges from the autoregressive sampling process. Sentence-level burstiness is a stronger signal than paragraph-level uniformity. Prioritize this dimension over D1 and D2 when your detection budget is limited.

### Detection Rule

Human writing exhibits **burstiness**: clusters of short sentences followed by long, complex ones; sudden shifts in syntactic complexity; unpredictable sentence-length variation. LLM writing exhibits **uniformity**: sentences cluster around the mean length with low variance, and syntactic structures repeat in patterns of 2-3.

### What to Measure

| Metric | Human Academic English | LLM-Generated Academic English |
|--------|----------------------|-------------------------------|
| **Sentence-length standard deviation** | 12-18 words | 7-10 words |
| **Sentence-length range (shortest to longest in a paragraph)** | Often 5-35+ words | Typically 12-28 words |
| **One-sentence paragraphs** | Present in 15-30% of paragraphs | Present in 0-5% of paragraphs |
| **Ultra-short sentences (under 8 words)** | 5-12% of sentences | 0-3% of sentences |
| **Ultra-long sentences (over 35 words)** | 5-15% of sentences | 2-5% of sentences |
| **Repeated syntactic templates** | Rare (same opening structure in <10% of consecutive sentences) | Common (same opening structure in 30-50% of consecutive sentences) |

### Syntactic Template Repetition Detection

LLMs are prone to repeating syntactic patterns within a paragraph. Common templates:

```
Template A: "By [verb-ing] [noun phrase], we [verb] [noun phrase]."
Template B: "The [noun] of [noun phrase] [verb] [noun phrase]."
Template C: "These [plural noun] [verb] that [clause]."
Template D: "[Noun phrase] not only [verb] but also [verb]."
Template E: "In [adjective] [noun], [subject] [verb] [object]." (repeated sentence openings)
```

**Check**: For any paragraph with 4+ sentences, do 3+ share the same syntactic skeleton? If yes, this is an LLM fingerprint.

### Fix Strategy

1. **Vary paragraph length deliberately**: Some paragraphs should be 1 sentence. Some should be 7-8 sentences. The average should be 3-5, but variance matters more than mean.
2. **Inject ultra-short sentences**: After a long, complex sentence (35+ words), follow with a 5-8 word sentence. This is a natural human rhythm that LLMs rarely produce.
3. **Break syntactic patterns**: If you find 3 consecutive sentences starting with "The [noun]...", rewrite at least 2 to start differently.
4. **Read for rhythm, not just correctness**: Does the paragraph have a human breathing pattern? Or does every sentence land at the same length like a metronome?

### Example

**AI text (uniform syntax):**
> The model was trained on a dataset of 10,000 images. The training process used a learning rate of 0.001. The validation set consisted of 2,000 held-out images. The performance was evaluated using standard metrics. The results indicated a significant improvement. The implications of these findings are discussed below.

**De-AI fix:**
> We trained the model on 10,000 images (learning rate 0.001) and evaluated it on a 2,000-image holdout set. Accuracy improved by 12.3 percentage points over the baseline. Why? We suspect the attention mechanism is capturing cross-modal dependencies that earlier architectures missed. Section 4 tests this explanation directly.

**What changed**: Six uniform sentences become 4 varied ones (21 words, 12 words, 3 words, 11 words). Syntactic variety includes a fragment ("Why?"), a specific number ("12.3 percentage points"), and a first-person methodological speculation that sounds like a researcher thinking.

### Automation Potential

**Partially automatable.** Standard deviation of sentence length, one-sentence-paragraph count, and repeated-opening-template detection are automatable. Burstiness "feel" requires human judgment.

---

## Dimension 4: The "Not Only... But Also..." Tic (MAJOR)

### Detection Rule

The construction "not only [X] but also [Y]" is massively overrepresented in LLM-generated text. This is not a subtle signal -- it is one of the most reliable single-feature detectors of GPT-family text in academic registers.

### Data

Research findings (Liang et al. 2024; GPT-detection studies): "not only...but also..." appears at 3-8x the rate in LLM-generated academic text compared to human-written academic text. It is an RLHF artifact: the model learned that parallel constructions please human raters evaluating "well-structuredness."

### Threshold

| Paper Length | Max Acceptable "not only...but also" |
|-------------|--------------------------------------|
| Any length | 0 |

**Zero tolerance.** This construction is so heavily associated with AI text that even one instance raises suspicion. If the parallel structure is genuinely the best way to make your point, use one of the alternatives below.

### Fix Strategy

1. **Delete one half**: Often only one of the two clauses carries new information. "X not only improves accuracy but also reduces latency" → "X both improves accuracy and reduces latency" or simply "X improves accuracy" (latency reduction is implied or separately stated).
2. **Split into two sentences**: "The treatment not only reduced symptoms but also improved quality of life." → "The treatment reduced symptoms (d = 0.45). Quality of life also improved, by 0.6 standard deviations."
3. **Use a compound predicate**: "X and Y both [verb]..." or "X [verb], and Y [verb]."
4. **Replace with contrast if one half is surprising**: "Not only did the cheaper drug match the expensive one -- it outperformed it (p = 0.02)." This is the rare case where the construction is earned, because there is genuine surprise, not just parallelism for its own sake.

### Automation Potential

**Fully automatable.** Simple string match.

---

## Dimension 5: Signposting Over-Density (MAJOR)

### Detection Rule

LLM-generated academic text contains excessive **metadiscourse about the text itself** -- phrases that tell the reader what the text is doing rather than doing it. While some signposting is conventional in academic writing, LLMs over-deploy it because they were trained to produce "clear structure."

### Signposting Phrases to Audit

| Category | Overused Phrases | Acceptable Alternative |
|----------|-----------------|----------------------|
| **Section preview** | "In this section, we will discuss...", "This section explores...", "The following section presents..." | Cut entirely. Just present the content. The section heading already tells the reader what the section is about. |
| **Section recap** | "As discussed above...", "As noted earlier...", "As previously mentioned..." | Cut 80%. If genuinely needed for cross-reference, use "Section 3 showed that..." |
| **Paper roadmap** | "The remainder of this paper is organized as follows...", "The rest of the paper is structured as follows..." | Cut entirely. This is a table-of-contents in prose form. The actual table of contents already exists. |
| **Forward reference** | "As will be shown in Section X...", "We will return to this point in..." | Cut most. Let the paper's structure speak for itself. |
| **Methodological signposting** | "It is important to note that...", "It should be emphasized that...", "It is worth mentioning that..." | Cut entirely. If it's important, the content will show why. These phrases are padding. |
| **Conclusion signposting** | "In conclusion...", "To summarize...", "Taken together, these findings..." | Cut "In conclusion" (the heading says it's the conclusion). "Taken together" is acceptable once per paper. |

### The Roadmap Paragraph Problem

LLMs almost always produce a "roadmap paragraph" at the end of the Introduction:

> "The remainder of this paper is organized as follows. Section 2 describes the data and methods. Section 3 presents the results. Section 4 discusses the implications and limitations. Section 5 concludes."

**This paragraph should be deleted in 95% of papers.** It wastes 50-80 words telling the reader what they will read, which they will discover by reading it. Human academics in most fields stopped writing roadmap paragraphs around 2010, except in very long review papers or theses. LLMs haven't caught up.

**Exception**: In some engineering and CS conferences with strict formatting traditions, a brief roadmap sentence is expected. Check your target venue.

### Acceptable Signposting Budget

| Paper Length | Max Signposting Phrases |
|-------------|------------------------|
| 3,000 words | 1-2 |
| 6,000 words | 3-5 |
| 10,000 words | 5-8 |

Count phrases from the table above. If you are over budget, cut the weakest ones first.

### Fix Strategy

1. **Delete the roadmap paragraph** entirely.
2. **Replace signposting with content transitions**: "In this section, we analyze the effect of X on Y" → "Does X affect Y? Figure 2 shows the main result."
3. **Trust the reader**: Academic readers know how papers are structured. They do not need you to narrate the structure. They need you to deliver the content.

### Automation Potential

**Fully automatable.** Regex match on signposting phrases, count, flag.

---

## Dimension 6: Hedge Quality and Calibration (MAJOR)

### Detection Rule

LLM-generated text shows two hedging problems: (1) **hedge stacking** -- multiple hedges on the same verb, creating phrases like "may potentially suggest" where one hedge would suffice, and (2) **formulaic hedging** -- repeating the same hedge construction ("may," "may," "may") rather than varying hedge types. The detection concern is NOT hedging itself -- hedging is scientifically appropriate and epistemically honest. The concern is poor calibration and formulaic delivery.

### Hedge Inventory

| Category | Hedge Words/Phrases |
|----------|-------------------|
| **Modal verbs** | may, might, could, would, can |
| **Epistemic verbs** | suggest, indicate, appear, seem, tend to |
| **Epistemic adverbs** | potentially, possibly, perhaps, probably, likely, presumably, arguably |
| **Epistemic adjectives** | possible, probable, likely, plausible, putative |
| **Approximators** | approximately, roughly, about, somewhat, relatively, to some extent |
| **Shields** | to our knowledge, as far as we know, based on the available evidence, within the limitations of this study |

### Hedge Stacking Detection

| Stacked Hedge | Problem | Fix |
|--------------|---------|-----|
| "may potentially suggest" | 3 hedges on one verb | Pick one. "may suggest" or "suggests" (if confident) or "potentially indicates" |
| "could possibly indicate" | 3 hedges | "could indicate" or "suggests" |
| "might be interpreted as" | 2 hedges + passive | "suggests" or "we interpret as" |
| "appears to potentially" | 2 hedges | "appears to" or "may" |
| "seems to suggest that perhaps" | 3 hedges | "suggests" |
| "it is possible that X may" | 2 hedges | "X may" or "it is possible that X" |
| "our findings tentatively suggest that there may be" | 3 hedges | "our findings suggest" |
| "to some extent, these results could be seen as" | 3 hedges | "these results suggest" or "these results do not support" |

### Hedge Density Threshold

Count: (number of hedging words/phrases) / (number of claims made)

| Ratio | Interpretation |
|-------|---------------|
| < 0.5 | Under-hedged. Claims may be overconfident. Check that each claim's certainty matches its evidence. |
| 0.5 - 1.0 | Normal human range. |
| 1.0 - 2.0 | Moderately over-hedged. LLM-suspicious. |
| > 2.0 | Heavily over-hedged. Very likely LLM-generated or LLM-polished. |

### Fix Strategy

The target is NOT "reduce hedging." Hedging is epistemically necessary in science. The target is: (a) eliminate STACKED hedging (multiple hedges on one verb), (b) replace FORMULAIC hedging ("it is possible that," "may potentially") with DIVERSE hedging (varied constructions at appropriate confidence levels), and (c) calibrate each hedge to the specific strength of the underlying evidence.

1. **One hedge per claim -- but vary the hedge type**: Choose the right level of certainty and use one construction to signal it. Avoid repeating the same hedge construction ("may," "may," "may") across consecutive sentences. Vary: modal verb here, epistemic adverb there, qualifying clause elsewhere.

2. **Replace formulaic hedging with diverse hedging**: 
   - Formulaic (AI-like): "may potentially," "could possibly," "it is possible that," "might be interpreted as"
   - Diverse (human-like): "is consistent with (though does not confirm)," "raises the possibility that," "we cannot exclude," "the evidence is suggestive but not definitive," "one interpretation is"

3. **Confidence-calibrated hedging**: If evidence is strong (large N, consistent, robust to specification), use fewer hedges. If weak (small N, noisy, exploratory), use more -- but always varied in form.

4. **Replace hedge stacks with precise uncertainty**: Instead of "may potentially suggest", write "suggests (though the wide confidence interval warrants caution)" -- actual quantified uncertainty is better than multiple hedges.

5. **Own your strongest claims but do not overclaim**: "We find that..." is stronger and more honest than "Our results may potentially suggest the possibility that..." HOWEVER: do not overclaim. Overclaiming ("We demonstrate that X causes Y" from observational data) is itself a detectable AI trait of a different kind. The rule is: match language to evidence strength, and use diverse forms to signal uncertainty where it is genuine.

6. **Warning: overclaiming is an AI trait.** Recent LLMs (GPT-4.5/Opus-era) sometimes overcompensate for hedging criticism by making unjustifiably strong claims. A manuscript that never hedges is as suspicious as one that hedges constantly. The human baseline (0.5-1.0 hedge/claim) is the target, not zero.

### Example

**AI text (hedge-stacked):**
> These findings may potentially suggest that there could possibly be a relationship between diet quality and cognitive performance, which might be interpreted as evidence that nutritional interventions could perhaps play a role in cognitive health.

**De-AI fix:**
> Higher diet quality was associated with better cognitive performance (beta = 0.12, 95% CI [0.04, 0.20]). Whether this relationship is causal remains unclear -- the association could reflect reverse causation or unmeasured confounding.

**What changed**: One claim ("associated with") at the right confidence level. The second sentence explicitly quantifies the uncertainty instead of hedging around it. Specific numbers replace vague epistemic adverbs.

### Automation Potential

**Partially automatable.** Hedge word counting and hedge-stack detection (adjacent hedges) are automatable. Quality of hedging (whether the right level of confidence is used) requires human judgment.

---

## Dimension 7: Bullet-to-Prose Conversion Artifacts (MAJOR)

### Detection Rule

Text that was clearly generated from a structured outline or bullet-point input carries detectable artifacts: each sentence is a self-contained "unit" expanded from one bullet point, with no flow between them. The paragraph reads like a list with the bullet characters removed.

### Artifact Patterns

| Artifact | Example | Why It's AI |
|----------|---------|-------------|
| **Enumeration without numbers** | "There are several factors that influence X. Factor A is important. Factor B also matters. Factor C plays a role as well." | The LLM received "Factors: A, B, C" as input and expanded each into a sentence. The result is a bulleted list without bullets. |
| **Equal-weight parallelism** | "X improves performance. Y enhances efficiency. Z increases accuracy. W reduces cost." | Four sentences with identical structure, each expanding one item. Human writing would group, compare, or prioritize. |
| **Missing transitions between sentences** | Each sentence starts fresh with a new subject. No pronouns refer backward. No content flows forward. | LLM treats each sentence as an independent completion problem. Human writing links sentences with anaphora and forward momentum. |
| **Missing relative importance** | All points presented as equally important with no weighting or hierarchy. | LLM doesn't know which bullet point matters more. Human writers naturally emphasize and subordinate. |
| **The "several factors" opener** | "Several factors contribute to..." or "Multiple mechanisms underlie..." followed by a list-like enumeration. | This is the LLM's way of signaling it received a list input and is now converting it to prose. Human writers rarely use this construction. |

### Fix Strategy

1. **Merge related points**: Don't give each factor its own sentence. Group related factors: "Two economic mechanisms -- price effects and substitution effects -- drive the result, while a third, income effects, operates in the opposite direction."
2. **Establish hierarchy**: Which factor matters most? Say so. "The dominant mechanism is X, accounting for roughly 60% of the total effect. Two secondary mechanisms, Y and Z, account for the remainder."
3. **Use anaphora**: Make later sentences refer back to earlier ones. "This pattern..." "That finding..." "The same mechanism..."
4. **Interleave evidence and interpretation**: Instead of "Result A. Result B. Result C. These results suggest..." → "Result A, and Result B, together suggest that [mechanism]. Result C provides direct evidence for this interpretation."

### Example

**AI text (bullet-to-prose):**
> Several limitations should be noted. The sample size was relatively small. The study was conducted in a single geographic region. The measures were self-reported. The design was cross-sectional. Future research should address these limitations.

**De-AI fix:**
> Three limitations warrant caution. First, the sample (N = 87, single-site) limits generalizability -- though the within-subject design partially offsets the power concern. Second, self-reported measures may inflate associations through common-method variance; objective measures for the primary outcome are available and should be used in replication. The cross-sectional design is a more fundamental constraint: it precludes temporal ordering, so we cannot distinguish whether X precedes Y or vice versa.

**What changed**: Instead of 5 flat sentences listing limitations, this version (a) groups related limitations (sample + region = generalizability), (b) notes mitigating factors (within-subject design), (c) prioritizes (cross-sectional design is labeled "more fundamental"), and (d) explains consequences (what the limitation actually means for interpretation).

### Automation Potential

**Requires human judgment.** Detection of equal-weight parallelism and missing anaphora is theoretically automatable with a parser, but reliable detection is hard. This is best caught by reading aloud.

---

## Dimension 8: The Generic-to-Specific-to-Generic "Sandwich Paragraph" (MAJOR)

### Detection Rule

LLMs overwhelmingly produce paragraphs with a rigid three-part structure:

1. **General statement** (topic sentence that restates what is already known)
2. **Specific content** (the actual new information -- often the shortest part)
3. **General restatement** (concluding sentence that rephrases the topic sentence)

This "sandwich" structure is teachable (and is taught in composition classes), so it appears in undergraduate writing. But in published academic prose by experienced researchers, paragraphs vary their structure much more. The LLM overuses the sandwich because it was the safest pattern in its training data.

### Detection Metric

For each paragraph, classify its structure:

| Structure | Description | Human Rate | LLM Rate |
|-----------|-------------|-----------|----------|
| **Sandwich** | General → Specific → General | 20-30% | 60-80% |
| **Inverted pyramid** | Specific → General (evidence first, interpretation second) | 15-25% | 3-8% |
| **Pyramid** | General → Specific (claim first, evidence second) | 15-25% | 8-15% |
| **Narrative** | Temporal or logical sequence | 10-20% | 5-10% |
| **Question-driven** | Poses a question, then answers it | 5-15% | 1-3% |
| **Fragment / transition** | One or two sentences, structural purpose | 10-20% | 2-5% |

### Fix Strategy

1. **Cut the concluding restatement of the paragraph in 50% of cases**. If the paragraph made its point, the reader doesn't need a summary sentence.
2. **Cut the topic sentence if it states the obvious**: "Many studies have examined the relationship between X and Y" → start with the specific finding or gap instead.
3. **Use question-driven paragraphs**: "Does X affect Y? The evidence is mixed." → then present the evidence. This is a distinctively human structure that LLMs rarely produce unprompted.
4. **Use inverted pyramid**: Start with your specific finding, then explain what it means. This is the strongest structure for Results paragraphs.
5. **Vary**: No single paragraph structure should appear in more than 40% of your paragraphs.

### Example

**AI text (sandwich):**
> Machine learning has revolutionized many fields of science. [General] In this study, we develop a novel deep learning architecture that achieves 94.3% accuracy on the benchmark dataset, outperforming previous methods by 3.2 percentage points. [Specific] These results demonstrate the potential of deep learning approaches for advancing scientific discovery. [General restatement]

**De-AI fix:**
> Our architecture achieves 94.3% accuracy on the benchmark dataset, a 3.2-percentage-point improvement over the previous best method (Gonzalez et al., 2025). This gain comes from a single design choice: replacing the standard self-attention layer with a cross-modal attention mechanism that integrates domain-specific features. Ablation experiments (Supplementary Table S2) confirm that the cross-modal module accounts for 80% of the improvement.

**What changed**: The sandwich becomes an inverted pyramid. It starts with the specific result, explains why it happened, and provides evidence for the explanation. No generic framing, no generic conclusion. Every sentence carries specific information.

### Automation Potential

**Partially automatable.** A parser could classify paragraph structures and flag when sandwich exceeds 50% of paragraphs. But the classification itself is fuzzy and may require LLM assistance.

---

## Dimension 9: Citation Integration Patterns (MAJOR)

### Detection Rule

LLMs integrate citations in characteristic ways that differ from human practice:

1. **Citation clustering**: Multiple citations stacked at the end of a sentence: "(Smith, 2020; Jones, 2021; Lee et al., 2022; Wang & Zhang, 2023)."
2. **Vague citation anchors**: "Previous studies have shown..." or "There is growing evidence that..." followed by a citation cluster, without specifying WHICH study showed WHAT.
3. **Citation-to-claim ratio imbalance**: Too many citations per substantive claim.
4. **Missing named citations**: LLMs rarely use author-name-in-text citations ("Smith (2020) found that..."), preferring parenthetical citations.

### Detection Metrics

| Metric | Human Academic English | LLM-Generated |
|--------|----------------------|---------------|
| **% citations in author-name-in-text form** | 30-50% | 5-15% |
| **% claims with 4+ citations stacked** | 5-15% | 25-40% |
| **% citations with specific content attribution** | 60-80% | 20-40% |
| **"Previous studies have shown" (with cluster)** | Rare (1-2 per paper) | Common (5-10 per paper) |

### Fix Strategy

1. **Use author-name citations for key predecessors**: "Gonzalez et al. (2025) achieved 91.1% accuracy using a transformer-based approach. We improve on their method by..."
2. **Attribute specific claims to specific papers**: Instead of "Previous studies have shown that X affects Y (A, 2020; B, 2021; C, 2022)" → "A (2020) first documented the X-Y association in a cohort of 500 patients. B (2021) replicated this in a larger sample, and C (2022) showed the effect is strongest in older adults."
3. **Reduce citation stacking**: If you need 4+ citations to support a claim, either (a) it is so well-established it doesn't need citations, or (b) you should name the key papers and relegate the rest to a footnote or Supplementary Table.
4. **Generate a "citation audit"**: For each citation in the text, ask: "What specific claim does this citation support?" If the answer is "the general point of the sentence," the citation is vague and should be moved or removed.

### Automation Potential

**Fully automatable.** Named-citation ratio, cluster count, and "previous studies have shown" frequency are all mechanically countable.

---

## Dimension 10: "In the Context of" and Other Preposition-Phrase Padding (MAJOR)

### Detection Rule

LLMs pad sentences with prepositional phrases that add cognitive load without adding information. These phrases are the verbal equivalent of "um" -- they fill space while the language model assembles the next content word.

### High-Frequency Padding Phrases

| Phrase | LLM Rate | Human Rate | Action |
|--------|---------|-----------|--------|
| "in the context of" | ~1 per 400 words | ~1 per 8,000 words | Delete or replace with a specific noun |
| "in terms of" | ~1 per 500 words | ~1 per 3,000 words | Delete. "In terms of accuracy, the model..." → "The model's accuracy..." |
| "with respect to" | ~1 per 600 words | ~1 per 4,000 words | Delete. "With respect to X..." → "For X..." or restructure |
| "in relation to" | ~1 per 800 words | ~1 per 5,000 words | Delete. Restructure sentence. |
| "from the perspective of" | ~1 per 1,500 words | ~1 per 20,000 words | Delete. "From a methodological perspective" → "Methodologically" |
| "in the case of" | ~1 per 1,000 words | ~1 per 10,000 words | Delete. "In the case of X" → "For X" or restructure |
| "in the absence of" | ~1 per 2,000 words | ~1 per 12,000 words | Replace with "without" unless the absence is the subject of study |
| "on the basis of" | ~1 per 2,000 words | ~1 per 15,000 words | Replace with "based on" or "from" |
| "a wide range of" | ~1 per 800 words | ~1 per 5,000 words | Replace with "various", "diverse", "many", or enumerate |
| "a variety of" | ~1 per 600 words | ~1 per 3,500 words | Replace with "various", "several", "different", or enumerate |

### Fix Strategy

For each instance of the above phrases, apply the **deletion test**: delete the phrase and its object. Does the sentence lose essential meaning? If yes, keep a simplified version. If no, delete permanently.

### Example

**AI text:**
> In the context of climate change adaptation, a wide range of strategies have been proposed in terms of coastal protection, with respect to both hard infrastructure and nature-based solutions.

**De-AI fix:**
> Coastal climate adaptation strategies fall into two categories: hard infrastructure (seawalls, levees) and nature-based solutions (mangrove restoration, dune stabilization).

**What changed**: "in the context of", "a wide range of", "in terms of", and "with respect to" all deleted. The sentence is shorter, clearer, and names the specific strategies instead of waving at them with padding phrases.

### Automation Potential

**Fully automatable.** Regex match on the padding phrases, count, flag.

---

## Dimension 11: Abstract and Title Formulaicism (MAJOR)

### Detection Rule

LLM-generated abstracts follow an extraordinarily rigid template, far more rigid than human-written abstracts in the same journal. LLM titles also converge on a few predictable patterns.

### Abstract Structural Rigidity

LLM abstracts almost always follow this exact sequence:

```
Sentence 1: Broad context / importance of the topic ("X plays a crucial role in Y...")
Sentence 2: Gap statement ("However, little is known about Z...")
Sentence 3: What we did ("In this study, we investigate...")
Sentence 4: Method summary ("Using [method] applied to [data], we...")
Sentence 5: Key result 1 ("We find that...")
Sentence 6: Key result 2 ("Furthermore, we show that...")
Sentence 7: Implication ("These findings suggest that...")
Sentence 8: Broader significance ("This work advances our understanding of...")
```

While many abstracts in high-impact journals follow a similar IMRAD structure, LLM abstracts are TOO perfectly templated. Every sentence exactly maps to one slot in the template, with no variation in order, no skipped slots, no combined slots.

### Detection Metrics

| Abstract Feature | Human | LLM |
|-----------------|-------|-----|
| Exact 8-sentence IMRAD template | 5-15% | 60-80% |
| Opening with a specific finding rather than context | 20-35% | 2-5% |
| Abstract containing a number | 50-70% | 30-45% |
| Abstract ending with a specific (non-generic) future direction | 40-60% | 10-20% |

### Title Patterns Overused by LLMs

| Pattern | Example | Why It Signals AI |
|---------|---------|-------------------|
| "On the [Noun] of [Topic]: A [Method] Approach" | "On the Dynamics of Urban Growth: A Machine Learning Approach" | Colon titles with "A [something] Approach" are heavily overrepresented in LLM output |
| "[Verb-ing] the [Noun]: [Result] from [Data]" | "Unraveling the Complexity: Insights from Genomic Data" | Gerund opening + colon + vague noun |
| "[Topic]: A Comprehensive Review" | "Artificial Intelligence in Healthcare: A Comprehensive Review" | "Comprehensive" + colon is an LLM title cliche |
| "Towards [Noun Phrase]" | "Towards a Unified Framework for Causal Inference" | "Towards" titles are genuine in CS but LLMs overuse them in fields where they are uncommon |

### Fix Strategy

**For abstracts:**
1. Consider opening with your strongest finding rather than broad context.
2. Include at least one specific number (effect size, percentage, count) in the abstract.
3. Combine template slots -- a sentence can serve both as "what we did" and "method summary."
4. End with a specific, falsifiable future direction, not "more research is needed."

**For titles:**
1. Avoid the colon-title + "A [Method] Approach" template.
2. If you use a colon title, make sure the first half is specific and substantive, not "On the nature of..."
3. The title should contain at least one content word that is specific to YOUR study, not generic to the field.

### Automation Potential

**Partially automatable.** Template matching on abstract structure and title patterns is automatable. Quality judgment on whether a title is appropriately specific requires human judgment.

---

## Dimension 12: Lack of Methodological Narrative (MAJOR)

### Detection Rule

Human methods sections often contain traces of the actual research process: decisions made, problems encountered, alternatives considered and rejected. These traces create a **methodological narrative** -- the reader can reconstruct why the researchers chose this approach. LLM methods sections describe what was done but rarely explain why, creating a "recipe" rather than a "story."

### Signs of Missing Methodological Narrative

| Human Methods Section | LLM Methods Section |
|----------------------|---------------------|
| "We initially modeled the data using OLS, but Breusch-Pagan tests revealed heteroskedasticity (p < 0.001), so we switched to robust standard errors." | "We used robust standard errors." |
| "The survey was piloted with 30 participants, leading to revisions of 7 items that showed poor test-retest reliability." | "A validated survey instrument was used." |
| "After excluding participants who failed both attention checks (n = 47), the final sample comprised..." | "Participants who failed attention checks were excluded." |
| "We chose the 3-month follow-up because prior work (Chen et al., 2023) found that effects decay after 4-6 weeks." | "Follow-up was conducted at 3 months." |
| "Contrary to our pre-registered plan to use ANOVA, we used a non-parametric Kruskal-Wallis test because..." | "Group differences were assessed using Kruskal-Wallis tests." |

### Fix Strategy

1. **Add "why" clauses to methodological choices**: For every analytical decision, ask yourself "why did we choose this?" and add the answer to the text.
2. **Include rejected alternatives**: What analysis did you plan but not run, and why? This is a strong human signal -- LLMs rarely volunteer what they didn't do.
3. **Include process details**: "During data cleaning, we noticed that..." "Pilot testing revealed that..." These details signal that a human actually did the work.
4. **Document surprises**: "We expected X, but found Y, which led us to..." This is the single strongest human signal in a methods section.

### Example

**AI text:**
> Data were analyzed using linear mixed-effects models with participant as a random effect. Model fit was assessed using AIC.

**De-AI fix:**
> We fit linear mixed-effects models with random intercepts for participants. We also tested random slopes for the treatment effect, but the model with random intercepts only showed better fit (AIC difference = 7.4) and avoided convergence warnings. All models were fit using lme4 (Bates et al., 2015) with Satterthwaite degrees-of-freedom approximation.

**What changed**: The LLM version states what was done. The human version explains what was considered, what was rejected, and why -- and includes software details that imply the author actually ran the code.

### Automation Potential

**Requires human judgment.** The absence of process language is detectable (simple count of "because", "so we", "we chose", "contrary to our"), but the quality of the narrative depends on the researcher's actual process knowledge.

---

## Dimension 13: Voice and Epistemic Stance Monotonicity (MAJOR)

### Detection Rule

Human academic writing shifts between different epistemic stances: confident assertions, cautious speculation, open questions, acknowledged ignorance. LLM writing maintains a nearly constant epistemic stance throughout -- typically a moderate-hedging, "reasonable person" tone that never commits too strongly and never admits deep confusion.

### Voice Dimensions That Should Vary

| Dimension | Human Pattern | LLM Pattern |
|-----------|--------------|-------------|
| **Confidence level** | Varies from "we demonstrate" (high) to "we cannot rule out" (low) depending on the strength of evidence | Consistent moderate hedging |
| **Personal voice** | "We" used selectively -- prominent in methods and interpretation, less in lit review | "We" used uniformly or avoided uniformly |
| **Evaluative language** | Strong judgments mixed with neutrality: "surprisingly", "disappointingly", "remarkably" | Avoids strong evaluative language; everything is "interesting" or "notable" |
| **Questions in text** | Occasional direct questions: "Why would this be the case?" | Rarely asks questions; always provides answers |
| **Concession strength** | "We were wrong about..." "Our initial hypothesis was not supported" | "Contrary to our expectations..." (mild, formulaic) |
| **First-person reflection** | "We do not have a good explanation for this finding" | "The mechanism underlying this finding remains unclear" (passive, depersonalized) |

### Important: Passive Voice Is NOT an AI Signal

Do not conflate "passive voice" with AI detection. GPT-4 uses passive voice LESS frequently than the average human academic writer (Kobak et al., 2024). The passive is a legitimate and common construction in academic English, particularly in Methods sections where agent demotion is conventional ("Samples were centrifuged at 3,000 rpm for 10 minutes"). Forcing every sentence into active voice produces worse, not better, science writing.

The AI signal in this dimension is NOT grammatical voice but **epistemic stance monotonicity**: a uniform, moderate-hedging tone that never commits too strongly and never admits deep confusion. The fix is stance VARIETY -- confident where warranted, cautious where warranted, openly ignorant where warranted -- using whatever grammatical forms are appropriate, passive or active.

### Fix Strategy
1. **Include at least one "we don't know" statement**: Explicitly acknowledge where your data cannot distinguish between explanations, and use first person: "We cannot distinguish between X and Y as explanations for this pattern."
2. **Include at least one surprise statement**: "We expected X, but..." or "Surprisingly, ..."
3. **Include at least one open question**: End a section with a genuine question you cannot answer, not a rhetorical one.
4. **Vary the degree of author presence**: Some sections should feel like "a researcher reporting" (high presence), others like "a finding being presented" (low presence).

### Automation Potential

**Partially automatable.** Confidence marker tracking, question count, first-person reflection count, and evaluative language count can be automated. The quality of stance calibration requires human judgment.

---

## Dimension 14: Adjectival Over-Modification (MINOR)

### Detection Rule

LLMs over-modify nouns with adjectives that do not add information. This is a subtler version of Dimension 1: the LLM has learned that "complex" sounds more academic than nothing, and "significant" more authoritative than nothing, even when the adjective is redundant with the noun or with other context.

### Over-Modification Patterns

| Pattern | Example | Problem |
|---------|---------|---------|
| **Redundant intensifier + adjective** | "highly complex", "extremely important", "very significant" | The intensifier doesn't add information. "Complex" is already complex. |
| **Vacuous positive adjective** | "innovative approach", "novel method", "significant contribution", "important finding" | These are author self-assessments, not descriptions. Let the reader decide if it's innovative. |
| **Double adjectives** | "complex and multifaceted", "important and significant", "novel and innovative" | One adjective would work. Two means both are weak. |
| **"Key" + noun** | "key factor", "key finding", "key insight", "key contribution" | One of the top 10 most overused LLM modifiers. Often deletable. |
| **"Robust" outside statistics** | "robust understanding", "robust framework", "robust evidence base" | "Robust" should be reserved for statistical procedures. Use "strong", "thorough", "well-supported" elsewhere. |
| **"Enhanced" / "improved" as default modifiers** | "enhanced performance", "improved outcomes" | If your method enhances/improves something, say by how much with a number. The adjective alone is a claim without evidence. |

### Fix Strategy

1. **The adjective deletion test**: Delete each adjective. Does the sentence lose essential meaning? If not, permanently delete.
2. **Replace adjective + noun with specific content**: "The innovative approach" → "The approach (which incorporates X and Y for the first time)"
3. **Show, don't claim**: "A significant improvement" → "A 12% reduction in error rate"
4. **One adjective per noun**: If you need two adjectives, one of them is probably not pulling its weight.

### Automation Potential

**Fully automatable.** Adjective density, double-adjective count, and key/robust/innovative frequency are all mechanically countable.

---

## Dimension 15: Lack of Concrete Specificity (MINOR)

### Detection Rule

LLM text gravitates toward the abstract and general. Human research writing, especially in empirical fields, includes concrete specifics: exact numbers, software versions, hardware specifications, exact dates, specific sample sizes at each stage, specific exclusion counts. LLMs omit these details because they were not in the prompt, or because the model defaults to summarizing rather than specifying.

### Specificity Gap Indicators

| Specificity Type | LLM Omission Rate | Example of Missing Specificity |
|-----------------|-------------------|-------------------------------|
| **Effect sizes with confidence intervals** | High | LLM: "Treatment improved outcomes." Human: "Treatment improved outcomes by 0.45 SD (95% CI [0.31, 0.59])." |
| **Exact N at each analysis stage** | High | LLM: "Participants were excluded for missing data." Human: "Of 847 participants, 23 had missing baseline data, 41 were lost to follow-up, and 12 failed attention checks, leaving 771 in the final analysis." |
| **Software versions and packages** | Medium | LLM: "Analyses were conducted in R." Human: "All analyses were conducted in R 4.3.1 using lme4 1.1-34 and emmeans 1.9.0." |
| **Hardware/experimental setup** | Medium | LLM: "The model was trained on GPUs." Human: "Training used 4 NVIDIA A100-80GB GPUs for 72 hours." |
| **Dates and time periods** | Medium | LLM: "Data were collected from hospital records." Human: "Data covered all admissions between January 2020 and December 2023." |
| **Specific exclusion criteria with counts** | High | LLM: "Outliers were removed." Human: "We excluded 4 participants with values more than 3 SD from the mean on any primary measure." |

### Fix Strategy

1. **Numbers audit**: Scan the manuscript for every claim that could be quantified. If a number exists (and it almost always does), insert it.
2. **N-at-each-stage**: Include a participant flow diagram or text description showing exactly how many observations were lost at each exclusion step.
3. **Software versions**: Always include version numbers for key packages. This is both human-specific and reproducibility-best-practice.
4. **Dates**: Specify time periods rather than "recently" or "over the past decade."

### Automation Potential

**Partially automatable.** Number density (numbers per 1,000 words), CI reporting rate, and N-at-stage reporting can be checked. Whether a specific number EXISTS for the claim requires access to the underlying research.

---

## Dimension 17: Light-Verb & Collocation Literalness (P0 — NNES-English only)

**Category:** CRITICAL for Chinese NNES detection

### Detection Rule

Chinese academic writing frequently uses light-verb constructions (进行 + V, 对...进行 + N, 通过 + N + 进行 + V) that translate literally into English as light-verb + nominalization patterns. These are among the strongest NNES-detectable signals because LLMs trained on English academic prose do not default to these constructions — they are learned directly from Chinese NNES training data.

### High-Confidence Light-Verb List

| Suspicious Construction | Natural Alternative | Why It Is Suspicious |
|------------------------|-------------------|---------------------|
| conduct analysis | analyze | Direct calque of 进行分析. Over 80% of human English uses the verb form. |
| perform investigation | investigate | 进行调查 → perform investigation |
| carry out research | research (verb) | 进行研究 → carry out research |
| make a conclusion | conclude | 得出结论 → make a conclusion |
| give explanation | explain | 给予解释 → give explanation |
| conduct evaluation | evaluate | 进行评估 → conduct evaluation |
| perform calculation | calculate | 进行计算 → perform calculation |
| carry out experiment | experiment (verb) | 进行实验 → carry out experiment |
| provide guidance for | guide | 提供指导 → provide guidance |
| undertake exploration | explore | 进行探索 → undertake exploration |

### Detection Metrics

```
lv_density = suspicious_light_verb_pairs / 1000 words
```

- **Threshold A (Warning):** > 2 high-confidence pairs per 1000 words in Introduction or Discussion
- **Threshold B (Flag):** suspicious pairs constitute > 15% of all verb-noun pairs
- **NNES-only:** This dimension should NOT be applied to native English speakers, as light-verb constructions in native writing are rare enough to be negligible

### Fix Strategy

1. Replace "conduct/perform/carry out/undertake + nominalization" with the verb form directly.
2. Exception: Keep "conduct a meta-analysis" or "perform a power analysis" where the noun names a specific methodology (not a generic action).
3. After replacement: the resulting text should be shorter and more direct.

### Automation Potential

**Fully automatable via curated blacklist.**

---

## Dimension 18: Clause-Opening Monotony (P1)

**Category:** MAJOR

### Detection Rule

LLM-generated and NNES academic prose exhibits a restricted set of sentence-opening patterns. The same structural openings repeat across paragraphs and sections, creating a monotone rhythm that human readers recognize as "robotic" even when individual sentences are well-formed.

### Sentence-Opening Families

Monitor the distribution of opening constructions across each section:

| Family | Examples | LLM/NNES Bias | Human Baseline |
|--------|----------|---------------|----------------|
| **Demonstrative/Article Subject** | This paper..., This study..., This work..., This article..., The present study..., Our analysis... | ~30-40% of sentences | ~15-25% of sentences |
| **Expletive "It"** | It is..., It can be seen that..., It should be noted that..., It is worth noting that..., It is important to..., It is possible that... | ~10-15% of sentences | ~3-7% of sentences |
| **Expletive "There"** | There is..., There are..., There exists..., There has been... | ~8-12% of sentences | ~2-5% of sentences |
| **Discourse Marker Openings** | Moreover,..., Furthermore,..., Additionally,..., However,..., In addition,..., Therefore,... | ~15-25% of sentences | ~8-15% of sentences |
| **Transitional Phrase** | In recent years,..., With the development of..., In this context,..., On the other hand,..., As a result,... | ~10-15% of sentences | ~3-8% of sentences |

### Detection Metrics

```
opener_entropy = H(sentence_opening_family)
```

- Compute Shannon entropy over the 5 opener families above (normalized by total sentences in the section).
- **Warning threshold:** Section-level opener entropy < 1.5 bits
- **Flag threshold:** Same family repeated 3+ times consecutively (e.g., "This paper... This study... Our work...")
- **Context note:** Expletive-it patterns like "It can be seen that.../It should be noted that.../It is important to note that..." belong in the Expletive "It" family count, NOT double-counted under D5 signposting.

### Section Sensitivity

| Section | Risk Weight | Notes |
|---------|-------------|-------|
| **Introduction** | Medium | Some formula is expected in background sections |
| **Methods** | Low | Methods descriptions are naturally repetitive |
| **Results** | Medium | Results sections should show varied openings |
| **Discussion** | High | Low opener entropy = most diagnostic in Discussion |

### Fix Strategy

1. **Vary the grammatical subject.** If 3 consecutive sentences start with "This paper/study/work/article", move the subject into the predicate and start with another element: "We examined...", "An important question is...", "Critically, ...", "Unlike prior studies, ..."
2. **Use adverbial fronting sparingly.** Move a single adverbial element to the front (e.g., "Unlike previous work, our approach..."), then return to subject-verb order. One adverbially-fronted sentence per paragraph is enough — more than that creates its own formula.
3. **Audit section openings.** The first 2-3 sentences of each section often carry the heaviest pattern density. These are read by every reviewer and matter disproportionately.

### Automation Potential

**Fully automatable.** Sentence opening detection is a simple POS-pattern match. Entropy computation is a single formula.

---

## Dimension 15B: Section-Specific Diagnostics

### Detection Rule

AI-like text is not equally suspicious in all sections. A highly formulaic Methods section is normal -- Methods sections in many fields ARE formulaic. A highly formulaic Discussion section is a red flag. Composite scores (D16) must be section-weighted.

### Section Risk Weights

| Section | AI-Like Prose Risk | Reason |
|---------|-------------------|--------|
| **Methods** | LOW risk | Methods sections are formulaic by convention. Passive voice, uniform sentence structure, and standardized terminology are normal and expected. Higher D2/D3/D5 scores in Methods are LESS concerning. |
| **Results** | MODERATE risk | Results sections should show specificity (numbers, CIs, effect sizes). Lack of specificity in Results is a stronger AI signal than in other sections. |
| **Introduction** | MODERATE-HIGH risk | AI introductions are recognizable by the "broad context → gap → we fill the gap" template rigidity (D11) and overuse of "plays a crucial role" constructions (D1). |
| **Discussion** | HIGH risk | Discussion is where human cognitive depth is most evident. AI Discussions are characterized by: (a) summary of results rather than interpretation, (b) formulaic hedging, (c) generic limitations, (d) missing author stance, and (e) "more research is needed" conclusions. A Discussion that reads like AI is the single strongest section-level red flag. |
| **Abstract** | HIGH risk (visibility) | Abstracts are disproportionately read. AI-typical abstracts are more likely to trigger editor/reviewer recognition even if the rest of the paper is human-like. |

### Composite Score Re-weighting (for D16)

When computing the De-AI Score, apply section weights:

```
Weighted Score = (0.10 × Methods score) + (0.20 × Results score) + (0.25 × Introduction score) + (0.30 × Discussion score) + (0.15 × Abstract score)
```

This down-weights formulaic sections (Methods) and up-weights cognitively demanding sections (Discussion) where AI artifacts are more diagnostic.

If you cannot score individual sections separately, apply this mental rule: **if the Discussion passes but the Methods fails, the paper is probably human-written. If the Methods passes but the Discussion fails, the paper is probably AI-generated.**

---

## Dimension 16: Composite De-AI Scoring Checklist

### Purpose

Like the Chinese guide's composite scoring (D19), this provides a single-page composite score that can be used as a Quality Gate (integrates with Q7 in the Academic Paper Pipeline). Each dimension is scored 0-5, where 0 = severe AI artifact, 5 = indistinguishable from skilled human academic prose.

### Scoring Rubric

| Dim | Dimension | 0-1 (Heavy AI) | 2-3 (Suspicious) | 4-5 (Human-like) | Score |
|-----|-----------|----------------|-----------------|-----------------|-------|
| D1 | Lexical Over-Representation | 5+ Tier 1 words present; multiple Tier 2/3 words at high density | 1-4 Tier 1 words; moderate Tier 2/3 density | 0 Tier 1 words; Tier 2/3 words at human baseline | |
| D2 | Discourse Marker Density | >2x threshold; "Moreover" present | 1-2x threshold; markers feel mechanical | Below threshold; markers feel natural | |
| D3 | Syntactic Uniformity | Sentence-length SD < 8; no short/long sentences | SD 8-12; some variety but templates detectable | SD > 12; bursty; mixed lengths; varied openings | |
| D4 | "Not Only...But Also" | 2+ instances | 1 instance | 0 instances | |
| D5 | Signposting Over-Density | Roadmap paragraph present; >2x threshold | 1-2x threshold; some unnecessary signposting | Below threshold; signposting feels earned | |
| D6 | Hedging Quality | >2.0 hedge/claim ratio; multiple hedge stacks | 1.0-2.0 ratio; 1-2 hedge stacks | 0.5-1.0 ratio; 0 hedge stacks; confidence calibrated to evidence | |
| D7 | Bullet-to-Prose Artifacts | 3+ paragraphs with list-like structure | 1-2 paragraphs with list-like structure | No list-like paragraphs; natural flow within paragraphs | |
| D8 | Sandwich Paragraph Rate | >60% sandwich paragraphs | 40-60% sandwich paragraphs | <40% sandwich; varied paragraph structures | |
| D9 | Citation Integration | <15% author-name citations; >25% claims with 4+ stacked citations | 15-30% author-name; moderate stacking | >30% author-name citations; <15% stacking; specific attributions | |
| D10 | Preposition Padding | >3x human baseline for padding phrases | 1-3x human baseline | At or below human baseline | |
| D11 | Abstract/Title Naturalness | Rigid 8-sentence template; colon-title with "A [X] Approach" | Mostly templated with minor variation | Structurally varied; contains numbers; specific title | |
| D12 | Methodological Narrative | No "why" clauses; no rejected alternatives; no process details | Some "why" but sparse; no rejected alternatives | Rich process narrative; alternatives considered; surprises documented | |
| D13 | Voice/Stance Variation | Uniform moderate hedging throughout; no first-person reflection | Some variation but limited; token "we were surprised" | Confident where warranted; acknowledges ignorance; varied author presence | |
| D14 | Adjectival Over-Modification | Heavy redundant adjective use; "key" + "innovative" + "robust" (non-statistical) | Moderate over-modification; some redundant adjectives | Adjectives carry information; no vacuous modifiers | |
| D15 | Concrete Specificity | No effect sizes; no CIs; no N-at-stage; no software versions | Some numbers but missing key specifics | Rich specificity: numbers, CIs, N-at-stage, versions, dates | |
| D17 | Light-Verb Literalness (NNES) | >4 high-confidence light verbs; >25% verb-noun pairs suspicious | 2-4 light verbs; 15-25% suspicious pairs | <=1 light verb; <15% suspicious; natural verb usage | |
| D18 | Clause-Opening Monotony | Opener entropy < 1.2 bits; same family 4+ consecutive sentences | Entropy 1.2-1.6 bits; same family 3 consecutive sentences | Entropy > 1.6 bits; varied openings throughout | |

### Composite Scoring

**Simple (unweighted):**
```
De-AI Score = (Sum of all 17 dimension scores) / 85  (normalized to 0.0 - 1.0)
```
Note: D17 (Light-Verb) should be excluded from the sum for native English speakers (set to 5). D17 is NNES-specific.
```

**Section-weighted (preferred, when section-by-section scoring is available):**
Apply the section weights from D15B and compute the section-weighted composite. The section-weighted score penalizes AI-like Discussion sections more heavily and forgives AI-like Methods sections.

**NNES-adjusted (for non-native English authors):**
If the first author's primary language is not English, raise the PASS threshold by 0.05-0.10 to accommodate the systematically higher D2, D3, and D5 scores typical of NNES academic prose.

| De-AI Score | Category | Action |
|------------|----------|--------|
| 0.80 - 1.00 | PASS | Indistinguishable from skilled human prose. Proceed to S8.5. |
| 0.65 - 0.79 | BORDERLINE | Suspicious. Fix all Critical and Major dimensions scoring 0-3 before proceeding. |
| 0.40 - 0.64 | FAIL - MODERATE | Detector-triggering. Multiple LLM fingerprints. Full De-AI pass required. |
| 0.00 - 0.39 | FAIL - SEVERE | Heavy AI generation. Likely AI-written with minimal human editing. Major rewrite needed. |

### Q7 Gate Integration

In the Academic Paper Pipeline, Stage 7 (Polish & De-AI) should require:

- [ ] De-AI Score >= 0.80 for PASS, OR
- [ ] De-AI Score >= 0.65 with all D1-D6 (Critical + Major) scoring 4+, OR
- [ ] If De-AI Score < 0.65: Gate FAILS. Return to S7 De-AI pass. Do not proceed to S8.5.

---

# Part 2: Cross-Disciplinary Variation

English AI prose is not uniform across fields. The markers above have different baseline frequencies in different disciplines, and some markers are discipline-specific.

## Field-Specific AI Markers

### Computer Science / Engineering

| AI Marker | Why It Signals AI |
|-----------|-------------------|
| "leverage" as a synonym for "use" in every other sentence | LLMs massively overuse "leverage" in CS contexts. Human CS writers use "use", "apply", "employ" with more variety. |
| "state-of-the-art" (SOTA) without qualification | LLM default praise. Human CS writers either cite a specific SOTA system or avoid the term. |
| "achieve" + number (e.g., "achieves 94.3% accuracy") | Overused by LLMs. Human CS writers use "reaches", "obtains", "yields", or report the number without a verb. |
| "benchmark" as a verb ("we benchmark our method on...") | Rare in human CS writing; common in LLM CS text. Humans "evaluate on" benchmarks. |
| "outperform" without specifying by how much | LLM: "Our method outperforms existing approaches." Human: "Our method reduces error by 12% compared to the next-best approach (Gonzalez et al., 2025)." |
| "demonstrate the effectiveness of" | LLM cliche. Human CS writers show results; they don't declare effectiveness. |
| "extensive experiments demonstrate that" | "Extensive" is not falsifiable. How many experiments? On what datasets? The sentence is padding. |

### Biomedical / Life Sciences

| AI Marker | Why It Signals AI |
|-----------|-------------------|
| "elucidate the mechanism" | LLMs love "elucidate." Human biomedical writers use "identify", "determine", "characterize", "define." |
| "plays a role in" | "X plays a role in Y" is the single most common LLM biomedical phrase. Human writers specify what kind of role: "X activates Y" or "X inhibits Y." |
| "shed light on" | LLM signposting. Human biomedical writers rarely use this metaphor in original research articles. |
| "mechanistic insights into" | Almost always AI when appearing in the abstract or introduction of a paper that is not actually a mechanism study. |
| "implicated in" | Overused by LLMs as a vague hedge. Human writers say "associated with" (for observational) or "causes" (for experimental). |
| "further investigation is warranted" | LLM conclusion default. Human writers specify what investigation, using what approach, to test what hypothesis. |

### Social Sciences / Economics

| AI Marker | Why It Signals AI |
|-----------|-------------------|
| "nuanced understanding" | Massively overused by LLMs trying to sound like qualitative researchers. Human social scientists demonstrate nuance rather than claiming it. |
| "intersection of" | "At the intersection of X and Y" is an LLM template for situating interdisciplinary work. Specific but overused. |
| "complex interplay" | Vague. What interacts with what, how, and with what consequences? LLMs use this as a placeholder for actual mechanisms. |
| "sheds light on broader societal" | LLMs defaulting to "broader significance" language for social science topics. Generic and uninformative. |
| "problematize" / "foreground" / "interrogate" | These critical-theory verbs are legitimate in some subfields, but LLMs deploy them indiscriminately across all social science contexts, including quantitative papers where they are stylistically inappropriate. |
| Question-in-title format ("Who Benefits? The Distributive Effects of...") | Genuine in sociology/political science, but LLMs overuse it in fields where it's not conventional. |
| "speak to" as a synonym for "address" or "relate to" | "These findings speak to broader debates about..." is an LLM tic in social science contexts. |

### Humanities

| AI Marker | Why It Signals AI |
|-----------|-------------------|
| "offers a compelling account of" | AI book-review or summary language bleeding into original humanities writing. |
| "in dialogue with" | Legitimately used in humanities, but LLMs deploy it as a default template. |
| "disrupts conventional narratives" | LLM default for claiming significance in humanities contexts. |
| "opens up new avenues for" | AI signposting dressed in humanities language. |

## Field-Adjusted Thresholds

The baselines in Part 1 assume general empirical-science academic writing. Adjust as follows:

| Dimension | CS/Engineering Adjustment | Biomedical Adjustment | Social Science Adjustment | Humanities Adjustment |
|-----------|--------------------------|----------------------|--------------------------|---------------------|
| D1 (Lexical) | ADD "leverage", "state-of-the-art", "demonstrate the effectiveness" to Tier 2 | ADD "elucidate", "mechanistic insights", "shed light on" to Tier 1 | ADD "nuanced understanding", "complex interplay" to Tier 2 | ADD "compelling account", "in dialogue with" to Tier 3 |
| D2 (Discourse) | Slightly HIGHER baseline (CS uses more "However") | Standard baseline | Slightly LOWER baseline for emphatic markers | LOWER baseline for causal markers |
| D5 (Signposting) | HIGHER tolerance for roadmap paragraphs in CS conference papers | Standard | Standard | LOWER tolerance (humanities writing uses less signposting) |
| D9 (Citations) | HIGHER tolerance for citation stacking in CS | Standard (author-name citations important) | HIGHER author-name-citation baseline expected | Author-name-dominant citation style; parenthetical rare |
| D12 (Method narrative) | Less applicable to theory papers | STANDARD -- this is crucial for biomedical | STANDARD for quantitative; narrative methods for qualitative | Different evidentiary logic; "method" may mean interpretive framework |

---

# Part 3: Automation Feasibility Matrix

| Dimension | Automated Detection | Automated Fix | Requires Human Judgment |
|-----------|-------------------|---------------|----------------------|
| D1: Lexical Over-Representation | YES | PARTIAL (replacement dictionary possible, quality variable) | Best replacement word choice |
| D2: Discourse Marker Density | YES | PARTIAL (can flag; can't judge naturalness) | Which markers to keep |
| D3: Syntactic Uniformity | PARTIAL (sentence length stats automated; template detection harder) | NO | Overall rhythm and burstiness |
| D4: "Not Only...But Also" | YES | YES (mechanical) | N/A |
| D5: Signposting Density | YES | PARTIAL (can flag; deletion judgment needed) | Which signposts are earned |
| D6: Hedging Quality | PARTIAL (density automated; stacking detectable) | NO | Appropriate confidence calibration |
| D7: Bullet-to-Prose Artifacts | NO | NO | YES |
| D8: Sandwich Paragraph Rate | PARTIAL (structure classification possible with NLP) | NO | YES |
| D9: Citation Integration | YES | PARTIAL (can flag stacks and vague citations) | Converting vague to specific citations |
| D10: Preposition Padding | YES | PARTIAL (deletion is safe most of the time) | Edge cases |
| D11: Abstract/Title Formulaicism | PARTIAL | NO | YES |
| D12: Methodological Narrative | PARTIAL (can count "why" clauses and process words) | NO | YES -- author must supply process knowledge |
| D13: Voice/Stance Variation | PARTIAL | NO | YES |
| D14: Adjectival Over-Modification | YES | PARTIAL (deletion test is mechanical) | Edge cases |
| D15: Concrete Specificity | PARTIAL (number density, CI reporting rate) | NO | Author must supply specific numbers |

### Automation Priority

**Implement first** (high-confidence, mechanical, catch the most egregious AI text):
- D1 (Lexical): word frequency scanner
- D2 (Discourse markers): density counter
- D4 ("Not only...but also"): presence detector
- D10 (Preposition padding): phrase counter
- D5 (Signposting): phrase counter

**Implement second** (computationally straightforward but output requires human review):
- D3 (Syntactic uniformity): sentence-length statistics
- D6 (Hedging): density and hedge-stack detector
- D9 (Citations): name-vs-parenthetical ratio
- D14 (Adjectival): modifier density counter

**Human-only** (requires understanding of content, not just form):
- D7 (Bullet-to-prose)
- D12 (Methodological narrative)
- D13 (Voice/stance variation)
- D15 (Specificity quality -- as opposed to quantity)

---

# Part 4: Comparison: English De-AI vs. Chinese De-AI

## What English Needs That Chinese Doesn't

| English-Unique Concern | Reason |
|------------------------|--------|
| **Lexical over-representation of specific words** (delve, pivotal, realm, tapestry, etc.) | Chinese AI text has "translationese" issues but not a specific lexicon of over-represented words, because the Chinese training data was smaller and more diverse. English training data was dominated by certain RLHF-preferred completions that encoded these words as "good academic English." |
| **"Not only...but also..." detection** | This specific parallel construction is massively over-represented in English LLM output but has no direct Chinese analogue. Chinese uses different parallel constructions (不仅...而且...) that are not as sharply over-represented. |
| **The sandwich paragraph** | English LLMs over-produce this structure because English composition pedagogy emphasizes topic-sentence-first paragraphs, and LLMs learned this from training data. Chinese academic writing has different paragraph conventions. |
| **"In the context of" and preposition-phrase padding** | These specific English preposition-phrase fillers have no direct Chinese equivalent. Chinese padding takes different forms (e.g., 在...的背景下, which is more concise). |
| **Citation integration patterns** | English citation conventions (author-name vs. parenthetical, stacking) are specific to English-language academic publishing. Chinese citation practices differ (more author-name, less stacking, different formatting). |
| **Field-specific markers** (SOTA, benchmark, leverage for CS; elucidate, mechanistic for biomedical) | These are English academic subculture markers. Chinese academic fields have different in-group markers. |
| **"Delve into" as the #1 AI shibboleth** | "Delve" is the most notoriously overused word in ChatGPT academic English. It is virtually absent from human academic prose. This specific lexical marker has no Chinese equivalent. |

## What Chinese Needs That English Doesn't

| Chinese-Unique Concern | Reason |
|------------------------|--------|
| **Translationese detection** (翻译腔) | Chinese AI text often reads like translated English. Markers include: overuse of 被字句 (passive voice, rare in native Chinese), 的之堆叠 (stacked 的), English word-order calques (modifier-before-noun chains that are grammatical in English but unnatural in Chinese). English has no translationese problem because the LLM is native-English. |
| **Classical Chinese / 成语 overuse** | Chinese LLMs over-deploy 成语 (four-character idioms) and classical constructions to sound "educated." This is analogous to English Latinisms (but specific to the Chinese diglossia between modern and classical registers). English LLMs do use Latinate vocabulary excessively, but it's a different phenomenon -- less about set phrases, more about register inflation. |
| **Register mismatch** (口语/书面语混用) | Chinese LLMs sometimes mix colloquial and formal registers (e.g., using 口语 particles like 吧, 吗 in academic prose, or conversely, using overly formal 书面语 in contexts that call for a middle register). English LLMs have better register control because the training data was larger and more stratified. |
| **Topic-comment structure flattening** | Chinese is a topic-comment language. Native Chinese academic prose uses topic chains and zero-anaphora in ways that LLMs struggle to replicate. LLM Chinese tends to over-specify subjects (a Subject-Verb-Object calque from English), producing unnaturally explicit prose. English is SVO-natively, so this is not an issue. |
| **Punctuation differences** | Chinese uses different punctuation conventions (、顿号, 「」引号 variants, full-width punctuation). LLMs sometimes use English punctuation in Chinese contexts, which is a strong AI signal. |
| **Character-level errors** | LLMs sometimes generate incorrect Chinese characters (homophone errors, character substitutions) that a native writer would never make. English LLMs don't make spelling errors, so this detection vector doesn't exist. |

## Shared Concerns (Both Languages)

| Concern | English Manifestation | Chinese Manifestation |
|---------|----------------------|----------------------|
| Discourse marker over-density | "Moreover, furthermore, additionally" | 此外，而且，另外，同时 |
| Paragraph length uniformity | Uniform 4-5 sentence paragraphs | Uniform paragraph lengths (often measured in characters) |
| Generic conclusions | "More research is needed" | 有待进一步研究 |
| Bullet-to-prose artifacts | List-like paragraphs without flow | Same |
| Over-hedging | "May potentially suggest" | 可能在一定程度上表明 |
| Lack of specific claims | Vague claims without numbers | Vague claims without numbers |

---

# Part 5: Evidence Base and Journal Positions

## Research Findings on LLM Academic English

| Finding | Source | Implication for De-AI |
|---------|--------|----------------------|
| GPT-3.5/4 abstracts are detected by humans at only ~50-60% accuracy (near chance) | Gao et al. (2023), Elsevier AI-detection studies | Human judgment alone is insufficient. Structured checklists improve detection. |
| Certain words (delve, pivotal, realm, etc.) appeared 10-100x more frequently in PubMed after ChatGPT's release | Kobak et al. (2024) "Monitoring the use of ChatGPT in academic writing through excess word frequency" (arXiv) | Dimension 1 (lexical over-representation) is empirically grounded, not just impressionistic. The "excess word" method is the most robust single detection strategy. |
| LLM text has lower perplexity and lower burstiness than human text | GPTZero technical reports; Mitchell et al. (2023) "DetectGPT" | Dimension 3 (syntactic uniformity/burstiness) has statistical foundations. |
| 33-50% of peer reviewers cannot reliably distinguish AI-generated from human-written abstracts in blinded tests | Nature (2023) editorial "Tools such as ChatGPT threaten transparent science" | The LLM prose problem is worse than most researchers think. |
| AI-generated references contain 30-70% fabricated citations depending on the model and field | Multiple reproduction studies (2023-2025) | Citation verification is essential. This is covered in Stage 6 of the pipeline but should be cross-checked during De-AI. |
| GPT detectors systematically misclassify non-native English (NNES) as AI-generated, with false positive rates of 50-70% for some detector-tool combinations | Liang et al. (2023) "GPT detectors are biased against non-native English writers" (Patterns, 4(7), 100779) | Every "this pattern = AI" rule also flags NNES writing. Composite scoring must be adjusted for NNES authors. See NNES caveat in Part 0. |
| Co-occurrence of multiple markers is far more diagnostic than any single marker | Consensus finding across detection studies | The composite scoring checklist (Dimension 16) is the correct approach. No single dimension is dispositive. |

## Journal Positions on AI Writing (as of 2025-2026)

| Journal/Publisher | Policy Summary |
|-------------------|---------------|
| **Nature Portfolio** | AI use must be declared in the Methods or Acknowledgements. AI cannot be listed as an author. AI-generated text must be disclosed. AI-generated images/videos are not permitted without explicit approval. |
| **Science (AAAS)** | AI-generated text, figures, or data are not permitted unless part of the study design and explicitly approved by the editors. Undisclosed AI use is considered scientific misconduct. |
| **Cell Press** | AI tools may be used to improve language and readability but must be disclosed. Authors are fully responsible for accuracy. Generative AI is not suitable for creating or modifying figures. |
| **The Lancet / Elsevier** | Authors must disclose use of AI-assisted technologies. AI cannot be an author. Authors are accountable for all content, including AI-assisted sections. |
| **ICML / NeurIPS / CVPR** | AI writing assistance must be disclosed. Some conferences prohibit AI-generated text in submissions. Policies are evolving rapidly. |
| **COPE (Committee on Publication Ethics)** | AI tools cannot be authors. Their use must be transparently disclosed. Editors should be alert to undisclosed AI use, but current detection tools are unreliable and should not be used as the sole basis for rejection. |

### Practical Conclusion from Journal Positions

1. **Disclosure is required, not optional** at all major journals.
2. **Undisclosed AI use = misconduct** at Science, Nature, and most other top venues.
3. **Detection tools are considered unreliable** by publishers -- they will not reject based solely on an AI detector score. But editors and reviewers are increasingly experienced at recognizing AI-written prose, and the "I know it when I see it" judgment is increasingly common in desk decisions.
4. **The safest strategy**: Make your text genuinely human-like. Disclosure provides legal cover, but it does not protect against the implicit quality penalty that AI-written text carries in peer review (reviewers perceive AI text as lower quality, even when factually correct, per multiple preprint studies).

---

# Part 6: Recommended Minimum Viable Set

If you can only implement a subset of these 19 dimensions, implement them in the following priority order. This ordering maximizes detection power per unit of implementation effort.

## Tier 1: Immediately Implement (Catches ~70% of AI text)

| Dim | What to Implement | Implementation Effort | Detection Power |
|-----|-------------------|----------------------|-----------------|
| **D1** | Lexical over-representation scanner: count Tier 1-3 words, flag above threshold | LOW: word list + counter script (1-2 hours to implement) | VERY HIGH: targets the most discriminative single feature |
| **D2** | Discourse marker density: count markers per 1,000 words, flag above threshold | LOW: marker list + counter script (30 min) | HIGH: LLM text is consistently over-markered |
| **D4** | "Not only...but also" detector: presence/absence | TRIVIAL: regex (5 min) | HIGH: near-zero false positive rate for AI text |
| **D6** | Hedge stack detector: regex for stacked hedges | LOW: hedge list + adjacency check (30 min) | MODERATE-HIGH: strong signal when positive |
| **D10** | Preposition-padding counter: count "in the context of", etc. | LOW: phrase list + counter (30 min) | MODERATE-HIGH: strong signal when positive |

**Total implementation effort: ~3 hours. Detection coverage: ~70% of AI-generated text.**

## Tier 2: Implement Next (Catches ~85% combined with Tier 1)

| Dim | What to Implement | Effort | Detection Power |
|-----|-------------------|--------|-----------------|
| **D3** | Sentence-length statistics (mean, SD, range, % ultra-short, % ultra-long) | MEDIUM: requires sentence segmentation + stats (2-3 hours) | HIGH: burstiness is a core LLM vs. human difference |
| **D5** | Signposting phrase counter (section preview, roadmap, section recap) | LOW: phrase list + counter (30 min) | MODERATE |
| **D9** | Citation pattern analyzer (author-name ratio, stacking count, vague attribution count) | MEDIUM: requires citation extraction + classification (3-4 hours) | MODERATE-HIGH |
| **D14** | Adjectival over-modification counter (adjective density, double-adjective pairs, key/innovative/robust counter) | LOW-MEDIUM: requires POS tagging + stat counter (2 hours) | MODERATE |

**Total additional effort: ~9 hours. Combined detection coverage: ~85%.**

## Tier 3: Human-Guided (the remaining ~15%)

| Dim | What to Do | Effort |
|-----|-----------|--------|
| **D7** | Read aloud to detect bullet-to-prose artifacts | 15-30 min per paper |
| **D8** | Check paragraph structure variety | 10-15 min per paper |
| **D11** | Check abstract and title against templates | 10 min per paper |
| **D12** | Methodological narrative audit: count "why" clauses, check for rejected alternatives | 20-30 min per paper |
| **D13** | Voice/stance variation check: mark confidence level per paragraph | 15-20 min per paper |
| **D15** | Numbers audit: flag every claim that could be quantified | 20-30 min per paper |

**Total human review time: ~2 hours per paper.** This is the irreducible human judgment layer that automation cannot replace.

### Surface vs. Deep Feature Classification

The 19 dimensions divide into two categories with different robustness properties:

**Surface features (degrading -- will weaken as LLMs improve):**
These exploit specific word lists, constructions, and statistical patterns from the current LLM generation. They are high-precision TODAY but require recalibration as models evolve.

| Dim | Feature | Degradation Risk | Recalibration Frequency |
|-----|---------|-----------------|------------------------|
| D1 | Lexical over-representation | HIGH -- word list changes per model generation | Every 3-6 months |
| D2 | Discourse marker density | MODERATE -- markers are stable but overuse patterns shift | Every 6-12 months |
| D4 | "Not only...but also" | MODERATE -- specific construction, may be RLHF'd out | Every 6-12 months |
| D5 | Signposting density | MODERATE | Every 6-12 months |
| D10 | Preposition padding | MODERATE -- specific phrases | Every 6-12 months |
| D14 | Adjectival over-modification | MODERATE-HIGH | Every 3-6 months |

**Deep features (robust -- will remain diagnostic as LLMs improve):**
These exploit fundamental properties of autoregressive text generation and the absence of genuine cognitive processes. They are lower-precision TODAY (harder to automate) but will INCREASE in relative importance over time.

| Dim | Feature | Robustness Rationale |
|-----|---------|---------------------|
| D3 | Syntactic burstiness | Emerges from autoregressive sampling; extremely hard to suppress without post-hoc editing |
| D6 | Hedge quality (not density) | Formulaic vs. diverse hedging reflects genuine epistemic reasoning vs. pattern matching |
| D7 | Bullet-to-prose artifacts | Emerges from prompt structure, not generation; detectable regardless of model quality |
| D8 | Sandwich paragraph rate | Reflects training data composition tendencies; slow to change |
| D9 | Citation integration | Named citations with specific attribution require external knowledge; LLMs default to parenthetical stacking |
| D12 | Methodological narrative | Requires actual research process knowledge; cannot be hallucinated convincingly at length |
| D13 | Voice/stance variation | Reflects genuine author cognition; monotonic stance is a structural LLM bias |
| D15 | Concrete specificity | Numbers, dates, versions, N-at-stage require ground-truth data not in the prompt |

**Investment strategy:** Implement surface-feature detectors first (they catch the most current AI text with the least effort). But prioritize deep-feature FIXES -- narrative, stance, and specificity improvements make the text genuinely human-like in ways that will survive future LLM improvements. A paper with a strong D12, D13, and D15 score is future-proof against detector evolution.

## Integration with Pipeline Stage 7

```
Stage 7: Polish & De-AI

Step 7A: Run Tier 1 automated checks → fix all flagged items
Step 7B: Run Tier 2 automated checks → fix all flagged items
Step 7C: Human-guided Tier 3 review → fix narrative, voice, specificity
Step 7D: Composite De-AI Scoring (Dimension 16) → if score < 0.65, loop back to 7A
Step 7E: Paper-audit PASS check (existing pipeline requirement)
```

---

# Part 7: The De-AI Paradox

A final note on strategy: the most effective De-AI technique is not to edit AI-generated text but to **write in a mode that prevents AI artifacts from appearing in the first place**.

The pipeline's Stage 4 (Write) should be informed by these dimensions. If the writer (human or agent) knows that sandwich paragraphs are an LLM tell, they can deliberately vary paragraph structure during drafting rather than fixing it in post-processing. If they know that "delve into" is toxic, they won't use it in the first pass.

**Prevention is cheaper than detection.** The De-AI framework is a safety net, not a writing guide. The writing guide is: write like a specific human researcher who did specific work, thinks in specific terms, and reports specific findings. The more specific the content, the harder it is for statistical patterns to emerge.

---

## References (for the De-AI guide itself)

1. Kobak, D., Gonzalez-Marquez, R., Horvát, E.-A., & Lause, J. (2024). Monitoring the use of ChatGPT in academic writing through excess word frequency. arXiv:2405.19049.
2. Liang, W., Izzo, Z., Zhang, Y., Lepp, H., Cao, H., Zhao, X., ... & Ye, J. (2024). Monitoring AI-modified content at scale: A case study on the impact of ChatGPT on peer reviews. ICML 2024.
3. Gao, C. A., Howard, F. M., Markov, N. S., Dyer, E. C., Ramesh, S., Luo, Y., & Pearson, A. T. (2023). Comparing scientific abstracts generated by ChatGPT to real abstracts with detectors and blinded human reviewers. npj Digital Medicine, 6, 75.
4. Mitchell, E., Lee, Y., Khazatsky, A., Manning, C. D., & Finn, C. (2023). DetectGPT: Zero-shot machine-generated text detection using probability curvature. ICML 2023.
5. Nature Editorial (2023). Tools such as ChatGPT threaten transparent science; here are our ground rules for their use. Nature, 613, 612.
6. COPE (2023). Authorship and AI tools. COPE Position Statement.
7. Science Journals Editorial Policies (2025). Artificial intelligence (AI) policy.

See also: `references/language-parity-note.md` — explains why the English and Chinese de-AI guides differ in length and methodology.
