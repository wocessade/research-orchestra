# Prerequisites

- [ ] Zotero installed and configured? → `skills-embedded/pyzotero.md` needs your API key and library ID. Optional for course-assignment and thesis pipelines.
- [ ] LaTeX distribution? → `skills-embedded/latex-document-skill.md` needs TeXLive/MiKTeX. Required for thesis (LaTeX) and English LaTeX papers.
- [ ] Python 3.8+? → `skills-embedded/nature-figure.md` needs matplotlib/seaborn; `python-docx` needed for Word output (course-assignment, thesis fallback)
- [ ] Tavily API key? → `references/tavily-search.md` needed for C2E web context search (course-assignment). Optional — falls back to `agent-browser` if unavailable.
- [ ] Playwright MCP configured? → `references/playwright-browser-automation.md` needed for CNKI/Wanfang Chinese source search (course-assignment, thesis). Falls back to user-as-external-skill pattern.
- [ ] Target journal picked? (Optional at start, required by Stage 8) → `skills-embedded/venue-templates.md`

## Skill Availability Pre-Flight

Run this check in Step 1 (after loading manifest, before executing any stage). Probe each skill below by invoking it — a successful load (even if it returns "no matching task") confirms availability. An error/unknown-skill response confirms it's missing.

### Critical Path Skills (pipeline cannot proceed without these)

| Skill | Used By Stages | Purpose |
|-------|---------------|---------|
| `skills-embedded/paper-lookup.md` | S2, D2, C2, T2 | Multi-database literature search (10 databases). Required for any literature-intensive stage. |
| `skills-embedded/citation-management.md` | S2, S6 | DOI verification, BibTeX management, citation deduplication. The primary defense against hallucinated citations. |
| `skills-embedded/literature-review.md` | S2 | Systematic review methodology, structured search strategy, PRISMA compliance. |
| `skills-embedded/paper-audit.md` | S7, S9 | Reviewer-style quality gate. No paper passes Q7 or Q9 without this. |

**If any critical skill is missing:** STOP-AND-ASK the user to install it before proceeding. Pipeline halts at Step 1.

### Important Skills (have fallbacks but quality degrades without them)

| Skill | Used By Stages | Fallback |
|-------|---------------|----------|
| `skills-embedded/scientific-brainstorming.md` | S1, C1, T1 | `skills-embedded/hypothesis-generation.md` or manual topic scoping |
| `skills-embedded/nature-reader.md` | S2, S4 | Manual full-text reading (higher effort, no structured extraction) |
| `skills-embedded/scientific-writing.md` | S3, S4, S7 | `skills-embedded/nature-writing.md` (different style conventions; may mismatch venue) |
| `skills-embedded/nature-writing.md` | S3, S4, S7 | `skills-embedded/scientific-writing.md` (more generic, less venue-tailored) |
| `skills-embedded/nature-polishing.md` | S7 | `skills-embedded/scientific-writing.md` (revise mode) or manual editing |
| `skills-embedded/scientific-visualization.md` | S5, D0 | `skills-embedded/nature-figure.md` or raw matplotlib/ggplot2 |
| `skills-embedded/nature-figure.md` | S5 | `skills-embedded/scientific-visualization.md` or raw matplotlib/ggplot2 |
| `skills-embedded/scientific-schematics.md` | S5, T2 | `skills-embedded/generate-image.md` or manual diagram tools |
| Web browser (agent-browser) | C2, T2, D2 | `WebSearch` + `WebFetch` (lower fidelity, may miss JavaScript pages) |
| Playwright MCP (headful browser) | C2, T2, S6, S2-LR | CNKI/Wanfang automated search, DOI browser verification, Google Scholar snowballing. User logs in once via pop-up browser. See `references/playwright-browser-automation.md`. Fallback: `agent-browser` or user-as-external-skill pattern |

**If an important skill is missing:** Warn the user with the affected stages and fallback. Let user decide: (1) install the missing skill, (2) proceed with fallback and documented quality risk, (3) skip affected stages if optional.

### Optional/Special-Purpose Skills

| Skill | Used By Stages | Notes |
|-------|---------------|-------|
| `skills-embedded/bgpt-paper-search.md` | S2 | Structured experimental data extraction from papers. Only needed for systematic reviews. |
| `skills-embedded/nature-academic-search.md` | S2, S6 | Multi-source literature workflows. Fallback when `skills-embedded/citation-management.md` not available. |
| `skills-embedded/pyzotero.md` | S2, S6 | Zotero library management. Skip if using BibTeX directly. |
| `skills-embedded/scientific-critical-thinking.md` | S2 | Evidence quality grading (GRADE, Cochrane). Only for clinical/health papers. |
| `skills-embedded/hypothesis-generation.md` | S1 | Formal hypothesis formulation. Fallback when `skills-embedded/scientific-brainstorming.md` not available. |
| `skills-embedded/bib-search-citation.md` | S6 | Local BibTeX library search. Only if user has a local .bib library. |
| `skills-embedded/nature-citation.md` | S6 | Nature/CNS-specific citation verification. Only for Nature-family submissions. |
| `skills-embedded/latex-paper-en.md` | S4 | Write directly in LaTeX. Only when writingFormat=latex. |
| `skills-embedded/latex-thesis-zh.md` | S4, S7 | Chinese LaTeX thesis writing. Only for thesis pipeline with LaTeX. |
| `skills-embedded/typst-paper.md` | S4 | Typst paper writing. Only when writingFormat=typst. |
| `skills-embedded/nature-response.md` | S11, S12 | Reviewer response letter. Only for R&R scenarios. |
| `skills-embedded/venue-templates.md` | S6, S8.5 | Journal-specific templates. Optional — can download manually. |
| `skills-embedded/latex-document-skill.md` | S8 | LaTeX compilation. Only needed for LaTeX output. |
| `skills-embedded/scientific-slides.md` | T7 | Research presentation slides. Only for thesis defense. |
| `skills-embedded/nature-paper2ppt.md` | T7 | Paper-to-PPT conversion. Only for thesis defense. |
| `skills-embedded/cover-letter.md` | S10 | Submission cover letter. Can write manually if unavailable. |
| `skills-embedded/generate-image.md` | S5 | AI image generation. Only as fallback for schematics. |

**If an optional skill is missing:** Note it and continue. The user will be informed when the affected stage is reached.

### Pre-Flight Output Format

After checking all skills, produce:

```
## Skill Availability Summary

### Available (N/M)
- skill_name — critical
- skill_name — important
- ...

### Missing (K/M)
- skill_name — critical → BLOCKS stages: S2, S6. Install before proceeding.
- skill_name — optional → SKIPPED in stages: T7. Defense PPT will be manual.
```

Critical missing skills trigger HARD STOP. Important missing skills trigger a warning with user choice. Optional missing skills are noted without blocking.
