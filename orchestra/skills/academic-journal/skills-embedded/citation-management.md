# Citation Management (Embedded)

**Source:** `citation-management` v1.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S2 (Literature Review), S6 (Citation Verification)

## Core Workflow

### Phase 1: Paper Discovery & Search
Search Google Scholar, PubMed, Crossref for papers on a topic.
Always record search strings BEFORE searching (prevents cherry-picking).

### Phase 2: Metadata Extraction & Verification
For each paper, extract: authors, title, journal, year, volume, pages, DOI.
Verify DOI resolves via Crossref or doi.org.

### Phase 3: BibTeX Generation
```bibtex
@article{key,
  author  = {Author, A. and Author, B.},
  title   = {Title},
  journal = {Journal Name},
  year    = {2024},
  volume  = {10},
  pages   = {1-10},
  doi     = {10.xxxx/xxxxx}
}
```

### Phase 4: Citation Validation
For each citation, verify:
1. DOI resolves to the correct paper
2. Title matches the cited claim
3. Author list is complete
4. Year/volume/pages are correct
5. The cited paper actually supports the claim it's attached to

## BibTeX Cleanup Rules
- Remove duplicate entries (dedup by DOI)
- Standardize journal abbreviations
- Fix Unicode/LaTeX special characters
- Ensure all required fields are present
- Sort entries alphabetically by first author
