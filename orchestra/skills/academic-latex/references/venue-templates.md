# Venue templates

## Selection

| Venue family | Typical class / notes |
|--------------|----------------------|
| IEEE conference | IEEEtran |
| ACM | acmart |
| NeurIPS/ICML/ICLR | venue zip / style files — use official |
| Springer LNCS | llncs |
| Elsevier | elsarticle |
| Nature-family | journal-specific; often Word+LaTeX hybrid rules |
| Chinese journal | follow 期刊 LaTeX/Word template; GB/T 7714 refs |
| Chinese thesis | `latex-thesis-zh` + university cls |

Always prefer the **official** template over reinventing preamble.

## CS conference notes (discipline=stem)

- Page limits are hard; figures and tables count.
- Related Work placement may be post-method (see `discipline-stem.md`).
- Supplemental material often separate.

## Journal format packet

Copy venue rules into `.paper/journal_format.md`: column width, bib style, ethics statements, data/code availability, figure DPI, supplemental rules.

## Camera-ready

- Apply accepted template deltas only.
- Do not introduce new claims without evidence.
- Re-run verify + compile after every batch.
