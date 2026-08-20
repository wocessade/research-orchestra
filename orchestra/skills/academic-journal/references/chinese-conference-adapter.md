---
name: chinese-conference-adapter
description: Chinese domestic conference adapter — simplified pipeline for 国内会议, deadline-driven, shorter papers, EI/CPCI收录 consideration
---

# Chinese Conference Adapter (国内会议适配)

When `venue=chinese-conference`, the pipeline adapts for domestic academic conferences (CCF Chinese conferences, 学会年会, 国内学术会议). This is a simplified path compared to journal publication.

## Conference vs Journal (Chinese Domestic)

| Dimension | Chinese Journal (chinese-domestic) | Chinese Conference (chinese-conference) |
|-----------|-----------------------------------|----------------------------------------|
| **Length** | 8-15 pages | 3-6 pages (most), 6-10 (CCF Chinese A) |
| **References** | 20-50 | 10-20 |
| **Literature review** | Systematic, thematic | Condensed, gap-focused |
| **Figures** | 2-3 full figures | 1-2 figures |
| **Deadline** | Rolling submission | Fixed deadline (annual/biannual) |
| **Review** | 2-3 months, possibly multiple rounds | 1-2 months, single accept/reject |
| **Format** | Journal template (.docx or .tex) | Conference template (specified in CFP) |
| **Proceedings** | Journal issue | Conference proceedings (possibly EI/CPCI indexed) |
| **Publication** | Formal publication | May be informal (论文集 only, no formal publication) |
| **S8.6 Execution Layer** | Full 7 sub-stages | Skip — conference has no journal qualification |
| **Rebuttal** | Usually none | Rarely; if present, brief |

## Conference Types

| Type | Examples | Pipeline Behavior |
|------|----------|-------------------|
| **CCF Chinese Conference (CCF 中文会议)** | 全国计算机大会 (CNCC) 分论坛, CCF 专委学术年会 | Use CCF tier mapping from `references/discipline-stem.md` |
| **学会年会** | 中国管理学年会, 中国社会学年会, 各学会学术年会 | Discipline-specific, often low barrier to entry |
| **高校主办会议** | 各大学主办的学术论坛、研究生论坛 | Variable quality; ask user about proceedings publication |
| **EI/CPCI 收录会议** | 有 EI/CPCI 收录的国内会议 | Higher standard — treat as C-tier journal equivalent |

## Simplified Pipeline for Conference

When `venue=chinese-conference`, the pipeline shortens:

| Stage | Change |
|-------|--------|
| **S2** Literature Review | Target 10-20 refs (not 20-50). Scoped to gap identification. |
| **S2.5** Novelty Audit | Simplify — conference bar is lower than journal. Contribution must be clear but doesn't need systematic 6-dimension scoring. |
| **S3** Outline | Conference-length outline. 3-4 sections, not full IMRAD. |
| **S4** Writing | One-pass writing. Lean prose — every sentence must earn its place. |
| **S5** Figures | 1-2 figures max. Simple and clear. |
| **S6** Citations | Full verification still required — conference reviewers check references too. |
| **S6.5** Reproducibility | Skip — not expected for conference papers. |
| **S7** Polish | One-pass De-AI check. Less exhaustive than journal polish. |
| **S8.5** Venue Selection | Skip — conference is already chosen before writing. |
| **S8.6** Execution Layer | Skip — no journal qualification, reverse engineering, or positioning audit. |
| **S8** Format | Conference template from CFP. Verify page limits. |
| **S9** Review | Lite — fatal-flaw check only. No multi-persona review. |
| **S9.5** Attack Drill | Skip — conference review is single-round. |
| **S10** Submission | Cover letter optional. Follow CFP submission instructions. |

## EI/CPCI Enhancement

If the user's goal is EI/CPCI 收录:

- **English abstract quality:** Must be grammatically correct and complete (not an afterthought). 200-300 words, structured.
- **English title + keywords:** Must use standard field terminology.
- **References:** Increase to 15-25, with 30%+ English-language references.
- **Figures:** All figure/table captions must be bilingual if required by proceedings format.

## Deadline Workflow

```
D-21: Idea + outline complete
D-14: Draft complete
D-7:  Polish + De-AI check
D-3:  Format check + page limit verification
D-1:  Final compile, PDF check
D-Day: Submit per CFP instructions
```

Conference deadlines are hard — the pipeline must track remaining days and warn if slipping.
