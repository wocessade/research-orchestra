---
name: discipline-stem
description: STEM/CS discipline adapter — CCF tiers, non-IMRAD paper structures, conference vs journal differences, deadline-driven workflow
---

# STEM Discipline Adapter (理工科适配)

> **~10 KB reference file.** Prefer on-demand partial reads.
> **Sections:** `## CCF Tier → Domestic Tier Mapping` · `### Subdomain Weight Exceptions` · `## CS Paper Structures (Non-IMRAD)` · `### System/Tool Paper` · `### Algorithm / Theory Paper` · `### Empirical / Measurement Paper`
> `### Survey / Review` · `### Key Structural Differences from Generic IMRAD` · `## Conference vs Journal (CS-Specific)` · `### Rebuttal Phase (Conference-Specific)` · `## Deadline-Driven Workflow` · `### Conference-Specific Adjustments` · `## CS-Specific Writing Conventions`

When `discipline=stem`, this reference supplements (not replaces) the standard pipeline. It provides STEM-specific conventions that override or refine the generic IMRAD defaults.

## P0 writing path (load with this file)

Also load `../../academic-shared/conference/cs-conference-path.md` and `../../academic-shared/contribution/contribution-gate.md` at S3/S4: contribution confirmation, Draft0 Intro, Results Takeaway, Final Intro after evidence, page-budget compression.

## CCF Tier → Domestic Tier Mapping

CCF (中国计算机学会) 推荐国际学术会议和期刊目录 is the authoritative ranking system for CS in China. Map to the generic domestic tier system:

| CCF Rating | Maps To | Examples |
|-----------|---------|----------|
| CCF-A 期刊 | A | TPAMI, TIFS, TDSC, JSAC, TOC |
| CCF-A 会议 | A | CVPR, ICCV, ICML, NeurIPS, SIGCOMM, CCS, IEEE S&P, OSDI, SOSP, PLDI |
| CCF-B 期刊 | A/B 交界 | TC, TPDS, TOSEM, TKDE |
| CCF-B 会议 | A/B 交界 | ICSE, ICDM, ICNP, EMNLP, ECCV |
| CCF-C 期刊/会议 | B | 受认可的国际发表 |
| CCF 中文 A | B | 《计算机学报》《软件学报》《中国科学：信息科学》 |
| CCF 中文 B | C | 《计算机研究与发展》《电子学报》《自动化学报》 |
| 无 CCF 分级但 EI/SCI 收录 | C~D | 视具体刊物而定 |
| 非 EI/SCI 收录中文期刊 | D | 普通计算机类期刊 |

### Subdomain Weight Exceptions

Not all CS subdomains follow the same conference-vs-journal weight pattern:

| Subdomain | Pattern | Examples |
|-----------|---------|----------|
| **AI/ML/CV/NLP** | 会议 >>> 期刊 | CVPR/ICCV/NeurIPS/ICML/ACL > most journals |
| **Systems/Architecture** | 会议 > 期刊 | OSDI/SOSP/ASPLOS/ISCA > most journals |
| **Security/Privacy** | 会议 ≈ 期刊 | CCS/IEEE S&P/NDSS/USENIX Security ≈ TDSC/TIFS |
| **Theory/Algorithms** | 期刊 ≥ 会议 | STOC/FOCS/SODA strong, but journal publication equally valued |
| **Software Engineering** | 会议 > 期刊 | ICSE/FSE/ASE > TOSEM/TSE (though both respected) |
| **Database** | 会议 > 期刊 | SIGMOD/VLDB/ICDE > TKDE (though TKDE highly respected) |

**Ask the user:** "你的子领域是什么? (AI/ML/系统/安全/理论/软件工程/数据库/其他)" to calibrate the conference-vs-journal weight.

## CS Paper Structures (Non-IMRAD)

CS papers follow discipline-specific structures. The standard IMRAD pipeline at S3/S4 must adapt:

