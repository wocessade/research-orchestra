# Citation workflow — nothing enters refs.bib unverified

Hallucinated citations are academic misconduct. Prompt-only bans do not stop fabrication; require retrieval + verification.

## Hard rule

**Never write BibTeX from memory.**

Path for every citation:

1. Discover candidates (Semantic Scholar, arXiv, OpenAlex, dblp, Zotero). Google Scholar is discovery-only.
2. Obtain stable ID: DOI > arXiv ID > publisher page.
3. Confirm title, first author, year, venue on the ID landing page / API.
4. Fetch BibTeX programmatically (CrossRef transform, arXiv export, or academic-shared literature helpers).
5. If citing a specific claim, confirm it appears in abstract or fetched text. "Paper exists" != "paper supports this sentence".
6. Only then append to `refs.bib`.

Unverifiable -> `\cite{PLACEHOLDER_author_year}` + `% TODO verify` and report count to user. Never silently substitute a similar paper.

## Dual check

| Check | Question |
|-------|----------|
| Existence | Does this bibliographic object resolve? |
| Support | Does it justify this sentence's claim? |

## Tooling

`verify_citations.py` expects a **JSON list** of entries (not raw `.bib`):

```bash
# From academic-latex skill root (or adjust path):
python ../academic-shared/literature/verify_citations.py \
  --input bibliography.json \
  --output-dir ./verification/
```

JSON entry keys: `{citation_key, title, authors, year, doi, venue, source}`.

For mechanical cite↔bib on LaTeX sources (keys only, no network):

```bash
python scripts/verify_paper.py /path/to/paper
# Chinese body:
python scripts/verify_paper.py /path/to/paper --allow-cjk
```

Export/maintain `bibliography.json` alongside `refs.bib` for DOI verification, or convert bib→json before calling verify_citations.

Also use academic-shared composer `literature-precheck.md` before polish.

## Style

- Pick cite command family once to match the template (biblatex / natbib / acmart).
- Every entry should carry `doi`, `eprint`, `url`, or `isbn`.
- Cite at the claim, not decorative end-of-paragraph clusters.
- Project logs/data are evidence, not bibliographic citations.

## Anti-patterns

- Inventing DOI-shaped strings
- Merging two real papers into a composite reference
- Citing a real paper for a claim it does not make
- Copy-pasting BibTeX without opening the record

## Pre-submit

- Every `\cite{key}` has a bib entry
- `verify_citations.py` clean or exceptions documented
- Matches gate-chain Q6 expectations

## Citation support bank (P1)

Maintain `.paper/citation_support_bank.md` (see `../../academic-shared/citation/citation-support-bank.md`).
Verify before promoting candidates into the manuscript `.bib`.
