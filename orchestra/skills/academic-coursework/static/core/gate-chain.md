# Quality Gate Chain

> **Gate 前的手卫生:** 每次门禁评估前，执行 `static/core/attention-defense.md` M1 的 stage handoff check——读 passport 的 Stage Completion Log，确认当前 axes 和上一 stage 输出未被遗忘。任何 gate 评估都建立在"知道自己从哪里来"的基础上。

**Idea-First:**
```
Q1 → Q0.5 → Q1.5† → Q2 → Q2.5 → Q3 → Q4 → Q5 → Q6 → Q6.5 → Q7 → Q8.5 → Q8.6* → Q8 → [Q8.25°] → Q9 → Q9.5 → Q10 → Q11 → Q12**
```
† Q1.5: conditional — only for causal/associational papers. Skipped when S0.5 routes to S2 for non-empirical paper types.
* Q8.6 is conditional: only for Chinese domestic journal targets. SOFT BLOCK — S8.6G "Ready/Not Ready" is a go/no-go decision; 7 sub-stages end with formal evaluation.
** Q12 is conditional: only when post-submission status = R&R (major/minor revision).
° Q8.25 is optional (ADVISORY) — preprint submission. Run before S9 only if user wants to post a preprint. See strategists/S8-strategist.md for instructions.

**Literature Review (Idea-First):**
```
Q1 → Q0.5 → Q2-LR → Q2.5 → Q3 → Q4 → Q5 → Q6 → Q6.5 → Q7 → Q8.5 → Q8.6* → Q8 → [Q8.25°] → Q9 → Q9.5 → Q10 → Q11 → Q12**
```
* Q8.6: conditional — only for Chinese domestic journal targets.
** Q12: conditional — only when post-submission status = R&R.
° Q8.25: optional — preprint submission (ADVISORY).

**Data-First:**
```
QD0 → QD1 → QD2 → Q0.5 → Q1.5* → Q2 → Q2.5 → ...
                      └→ Q2-LR → Q2.5 → ...
```
\* Q1.5: conditional — only for causal/associational papers. Skipped when S0.5 routes to S2 for non-empirical paper types.
  Q2-LR branch: taken when paperType=literature-review (systematic review).

**Course-Assignment:**
```
QC1 → QC2 → QC3 → QC4 → QC5 → QC5.5†
```
† QC5.5: conditional — only triggered by keyword (padding/de-AI/plagiarism-check) after C5 convergence. See `strategists/C5.5-strategist.md`.

**Thesis:**
```
QT1 → QT1.5* → QT2 → QT3 → QT4 → QT5 → QT6 → QT6.7† → QT6.5** → QT7
```
\* QT1.5: conditional — only when hasData=true (thesis with data).
† QT6.7: conditional — only triggered by keyword (padding/de-AI/plagiarism-check) after T6 convergence. See `strategists/T6.7-strategist.md`.
\** QT6.5: conditional — only when degree=master (盲审准备).

**Existing-Manuscript:**
```
Q7 → Q8.5 → Q8.6* → Q8 → [Q8.25°] → Q9 → Q9.5 → Q10 → Q11 → Q12**
```
* Q8.6: conditional — only for Chinese domestic journal targets. SOFT BLOCK — S8.6G "Ready/Not Ready" is a go/no-go decision; 7 sub-stages end with formal evaluation.
** Q12: conditional — only when post-submission status = R&R (major/minor revision).
° Q8.25: optional (ADVISORY) — preprint submission. Run before S9 only if user wants to post a preprint. See strategists/S8-strategist.md for instructions.

## Gate Rules

