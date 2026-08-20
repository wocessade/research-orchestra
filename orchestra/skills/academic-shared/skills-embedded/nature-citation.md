# Nature Citation (Embedded)

**Source:** `nature-citation` | **Snapshot:** 2026-06-06
**Pipeline usage:** S6 — Nature/CNS-specific citation verification

## Scope
- `Nature系列`: Nature Portfolio + Nature Communications + Communications [field] + Scientific Reports + npj journals
- `CNS`: Cell, Nature, Science + major sister journals
- `CNS及其子刊`: All accepted titles in Nature Portfolio, AAAS Science family, Cell Press

## Workflow
1. Segment manuscript text into citable segments
2. Search accepted journals for each segment
3. For each candidate: flag support strength (强支撑/部分支撑/背景支撑/不建议引用)
4. Export as `.enw`, `.ris`, or Zotero `.rdf`

## Source Hierarchy
1. Structured metadata: Crossref, PubMed, DOI metadata
2. Publisher pages: nature.com, science.org, cell.com
3. Full text or abstract pages
4. Secondary: Google Scholar, Semantic Scholar (discovery only)

## Chinese-User Mode
- Accept Chinese text, search with English concept queries
- Return segment notes in Chinese
- Flag overclaiming clearly
