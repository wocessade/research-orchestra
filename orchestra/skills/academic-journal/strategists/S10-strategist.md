# Stage S10: Submission Prep [Strategist]

**Gate:** Q10 (BLOCK) — cover letter written, data statement ready, all author approvals obtained.

**Goal:** Package everything the journal needs. Missing a required item = desk rejection regardless of paper quality.

**Needs Composers:** none (uses skills-embedded tools)

## Decisions

### Data Statement Routing (10B, lines 22-34)
- IF S6.5 ran → start from S6.5 draft. Adapt to target journal DAS format.
- IF journal is Nature-family → use `nature-data.md` with full FAIR metadata checklist.
- IF general journal → use simple template: "Data and code are available at [repository] under [license]."
- IF restricted data → use manual template: "Data cannot be shared publicly due to [reason]. Researchers may request access via [process]."
- IF no data to share (pure theory/modeling) → explain what IS available (code, simulation parameters, proofs).

### CS/Engineering Conditional (10-CS, lines 45-53)
- ONLY CS/Engineering papers run artifact submission package checks: anonymous repo link, README, pinned requirements.txt/environment.yml, claim-to-script map, pre-submission dry run.
- ELSE → skip artifact section.

### Ethics & Integrity Audit (10E, lines 69-84)
**COND. BLOCK** — blocks if:
- Image integrity violations found, OR
- >=2 data integrity flags, OR
- >=1 citation-claim mismatch.

Otherwise advisory.

**Red flags that block gate:**
- Human/animal subjects but no IRB/IACUC protocol number in Methods.
- Any duplicated/spliced image regions.
- Verbatim self-copy >2 sentences from prior publications.
- Data integrity patterns: p-values clustered at 0.049-0.051, identical SDs across groups, means too close to integers, Shapiro-Wilk p > 0.99.
- Claim-citation mismatch (spot-check 5 random citations).
- Missing grant numbers or COI for any author.

**Severity inheritance:** Flaws found here that are ALSO paper-audit Critical items → inherit Critical severity. Otherwise remain advisory.

### Cover Letter Generation (10A, lines 8-19)
Use `skills-embedded/cover-letter.md`. Must include: Hook (1-2 sentences), Gap (2-3 sentences), Contribution (3-4 sentences), Fit (2-3 sentences, reference recent journal papers), Declarations. Never restate the abstract — cover letter is for the editor.

### Composer Sequence
None. S10 relies on skills-embedded tools (cover-letter.md, nature-data.md, academic-research.md) — no composer invocation.

## Gate

### Q10 Gate Checklist
- [ ] Cover letter written and aligned with paper claims
- [ ] Data Availability Statement ready (or access path documented)
- [ ] Author list complete, affiliations correct, corresponding author marked
- [ ] All co-authors have read and approved the final version
- [ ] Response matrix from Stage 9 archived
- [ ] All fonts embedded in PDF
- [ ] PDF metadata correct (title, authors, keywords)
- [ ] File naming follows journal convention
- [ ] Word/page count confirmed within venue limits
- [ ] All figure resolution requirements met (300 DPI minimum for raster)
- [ ] Conflict of interest statement included
- [ ] Funding acknowledgments complete with grant numbers
- [ ] Ethics approval statement included (if human/animal subjects)
- [ ] Data deposited in repository with accession number/DOI included in manuscript
- [ ] Suggested reviewers prepared (3-5 names with affiliations and expertise justification)
- [ ] Opposed reviewers listed if needed
- [ ] Preprint status declared in cover letter (if previously posted)
- [ ] Blind manuscript version prepared if double-blind review
- [ ] CRediT author contribution statement included
- [ ] ORCID iD for corresponding author provided
- [ ] Raw manuscript files (.tex, .bib, figures/) backed up separately from compiled PDF

### Gate Failure Route
Q10 is BLOCK.

1. Inspect specific failed check item -> route back to corresponding sub-step:
   - Cover letter missing/incomplete -> S10A.
   - Author approvals missing -> S10B (author confirmation).
2. Fix, re-run affected sub-step, re-evaluate gate.
3. After 2 fix attempts still fail -> STOP-AND-ASK: expand scope, relax standards, or proceed with current state.
