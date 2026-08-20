# Citation Support Bank Protocol (P1)

PaperSpine-inspired claim-level citation bank.

## Purpose

Map **claims → candidate papers** before locking bibliography prose.

## Stages

| Stage | Action |
|-------|--------|
| S2 / T2 | Create `.paper/citation_support_bank.md`; fill gap/contrast/method candidates |
| S4 | When writing, prefer bank keys; add new rows if a new claim appears |
| S6 | Verify DOIs; set `verified=true`; drop unresolvable or mark PLACEHOLDER_ |
| S7 | Spot-check top claims still match bank locators |

## Commands

```bash
# After .bib exists:
python ../academic-shared/literature/bib_to_bibliography.py refs.bib -o bibliography.json
python ../academic-shared/literature/verify_citations.py --input bibliography.json --output-dir ./verification/
```

Also: `/check-refs` → `../commands/check-refs.md`.
