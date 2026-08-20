# DO / DON'T Rules

## DO

- Verify every citation before writing (Stage 2, then again Stage 6)
- Use the two-stage write process: outline first, prose second
- Include at least 1 schematic + 2 data figures per paper
- Follow the Polish Loop: polish → audit → fix → re-polish (minimum 2 passes)
- Polish AFTER content is complete, not paragraph by paragraph
- Read key papers with `skills-embedded/nature-reader.md` (中英对照) before citing them
- Run snowballing (backward + forward) on top 10 papers
- Define inclusion/exclusion criteria BEFORE starting literature search
- Save all search strings for reproducibility
- Tag papers in Zotero by theme, quality, and relevance
- Report effect sizes AND confidence intervals, not just p-values
- Check figure-text consistency before polish stage
- Respect quality gates — don't proceed with unresolved Critical/major items
- Vary paragraph length; read prose aloud to catch AI rhythm
- **Stop and ask** at uncertainty, decision points, and ambiguous results (see Stop and Ask Protocol)
- **Ask for more data** when a borderline pattern would become publishable with additional evidence
- **Seek help for skill gaps**: if the pipeline needs something (analysis method, visualization, format conversion, domain knowledge) that no installed skill covers, tell the user exactly what's needed and ask if they can provide a tool/script/approach — never silently substitute a wrong method
- **Run the novelty audit** (Stage 2.5) after literature review — check what makes your paper different from published work before you start writing
- **Select your target journal before formatting** (Stage 8.5) — formatting for the wrong journal means reformatting
- **Document your identification strategy** if your paper makes causal claims — "we controlled for confounders" is not a strategy
- **Run the reproducibility check (Stage 6.5)** — back up data, record random seeds, document package versions
- **Run the reviewer attack drill (Stage 9.5)** before submission — find your own fatal flaws before reviewers do
- **Identify your paper type at S1 or D2** — a Software Paper is not a Data Paper is not a Registered Report. Each has a different structure, different skills, and different venues. The standard IMRAD pipeline adapts to your paper type, not vice versa
- **Share the S3 claim outline with co-authors before writing prose** — structural feedback after S4 is 3-5× more expensive to act on

## DON'T

- Skip literature review and write from memory
- Use `skills-embedded/nature-citation.md` for non-Nature journals
- Submit when `skills-embedded/paper-audit.md` reports unresolved Critical/major items
- Polish and format simultaneously — content first, format last
- Write abstract before the rest of the paper is done
- Use "moreover/furthermore/additionally" more than twice per page
- Report "p<0.05" without exact values
- Use the same sentence structure in consecutive paragraphs
- Keep placeholder text like "[insert figure here]" or "[TBD]" in final draft
- Proceed to next stage if current quality gate has unresolved Critical/major items
- **Forge ahead silently** when uncertain — a 30-second question saves hours of rewriting
- **Settle for weak data** without asking if stronger data exists — "do you have X" costs nothing to ask
- **Fake a capability** no installed skill handles — say "I can't do X with current tools, can you help?" instead of doing X poorly with the wrong tool
- **Claim causality** without an identification strategy — downgrade to "associated with" or go back to Stage 1.5
- **Format before selecting a venue** — Stage 8.5 comes before Stage 8
- **Report p-values during exploratory data analysis (D1)** — discovery is not confirmation; p-values have no meaning until you've chosen a hypothesis
- **Skip reproducibility (S6.5) and reviewer attack (S9.5) checks** — they catch what peer review would find anyway, but with time to fix
- **Confuse a preliminary novelty check (D2B) with a systematic novelty audit (S2.5)** — the real assessment needs a full literature review
- **Let an agent self-mark its own Chinese citation output as [USER-SOURCED]** — this tag can only be added by the main pipeline after receiving user-provided CNKI/Wanfang search results. An agent fabricating citations and self-tagging them as user-sourced is the highest-severity violation of citation integrity.
