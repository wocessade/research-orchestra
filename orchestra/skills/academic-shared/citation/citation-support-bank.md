# Citation Support Bank Protocol (P1)

Map claims to candidate papers before locking bibliography prose. Keep two independent checks:

- `verified`: legacy column, **bibliographic identity only** (title/authors/year/DOI or other stable record match). DOI lookup failure is unresolved metadata, not automatic proof of fabrication.
- `support_status`: pending / supports / partial / mismatch / unavailable. Only supports permits using the source as support for that exact claim; partial requires narrowing or additional evidence.
- `locator` + `source_excerpt`: exact accessible source location and verbatim supporting text. A title or DOI alone never verifies a numerical, causal or comparative claim.

## Stages

| Stage | Action |
|-------|--------|
| S2 / T2 | Seed `.paper/citation_support_bank.md` from the template; candidates start support_status=pending. |
| S4 / T4 | Use candidates only within what has been read; link all evidence-requiring claims to the ledger, including uncited claims. |
| S6 / T2 verification | Verify bibliographic identity, then separately inspect original evidence and record support_status, locator and source_excerpt. |
| S7 / T5 | Recheck core claims and changed wording against source scope; unresolved support remains a review issue. |

When text, cited edition or source evidence changes, reset the affected support_status to pending and append a pending ledger revision. verified stays true only if bibliographic identity still matches.
Existing banks with only verified remain readable: missing support_status means pending, never supports. Add the new columns when updating that bank; do not silently promote legacy rows.

## Commands

```bash
python ../academic-shared/literature/bib_to_bibliography.py refs.bib -o bibliography.json
python ../academic-shared/literature/verify_citations.py --input bibliography.json --output-dir ./verification/
```

These commands verify bibliography metadata; they do not establish claim entailment. The review follows [ledger-protocol.md](../evidence-ledger/ledger-protocol.md). `/check-refs` remains available via [check-refs.md](../commands/check-refs.md).
