# Paper Lookup (Embedded)

**Source:** `paper-lookup` v1.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S2 (Literature Review), D2, C2, T2 — fallback when `literature/literature_search.py` is unavailable

## Core Workflow
1. **Understand the query** — specific paper? topic? author? OA PDF?
2. **Select database(s)** — use the selection guide below
3. **Make API call(s)** — use WebFetch/Bash curl for REST endpoints
4. **Return results** — raw JSON + list of databases queried

## Database Selection Guide

| Need | Primary | Also consider |
|------|---------|--------------|
| Biomedical topic | PubMed | Semantic Scholar, OpenAlex |
| Full text biomedical | PMC | CORE |
| Biology preprints | bioRxiv | Semantic Scholar |
| Health preprints | medRxiv | Semantic Scholar |
| Physics/CS preprints | arXiv | Semantic Scholar |
| All fields | OpenAlex | Semantic Scholar, Crossref |
| Paper by DOI | Crossref | Unpaywall, Semantic Scholar |
| OA PDF | Unpaywall | CORE, PMC |
| Citation graph | Semantic Scholar | OpenAlex |
| Author publications | Semantic Scholar | OpenAlex |

## Common API Endpoints

- **PubMed:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmode=json`
- **OpenAlex:** `https://api.openalex.org/works?search={query}`
- **Crossref:** `https://api.crossref.org/works?query={query}&mailto={email}`
- **Semantic Scholar:** `https://api.semanticscholar.org/graph/v1/paper/search?query={query}`
- **arXiv:** `http://export.arxiv.org/api/query?search_query=all:{query}&max_results=50`

## Identifier Formats
- DOI: `10.xxxx/xxxxx`
- PMID: integer (PubMed)
- arXiv: `YYMM.NNNNN`
