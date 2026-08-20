# NNES Chinese-English Academic Writing Guide

## Version: 1.0 | 2026-06-23
## Scope: Chinese native speakers writing English academic manuscripts
## Auto-load: Stage 4 (Write) and Stage 7 (Polish) when `language=en`
## Integrates with: `english-academic-writing-guide.md`, `english-de-ai-guide.md`

---

> **~10 KB reference file.** Prefer on-demand partial reads.
> **Sections:** `## Version: 1.0 | 2026-06-23` · `## Scope: Chinese native speakers writing English academic m...` · `## Auto-load: Stage 4 (Write) and Stage 7 (Polish) when `lan...` · `## Integrates with: `english-academic-writing-guide.md`, `en...` · `## 1. Topic-Comment to Subject-Verb Conversion` · `## 2. Modifier Placement`
> `## 3. Articles and Determiners` · `## 4. Paratactic to Hypotactic Conversion` · `## 5. Common Lexical Transfer Errors` · `## 6. 15-Point Self-Check for Chinese NNES Authors` · `## 7. Voice and Tense Quick Reference` · `## Integration Notes`

This guide targets structural transfer errors from Chinese to English -- patterns that arise because Chinese and English organize information differently at the sentence level. The De-AI detection framework (`english-de-ai-guide.md`) notes that GPT detectors misclassify NNES writing as AI-generated at 50-70% false positive rates. Many of the features that trigger detectors (low burstiness, formulaic discourse markers, restricted lexical variety) are also features of NNES academic English. Fixing the underlying transfer patterns improves both your writing quality and your De-AI score simultaneously.

---

## 1. Topic-Comment to Subject-Verb Conversion

Chinese uses topic-comment structure; English requires subject-verb. This is the single most pervasive transfer error.

A Chinese sentence announces a topic, then makes comments about it -- the topic need not be the grammatical subject. An English sentence requires an explicit grammatical subject that performs the verb's action or is described by it.

**Examples:**

- Chinese topic-comment word order: "The experiment results, we analyzed using SPSS"
- English subject-verb: "We analyzed the experimental results using SPSS"

- Chinese-style topic fronting: "As for the control group, no significant difference was found"
- English restructuring: "The control group showed no significant difference"

- Chinese zero-subject (dropped subject): "Compared with previous methods, achieved better performance"
- English with explicit subject: "Our method achieved better performance than previous approaches"

**Rule:** Every English sentence must have an explicit grammatical subject. If the Chinese original drops the subject, add one: "We", "The study", "This finding", "These results", "The present work".

**Self-check:** For each sentence, underline the grammatical subject. If you cannot find one, the sentence is a topic-comment transfer.

---

## 2. Modifier Placement

Chinese places all modifiers before the noun (left-branching). English can place modifiers after the noun via relative clauses, prepositional phrases, and participial phrases (right-branching). Chinese NNES authors tend to stack modifiers before the noun, producing unreadable pre-posed chains.

**Examples:**

- Pre-posed modifier chain: "The using deep learning methods developed prediction model"
- Post-modified: "The prediction model developed using deep learning methods"

- Pre-posed: "The in 2024 by WHO published report"
- Post-modified: "The report published by WHO in 2024"

- Pre-posed: "The hospital-acquired infection rate reduction intervention compliance assessment protocol"
- Post-modified: "the protocol for assessing compliance with the intervention designed to reduce hospital-acquired infection rates"

**Rule:** If a modifier phrase is longer than 3-4 words, move it after the noun. Use "that" clauses, "which" clauses, "-ing" participles, and "by" phrases.

**Of-phrase chains:** English tolerates two nested "of" constructions; three is borderline; four is unreadable. "The effect of the concentration of the inhibitor of the enzyme on the rate of the reaction" should become "How inhibitor concentration affects reaction rate."

---

## 3. Articles and Determiners

Chinese lacks articles (a/an/the) and grammatical plural marking. Chinese NNES writers frequently drop them in English, producing prose that reads as ungrammatical rather than NNES-accented.

**Heuristics:**

| Situation | Article | Example |
|-----------|---------|---------|
| First mention of a countable singular noun | a/an | a method, an algorithm, a finding |
| Previously mentioned or uniquely identifiable | the | the method described above, the results |
| Generic plural or uncountable noun | no article | Methods vary across disciplines; Research shows that... |
| Noun specified by an of-phrase or that-clause | the | the effect of temperature, the finding that X affects Y |
| Superlatives and ordinals | the | the largest effect, the first study |
| Shared knowledge in the field | the | the literature, the scientific community |

**Self-check:** Read your text and underline every common noun. Ask: (1) Is it countable? (2) Is it specific or general? (3) Is it first mention? If the answer to any question is unclear, you are probably missing an article.

---

## 4. Paratactic to Hypotactic Conversion

Chinese favors paratactic structures -- clauses joined by meaning without explicit connectors. English requires hypotactic structures -- explicit logical connectors showing how clauses relate.

**Examples:**

