# Changelog

All notable changes to academic skills (coursework, journal, thesis, shared).

## 2026-07-27 — Academic Research Engine (sibling)

### Added
- `academic-research-engine/` — RQ/H/EXP/NEG state machine, literature radar routing (nature-* call-outs), handoff to `.paper` P0/P1 artifacts
- `academic-shared/research/` — canonical ID schemas + `metrics.schema.json`
- Scripts: `validate_experiment_card.py`, `ingest_run.py`, `handoff_sync.py`
- Journal S1/S3 + thesis T1 preload when `.research/handoff` exists; quick-routing + SKILL.md pointers

### Notes
- Does not reimplement nature-reader / literature-pipeline / weekly-review
- Default compute mode: human_in_loop (no default GPU runner); deep_synthesize is docs-only radar mode

## 2026-07-27 — Issues / rewrite matrix / citation bank (P1)

### Added
- `academic-shared/issues/` — issues.csv contract, `validate_issues.py`, results-backfill
- `academic-shared/rewrite/` — rewrite matrix protocol + template
- `academic-shared/citation/` — citation support bank protocol + template
- Wired S2/S4/S6/S7, T2/T6, latex workflow, gate-chain Q4/Q6/Q7/QT6, quick-routing, SKILL.md, manifests

## 2026-07-27 — Contribution gate + CS conference path (P0)

### Added
- `academic-shared/contribution/` — gate protocol, templates, `contribution_check.py`
- `academic-shared/conference/cs-conference-path.md` — Draft0 → Final Intro, Takeaway, page compression
- Journal S3/S4 + Thesis T1/T4 wiring; Q3/Q4/QT1 gate-chain updates
- quick-routing + SKILL.md updates (journal/thesis/latex/coursework)

### Inspired by
PaperSpine contribution-first, SNL Draft0/Final Intro/Takeaway, Nature conference claim-first (not full ARS/CNS stacks)

## 2026-07-27 — Contribution gate + CS conference path (P0)

### Added
- `academic-shared/contribution/` — gate protocol, templates, `contribution_check.py`
- `academic-shared/conference/cs-conference-path.md` — Draft0 → Final Intro, Takeaway, page compression
- Journal S3/S4 + Thesis T1/T4 wiring; Q3/Q4/QT1 gate-chain updates
- quick-routing + SKILL.md updates (journal/thesis/latex/coursework)

### Inspired by
PaperSpine contribution-first, SNL Draft0/Final Intro/Takeaway, Nature conference claim-first (not full ARS/CNS stacks)

## 2026-07-27 — Completeness pass (coursework + bridges)

### Added
- **`academic-shared/literature/bib_to_bibliography.py`** — BibTeX → `bibliography.json` for `verify_citations.py` (`--and-verify` optional)
- **`academic-shared/SMOKE-LATEX-PLOTTING.md`** — minimal end-to-end wiring checklist
- **coursework** `writingFormat` axis; latex-paper-en + figure routers + sibling skill refs; C3 format routing

### Fixed
- **gate-chain.md** control-character corruption (`\x07` / split `verify_paper`); QC3 latex branch; Q5 type-appropriate minima

### Changed
- Journal S4/S6/S7/S8 and thesis T4: explicit Tool Commands for check-refs / de-ai / latex-cleanup / verify-math / bib bridge
- Thesis manifest: commands + `checkpoint/state_manager.py` on T4
- sync-to-modules coursework allowlist expanded for latex/plotting routers


## 2026-07-27 — LaTeX pipeline audit fixes

### Fixed (Critical)
- **Broken relative paths** in `skills-embedded` routers: `../academic-latex` resolved under module dirs (missing). Corrected to `../../academic-latex` / `../../academic-plotting`. Same fix for `composers/format-routing.md` and shared latex/plotting README indexes.
- **S5/S6/S8 strategists** now explicitly load academic-plotting / academic-latex citation+verify_paper gates for `writingFormat=latex`.

## 2026-07-27 — Academic LaTeX + Plotting skill expansion

### Added
- **`academic-latex/`** — standalone skill: claim-evidence LaTeX workflow, verified citations, Core-First drafting, compile/debug, de-AI safety zones, `scripts/verify_paper.py`
- **`academic-plotting/`** — standalone skill: figure contracts, evidence vs concept backend split, data-chart + concept-diagram refs, journal profiles, Okabe–Ito, QA checklist, `plot_style.py` / `validate_figure_spec.py`
- **`academic-shared/latex/README.md`** and **`plotting/README.md`** — pointers to sibling canonical skills

### Changed
- **`skills-embedded/latex-paper-en.md`**, **`nature-figure.md`**, **`scientific-visualization.md`**, **`scientific-schematics.md`** — upgraded from thin snapshots to routers loading academic-latex / academic-plotting
- **`composers/format-routing.md`**, **`academic-journal` S4 strategist / manifest / quick-routing / SKILL.md** — wire `writingFormat=latex` and S5 figures to the new protocols

