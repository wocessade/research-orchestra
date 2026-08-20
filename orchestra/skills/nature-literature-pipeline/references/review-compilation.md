# Review Compilation Workflow

On-demand workflow for compiling a focused literature review from accumulated papers. Complementary to the daily automated pipeline — pipeline handles daily discovery, this handles concentrated compilation.

## Phase 1: Inventory

- Extract from Obsidian vault (`D:/MD ideas/`): search literature notes by topic keywords
- Extract from Zotero: use `@xevos117/mcp-zotero` MCP tools to search by tag/collection
- Deduplicate across sources
- Grade relevance: A = directly relevant, B = partially relevant, C = background

## Phase 2: Gap Filling

- Identify gap types: specific sub-topic lacking coverage, specific method with scarce papers, specific time-scale gaps
- Targeted search: arXiv API with focused keywords, follow citation chains of key papers
- For CS: check Papers With Code, GitHub repos linked to papers

## Phase 3: Architecture Design

- One causal chain through the review
- Avoid directory-style A→B→C listing
- Core contribution section occupies ~30% of text
- For CS reviews: problem formulation → methods taxonomy → key results comparison → open challenges

## Phase 4: BibTeX Export

- Create `.bib` file for Zotero import
- Group entries by section with `%` comment separators
- Each entry: title, author, venue, year, doi, arxiv

## Typical Scope (CS/AI Review)

- Literature: 50-100 papers
- Figures: 5-8 self-drawn (taxonomy diagrams, comparison tables, trend charts)
- Target: survey papers for top CS venues, Chinese core journals
