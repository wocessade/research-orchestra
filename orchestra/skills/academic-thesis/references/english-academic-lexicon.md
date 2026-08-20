# English Academic Lexicon -- Positive Alternatives

## Version: 1.0 | 2026-06-23
## Scope: English-language academic manuscripts, all disciplines
## Auto-load: Stage 4 (Write) and Stage 7 (Polish) when `language=en`
## Complements: `english-de-ai-guide.md` (what to avoid) and `english-academic-writing-guide.md` (how to write)

---

For every "avoid" pattern in the English De-AI framework, here is what to use instead. This is a positive-construction resource -- do not memorize the avoid column; build the habit of reaching for the "use instead" column.

## Discourse Markers

| Avoid | Use Instead |
|-------|-------------|
| Moreover, Furthermore | "We next examined...", "Two additional findings emerged", "A related observation was..." |
| Notably, Importantly | "The largest effect was...", "Unexpectedly, ...", "Of particular relevance, ..." |
| Interestingly | Either explain WHY it is interesting, or cut the word |

## Transition Phrases

| Avoid | Use Instead |
|-------|-------------|
| "It is worth noting that" | State the point directly |
| "It should be emphasized that" | Emphasize it by placing it in a short sentence; or use "Critically," if genuinely critical |
| "It is important to note that" | Delete entirely -- if important, the reader will know |

## Claim Strengthening

| Avoid | Use Instead |
|-------|-------------|
| "plays a crucial/essential role in" | Describe the specific mechanism: "X activates Y by binding to Z" |
| "has been demonstrated to" | "X has been shown to" (for replicated findings); name the specific study for specific findings |
| "highlights the importance of" | "underscores the need for" (if arguing for future work) or be specific about what was shown |

## Vague Intensifiers

| Avoid | Use Instead |
|-------|-------------|
| "a wide range of" | Name the range: "temperatures from 20 C to 80 C", "across five domains" |
| "a variety of" | Be specific: "four methods", "multiple approaches including..." |
| "in the context of" | Delete or use concrete terms: "in X settings", "when Y is present" |
| "in terms of" | Delete; restructure. "In terms of accuracy" becomes "Accuracy..." |

## Citation Integration

| Avoid | Use Instead |
|-------|-------------|
| Citation stacking: "(Smith 2020; Jones 2021; Lee 2022)" without synthesis | Named citations with signal verbs: "Smith (2020) first demonstrated..., Jones (2021) extended this to..., and Lee (2022) recently confirmed..." |
| "Previous studies have shown..." (without naming them) | Name at least 1-2 key studies: "Smith (2020) and Jones (2021) found..." |
| "There is growing evidence that..." (vague) | "Three independent replications since 2020 confirm that..." |

## Method Description

| Avoid | Use Instead |
|-------|-------------|
| "A comprehensive analysis was conducted" | "We analyzed..." (say what you did and how) |
| "The data were subjected to statistical analysis" | "We fit linear mixed-effects models (lme4 1.1-34) with..." |
| "Various parameters were optimized" | "We tuned three hyperparameters (learning rate, dropout, batch size) via grid search" |

## Discussion Scaffolding

| Avoid | Use Instead |
|-------|-------------|
| "These findings shed light on..." | "These findings identify a specific mechanism by which..." |
| "Our results contribute to a growing body of evidence" | "Our results, together with Smith (2020) and Jones (2021), establish that..." |
| "Further research is needed to" (generic) | "A randomized trial with an active control would test whether the effect is specific to..." (specific future direction) |
| "This opens up new avenues for research" | "This finding raises a specific testable question: does X also affect Y?" |

## Precision Boosters

When tempted to use a vague phrase, substitute a specific one:

| Vague | Precise |
|-------|---------|
| "in recent years" | "since 2020" (or the actual timeframe) |
| "many studies" | "over 30 studies" (or the actual number from your literature search) |
| "a significant increase" | "a 23% increase (p = 0.01)" |
| "most participants" | "78% of participants (187/240)" |
| "the results were better" | "accuracy improved by 8.5 percentage points" |
| "a large effect" | "Cohen's d = 1.3 (95% CI [0.9, 1.7])" |
| "the model performed well" | "the model achieved an F1 score of 0.87 on the held-out test set" |

## Section Openings to Replace

| Generic Opening | Content-First Opening |
|----------------|----------------------|
| "In recent years, there has been growing interest in..." | "Surface water salinization threatens drinking water supplies for over 300 million people globally, yet..." |
| "With the rapid development of [field]..." | Start with the specific gap or contradiction your paper addresses |
| "The remainder of this paper is organized as follows..." | Delete. The section headings are the roadmap. |
| "This study makes several contributions to the literature" | Name the contributions: "This study provides the first field-scale test of..." |

## Light-Verb Replacements (D17)

Chinese NNES authors frequently use light-verb + nominalization patterns calqued from Chinese (进行分析, 进行调查, 进行研究). Replace with the direct verb form:

| Light-Verb Construction | Direct Verb |
|-------------------------|-------------|
| "conduct analysis" | "analyze" |
| "perform investigation" | "investigate" |
| "carry out research" | "research" (verb) |
| "make a conclusion" | "conclude" |
| "give explanation" | "explain" |
| "conduct evaluation" | "evaluate" |
| "perform calculation" | "calculate" |
| "provide guidance for" | "guide" |
| "undertake exploration" | "explore" |

The direct verb form is shorter, stronger, and avoids the NNES calque signal. Exception: keep "conduct a meta-analysis" or "perform a power analysis" where the noun names a specific methodology, not a generic action.

## Sentence Openers — Variety Alternatives (D18)

If your sentences start with the same family repeatedly, vary the opener. Below are 5 common opener families and one structural alternative each:

| Overused Opener | Alternative |
|----------------|-------------|
| "This study analyzes..." | "We analyzed..." |
| "This paper contributes to..." | "Our contribution is to..." |
| "There is growing evidence that..." | "A growing body of evidence supports..." |
| "It is important to note that..." | "Critically, ..." / [delete entirely] |
| "It can be seen that..." | [delete or rephrase with concrete subject] |
| "Moreover, ..." | "Two additional findings emerged: ..." |
| "Furthermore, ..." | "A related observation was..." |
| "In recent years, ..." | [start with the specific problem] |
| "With the development of..." | "Advances in X have enabled..." |

Rule: vary the grammatical subject. If 3 consecutive sentences start with "This paper/study/work/article", move the subject into the predicate and start differently.

---

## How to Use This Lexicon

1. **Draft first, consult second.** Write your draft without looking at either the avoid or use-this list. Then scan for each "avoid" pattern and substitute.
2. **Build recognition, not memorization.** Focus on one category per revision pass. Run a discourse-marker pass, then a vague-intensifier pass, then a citation-integration pass.
3. **When in doubt, be specific.** Every item in the "avoid" column is a way of being vague. Every item in the "use instead" column is a way of being specific. The principle is more important than the word list.
4. **This lexicon is lossy by design.** It gives you the most common alternatives. For edge cases, consult `english-de-ai-guide.md` for the full detection rationale and `english-academic-writing-guide.md` for the positive craft instruction.
