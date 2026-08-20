# Compile and debug

## Default loop

```bash
latexmk -pdf main.tex
# or
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
# Chinese
latexmk -xelatex main.tex
```

After each edit batch: scan log -> open PDF on changed pages.

## Debug strategy

1. Fix the **first** hard error; LaTeX errors cascade.
2. Prefer "stop on first error" when available (Overleaf / latexmk).
3. Line numbers can be wrong (`Missing $`) — search backward.
4. Binary-search with temporary `\end{document}` or commenting `\input`s.
5. Clear aux cache if stale (Overleaf: clear cache; local: `latexmk -C`).

## Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Undefined cite on first pass | Need full chain | latexmk / bib + re-run |
| Undefined control sequence | Missing package or typo | Load package or fix command |
| Missing `$` inserted | Math outside math mode | Find real locus backward |
| Runaway argument | Unmatched `{}` or blank line in forbidden arg | Brace match |
| File not found (figure) | Wrong path / not generated | Fix path; run plotting script |
| Too many unprocessed floats | Float backlog | `placeins`, `\clearpage`, subfigures |
| Timeout (Overleaf) | Errors + heavy TikZ/images | Fix errors; draft mode; externalize; compress |
| Overfull `\hbox` | Tight lines | microtype, reword, allow sloppy in draft only |

## AI-generated TeX pitfalls

- Hallucinated package names
- Hallucinated biblatex styles (ieee/apa/chicago — see whitelist above)
- Invalid environment nesting (table inside figure)
- Conflicting preamble vs venue class
- Blank lines inside `\title`/`\author`
- Deprecated commands
- `\usepackage{multirow}` — not in base TeX Live; use tabular-only layouts or check with `kpsewhich multirow.sty` first

Always compile before trusting model output. Specify existing packages in prompts so the model does not invent new ones. When a package is uncertain, check with `kpsewhich <name>.sty` before using it.

## BibTeX / biber

- `.bbl` errors often mean `.bib` problems — check `.blg`.
- biblatex users need `biber`, not `bibtex`.
- Mismatched backend is a frequent agent mistake.

### biblatex style whitelist (always available in base TeX Live)

Do NOT use `style=ieee`, `style=apa`, `style=chicago`, etc. — these require extra
packages (`biblatex-ieee`, `biblatex-apa`, …) that are frequently missing,
especially when `tlmgr` is unavailable (CI, containers, restricted Windows).

**Always-available styles (part of biblatex core):**

| style | Appearance | Maps to venue |
|-------|-----------|---------------|
| `numeric` | `[1]`, `[2,3]` | IEEE, ACM (closest) |
| `alphabetic` | `[ABC20]` | Some CS conferences |
| `authoryear` | `(Smith, 2020)` | APA, Harvard |
| `authortitle` | Author–title | Humanities journals |

For IEEE-like numbered citations: `style=numeric, sorting=none`.

### latexmk silent failure with missing style

When `\usepackage[biblatex]{style=xxx}` references a missing style file,
pdflatex exits non-zero **before** writing a complete `.bcf`.  latexmk
then aborts the entire chain — biber **never runs**, and subsequent
pdflatex passes **never happen**.  The log will show a cascade of
`\cite undefined` errors that will never resolve.

**Recognition**: latexmk output shows "Collected error summary" with zero
biber invocations in the log.

**Fix**: first, switch to a known-safe biblatex style (see whitelist above).
Then run the manual four-step chain once:
```bash
pdflatex -interaction=nonstopmode main.tex
biber main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```
After the fix takes, latexmk will work normally on subsequent runs.

## Done for compile gate

- Exit code 0 from latexmk (or documented soft warnings only)
- No undefined citations/references
- Figures exist on disk
- verify_paper.py hard fails = 0
