# Quick Routing by Paper Type

| Paper Type | Entry | Key Skills (in order) |
|---|---|---|
| **I have data, no paper** | **Data-First** D0 | D0(analyze)→D1(EDA)→D2(story)→S2(lit review)→... |
| **I have a topic, no data** | Idea-First S1 | S1(brainstorm)→S2(lit review)→S3(outline)→... |
| **English high-impact journal** | Either | `skills-embedded/nature-writing.md` → `skills-embedded/nature-figure.md → ../academic-plotting/` → `skills-embedded/nature-citation.md` → `skills-embedded/nature-polishing.md` → `skills-embedded/nature-response.md` |
| **English conference (CS/Eng)** | Either | **P0 path:** contribution gate → Draft0 → Method/Results(Takeaway) → Final Intro. Load `../academic-shared/conference/cs-conference-path.md` + `../academic-shared/contribution/contribution-gate.md`. Skills: `latex-paper-en → ../academic-latex/` → `scientific-visualization → ../academic-plotting/` → `citation-management` → `venue-templates` |
| **Grant proposal** | Either | `skills-embedded/research-grants.md` → `skills-embedded/scientific-brainstorming.md` → `skills-embedded/hypothesis-generation.md` |
| **Literature review only** | Idea-First S1 | literature-review → paper-lookup → citation-management → scientific-schematics. **Enhanced search:** `literature/literature_search.py` provides multi-source search (OpenAlex+SemanticScholar+CrossRef+GoogleScholar) with 3D quality scoring, snowballing, and citation network analysis across all literature stages (S2). |
| **Chinese domestic journal (国内核心/学报/CSCD/CSSCI)** | Either | See `references/chinese-journal-adapter.md` |
| **Empirical research (standard IMRAD)** | Either (detected by default) | Standard pipeline. S1→S0.5→S1.5→S2→… (full pass). Full IMRAD structure at S3-S4. Data figures at S5. This is the default paper type. | `skills-embedded/nature-writing.md` → `skills-embedded/nature-figure.md → ../academic-plotting/` → `skills-embedded/citation-management.md` → `skills-embedded/nature-polishing.md` |
| **Theory / conceptual paper** | Idea-First S1 | S1→S0.5→S2 (skip S1.5). S3-S4: logical argument structure replaces IMRAD. S5: conceptual diagrams, not data figures. | literature-review → scientific-schematics → citation-management |
| **Registered Report** | Idea-First S1 | S1→S0.5→S1.5(full/RR)→S2→… S1.5-RR adds dedicated RR sub-sections: hypothesis specification (confirmatory vs exploratory), pre-registered analysis plan script, Stage 1/Stage 2 boundary. Produce Stage 1 protocol (Intro+Methods) → in-principle acceptance → data collection → Stage 2. | hypothesis-generation → literature-review → paper-lookup |
| **Data Paper** | Data-First D0 | D0→D1→D2→S0.5→S2 (skip S1.5). S3-S4 use Data Descriptor structure, not IMRAD. S5 has no data figures — use metadata tables instead. | literature-review → paper-lookup (for provenance) → citation-management |
| **Software/Tool Paper** | Idea-First S1 | S1→S0.5→S2 (skip S1.5). S3-S4 focus on architecture/API/performance, not hypothesis testing. S5 uses architecture diagrams. | scientific-writing → scientific-schematics → citation-management → venue-templates |
| **Benchmark Paper** | Data-First D0 | D0→D1→D2→S0.5→S2 (skip S1.5). S5 outputs leaderboards/comparison tables. S2 literature search centers on existing benchmarks. | scientific-visualization → literature-review → nature-figure → citation-management |
| **Rebuttal/Revision** | N/A (already have paper) | nature-response → paper-audit → nature-polishing |
| **Half-finished draft (部分手稿)** | **Partial-Manuscript SP** | SP(assess)→S4(fill gaps)→S5+S6+S6.5→S7(polish)→… S4 skips Complete sections, supplements Partial sections, writes Missing sections from scratch. Stepping mode recommended. |
| **CS conference (CCF 会议)** | Either | discipline=stem + **cs-conference-path** (Draft0→Final Intro, page budget, Takeaway). Contribution gate at Q3. `references/discipline-stem.md` + `../academic-shared/conference/cs-conference-path.md` | latex-paper-en → academic-latex → scientific-visualization → citation-management → IEEEtran/acmart |
| **CS journal (CCF 期刊)** | Either | discipline=stem. CS paper structure. Venue selection via CCF tier system. `references/discipline-stem.md` | `skills-embedded/nature-writing.md` → `skills-embedded/nature-figure.md → ../academic-plotting/` → `skills-embedded/citation-management.md` → `skills-embedded/nature-polishing.md` |

**For journal selection strategy (which venue to target):** See **Stage 8.5 (Publication Strategy)**. The table above only maps paper types to skills.

**For CS discipline routing (CCF tiers, non-IMRAD structures, deadline workflow):** See `references/discipline-stem.md`. Loaded automatically when `discipline=stem`.


## P0 hard gates (all empirical / CS paths)

| When | Load | Artifact |
|------|------|----------|
| Before Q3 / body draft | `../academic-shared/contribution/contribution-gate.md` | `.paper/confirmed_contribution.md` (`user_confirmed: true`) |
| S3 stem/conference | `../academic-shared/conference/cs-conference-path.md` | `.paper/draft0_intro.md` |
| S4 Results | contribution-experiment map template | `.paper/contribution_experiment_map.md` + Takeaways |

## P1 contracts (writing & revision)

| Phase | Load | Artifact |
|-------|------|----------|
| S2→S6 | `../academic-shared/citation/citation-support-bank.md` | `.paper/citation_support_bank.md` |
| S3→S4 | `../academic-shared/issues/issues-contract.md` | `.paper/issues.csv` |
| Pre-strong Results | `../academic-shared/issues/results-backfill.md` | status → `verified` |
| S7 major rewrite | `../academic-shared/rewrite/rewrite-matrix.md` | `.paper/rewrite_matrix.md` |

## Research engine → writing

| When | Action |
|------|--------|
| `.research/handoff/` present | S1/S3 preload `ready_for_writing.md`; prefer verified EXP→Ci; honor NEG forbidden claims |
| Need to materialize `.paper/*` | `../academic-research-engine/scripts/handoff_sync.py` |
| Protocol | `../academic-research-engine/references/handoff-to-writing.md` + `../academic-shared/research/schemas.md` |
