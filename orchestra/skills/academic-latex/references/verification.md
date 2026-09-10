# Mechanical verification

Long-document generation degrades silently. Trust scans, not impressions.

## When to verify

Run `verify_paper.py` after a meaningful draft/revision batch and before delivery. Compile and inspect changed pages for layout-affecting edits and inspect the final PDF at delivery. Repeat after a fix or new change; do not require fixed repair rounds or a full compile after every paragraph.

Draft placeholders may remain while evidence is being collected; report them as unresolved. They block a final-ready claim, not unrelated draft work. Citation and numerical evidence requirements remain unchanged.

## Hard failures (block)

| Check | Why |
|-------|-----|
| CJK in EN `.tex`/`.bib` | Chat language leaking into English manuscript |
| `[CLAIM NEEDS EVIDENCE]`, `PLACEHOLDER_`, naked `TODO` | Unresolved debts |
| `\cite{key}` without bib entry | Broken cites; hallucination hotspot |
| `\ref{key}` without `\label` | Broken cross-refs |

## Soft warnings

- AI-vocabulary hits (allowed when technical)
- Throat-clearing phrases; body `\textbf`
- Unused bib entries
- Bib without doi/eprint/url/isbn

## Reporting judgment calls

```text
<file>:<line>  [Critical | Major | Minor]
Before: ...
After:  ...
Why:    ...
```

Apply authorized mechanical fixes as a batch and verify. Ask before changing scientific meaning or resolving an outstanding author decision.

## Pre-submit bundle

1. `verify_paper.py` clean
2. `verify_citations.py` clean (or documented exceptions)
3. `/latex-cleanup` checklist
4. academic-plotting QA for all figures
5. Gate-chain Q5/Q6 criteria
