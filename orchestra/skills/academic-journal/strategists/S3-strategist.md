# Stage S3: Outline [Strategist]

**Gate:** Q3 (BLOCK) — outline has IMRAD sections, 3-5 key claims per section, contribution stated
**Also loads:** `../academic-shared/contribution/contribution-gate.md`
**Goal:** Build a claim-level skeleton before writing a single sentence of prose.
**Needs Composers:** [claim-to-paragraph, introduction-writing]

## Decisions

### Composer Sequence

Composers are used in S4, not S3. S3 produces the claim outline that composers consume.

### Discipline Routing (S3, lines 11-12)

Inspect `passport.discipline`:
- IF `discipline=stem` → load `references/discipline-stem.md` → use CS paper structure (System/Algorithm/Empirical/Survey) instead of IMRAD
  - Place Related Work after main technical content per CS convention
- ELSE → use standard IMRAD structure

### Paper Type Structure Routing (S3, lines 13-19)

Inspect `passport.paper_type` and map to section structure:

| Paper Type | Structure | Reference |
|------------|-----------|-----------|
| Empirical (default) | IMRAD | — |
| Data paper | Data Descriptor (Introduction → Methods → Data Records → Technical Validation → Usage Notes) | `references/quick-routing.md` |
| Software/tool paper | Architecture → Implementation → Validation → Usage | `references/quick-routing.md` |
| Benchmark paper | Task Definition → Benchmark Design → Results → Analysis | `references/quick-routing.md` |
| Literature review | Thematic/synthesis (Scope & Method → Thematic Synthesis → Gap Analysis → Future Directions) | `references/quick-routing.md` |
| Theory/conceptual paper | Logical argument (Problem → Framework → Implications) | `references/quick-routing.md` |

### Two-Stage Outline Protocol (S3, lines 26-34) — MANDATORY

### Research-engine handoff preload (before contribution gate)

IF `.research/handoff/` is present (resolve research root relative to `{paper_dir}` or cwd):

1. Preload `ready_for_writing.md` + any linked verified EXP rows.
2. Seed contribution / map / issues **from handoff** when richer than empty templates; still require `user_confirmed: true` on `confirmed_contribution.md`.
3. Never copy `planned` strong numbers into outline claims — use hedging or `[CLAIM NEEDS EVIDENCE]`.
4. If NEG forbidden-claim list exists → attach to outline limitations / non-goals.
5. Optional: run `py -3 ../academic-research-engine/scripts/handoff_sync.py --research-root … --paper-dir {paper_dir}` if `.paper/` not yet seeded.

ELSE → contribution gate as usual.

### Contribution Gate + Mini Draft0 (P0) — MANDATORY before Q3 pass

1. Create `{paper_dir}/.paper/confirmed_contribution.md` from `../academic-shared/contribution/confirmed_contribution.template.md`.
2. Socratic-refine vague aims into 1–3 claim-first contributions; STOP-AND-ASK until user confirms → set `user_confirmed: true`.
3. Run `python ../academic-shared/contribution/contribution_check.py {paper_dir}/.paper/confirmed_contribution.md`.
4. Seed `{paper_dir}/.paper/contribution_experiment_map.md` from `../academic-shared/contribution/contribution-experiment-map.template.md`.
5. IF `discipline=stem` OR venue is CS conference OR `paperType` is conference-like:
   - Load `../academic-shared/conference/cs-conference-path.md`
   - Write `.paper/draft0_intro.md` (identity + gap + Ci + eval sketch + page budget) — **not** final Intro
6. Q3 fails closed if contribution file unconfirmed.


Two-phase flow — never skip to prose directly:

**Phase 1 — Claim Outline:**
For each section, list 3-5 key claims as bullet points. Each claim = one sentence the section will prove.

**Phase 2 — Prose Outline:**
Expand each claim into a 2-3 sentence paragraph skeleton. This becomes the writing scaffold for S4.

### Overview / Introduction Section Timing

Write the Introduction's overview paragraph LAST — after core section claims are solidified.

### Claim Quality Check Gate (S3, lines 54-59)

Every claim must satisfy:
- **Specific** — not vague, contains effect sizes/quantities
- **Evidence-backed** — maps to exact data/figure/table
- **Sequential** — claims build on each other; Claim N+1 should still hold if Claim N is false
- **Falsifiable** — reader can look at data and conclude claim is false

### S3-to-S4 Pre-Flight Alignment (S3, lines 72-83) — Advisory

Before entering S4, run internal coherence checks. NOT a formal gate, but failure here causes major rework at S7:

| Check | Red Flag |
|-------|----------|
| Contribution alignment | Abstract says one thing, Methods describes another |
| Limitations coverage | No limitation claims despite known weaknesses |
| Claim coverage | A claim exists but no evidence source named |
| Logical flow | Claims jump between unrelated ideas |

IF any Red Flag → fix outline NOW before proceeding to S4.

### Language Routing for Chinese Theses (S3, line 84)

For Chinese thesis chapter planning → use `skills-embedded/latex-thesis-zh.md`.

### STOP-AND-ASK Points
- If discipline is unknown or unsupported → ask user to clarify discipline
- If paper type has no matching structure → ask user to confirm custom structure

## Gate

### Q3 Gate Checklist
- [ ] Outline has the appropriate sections for the paper type (IMRAD / Data Descriptor / Architecture-Implementation-Validation / etc.) with 3-5 claims each
- [ ] Every claim is specific and evidence-mapped
- [ ] Contribution claim is clear and non-obvious
- [ ] `confirmed_contribution.md` with `user_confirmed: true` (contribution_check.py OK)
- [ ] `contribution_experiment_map.md` seeded (every Ci has ≥1 planned row)
- [ ] IF stem/CS conference: `draft0_intro.md` present; page budget recorded
- [ ] Introduction *plan* follows funnel (Final Intro prose is written in S4 after evidence)
- [ ] Gap analysis from S2 section 2F referenced in Introduction claims

### Gate Failure Route
Q3 is BLOCK.

1. First failure → identify which check items failed → route back to corresponding sub-step (S3A.1 claim outline or S3A.2 prose outline) → re-run → re-evaluate gate.
2. After 2 fix attempts still fail → **STOP-AND-ASK** user: expand scope, relax criteria, or proceed with current state. Route back to S3A, complete missing section declarations, then re-submit.
### LaTeX outline hooks (writingFormat=latex)

IF `writingFormat == latex` (EN or zh):
1. Outline must name the intended tree: `main.tex`, `sections/*.tex`, `figures/`, `tables/`, bibliography file + backend (biblatex+biber vs bibtex).
2. Each planned figure gets a one-line academic-plotting contract hook (id, class evidence-result|concept-method, message).
3. Point authors at `../academic-latex/references/project-layout.md` (module-root path).
4. Chinese thesis: also bind university cls via `skills-embedded/latex-thesis-zh.md`.
