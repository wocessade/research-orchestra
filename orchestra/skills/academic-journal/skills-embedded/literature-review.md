# Literature Review (Embedded)

**Source:** `literature-review` v1.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S2 (Literature Review), S2-LR (Lit Review for lit-review paperType)

## Core Workflow

### Phase 1: Planning & Scoping
1. **Define Research Question** — use PICO (Population, Intervention, Comparison, Outcome) for clinical/biomedical
2. **Establish Scope** — review type (narrative/systematic/scoping/meta-analysis), time period, geography
3. **Develop Search Strategy** — identify 2-4 main concepts, synonyms, Boolean operators, select 3+ databases
4. **Set Inclusion/Exclusion Criteria** — date range, language, publication types, study designs

### Phase 2: Systematic Literature Search
1. Multi-database search (OpenAlex, Semantic Scholar, Crossref, PubMed, arXiv)
2. Deduplicate results (by DOI + title similarity)
3. Screen by title/abstract against inclusion criteria
4. Full-text screening of remaining papers
5. Snowballing: check references of included papers for missed studies

### Phase 3: Data Extraction & Quality Assessment
- Extract: study design, sample size, methods, key findings, limitations
- Quality score each paper on 3 dimensions:
  - **Methodological rigor** — design, sample, controls, blinding
  - **Evidence strength** — effect size, precision, consistency
  - **Reporting quality** — completeness, transparency

### Phase 4: Synthesis
Organize findings thematically (3-5 themes). For each theme:
- What do the papers say?
- What is the level of agreement/disagreement?
- What gaps remain?

### Phase 5: PRISMA (for systematic reviews)
- PRISMA flow diagram: records identified → screened → full-text → included
- PRISMA checklist for reporting