### Notes
- Assists authors; does not fabricate results or unverified citations
- Sync embedded routers with: `python sync-to-modules.py --component skills-embedded`
All notable changes to academic skills (coursework, journal, thesis, shared).

## 2026-06-30 — Batch 4: Chinese Journal Evaluate System

### Added
- **`academic-journal/evaluate/config/chinese_core.yaml`** — 152 lines, A/B1/B2/B3/C1/C2/C3 tier profiles, 10 scored + 3 scoreless dimensions, gate_blockers (suspected_fabrication, missing_domestic_literature, empirical_without_method, unsupported_contribution_claim), coupling_rules, Chinese AI-tone curves (随……的发展, 翻译腔, 对仗标题, etc.)
- **`academic-journal/evaluate/config/chinese_conference.yaml`** — conference-specific config with lower thresholds, paper_type_profiles with critical questions per type
- **`academic-journal/evaluate/agents/chinese/`** — 13 agent files (10 scored + 3 scoreless), all expanded to 87-114 lines with full rubrics, severity definitions, band descriptions, and inter-dimension boundaries
- **`stage_agents.md`** rewritten — route table for zh chinese-domestic (A-C3) and chinese-conference (D), tier normalization mapping (顶刊→A, CSSCI核心→B1, etc.), agent placement decision (fork from thesis, journal-local)

### Design decisions
- Chinese journal agents are **journal-local** (`academic-journal/evaluate/agents/chinese/`), forked from thesis Chinese agents' anti-flattery protocol but journal-specific
- 10 scored dimensions mapped to journal needs: problem_contribution, literature_context (emphasis on CNKI/万方), theory_depth, methodology_design, data_analysis, logic_consistency, structure_organization, innovation_fit, format_reference (GB/T 7714), academic_style
- 3 scoreless: ai_tone_detector_zh (triplicate, Chinese-specific markers), factual_accuracy_zh (gate blocker), first_review_synthesizer_zh (20+ item reviewer-style checklist)
- Weights sum to 1.00 for scored dimensions; paperType-aware with fallback_weight_to

## 2026-06-30 — Batch 3: Reference TOC + Conflict Detection

### Added
- **TOC headers** on 19 reference files >10KB across all three modules, with partial-read hints
- **Style rule conflict scan** (check #12) in all three `validate_pipeline.py` scripts — detects contradictory writing rules across references
- **`add_toc.py`** in `academic-shared/scripts/` — utility to add TOC headers to large reference files

### Fixed
- **Roadmap paragraph conflict**: `english-paper-template.md` (journal + thesis) now instructs concrete content preview instead of formulaic "The remainder of this paper is organized as follows..." — consistent with de-AI guides
- Conflict scan regex tightened to single-line matching (`[^\n]` instead of `.`) to eliminate false positives

### Fixed
- Validate scripts: conflict check placed before Summary section so warnings are actually printed
- Journal/thesis validate: roadmap paragraph contradiction now flagged as warning

## 2026-06-30 — Batch 2: Checkpoint Schema + Validate Hardening

### Added
- **`checkpoint/checkpoint_schema.json`** — unified JSON Schema draft-07 for all three modules (`paper_slug`, `module`, `current_stage`, `completed_sections`, `outputs`, `next_action`)
- **`requirements.txt`** — minimum Python dependencies (PyYAML, python-docx, PyMuPDF)
- **Non-axis condition key detection** (check #20) in all three validate scripts — catches bare condition keys like `mode: stepping` that aren't defined as axes
- **Dependency graph reachability check** (check #21) in all three validate scripts — traces backwards through next/route to verify every dep_graph start is reachable from an entry point

### Removed
- 3 `__pycache__/` directories (journal ×1, thesis ×2)

## 2026-06-30 — Batch 1: Manifest Routing + Doctor

### Added
- **`doctor.py`** in `academic-shared/scripts/` — pure stdlib environment checker (Python version, package availability via `importlib.util.find_spec`, network targets via TCP, git/pandoc commands)

### Fixed
- **Journal `mode` axis** — added `mode` axis with values `[stepping, standard, revision-only, submission-only]`; stepping references were unreachable by validator before this fix
- **Thesis `existing-manuscript` routing** — changed from single path `[T7]` (defense-only) to 6 explicit paths starting at T5+T6 (review + revision), with optional T6.5 (master inflation), T6.7 (padding), T7 (defense)
- **3× SKILL.md frontmatter** rewritten from "generate complete papers with one command" to "assist with writing, not replace the author"

### Changed
- All three `validate_pipeline.py` scripts pass with 0 errors after fixes
