# Predatory Journal Detection Protocol

**Purpose:** Automated detection of predatory / hijacked / questionable journals before formatting and submission.
**Used by:** Stage 8.5 (Publication Strategy), Section 8.5D.5
**Data source:** `references/data/bealls_list_cache.json`

## When to Run

When **one or more candidate journals** have been identified in 8.5C (Venue Name Generation).
For each candidate journal (ISSN or name), run Steps 1-3 in order.

## Step 1: Beall's List Cache Check

Load `references/data/bealls_list_cache.json` and check:
1. **ISSN exact match** — check if journal ISSN appears in the cache
2. **Name Levenshtein match** — journal name within Levenshtein distance < 3 of any cached entry

### Result
- HIT → BLOCK. This journal is flagged as potentially predatory. Recommend replacement.
- CLEAR → Continue to Step 2.

> **Cache maintenance:** Beall's List is maintained at https://beallslist.net/. Update `bealls_list_cache.json` periodically (recommended: every 3 months). The cache includes journals from the original Beall's List and subsequent community-maintained lists (Cabell's Blacklist, Stop Predatory Journals).

## Step 2: Think. Check. Submit. Cross-Check

Apply the Think. Check. Submit. checklist (https://thinkchecksubmit.org/) via AI agent review:

| Red Flag | Check |
|----------|-------|
| Peer review process not described or unclear | Visit journal website (if available) and check peer review policy |
| Editorial board listed but members unreachable | Check 2-3 editorial board members — are they real researchers in the field? |
| APC hidden or only revealed after submission | Is the APC clearly stated on the website? |
| Journal name similar to established journal | Check for "hijacked" journals — lookalike names of legitimate journals |
| Contact email uses free service (Gmail, Yahoo) | Legitimate journals typically use institutional or publisher email |
| Claims rapid publication (48-72 hours) without peer review | Fast turnaround without rigorous review is a key red flag |
| Promises guaranteed indexing in WoS/Scopus | No journal can guarantee indexing — indexing is determined post-publication |

### Result
- **0 flags** → PASS. Continue to Step 3.
- **1 flag** → PASS with note. Continue to Step 3, flag as `[WARN: single red flag — verify manually]`.
- **2+ flags** → WARN. Recommend manual verification before proceeding.

## Step 3: OpenAlex Verification

Query OpenAlex Sources API for credibility signals:

```
GET https://api.openalex.org/sources?search={journal_name}
```

Check each matching result:

| Check | Criteria | Status |
|-------|----------|--------|
| Type | `type='journal'` | Must be 'journal' (not 'ebook-platform', 'repository') |
| Works count | `works_count > 100` | Established journal |
| Cited by count | `cited_by_count > 0` | Has citation impact |
| New journal | `works_count < 20` | WARN — very new journal, verify carefully |

### Result
- **All checks pass** → PASS. Journal is legitimate.
- **New journal warning** → WARN. Flag as `[WARN: new journal — verify publication track record]`.
- **No results or type mismatch** → WARN. Flag as `[WARN: not indexed in OpenAlex — verify legitimacy]`.

## Final Verdict

| Detection Result | Action |
|-----------------|--------|
| Beall's List HIT | **BLOCK** — Replace this journal with a verified alternative |
| Think.Check.Submit. 2+ flags | **WARN** — Manual confirmation required before proceeding |
| OpenAlex not indexed | **WARN** — Check if newly launched legitimate journal before proceeding |
| All checks pass | **PASS** — Journal appears legitimate |

## Output

Record the verification result for each candidate journal:

```
Journal: {name} (ISSN: {issn})
Beall's Cache: CLEAR
Think.Check.Submit.: {N} flags — {PASS/WARN}
OpenAlex: {works_count} works, {cited_by_count} citations — {PASS/WARN}
Verdict: {PASS/WARN/BLOCK}
```

Append all results to `{output_dir}/venue_verification.md`.