| Gate | Type | Condition to proceed |
|------|------|---------------------|
| Q1 | BLOCK | Research question is specific, testable, and stated in one sentence. Not "exploring X" — "testing whether X affects Y through Z". |
| Q0.5 | SOFT BLOCK | Project sanity check passed. **Idea-First:** 0-1 "No" = proceed, 2+ "No" = explicit justification required. **Data-First:** 0 No = proceed (to S1.5, or S2-LR for literature-review), 1+ No = SOFT BLOCK — must either return to D2, narrow scope, or document explicit override. See Stage 0.5A for full scoring. |
| Q1.5 | COND. BLOCK | For causal/associational papers: identification strategy documented. For registered reports: pre-registered design complete (hypotheses, methods, analysis plan, power analysis). For descriptive/theory/review papers: N/A. |
| Q2 | BLOCK | Gap analysis document exists with 10+ verified citations. No unverified DOIs. PRISMA diagram if systematic review. |
| Q2-LR | BLOCK | PRISMA 2020 flow diagram generated with all 4 tiers quantified. Search strategy documented for ALL databases (strings, coverage dates, reproducible). Inclusion/exclusion criteria defined as structured table. Quality assessment completed with appropriate tool per study design. Synthesis method selected and justified. All DOIs verified. For systematic reviews: protocol registration number documented. |
| Q2.5 | ADVISORY | Novelty audit complete. Contribution type classified. Scoop risk assessed. Strongly advised but can override. |
| Q3 | BLOCK | Outline has IMRAD (or type-appropriate) sections, 3-5 key claims per section, and the contribution is stated. **Also:** `{paper_dir}/.paper/confirmed_contribution.md` exists with `user_confirmed: true` and 1–3 claim-first contributions (`python academic-shared/contribution/contribution_check.py …` OK). IF `discipline=stem` or CS conference: `.paper/draft0_intro.md` present (mini Draft0). |
| Q4 | BLOCK | Complete draft exists. Every section has prose (not bullet points). No placeholder text ("[add more here]"). **Also:** Results subsections end with Takeaway; `.paper/contribution_experiment_map.md` covers every Ci; Final Introduction rewritten after Methods/Results (Draft0 is not the final Intro). No strong conclusions for evidence rows still `planned`/`placeholder`. **P1:** `.paper/issues.csv` exists and `validate_issues.py` OK (results rows verified or user-waived in notes). |
| Q5 | BLOCK | Type-appropriate figure minima per S5 (default: ≥1 schematic + ≥2 data figures; theory/short notes may document a lower plan at S3). All produced figures have complete captions (What/How/Takeaway). Colorblind-safe palette. Axes labels readable (≥8pt, no default matplotlib styling). Figure-text consistency cross-checked. Vector (SVG/PDF) for line art; ≥300 DPI raster. Multi-panel aligned. **Also:** each figure has a figure-contract (message + backend class) via academic-plotting; evidence/result figures are deterministic; concept diagrams may use generative backends but never invent numeric results. Skip figure minima only with explicit S3 exemption logged in passport. |
| Q6 | BLOCK | Every citation verified (DOI resolves). BibTeX file compiles without errors. Reference count matches citation count. **If writingFormat=latex:** `academic-latex/scripts/verify_paper.py` reports CLEAN (or user-waived blockers); no unresolved PLACEHOLDER_ cites; cite keys match .bib. **P1:** `.paper/citation_support_bank.md` present; keys used in Intro/RW/Discussion prefer verified bank rows. |
| Q6.5 | SOFT BLOCK | Reproducibility check complete: data backed up, code documented, seeds set, DAS (Data Availability Statement) drafted. Can override with documented reason and limitation statement in paper. |
| Q7 | BLOCK | `skills-embedded/paper-audit.md` gate returns PASS. No Critical or major items remain. Moderate/minor advisory items may persist. Factual accuracy check (S7G) complete — no Critical factual errors; all Major factual errors fixed or deferred. **P1:** Major prose rewrites logged in `.paper/rewrite_matrix.md` with Status=done (or waived). |
| Q8.5 | SOFT BLOCK | Publication strategy selected. Can proceed with warning if using pre-chosen venue. |
| Q8.6 | SOFT BLOCK | Chinese domestic journal execution layer complete (only when venue=chinese-domestic). S8.6G "Ready/Not Ready" is a go/no-go decision. If "Not Ready": return to S8.5 for re-selection. Can override with documented reason. |
| Q8 | BLOCK | PDF compiles without LaTeX errors. Template matches venue selected at Stage 8.5. |
| Q8.25 | ADVISORY | Preprint posted to server (or decision documented to skip). Preprint-ready PDF prepared with disclaimer, license, metadata. ORCID updated. Co-authors notified. Never blocks — can override without justification. |
| Q9 | BLOCK | `skills-embedded/paper-audit.md` gate returns PASS. All Critical items fixed (equivalent to HIGH in S9 severity terms). Response matrix filled. **Emergency:** Run S9-Lite (paper-audit, fatal-only, 1 round, skip 4 reviewer personas). All fatal items must be fixed. Moderate/minor items deferred to revision stage. |
| Q9.5 | SOFT BLOCK | Reviewer attack drill complete. All "Fix Now" items resolved. Top 5 fatal flaws pass. Can override with documented reason, but unreviewed fatal flaws are the #1 cause of first-round rejection. |
| Q10 | BLOCK | Cover letter written. Data statement ready. All author approvals obtained. |
| Q11 | SOFT BLOCK | Post-submission tracking complete. **R&R:** route to S12 (Revise & Resubmit) — all reviewer comments addressed in Response Matrix with change locations documented. **Rejection:** root cause documented, new venue selected. **Acceptance:** proof checked, final version submitted. |
| Q12 | BLOCK | (R&R only) All reviewer comments parsed, numbered, and classified (S12A). Response strategy confirmed by user (S12B). All revisions applied to manuscript source with response letter drafted (S12C). Response letter audit passed — all responses aligned, located, collegial, complete (S12D). Revised manuscript audit passed (fatal-only, S12E). Cross-verification complete — every response claim confirmed in manuscript (S12F). Revised manuscript compiles without errors. No unresolved [UNVERIFIED CLAIM] flags. |
| QD0 | SOFT BLOCK | Data manifest (D0Z) confirmed by user. Data inventory complete. Structure, variables, missingness documented. D0A-D0D done. Incomplete manifest does not block — user can proceed with partial manifest and fill remaining fields later. |
| QD1 | BLOCK | EDA complete. Patterns documented. Alternative explanations tested or flagged. NO p-values. |
| QD2 | BLOCK | ONE research question selected. Targeted novelty check confirms gap exists. |
| QC1 | BLOCK | Topic selected and stated in one sentence. 3+ core arguments identified with logical progression. User confirmed topic and arguments before proceeding to C2. |
| QC2 | BLOCK | 15+ references collected after deduplication. Mix of Chinese and English sources (at least 3 from each language). Each argument from C1 has 3+ supporting references (quality score >= 5.0 for at least 2 of the 3). All entries have title + author + year. Quality matrix generated with 3D composite scores. Snowballing (forward + backward, depth >= 1). Citation network analysis reviewed (consensus/controversy/frontier). A+B tier minimum: 12 standard / 6 emergency. C-tier <= 20% cap. Web context search (Tavily) complete. Web-academic cross-reference done. Full checklist: 22 items in C2.md QC2. |
| QC3 | BLOCK | Complete draft exists in the chosen writingFormat. **Default (word):** .docx with required sections (title, author/affiliation, abstract, keywords, introduction, body 3+ argument sections, conclusion, references, AI acknowledgement); 8+ pages; 宋体 body / 黑体 headings / 1.5 spacing / first-line indent. **If writingFormat=latex:** compilable .tex project instead of .docx; same section coverage; `academic-latex/scripts/verify_paper.py --allow-cjk` CLEAN (or waived); figures via academic-plotting routers when figures are required. |
| QC4 | BLOCK | All 6 review agents (5 scored + 1 factual_accuracy) complete via evaluate module. Issues categorized by severity (Critical/Major/Minor). Consolidated issue list produced with deduplication and conflict resolution. |
| QC5 | BLOCK | (Prerequisite: all Critical items from the most recent review must be fixed; all Major items must be fixed or deferred.) Convergence achieved: no new Critical items AND ≤ 2 new Major items from the most recent review round vs. the previous round. Hard limit: 3 review-revision rounds total. Degeneration: if a previously-fixed issue reappears unchanged, stop and fix properly before re-review. |
| QC5.5 | COND. BLOCK | (Keyword-triggered after C5 convergence — padding/de-AI/plagiarism-check.) Inflation round complete: target word count reached. Post-inflation De-AI scan passed (no new AI-signal above thresholds). Plagiarism risk ≤ acceptable threshold. Padding source audit passed (every addition source-tagged, no fabricated references). Must re-run C4 evaluate module after inflation with full 6-agent suite. Inflated manuscript passes QC4 thresholds. Converged within 2 rounds or revert to pre-padding version. |
| QT1 | BLOCK | Topic selected and stated in one sentence. 任务书 complete. 开题报告 complete with all 6 required sections. User explicitly confirmed topic, 任务书, and 开题报告. **Also:** `.paper/confirmed_contribution.md` with `user_confirmed: true` (1–3 thesis contributions / 创新点); seed `.paper/contribution_experiment_map.md` for planned chapters/experiments. |
| QT1.5 | COND. BLOCK | Data manifest confirmed by user. Descriptive exploration complete (univariate summaries, distributions, correlations, missingness map). Data understanding summary written for methodology reference. Only applies when hasData=true. |
| QT2 | BLOCK | Degree-differentiated (lit review chapter minimum): bachelor 20+ refs (5CN+5EN) / master 30+ refs (10CN+10EN). References organized into 3-5 themes (not just language-based). Research gap clearly identified. Thematic outline for 文献综述 chapter written. At least 3 existing 硕博论文 referenced (master); recommended at least 1 (bachelor). All entries have title + author + year + source in GB/T 7714 format ([J],[M],[D],[C],[S],[EB/OL]). Note: QT4 sets higher thesis-wide totals (bachelor 20+/master 50+). |
| QT3 | BLOCK | Methodology chapter complete (not outline, not bullet points). Research design type clearly stated. Data/sources fully documented. Analysis methods specified with justification. Replicability standard met — another researcher could reproduce from this description. Ethical considerations addressed. Chapter fits degree-level depth (bachelor: adequate, master: thorough). |
| QT4 | BLOCK | All required chapters present: 封面, 绪论, 文献综述, 研究方法, core chapters (≥1), 结论与展望. Core chapters substantive (3K+ words/chapter bachelor / 5K+ master). Word count: 15K+ (bachelor), 30K+ (master). Reference count (thesis-wide): 20+ (bachelor), 50+ (master). Chinese abstract (bachelor 300-500字 / master 500-1000字) and English abstract (bachelor 200-300 words / master 300-500 words) present. 声明页, 致谢, standalone AI declaration present. All in-text citations have reference entries. GB/T 7714 references. GB/T 7713.1 structural compliance (title page format, abstract structure, section numbering, page layout). LaTeX compiles / .docx opens. No placeholder text. Each chapter starts on new page. **If LaTeX:** run `academic-latex/scripts/verify_paper.py --allow-cjk` CLEAN (or waived); inherit academic-latex citation rules (no memory BibTeX). |
| QT5 | BLOCK | All 9 (humanities bachelor) / 10 (STEM bachelor) / 11 (master) review agents complete via evaluate module (7/8/8 scored + ai_tone (scoreless curve) + factual_accuracy per tier; master adds ethics_reviewer = 3/3/4 scoreless). Plagiarism check guidance produced (high-risk passage identification + rewrite suggestions). Issues categorized by severity (Critical/Major/Minor). Consolidated issue list produced with deduplication. |
| QT6 | SOFT BLOCK | (Prerequisite: all Critical items from the most recent review must be fixed; all Major items must be fixed or deferred.) Convergence achieved: no new Critical items AND ≤ 2 new Major items from the most recent review round vs. the previous round. Hard limit: 3 review-revision rounds total — if reached without convergence, proceed to T7 with caveat. Degeneration: if a previously-fixed issue reappears unchanged, stop and fix properly before re-review. If T6-Pre (查重) was run: plagiarism-critical passages (Priority ≥ 2.5 — see `references/T6-plagiarism-check.md` for formula) treated as equivalent to Critical items; all priority passages fixed and per-chapter targets met per `references/T6-plagiarism-check.md`. **P1:** major prose rewrites logged in `.paper/rewrite_matrix.md` (Status=done or waived). |
| QT6.7 | COND. BLOCK | (Keyword-triggered after T6 convergence — padding/de-AI/plagiarism-check.) Inflation round complete: target word count reached (bachelor 15K+ → 20K+, master 30K+ → 35K+). Post-inflation De-AI scan passed (no new AI-signal above thresholds per `chinese-de-ai-guide.md`). Plagiarism risk ≤ acceptable threshold. Padding source audit passed (every addition source-tagged, no fabricated references). Must re-run T5 evaluate module after inflation with full agent suite matching degree+discipline. Inflamed thesis passes QT5 thresholds. Converged within 2 rounds or revert to pre-padding version. |
| QT6.5 | SOFT BLOCK | (degree=master only) Blind review version packaged: all identifiers anonymized (advisor, author, school, self-citations, fund numbers, lab names). PDF metadata cleaned. Dual versions: 盲审版 + 完整版. Bachelor theses bypass this gate. Can override if university does not require blind review. |
| QT7 | BLOCK | Defense PPT exists (15+ bachelor / 20+ master slides). Defense script (讲稿) written with slide markers and time estimates. Anticipated Q&A prepared (15+ questions across all 6 categories: research design, contribution, depth, future work, weaknesses, practical). Script slide markers align with PPT. Q&A covers all identified thesis weaknesses from T5 review. Defense rehearsal notes provided. Final thesis PDF/DOCX verified. User confirmed defense materials are satisfactory. |
