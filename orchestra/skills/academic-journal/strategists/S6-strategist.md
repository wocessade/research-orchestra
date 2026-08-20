# Stage S6: Citations & References [Strategist]

**Gate:** Q6 (BLOCK) — every citation verified (DOI resolves), BibTeX compiles, reference count matches citation count
**Goal:** Every citation is real, accessible, and correctly formatted for the target venue.
**Needs Composers:** [citation-anchor-format, literature-precheck]

## Decisions

### Tool Commands (S6)

### Citation Support Bank (P1)

1. Load `.paper/citation_support_bank.md` + `../academic-shared/citation/citation-support-bank.md`.
2. Verify candidate DOIs; set `verified=true`; remove or PLACEHOLDER_ failures.
3. Prefer bank keys when normalizing bibliography; keep bank ≠ style samples.


1. IF manuscript has `.bib` only → convert first:
   `python ../academic-shared/literature/bib_to_bibliography.py {bib} -o {output_dir}/bibliography.json`
2. Run `/check-refs` checklist: `../academic-shared/commands/check-refs.md`
3. IF `writingFormat=latex` → also `python ../academic-latex/scripts/verify_paper.py {tex_root}`


### Composer Sequence

1. Run batch verification (primary mechanism)
2. For each verdict → route accordingly
3. Run claim-to-citation alignment for top-5 references
4. Retraction check (advisory)
5. Per-reference verification for failed entries (legacy methods)
6. Chinese refs via Playwright CNKI/Wanfang workflow
7. BibTeX format and compile check


### LaTeX / BibTeX path (writingFormat=latex)

IF `writingFormat == latex`:

1. Also follow `../academic-latex/references/citations.md` — **no BibTeX from memory**.
2. Primary bibliography file is the manuscript `refs.bib` / `references.bib` (not only bibliography.json).
3. After DOI verification, run:
   `python ../academic-latex/scripts/verify_paper.py {paper_dir}/latex` (or paper root containing `.tex`/`.bib`)
   Hard-fail on cite↔bib mismatch and `PLACEHOLDER_` keys.
4. Ensure bibliography backend matches template (biblatex+biber vs bibtex) — see academic-latex project-layout.
5. Q6 still requires every `\cite` key to resolve after full compile chain.

### Batch Verification Routing (S6, lines 21-37)

Run `verify_citations.py` on the full reference list:

```bash
python ../academic-shared/literature/verify_citations.py \
  --input {output_dir}/bibliography.json \
  --output-dir {output_dir}/verification/
```

Read `{output_dir}/verification/verification_report.json`. Per-entry verdicts:

| Verdict | Action | Severity |
|---------|--------|----------|
| `true` | Proceed normally | — |
| `false` (DOI existed but no API matched) | **BLOCKING.** Replace or delete the citation. Document in fix log. | CRITICAL |
| `unresolvable` | Tag as `⚠️ [待用户确认]`. Resolve via Tier 2/3 protocols before gate passes. | HIGH |
| `contamination_level=high` | Review manually. If preprint without peer-reviewed follow-up, note in citation. | MEDIUM |
| `preprint_post_2024=true` | Label as "preprint" in text, not as peer-reviewed publication. | MEDIUM |

**Re-verification flow:** After fixing any issues, re-run `verify_citations.py`. Cache means re-runs are fast.

### Claim-to-Citation Alignment (S6, lines 39-61) — NEW

For top-5 most heavily cited references, perform alignment check:

1. Extract: "What does our manuscript CLAIM this paper says?"
2. Verify against paper's own abstract/intro/conclusion: "What does the paper ACTUALLY say?"
3. Classify:

| Classification | Action |
|---------------|--------|
| `SUPPORTS` | Proceed |
| `PARTIALLY SUPPORTS` | Adjust claim wording |
| `DOES NOT SUPPORT` | **Critical** — rewrite or find correct citation |

Document results in `{output_dir}/citation_audit_summary.md`.

### Retraction Check (S6, lines 63-65) — ADVISORY

Optional check against retraction databases (Retraction Watch, PubMed):
- IF ≥2 citations found in retraction databases → warn user and suggest replacement citations
- This is ADVICE only — not blocking

### Per-Reference Verification — Legacy Methods (S6, lines 67-73)

For individual references that failed batch verification (verdict=false or unresolvable):

