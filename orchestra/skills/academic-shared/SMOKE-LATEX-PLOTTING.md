# Smoke checklist — academic-latex + academic-plotting

Run after syncing routers or changing verify/plot scripts. Goal: prove the **wiring works**, not produce a real paper.

## 0. Paths

From `~/.claude/skills/` (or your skills root):

```text
academic-latex/
academic-plotting/
academic-shared/
academic-journal/   # optional path A
academic-thesis/    # optional path B
academic-coursework/# optional path C
```

## 1. Minimal LaTeX project

Create a temp folder `smoke_paper/` with:

- `main.tex` — article class, one section, one `\cite{smoke2020}`, one `\includegraphics` optional
- `refs.bib` — one real entry with DOI (or use PLACEHOLDER_test and expect HARD fail)

```bash
python academic-latex/scripts/verify_paper.py smoke_paper
# expect CLEAN for a consistent toy project, or HARD listing real issues
```

Chinese body:

```bash
python academic-latex/scripts/verify_paper.py smoke_paper --allow-cjk
```

## 2. Bib → verify bridge

```bash
python academic-shared/literature/bib_to_bibliography.py smoke_paper/refs.bib -o smoke_paper/bibliography.json
python academic-shared/literature/verify_citations.py --input smoke_paper/bibliography.json --output-dir smoke_paper/verification
```

Or one step:

```bash
python academic-shared/literature/bib_to_bibliography.py smoke_paper/refs.bib -o smoke_paper/bibliography.json --and-verify --output-dir smoke_paper/verification
```

## 3. Figure contract + style

```bash
python academic-plotting/scripts/plot_style.py --print-rcparams
# Write a one-figure YAML contract, then:
python academic-plotting/scripts/validate_figure_spec.py path/to/figure_spec.yaml
```

Produce one deterministic line/bar chart script under `smoke_paper/figures/` using Okabe–Ito; export PDF + PNG preview.

## 4. Pipeline router check (no full paper)

| Module | Load | Expect |
|--------|------|--------|
| journal | `skills-embedded/latex-paper-en.md` | points to `../../academic-latex/` |
| journal | `nature-figure.md` | points to `../../academic-plotting/` |
| thesis | same routers + T4 Axis 5 | `--allow-cjk` for zh |
| coursework | same routers after sync | C3 latex branch when `writingFormat=latex` |

```bash
python academic-shared/sync-to-modules.py --component skills-embedded
python academic-shared/sync-to-modules.py --component static-core
```

## 5. Commands

- S6 / C2: `/check-refs` → `academic-shared/commands/check-refs.md`
- S7 / C5: `/de-ai` → `commands/de-ai.md` (+ latex `style-de-ai.md` safety zones)
- S8 / T4: `/latex-cleanup` → `commands/latex-cleanup.md` + `verify_paper.py`
- S3/S4: `/verify-math` when derivation-heavy

## Pass criteria

- [ ] `verify_paper.py` runs without import errors
- [ ] bib→json→`verify_citations` path documented and executable
- [ ] figure validators run
- [ ] coursework `skills-embedded` contains latex-paper-en + three figure routers
- [ ] gate-chain Q6/QC3/QT4 text has no control characters / broken `verify_paper` tokens

## 6. P1 contracts (optional smoke)

`ash
cp academic-shared/issues/issues.template.csv smoke_paper/.paper/issues.csv
python academic-shared/issues/validate_issues.py smoke_paper/.paper/issues.csv
`

Also create empty drafts of citation_support_bank.md and rewrite_matrix.md from templates under academic-shared/citation and rewrite/.
