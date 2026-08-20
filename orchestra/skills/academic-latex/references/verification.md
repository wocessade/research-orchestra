# Mechanical verification

Long-document generation degrades silently. Trust scans, not impressions.

## Loop

```text
draft section -> verify_paper.py -> fix hard fails -> re-run
             -> CLEAN -> compile PDF -> next section
```

Two fix passes are normal; fixes introduce new errors.

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

Group, let user accept/reject, apply batch, re-verify.

## Pre-submit bundle

1. `verify_paper.py` clean
2. `verify_citations.py` clean (or documented exceptions)
3. `/latex-cleanup` checklist
4. academic-plotting QA for all figures
5. Gate-chain Q5/Q6 criteria