| Context | Tool |
|---------|------|
| Nature-family journals | `skills-embedded/nature-citation.md` (auto-filters to Nature Portfolio, AAAS Science, Cell Press) |
| General papers | `skills-embedded/citation-management.md` for verification |
| Formatting BibTeX | `skills-embedded/bib-search-citation.md` |

### Chinese References Workflow (S6, lines 75-84)

For each Chinese-language reference, structured fallback chain:

1. **Primary — Playwright MCP (CNKI):** Navigate to CNKI → search by title → confirm author/journal/year match
   - Match → mark `[VERIFIED: CNKI]`
   - Mismatch → mark `[NEEDS USER CONFIRMATION]`
2. **Fallback 1 — Wanfang:** Retry via Playwright MCP (same browser session)
3. **Fallback 2 — Both failed:** Mark as `[NEEDS USER CONFIRMATION]` → present to user for manual verification
4. **If Playwright MCP unavailable:** Manual checklist. Ask user to verify flagged references against CNKI/Wanfang. Provide copy-paste-ready checklist.
5. **Document:** "Chinese-language references verified via CNKI/Wanfang; English-language references verified via DOI resolution."

### Citation Count Targets (S6, lines 86-96)

| Paper Type | Expected References |
|------------|-------------------|
| Short communication / letter | 15-30 |
| Standard research article | 30-60 |
| Comprehensive review | 80-150 |
| Systematic review / meta-analysis | 50-200+ |

Too few = poor literature grounding. Too many = indiscriminate citing. Every reference should be cited at least once.

### Common Citation Error Audit (S6, lines 97-108)

| Error | Detection |
|-------|-----------|
| Hallucinated DOI | `skills-embedded/citation-management.md` DOI check |
| Real paper, wrong claim | `skills-embedded/nature-reader.md` re-check |
| Preprint cited as peer-reviewed | Check journal field in BibTeX |
| Wrong author/year/venue | `skills-embedded/citation-management.md` metadata validation |
| Missing citation for key claim | Manual: every non-trivial claim needs source |
| Self-citation overuse | Count: >20% raises reviewer eyebrows |
| Format inconsistency (APA vs Vancouver mixed) | `skills-embedded/bib-search-citation.md` auto-detect and normalize |

### STOP-AND-ASK Points
- `false` verdict: confirm fabricated DOI suspicion with user. Replace or delete.
- `unresolvable` after Tier 2/3 resolution: ask user to provide correct citation or accept removal.
- `DOES NOT SUPPORT` in claim alignment: ask user whether to rewrite claim or find correct citation.
- ≥2 retracted citations found: warn user, suggest replacements.

## Gate

### Q6 Gate Checklist
- [ ] `verify_citations.py` batch verification complete — `verification_report.json` reviewed
- [ ] No `false` verdicts remain (all DOI-keyed unmatched citations resolved: replaced or deleted)
- [ ] No `unresolvable` citations left unresolved (all tagged as ✅ or ⚠️ user-confirmed)
- [ ] **Metadata check: title/author/venue/year matches API response for top 20% of references**
- [ ] Contamination signals reviewed: `contamination_level=high` entries inspected
- [ ] Preprint citations (`preprint_post_2024=true`) correctly labeled in text
- [ ] **Claim-to-citation alignment (6A.2) complete for top-5 references — no `DOES NOT SUPPORT` findings**
- [ ] BibTeX file compiles without errors (run `skills-embedded/bib-search-citation.md` export)
- [ ] Reference count matches citation count (no orphan refs, no missing refs)
- [ ] Citation style matches target venue requirements (check `skills-embedded/venue-templates.md`)
- [ ] **文献审计摘要已写入 `{output_dir}/citation_audit_summary.md`**

### Gate Failure Route
Q6 is BLOCK.

1. First failure → identify which check items failed → route back to corresponding sub-step:
   - DOI issues → route to S6A (DOI verification), re-verify unresolved citations
   - Reference count mismatch → route to S6A.2 (claim alignment) or S6C (audit)
   - BibTeX compile errors → route to S6A.1 (formatting)
2. Re-run affected sub-steps → re-evaluate gate.
3. After 2 fix attempts still fail → **STOP-AND-ASK** user: expand scope, relax standards, or proceed with current state. Route back to S6A, re-verify unresolved entries.
