---
name: academic-latex
description: >
  Write, revise, compile, and audit academic papers in LaTeX with claim-evidence
  engineering, verified citations, mechanical verification, and venue-aware
  layout. Use when writingFormat=latex, Overleaf/.tex work, 写LaTeX论文, polish
  sections, add verified BibTeX, fix compile errors, de-AI LaTeX prose, prepare
  camera-ready, or when academic-journal/thesis S4–S8 needs the LaTeX path.
  Complements academic-plotting for figures. Assists authors — does not submit
  fabricated results or unverified citations.
---

# Academic LaTeX — Claim-Evidence Paper Engineering

Treat LaTeX paper writing as **claim–evidence engineering with a compile gate**,
not fluent prose generation. This skill is the canonical LaTeX protocol for the
`academic-*` family (`academic-journal` / `academic-thesis` / `academic-coursework`).

**Standalone use:** invoke this skill directly.  
**Pipeline use:** `writingFormat=latex` → S4 loads this protocol (via
`skills-embedded/latex-paper-en.md` router); S5 uses `academic-plotting`; S6/S8
reuse citation + compile gates here.

## Non-negotiable rules

1. **Claim ledger.** Every quantitative or comparative claim traces to a project
   artifact (CSV, log, table script, verified paper). No artifact → mark
   `[CLAIM NEEDS EVIDENCE]` — never polish unsupported claims.
2. **No citation from memory.** BibTeX only after DOI/CrossRef/arXiv/Semantic
   Scholar verification. Unverifiable → `PLACEHOLDER_…` + tell the user. See
   [references/citations.md](references/citations.md).
3. **Core-First draft order** (default): Methods → Results → Discussion →
   Introduction → Abstract → Title. Framing sections after evidence sections.
4. **Compile before judging layout.** Never assess floats/density from `.tex`
   alone; build PDF and inspect changed pages. Blind / text-only orchestrator:
   render changed pages to PNG (or PDF page images) and verify **one layout
   hypothesis** via `../deepseek-vision` (overflow, clipped float, sparse page) —
   not a full-page describe. Single-figure quality → `academic-plotting`.
5. **Mechanical verification after every section.** Run
   `scripts/verify_paper.py` (or the checklist in
   [references/verification.md](references/verification.md)) and fix hard
   failures before the next section.
6. **Context hygiene.** One section per sitting; open only that section’s
   evidence; re-read artifacts before writing numbers. Long sessions → handoff
   with a short state note (integrate with academic-shared session persistence).
7. **Figures.** Evidence plots → `academic-plotting` (deterministic). Concept
   diagrams → `academic-plotting` concept route. Never invent numbers in figures.
8. **Do not replace the author.** Assist structuring, drafting, checking, and
   packaging. Scientific correctness and submission decisions stay with the user.

## Progressive loading (do not load everything at once)

| Task | Load first |
|------|------------|
| Full paper / major revision | [references/workflow.md](references/workflow.md), [references/project-layout.md](references/project-layout.md), `../academic-shared/contribution/contribution-gate.md` |
| Issues / backfill | `../academic-shared/issues/issues-contract.md`, `results-backfill.md` |
| Major rewrite | `../academic-shared/rewrite/rewrite-matrix.md` |
| Citation bank | `../academic-shared/citation/citation-support-bank.md` |
| CS conference draft | `../academic-shared/conference/cs-conference-path.md`, [references/section-writing.md](references/section-writing.md) |
| Section draft / revise | [references/section-writing.md](references/section-writing.md), [references/style-de-ai.md](references/style-de-ai.md) |
| Citations | [references/citations.md](references/citations.md) + academic-shared `literature/verify_citations.py` |
| Claim–evidence audit | [references/claim-evidence.md](references/claim-evidence.md) + `../academic-shared/evidence-ledger/ledger-protocol.md` |
| Layout / floats / density | [references/latex-conventions.md](references/latex-conventions.md) |
| Compile errors | [references/compile-debug.md](references/compile-debug.md) |
| Venue / template | [references/venue-templates.md](references/venue-templates.md) |
| Pre-submit / camera-ready | [references/verification.md](references/verification.md), `/latex-cleanup` |
| Figures | `../academic-plotting/SKILL.md` |

