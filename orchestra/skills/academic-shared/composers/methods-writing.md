# Composer: Methods Section Writing

**Purpose:** Write a reproducible Methods/Materials section in past tense with active voice preference.
**Used by:** S4 (Journal), T4 (Thesis), C3 (Coursework)
**Parameters:** `{target_word_count}`, `{language}` (en/zh), `{writing_format}` (IMRAD/章-节)

## Instructions

1. **Tense and voice.** Use past tense throughout ("We collected," "Samples were prepared"). Active voice is preferred ("We trained the model using...") but passive is acceptable for standard procedures ("Data were normalized using min-max scaling").

2. **What to include.** Cover these elements as applicable to your study:
   - Equipment, instruments, and their models/manufacturers
   - Software framework, library versions, and hyperparameters
   - Dataset source, sample size, and exclusion criteria
   - Experimental settings (temperature, pressure, epochs, batch size)
   - Statistical tests used and significance thresholds
   - Any ethical approvals or participant consent procedures

3. **Reproducibility as the goal.** A reader with equivalent resources should be able to replicate your exact procedure. If a detail matters for the result, include it. If you are omitting a detail (proprietary, patent-pending), state this explicitly.

4. **Structure by workflow.** Organize subsections in the order the work was actually performed, not alphabetically or by perceived importance. Typical flow: Participants/Data → Materials → Procedure → Statistical Analysis.

5. **Parameterization.**
   - `{target_word_count}`: Adjust depth accordingly. Shorter counts mean tighter focus on novel or non-standard procedures; standard methods get a citation.
   - `{language}`: If "zh", use Chinese section titles (方法, 材料, 实验设置, 统计分析). If "en", use IMRAD-style headings (Methods, Materials, Experimental Setup, Statistical Analysis).
   - `{writing_format}`: If "IMRAD", Methods is a standalone section. If "章-节", integrate as a subsection within the appropriate chapter.

## Verification

- [ ] Every equipment/software item mentioned includes a version, model, or specification
- [ ] Sample sizes are stated for every experiment — no dangling "we tested the model"
- [ ] Exclusion criteria are defined (e.g., "participants with < 80% trial completion were excluded")
- [ ] Statistical tests are named with significance level (e.g., "two-tailed t-test, alpha = 0.05")
- [ ] Passage could be read aloud to a colleague and they could reproduce the work
- [ ] Word count is within 10% of `{target_word_count}`

## Common Pitfalls

- **"We used standard methods" without citation.** If the method is not original, cite the protocol paper. If it is original, describe it in enough detail that a reviewer can assess it.
- **Mixing Results into Methods.** Do not report what the data showed. "We measured accuracy with 5-fold cross-validation" (Methods) vs. "5-fold cross-validation achieved 92.3% accuracy" (Results).
- **Software version omission.** "Python, scikit-learn" is not reproducible. "Python 3.10.4, scikit-learn 1.2.0" is.
- **Assuming reader expertise.** Define field-specific jargon, acronyms on first use, and non-obvious parameter choices (e.g., "C = 1.0 chosen via grid search").
