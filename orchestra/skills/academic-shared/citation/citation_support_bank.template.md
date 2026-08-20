# Citation Support Bank

> Path: `{paper_dir}/.paper/citation_support_bank.md`
> Claim-level candidate citations — **not** a style sample library.

| claim_id | section_role | candidate_key | doi_or_arxiv | support_type | locator | verified | notes |
|----------|--------------|---------------|--------------|--------------|---------|----------|-------|
| CLM-001 | intro-gap | smith2023 | 10.xxxx/… | contrast | §3 ¶2 | false | |
| CLM-010 | method | baselinemethod | arXiv:…. | method | abstract | true | |

## support_type

`support` | `contrast` | `method` | `dataset` | `metric` | `related`

## Rules

1. Seed at S2 from gap analysis; expand at S6.
2. `verified=true` only after DOI/S2/CrossRef (or `verify_citations` / bib bridge).
3. Prefer citing from this bank in Intro / Related Work / Discussion — do not invent keys.
4. Separate from style_learning samples (those are prose tone only).