## Project metadata (collect once)

At scaffold time, record and freeze (never invent):

| Field | Notes |
|-------|--------|
| Author / affiliation | Exact strings for title page |
| Venue / template | IEEEtran, acmart, journal cls, thesis class… |
| Degree / module | If report/thesis |
| Supervisor | If required |
| Bibliography backend | biblatex+biber **or** bibtex — pick once |
| Language | Report language vs conversation language |
| writingFormat | Must stay `latex` for this path |

Store under `{paper_dir}/.paper/metadata.md` when using academic-* pipelines.

## Per-paper context packet (`.paper/`)

Maintain concise files so future sessions avoid re-reading the whole manuscript:

```text
.paper/
  metadata.md
  journal_format.md          # venue rules
  style_overrides.md         # optional
  context.md                 # thesis, gap, contributions, claims to avoid
  claim_evidence_ledger.md   # or evidence_ledger.jsonl (shared protocol)
  figure_inventory.md        # paths, roles, messages (plotting skill owns detail)
  glossary.md                # one term → one rendering
  submissions_log.md
```

## Workflow (summary)

### First invocation
1. Inventory artifacts (code, logs, notes, venue template) — paper is written
   *from* these, not from chat memory.
2. Build claim–evidence map; propose outline; **get user verdict** before long draft.
3. Scaffold layout per [references/project-layout.md](references/project-layout.md).
4. Draft section-by-section (Core-First), citing as you write.

### Per-section loop
1. Open only this section’s evidence → draft.
2. Run `python scripts/verify_paper.py <paper_root>` (hard fails block).
3. `latexmk -pdf` (or tectonic / xelatex as required) → scan log → eyeball PDF.
4. Update glossary + ledger; append evidence_ledger entries (shared protocol).

### Revision priority
Paper architecture → section job → paragraph logic → claim/evidence/boundary →
sentence polish. Fix the highest broken level first.

## Integration with academic-* pipeline

| Stage | Role of this skill |
|-------|-------------------|
| S3 | Outline must name LaTeX file map + figure plan hooks |
| S4 | Primary writer when `writingFormat=latex` |
| S5 | Delegate figures to `academic-plotting`; keep `\includegraphics` paths |
| S6 | Citation verify — same rules as `references/citations.md` |
| S7 | De-AI + polish with `references/style-de-ai.md` safety zones |
| S8 | Compile gate + `/latex-cleanup` |
| Q6/Q5 | Gate-chain citation + figure BLOCK criteria |

Chinese thesis path: still use `latex-thesis-zh` for GB/T layout, but inherit
claim/citation/verify rules from this skill.

## What NOT to do

- Invent related work, datasets, metrics, or significance.
- Write BibTeX from memory or “similar-sounding” papers.
- Bullet-heavy AI-slide prose for body sections.
- Commit / submit / upload without user request.
- Re-run experiments unless asked — archived results are canonical.
- Load all references into one turn — route by task.

## Scripts

```bash
# From this skill directory (adjust paths)
python scripts/verify_paper.py /path/to/paper
python scripts/verify_paper.py /path/to/paper --json
```

Hard failures: CJK leakage in EN papers, unresolved placeholders, cite↔bib
mismatch, missing `\label` for refs used. Soft: AI vocabulary, unused bib keys,
entries without doi/eprint/url.

## Federation bridges

- Contribution gate: `../academic-shared/contribution/contribution-gate.md`
- CS conference path: `../academic-shared/conference/cs-conference-path.md`

- BibTeX → verify: `../academic-shared/literature/bib_to_bibliography.py`
- Wiring smoke: `../academic-shared/SMOKE-LATEX-PLOTTING.md`

## P1 contracts

- Issues: `../academic-shared/issues/issues-contract.md`
- Backfill: `../academic-shared/issues/results-backfill.md`
- Rewrite: `../academic-shared/rewrite/rewrite-matrix.md`
- Citation bank: `../academic-shared/citation/citation-support-bank.md`
