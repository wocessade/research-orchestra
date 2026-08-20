# Project layout

## Recommended tree

```text
paper/   (or {paper_dir}/latex/)
├── main.tex
├── sections/
├── figures/          # academic-plotting outputs
├── tables/           # generated .tex — never hand-type result numbers
├── refs.bib
├── latexmkrc
├── Makefile
└── scripts/
.paper/
├── metadata.md
├── context.md
├── claim_evidence_ledger.md
├── figure_inventory.md
├── glossary.md
└── journal_format.md
docs/results/         # canonical CSVs / metrics
```

## main.tex hygiene

- Load venue class first (`IEEEtran`, `acmart`, journal/thesis cls).
- Prefer template defaults; avoid 50+ lines of spacing hacks.
- Load `hyperref` late (before `cleveref` if used).
- `booktabs` + `siunitx` for tables/numbers; `graphicx` for figures.
- Pick one bibliography backend: `biblatex`+`biber` OR classic bibtex.
- Chinese body: xelatex/lualatex + CJK fonts; English papers must not leak CJK.

## Front matter (reports / theses)

Order: title page -> declaration (if required) -> abstract -> TOC.
Confirm declaration wording with the user. Never invent a university logo.

## Numbers pipeline

```text
docs/results/*.csv  ->  scripts/make_table_*.py  ->  tables/*.tex
docs/results/*.csv  ->  academic-plotting        ->  figures/*.{pdf,png}
```

## Include pattern

Prefer PDF for plots; PNG fallback via `\IfFileExists`.

## Engines

| Need | Engine |
|------|--------|
| Most EN conference/journal | `latexmk -pdf` / pdflatex |
| Chinese / custom fonts | xelatex or lualatex |
| Lightweight / CI | tectonic |

Windows: probe tools first. If none, tell the user to install TeX.
