# Composer: Results Section Writing

**Purpose:** Write a Results section in past tense, leading with data rather than interpretation.
**Used by:** S4 (Journal), C3 (Coursework)
**Parameters:** None (pure execution — word count and tense are fixed by convention)

## Instructions

1. **Tense.** Use past tense throughout ("The model achieved," "Accuracy improved by"). Avoid present tense for your own findings ("The results show" is acceptable in lead-in, but individual findings are past tense).

2. **Lead with the finding, not the figure.** Each paragraph opens with the one key takeaway, followed by the supporting evidence.
   - GOOD: "Fine-tuning improved cross-domain accuracy by 12.4 percentage points (p < 0.01), as shown in Figure 3."
   - BAD: "Figure 3 shows the accuracy of fine-tuned models across three domains."

3. **One finding per paragraph.** Each paragraph should communicate exactly one result. If you have three major findings, you should have three paragraphs (or three subsections, for longer works).

4. **Evidence bundle.** After stating the finding, provide:
   - The quantitative evidence (effect size, p-value, confidence interval)
   - A visual reference ("Figure X," "Table Y")
   - Only the statistics that directly support the claim — do not dump every output number

5. **Report negative and null results.** If an experiment did not work or a hypothesis was not supported, state it plainly. A null result with adequate power is a valid finding.

6. **No interpretation.** Do not say "this suggests that," "these results imply," or "the reason may be." Those belong in Discussion. The Results section is for reporting what the data say, not what they mean.

## Verification

- [ ] Every paragraph opens with a finding, not a figure reference
- [ ] Past tense used throughout body sentences
- [ ] Each key result is stated once — no redundant prose repetition
- [ ] Negative/null results are reported alongside positive ones
- [ ] No interpretive language ("suggests," "implies," "indicates" as conclusion) — save for Discussion
- [ ] No Methods content leaked into Results (e.g., "we used 10-fold CV" does not belong here)

## Common Pitfalls

- **"Figure 3 shows..." as a topic sentence.** The figure is the evidence, not the finding. State the finding first — the reader wants the destination, not the map.
- **Interpreting results in Results.** Every sentence that starts with "This suggests..." or "This may be because..." belongs in Discussion. In Results, state what happened; in Discussion, state why it matters.
- **Repeating every table number in prose.** "Table 1 shows accuracy, Table 2 shows precision, Table 3 shows recall" is not narrative prose. Reference the key comparison and cite the table: "Fine-tuning precision (Table 2) improved across all domains."
- **Dumping every output statistic.** Not every intermediate metric needs reporting. Report only the numbers that answer your research question or support your claim.
- **Omitting variability.** A mean without a standard deviation or confidence interval is incomplete. "Accuracy was 92%" is not a result — "Accuracy was 92% (SD = 1.8, n = 50)" is a result.