### System/Tool Paper
```
1. Introduction
   - Problem statement + motivation
   - Proposed approach (one paragraph overview)
   - Contributions (numbered list)
2. Background / Motivation
   - Domain context, existing solutions and their limitations
3. System Design / Architecture
   - Design goals / requirements
   - Architecture overview (schematic required)
   - Key components and design decisions
   - Novel techniques introduced
4. Implementation
   - Technical details, stack, optimizations
5. Evaluation
   - Experimental setup (hardware, workloads, baselines)
   - Performance results (throughput, latency, resource usage)
   - Comparison to baselines
   - Ablation study (contribution of each component)
6. Related Work (placed AFTER evaluation — CS convention)
7. Conclusion + Future Work
```

### Algorithm / Theory Paper
```
1. Introduction
   - Problem definition (formal or informal)
   - Limitations of existing approaches
   - Proposed algorithm / theoretical contribution
2. Preliminaries / Problem Formulation
   - Notation, definitions, assumptions
   - Formal problem statement
3. Algorithm / Main Result
   - Algorithm description (pseudocode)
   - Correctness proof or theoretical analysis
   - Complexity analysis
4. Experimental Evaluation (if applicable)
   - Synthetic + real-world datasets
   - Comparison to baselines
   - Runtime/scalability analysis
5. Related Work (placed AFTER main content)
6. Conclusion
```

### Empirical / Measurement Paper
```
1. Introduction
   - Research questions / hypotheses
2. Background
   - Technical context needed to understand measurements
3. Methodology
   - Data collection, measurement setup, metrics
4. Results
   - Present findings with evidence
5. Discussion
   - Interpret results, implications, limitations
6. Related Work (placed AFTER discussion)
7. Conclusion
```

### Survey / Review
```
1. Introduction
   - Scope, taxonomy preview, contribution
2. Background / Preliminaries (if needed)
3. Taxonomy / Classification Framework
4-N. Detailed Survey by Category
N+1. Discussion / Open Problems / Future Directions
N+2. Conclusion
```

### Key Structural Differences from Generic IMRAD

| Generic IMRAD | CS Convention |
|---------------|---------------|
| Related Work right after Introduction | Related Work before Conclusion (after main technical content) |
| Methods → Results → Discussion | System Design → Implementation → Evaluation or Algorithm → Analysis → Experiments |
| "Methods" section | "System Design" / "Algorithm" / "Architecture" / "Methodology" |
| Single "Discussion" section | Discussion woven into Evaluation or separate section |
| Abstract 150-250 words (journal) | Abstract 150-200 words (conference) or 200-300 (journal) |

## Conference vs Journal (CS-Specific)

| Dimension | CS Conference | CS Journal |
|-----------|--------------|------------|
| **Importance** | Primary in most subdomains | Secondary in AI/ML/CV; equal in security/theory |
| **Deadline** | Fixed annual/biannual, hard cutoff | Rolling submission |
| **Length** | 6-14 pages double-column | 12-20+ pages |
| **Template** | `\documentclass[conference]{IEEEtran}` or `acmart` | Same or journal-specific |
| **Review** | 3-5 reviewers, single rebuttal round, 2-3 months | 2-4 reviewers, possibly multiple rounds, 6-18 months |
| **Rebuttal** | 1-week window, 500-1000 words, CRITICAL | Some have, many don't |
| **Supplementary** | Independent PDF/ZIP, submitted with main paper | Optional, integrated or separate |
| **Camera-Ready** | 2-4 weeks after acceptance | Minor revisions after conditional accept |
| **Presentation** | In-person talk + possibly poster | N/A |
| **Archival** | Proceedings in digital library (IEEE Xplore, ACM DL) | Journal issue |

### Rebuttal Phase (Conference-Specific)

CS conference rebuttal is a unique phase not covered by the generic pipeline's S12 (R&R response):

**Constraints:**
- Fixed window: typically 1 week
- Character/page limits: 500-1000 words or 1 page
- Cannot change the paper — can only respond, clarify, and promise changes
- Strategy: identify which reviewers can be convinced vs. which are hostile

