# Composer: Abstract and Title Writing

**Purpose:** Write a structured abstract (problem → method → key result → implication) and a specific, searchable title.
**Used by:** S4 (Journal), T4 (Thesis), C3 (Coursework)
**Parameters:** `{target_word_count}` (abstract word count), `{language}` (en/zh), `{degree_level}` (bachelor/master/none)

## Instructions

### Abstract

1. **Four-sentence structure (or equivalent).** The abstract must cover exactly four elements, in order:
   - **Problem/Background (sentence 1):** What is the gap or problem this work addresses.
   - **Method (sentence 2):** What approach was taken (high-level — no technical details).
   - **Primary result (sentence 3):** The key finding WITH effect size. "We achieved high accuracy" is insufficient. "Accuracy improved from 81% to 94% (p < 0.001)" is sufficient.
   - **Implication (sentence 4):** What this means for the field and what should happen next.

2. **Word count discipline.**
   - English abstracts: 150-250 words. Hard limit. Every word must carry weight.
   - Chinese abstracts: 300-1000 characters depending on `{degree_level}`:
     - Bachelor: 300-500 characters
     - Master: 500-1000 characters
     - No degree (journal/coursework): Use `{target_word_count}` directly

3. **Chinese abstract specifics (from T4).**
   - Include keywords (关键词) after the abstract, 3-8 terms
   - Structure follows the same four elements as English
   - Must be a standalone summary — reader should understand the whole paper from the Chinese abstract alone

4. **No citations in abstract.** The abstract must be self-contained and readable without the main text. Do not include citation markers.

5. **Write abstract LAST.** The abstract summarizes what the paper found. It cannot accurately do this until Results and Discussion are finalized. An abstract written first will frequently contradict the actual findings.

### Title

1. **Specific and searchable.** The title should contain the key concepts that a researcher would search for. "An improved method for X using Y" is better than "A study of X."

2. **No padding phrases.** Avoid:
   - "A Study of..."
   - "Research on..."
   - "An Investigation into..."
   - "Preliminary observations on..."
   These waste words and add no information.

3. **Colon use.** Use a colon only when the title has two distinct parts (e.g., method and application): "BERT Fine-Tuning for Clinical NLP: A Case Study on Discharge Summaries." If a colon is not needed, do not add one.

4. **Length.** 10-20 words for English. 15-30 characters for Chinese. Shorter is better.

5. **Tone.** Declarative and factual. Avoid hype ("novel," "first-ever," "state-of-the-art" unless verifiable). Use standard terminology rather than clever wordplay.

6. **Parameterization.**
   - `{language}` = "zh": Write title and abstract in Chinese. Include English abstract as second section for thesis.
   - `{language}` = "en": Title and abstract in English.
   - `{degree_level}`: Determines Chinese abstract character count and whether both Chinese and English abstracts are required.

## Verification

- [ ] Abstract follows the four-element structure (problem → method → result → implication)
- [ ] Primary result includes an effect size, not a qualitative claim
- [ ] English abstract is 150-250 words (or `{target_word_count}` range)
- [ ] Chinese abstract character count matches `{degree_level}` guidelines
- [ ] No citations in abstract
- [ ] Title is 10-20 words (English) / 15-30 characters (Chinese)
- [ ] Title avoids "A Study of," "Research on," "An Investigation into"
- [ ] Title claims are supported by data in the paper (abstract was written last)
- [ ] Keywords provided (3-8) for Chinese abstract

## Common Pitfalls

- **Background taking 50% of the word budget.** The first sentence should be one line, not three. The result and implication need the most space.
- **Abstract contradicts actual finding.** This happens when the abstract is written first and never updated. Always verify after Results are final that the abstract matches.
- **Vague title.** "Deep Learning for Text Classification" is not searchable — hundreds of papers share this title. "Hierarchical Attention Networks for Document Classification" is specific.
- **No effect size in abstract.** "We achieved good results" tells the reader nothing. "3.2% improvement over baseline" gives the reader a meaningful takeaway.
- **Abstract packed with method details.** The abstract should describe the approach at a high level. Save the hyperparameters and framework versions for Methods.
