# Nature Academic Search (Embedded)

**Source:** `nature-academic-search` | **Snapshot:** 2026-06-06
**Pipeline usage:** S2, S6 — fallback when literature/literature_search.py is unavailable

## Source Routing
| Need | Primary (T1) | Secondary (T2) | Last Resort (T3) |
|------|-------------|----------------|-------------------|
| Medical/clinical | PubMed | Semantic Scholar | Google Scholar |
| Cross-disciplinary | Crossref | Semantic Scholar | Scopus |
| Preprints/CS/physics | arXiv | bioRxiv/medRxiv | — |
| Exhaustive review | PubMed+CrossRef+arXiv | Semantic Scholar+bioRxiv | WoS/Scopus |

## PubMed Tools
- `esearch` + `esummary` / `efetch` for metadata
- MeSH term exploration for search strategy
- ID conversion: DOI ↔ PMID ↔ PMCID
- Related article discovery