**Rebuttal tactics:**
- For each reviewer concern: (1) acknowledge, (2) clarify misunderstanding, (3) describe planned change, (4) cite line numbers where evidence already exists
- Never argue with a reviewer — even incorrect criticism must be addressed respectfully
- If two reviewers disagree on a point: leverage the positive reviewer's comment in response to the negative one
- Priority: address concerns raised by multiple reviewers first, then AC/meta-reviewer comments, then individual concerns

## Deadline-Driven Workflow

For conference submissions, the timeline is frozen — you don't move the deadline, the deadline moves you.

```
D-30: S1-S3 complete (idea + lit review + outline)
       → Venue already known (you chose CVPR/ICML/etc. before starting)
       → Skip S0.5 full feasibility, skip S8.5 venue selection
D-21: S4 draft complete (all sections, rough prose)
D-14: S5 figures + S6 citation checks
D-10: S7 polish + internal review
       → Share with co-authors
       → 3-referee model (7B-ALT) recommended for A-tier conferences
D-7:  Send to advisor/collaborators for final feedback
D-3:  S9 final review (lite — fatal-flaw check only, skip multi-persona full review)
D-1:  Format check — margins, font embedding, PDF/A compliance, page limits
       → Supplementary material final packaging
D-Day: Submit (at least 6 hours before hard deadline — server crashes are common)
D+30~60: Notification
D+30~67: Rebuttal window (if applicable)
       → Prepare response to all reviewer concerns
       → Addressed concerns table: Reviewer | Concern | Response | Promised Change
D+60~90: Final decision
```

### Conference-Specific Adjustments

| Pipeline Stage | Conference Mode |
|---------------|-----------------|
| S0.5 (feasibility) | Skip — venue already chosen |
| S1.5 (research design) | Keep — identification strategy still matters |
| S2 (lit review) | Scoped — 10-20 papers, not exhaustive |
| S2.5 (novelty) | Critical — conference reviewers prioritize novelty |
| S3 (outline) | CS structure, not IMRAD |
| S4 (writing) | Concise, figure-driven, page-limit-aware |
| S5 (figures) | 2-4 compact figures, efficient use of space. Vector format mandatory |
| S6 (citations) | Full verification — conference reviewers check references |
| S6.5 (reproducibility) | Soft — most conferences don't require artifact evaluation but it helps |
| S7 (polish) | Critical — every word counts with page limits |
| S8 (compile) | Template-driven (IEEEtran/acmart), page limit check per line |
| S8.5 (venue) | Skip — already chosen |
| S8.6 (Chinese) | Skip — not applicable |
| S9 (review) | Lite — fatal-flaw only. S9.5 (reviewer attack drill) recommended |
| S9.5 (attack drill) | Keep — anticipate reviewer criticisms before rebuttal window opens |
| S10 (submission) | Supplementary materials packaging + cover letter optional |
| S11 (post-submit) | Track notification date, prepare rebuttal templates |
| S12 (revision) | Conference rebuttal (different from journal R&R — see §Rebuttal Phase) |

## CS-Specific Writing Conventions

| Convention | Rule |
|-----------|------|
| **Contributions list** | Numbered list in Introduction, typically 3-4 items. Each item = one concrete contribution |
| **Figures first** | CS reviewers often scan figures before reading text. Every figure must tell a story independently |
| **Pseudocode** | Use `algorithm2e` or `algorithmicx` package. Not prose description of algorithm steps |
| **Evaluation section** | The most important section after Introduction. Must include: setup, baselines (with justification), metrics, results, ablation, discussion |
| **Table conventions** | Bold best results. Statistical significance markers (superscripts). Standard deviations in parentheses |
| **Math notation** | Consistent throughout. Define all symbols at first use. No undefined variables |
| **Code/System names** | Small caps or monospace font. No trademark symbols |