- Comma splice (paratactic): "The sample size was small, the results should be interpreted cautiously"
- Causal connector (hypotactic): "Because the sample size was small, the results should be interpreted cautiously"
- Prepositional phrase: "Given the small sample size, the results should be interpreted cautiously"
- Semicolon + connector: "The sample size was small; therefore, the results should be interpreted cautiously"

- Missing contrast marker: "The treatment group improved, the control group did not"
- Explicit contrast: "The treatment group improved, whereas the control group did not"

- Stacked clauses without hierarchy: "The model was trained on 10,000 images, the validation set was 2,000 images, we used a learning rate of 0.001"
- Hierarchical with connectors: "The model was trained on 10,000 images with a learning rate of 0.001 and validated on a separate 2,000-image holdout set"

**Rule:** If two clauses sit next to each other with only a comma between them, add a logical connector (because, although, whereas, therefore, however, while, since, after) or break them into separate sentences.

---

## 5. Common Lexical Transfer Errors

These patterns arise because certain Chinese academic constructions have literal English equivalents that are grammatical but unnatural.

| Chinese Pattern | Literal Transfer (avoid) | Natural English (use) |
|----------------|--------------------------|----------------------|
| Verb dilution | "conduct/carry out analysis" | "analyze" |
| Light-verb construction | "perform an investigation of" | "investigate" |
| Verb dilution | "make a comparison between" | "compare" |
| Preposition overuse | "through the use of" | "using", "by" |
| Determiner overuse | "this research/article/paper" | "the present study", "our work", or rephrase without the determiner |
| Existential placeholder | "there exists a problem" | "a problem arises", "one limitation is" |
| Redundant comparison | "different methods have different results" | "methods differ in their results" |
| Temporal cliche | "with the development of..." | "as X has advanced", "recent advances in X" |
| Quantity cliche | "more and more researchers" | "a growing body of research", "increasing attention" |
| Verb dilution | "give guidance to" | "guide", "inform" |
| Nominalization chain | "the improvement of the performance of the model" | "improving model performance" |
| Passive default | "it was found that" | "we found that" or "the results showed that" |
| Redundant scope | "in the process of" | delete; "in the process of analyzing" becomes "while analyzing" |
| Hedge dilution | "has a certain degree of influence" | "influences" or "affects (beta = 0.23)" |

**Principle:** Prefer the verb over the verb-noun pair. Prefer the specific over the placeholder. Prefer the direct over the circumlocution.

---

## 6. 15-Point Self-Check for Chinese NNES Authors

Run this checklist on every section before submitting.

1. Does every sentence have an explicit grammatical subject?
2. Are articles (a/an/the) present where needed?
3. Are all verbs in the correct tense? (See Section 7 for tense-by-section.)
4. Are there any comma splices? (Two independent clauses joined only by a comma.)
5. Were any sentences translated word-for-word from Chinese that should be restructured?
6. Are all "conduct/carry out/perform + noun" patterns replaced with direct verbs?
7. Are prepositions correct? (in the field, on the topic, at the level, by the method, for the purpose of)
8. Is the word order Subject-Verb-Object, not Topic-Comment?
9. Are plural nouns marked with -s where needed?
10. Are relative clauses and long modifiers placed after the noun (not pre-posed)?
11. Is "more and more" replaced with academic alternatives?
12. Are logical connections explicit between clauses? (because, therefore, however, although, whereas)
13. Are numbers and units formatted correctly? (spacing, SI units, significant figures, decimal points not commas)
14. Is the citation format consistent? (integral vs. non-integral, per the target journal's style)
15. If unsure about a collocation, check: do native-speaker papers in your target journal use this phrase?

---

## 7. Voice and Tense Quick Reference

| Section | Dominant Tense | Voice Guidance |
|---------|---------------|----------------|
| Introduction (established knowledge) | Present | Active preferred |
| Introduction (gap/contribution) | Present | Active |
| Introduction (prior studies) | Past or Present perfect | Active |
| Methods | Past | Active or passive (both acceptable) |
| Results | Past | Active preferred |
| Discussion (your findings) | Past / Present perfect | Active |
| Discussion (literature comparison) | Present | Active |
| Discussion (implications) | Present | Active |
| Conclusion | Present | Active |

**Note on passive voice:** Passive is legitimate in Methods sections ("Samples were centrifuged at 3,000 rpm") and when the agent is unknown or irrelevant. The problem is not passive voice itself but the Chinese NNES tendency to use passive as a default because Chinese topic-comment structure maps more naturally to English passive. Ask: "Who did this?" If the answer is "we" and the information matters, use active.

---

## Integration Notes

- This guide loads automatically at Stage 4 (Write) and Stage 7 (Polish) when `language=en`.
- It is a structural companion to `english-academic-writing-guide.md` (craft instruction) and `english-de-ai-guide.md` (detection framework).
- Key insight for Chinese NNES authors: fixing transfer errors (topic-comment, missing articles, paratactic clauses) simultaneously improves writing quality, reduces AI-false-positive risk, and makes specific-verb choices that eliminate De-AI lexical markers (D1).
- The 15-point checklist is self-contained; run it at the end of writing before entering the De-AI pipeline.
