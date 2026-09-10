# Composer: literature-precheck

**Purpose:** Batch-verify all DOIs via verify_citations.py and spot-check claim-to-citation alignment before proceeding to polish, preventing fabricated/hallucinated references from entering the final manuscript.
**Used by:** academic-journal S7 (existing-manuscript entry precheck), academic-journal S6 (citation verification)
**Parameters:** `{entry_type}` (existing-manuscript = full verify all DOIs; normal = 20% spot-check), `{output_dir}`

## Instructions

### 1. Primary Verification Mechanism

Run `verify_citations.py` as the primary verification mechanism -- faster and more systematic than manual DOI-by-DOI checks:

```bash
python literature/verify_citations.py \
  --input {output_dir}/bibliography.json \
  --output-dir {output_dir}/verification/
```

**Scale by entry type:**
- `entry_type=existing-manuscript` -> verify ALL DOIs in the reference list
- `entry_type=normal` -> verify at least 20% of DOIs (spot-check)

**Expected output:** `{output_dir}/verification/verification_report.json`

**Response to verdicts:**

| Verdict | Meaning | Action |
|---------|---------|--------|
| `false` | DOI existed but no API matched | Metadata unresolved: inspect the actual source or correct record. API absence alone is not fabrication. |
| `unresolvable` | DOI could not be resolved | Tag as `TODO [awaiting user confirmation]`. Must resolve before gate. |
| `contamination_level=high` | Suspicious citation signal | Review manually. If the paper is a preprint without peer-reviewed follow-up, note this. |
| `preprint_post_2024=true` | Published after 2024 as preprint | Ensure citation is labeled "preprint" in the text, not as peer-reviewed. |

**Re-verification flow:** After fixing any issues, re-run `verify_citations.py`. The cache means re-runs are fast -- only uncached entries trigger API calls.

### 2. Claim-to-Citation Alignment (Spot-Check)

After metadata verification, check every core and changed evidence-requiring claim, then sample other claims by impact:

1. For each selected source, extract: "What does our manuscript CLAIM this paper says?"
2. For the same sources, verify against the paper's own abstract/intro/conclusion: "What does the paper ACTUALLY say?"
3. Classify each alignment:

| Classification | Meaning | Action |
|---------------|---------|--------|
| `SUPPORTS` | Claim matches paper's actual finding | Proceed |
| `PARTIALLY SUPPORTS` | Claim is directionally correct but overstated/understated | Adjust claim wording |
| `DOES NOT SUPPORT` | Claim contradicts or is absent from the cited paper | **Critical** -- rewrite or find correct citation |

**Scale by entry type:**
- `entry_type=existing-manuscript` -> check all core and changed claims, then sample other citations (all references are verified for DOI existence, so claim alignment is a representative sample)
- `entry_type=normal` -> check all core and changed claims, then sample other citations (from the 20% DOI-verified subset if possible)

### 3. Retraction Check (Advisory)

After batch verification, optionally check against retraction databases (Retraction Watch, PubMed retractions with "Retracted Publication" filter). This is ADVICE only -- not blocking. If 2+ citations are found in retraction databases, warn the user and suggest replacement citations.

### 4. Chinese References Verification

For Chinese-language references, use Playwright MCP browser automation:

1. **Auto-verify via Playwright MCP (CNKI):** For each Chinese-language reference:
   a. Use Playwright MCP to navigate to CNKI -> search by title
   b. If the paper is found -> confirm author/journal/year match
   c. Match -> mark as `[VERIFIED: CNKI]`. Mismatch -> `[NEEDS USER CONFIRMATION]`

2. **Failed CNKI?** Retry via 万方 (Playwright MCP, same browser session).

3. **Failed both databases?** Mark as `[NEEDS USER CONFIRMATION]` and present to user for manual verification.

4. **If Playwright MCP unavailable:** Fallback to manual checklist. Ask user to verify flagged references against CNKI/Wanfang. Provide a copy-paste-ready checklist.

5. **Document:** Add a note in the manuscript: "Record bibliography lookup methods in citation_audit_summary.md, not as boilerplate in manuscript prose."

### 5. Documentation

Document results in `{output_dir}/citation_audit_summary.md`:

```markdown
## Literature Precheck Summary
**Entry type:** {entry_type}
**Batch verification:** complete (X/Y DOIs verified)
**Claim-to-Citation Alignment:**
| Reference | Our Claim | Paper's Actual Finding | Verdict |
|-----------|-----------|----------------------|---------|
| Smith 2024 | ... | ... | SUPPORTS |
| ... | ... | ... | PARTIALLY SUPPORTS |
**Retraction check:** [passed / flagged N papers]
**Chinese references:** [X verified via CNKI, Y flagged]
**Overall:** [PASS / issues found -- see details above]
```

## Verification

- [ ] `verify_citations.py` batch verification complete -- `verification_report.json` reviewed
- [ ] For existing-manuscript: all DOIs verified (100% coverage)
- [ ] For normal entry: at least 20% of DOIs verified
- [ ] Metadata mismatches investigated; unresolved core support recorded as open review issues, not automatically labeled fabrication
- [ ] No `unresolvable` citations left unresolved (all tagged as user-confirmed or replaced)
- [ ] Contamination signals reviewed: `contamination_level=high` entries inspected
- [ ] Preprint citations (`preprint_post_2024=true`) correctly labeled in text
- [ ] Claim-to-citation alignment checked for 5 citations
- [ ] All `DOES NOT SUPPORT` entries resolved (rewritten or citations replaced)
- [ ] Chinese references verified via CNKI/Wanfang (if applicable)
- [ ] Retraction check advisory completed (if applicable)
- [ ] Results documented in `{output_dir}/citation_audit_summary.md`

## Common Pitfalls

- **Skipping existing-manuscript full verify:** Existing manuscripts that skipped S1-S6.5 may have entirely fabricated references. Spot-check is insufficient -- verify EVERY DOI.
- **Claim alignment on verified-only subset for normal entry:** When `entry_type=normal`, the 20% DOI-verified subset might not overlap with the 5 claim-alignment samples. Ensure claim-alignment papers are also DOI-verified.
- **Assuming Chinese references are covered by DOI verification:** Chinese domestic journals may not have resolvable DOIs in OpenAlex/Crossref. Always route Chinese references through CNKI/Wanfang via Playwright MCP.
- **Preprint labeling oversight:** Papers published after 2024 flagged as `preprint_post_2024=true` must be labeled "preprint" in the text. Failing to do so is a gate-blocking issue.
- **Retraction check as afterthought:** While advisory, finding 2+ retracted citations in a manuscript is a serious credibility issue. Do not skip the retraction check just because it is "advisory."
- **Re-verification without cache awareness:** After fixing citations, re-run `verify_citations.py`. Only uncached entries trigger API calls, so re-runs are fast.
