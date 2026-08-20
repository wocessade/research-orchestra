---
name: chinese-journal-adapter
description: Chinese domestic journal submission adapter — Stage 8.6 execution layer, journal tiers, GB/T standards, per-stage tool substitutions
---

## Chinese Domestic Journal Adapter (国内期刊适配)

When the target is a Chinese domestic journal (国内核心/学报/CSCD/CSSCI), the pipeline stages remain the same but tools and data sources change. **The user is your external skill** — you cannot access CNKI, 万方, or 维普, so ask when you would otherwise search.

### Core Rule

## Chinese Path Summary (中文投稿路径概览)

When you target a Chinese domestic journal (中文核心期刊), the pipeline transforms in these key ways:

| Difference | International Path | Chinese Domestic Path |
|-----------|-------------------|----------------------|
| **Literature search** | Agent auto-searches 10 databases via `skills-embedded/paper-lookup.md` | User runs CNKI/万方/维普 searches (agent cannot access them) |
| **Journal tiers** | SCI Q1-Q4 / SSCI quartiles → Route A/B/C | A (学科顶刊) / B1-B3 (核心: CSSCI/CSCD/北大核心) / C1-C3 (扩展版/入库) / D (普刊/学报) |
| **Formatting target** | LaTeX → PDF (most journals) | .docx (most journals) — ask before formatting |
| **Reference style** | Vancouver/APA/Nature | GB/T 7714 (most journals) |
| **Extra gate** | S8.5 → S8 | S8.5 → S8.6 (7 sub-stage execution layer) → S8 |
| **AI detection** | 16-dimension English De-AI guide | 19-dimension Chinese De-AI guide (includes translationese markers) |
| **Cover letter** | English, structured | Chinese, shorter, may require 导师/通讯作者 signature |

These substitutions affect: D2D, S2, S4, S6, S7, S8, S8.5, S10. See §Per-Stage Substitutions for the full mapping.

Key difference from international path: the agent cannot access CNKI/万方/维普 directly — the user is the external skill for Chinese database access. This starts at D2D and continues through S2, S6, and S10.

### English Submission to Chinese Journals

When `venue=chinese-domestic` and `language=en` (e.g., Science China, Chinese Physics B, Journal of Integrative Plant Biology):

- Use `chinese-journal-adapter` for formatting rules: GB/T 7714 references, dual abstracts (Chinese + English), page-1 footnote layout
- Use `english-de-ai-guide.md` (not chinese-de-ai-guide) for AI detection
- Use `skills-embedded/nature-writing.md` (not `skills-embedded/scientific-writing.md` zh mode) for prose
- S8.6 sub-stages still apply (journal qualification, positioning, etc.)
- Ask: "Does this journal have specific English formatting requirements that differ from the Chinese guidelines?"

### Core Rule

Same stages, same gates, same dependency chain. Three things change:
1. **Literature source**: User provides Chinese database search results instead of automated PubMed/arXiv queries
2. **Output format**: Likely .docx, not LaTeX PDF
3. **Journal tier system**: CSCD/CSSCI/北大核心 instead of SCI/SSCI quartiles

After S8.5 selects the domestic journal tier, proceed to **Stage 8.6 (Chinese Journal Execution Layer)** for submission-specific checks before formatting.

### Per-Stage Substitutions

| Stage | International | Domestic | What You Ask the User |
|-------|--------------|----------|----------------------|
| **D2D** | `skills-embedded/paper-lookup.md` targeted search to confirm novelty before full lit review | User searches CNKI/万方/维普 for the candidate question | *"请在[CNKI/万方/维普]检索你候选研究问题的关键词: [keywords]. 这个 exact finding 已经被发表过了吗? 如果有, 你的区分点是什么(不同人群/方法/时期/机制)?"* |
| **S2** | `skills-embedded/paper-lookup.md` auto-searches PubMed/arXiv/10 databases | User runs the search manually | *"请在[CNKI/万方/维普]检索关键词: [keywords]. 导出标题+摘要列表给我, 或截图搜索结果."* |
| **S2D** | Gap analysis from BibTeX library | Same method, different papers | Agent reads user-provided papers via `skills-embedded/nature-reader.md` (中英对照 mode) and produces gap analysis normally |
| **S2.5** | Competing paper journal from BibTeX `journal` field | Journal tier system differs. Note: Chinese papers from CNKI/万方 don't export BibTeX — extract journal names manually from user-provided reference lists. | *"你的目标期刊等级是? A-学科顶刊 / B1-CSSCI / B2-CSCD / B3-北大核心 / C1-C3-扩展版/科技核心 / D-普刊/学报"* |
| **S4** | `skills-embedded/nature-writing.md` for English prose | `skills-embedded/scientific-writing.md` (zh mode), style-match from sample paper | *"请发一篇该期刊最新发表的范文(.pdf或文本), 我读完后按同样风格写."* Then use `skills-embedded/nature-reader.md` to study the style; `skills-embedded/scientific-writing.md` (zh mode) to write. |
| **S6** | `skills-embedded/citation-management.md` DOI verification + BibTeX | GB/T 7714 format, no BibTeX | *"请提供参考文献列表(GB/T 7714格式), 我来核对顺序、作者、年份、卷期页码."* |
| **S7** | `skills-embedded/nature-polishing.md` for English | Chinese De-AI: `chinese-de-ai-quick-ref.md` (~100 lines, auto-loaded at S7) for core detection rules. For deep 19-dimension scan, load `chinese-de-ai-guide.md` on demand. Use `skills-embedded/latex-thesis-zh.md` de-AI mode for execution. | No ask needed. Quick-ref covers key AI pattern detection including translationese markers (零主语/的-堆叠/被-过度使用). Section risk weights: Discussion = HIGH risk, Methods = LOW risk. |
| **S8** | `skills-embedded/latex-document-skill.md` → PDF | Most accept .docx only | *"该期刊是否只收Word? 如果是, 我生成格式干净的 .docx; 如果是LaTeX, 我用latex-document-skill编译."* |
| **S8.5** | Route A/B/C via SCI tiers | Domestic tier system (A/B/C/D) → **Stage 8.6** | See §Domestic Journal Tiers above. Ask: *"你所在单位/学科对毕业/评职称的期刊级别要求是什么? 你的发表目标是什么? (冲好刊/正常发表/满足毕业/评职称)"* |
| **S8.6** | N/A (no equivalent) | Chinese journal execution layer | See §Stage 8.6 below. Runs after S8.5 for domestic targets only. |
| **S10** | `skills-embedded/cover-letter.md` in English | Chinese cover letter, shorter | *"请确认: 稿件推荐信/声明是否需导师或通讯作者签署? 基金项目号是多少?"* |

### Domestic Journal Tiers (替代 8.5A Route A/B/C)

When the target is a Chinese journal, replace the international Route A/B/C system with this tier system. **Tiers are objective classifications based on recognized evaluation systems, not publishing strategies.** Strategy (稳发/快发/冲顶) is a separate dimension overlaid at S8.5 decision time.

#### Tier Definitions

| Tier | Source | Description | Review Cycle |
|------|--------|-------------|-------------|
| **A — 学科顶刊** | CSSCI 学科排名前 3-5 + CSCD 对应 JCR 一区 | Flagship journals within the discipline. Highest rejection rate. Requires significant contribution. 例：《经济研究》《管理世界》《中国科学》《计算机学报》《社会学研究》 | 6-12 月 |
| **B1 — CSSCI 来源期刊** | 南京大学 CSSCI 来源期刊目录（含扩展版中公认质量较高的部分） | ~500-600 种，覆盖人文社科。国内社科领域主流评价标准 | 4-8 月 |
| **B2 — CSCD 核心库** | 中科院 CSCD 核心库 | ~1000 种，覆盖自然科学/工程技术。国内理工领域主流评价标准 | 4-8 月 |
| **B3 — 北大核心** | 北京大学《中文核心期刊要目总览》 | ~1900 种，全学科覆盖。覆盖面最广的核心期刊体系。B1/B2 收录的期刊多数也在 B3 中 | 4-8 月 |
| **C1 — CSSCI 扩展版** | 南京大学 CSSCI 扩展版来源期刊 | CSSCI 候补梯队，部分高校视同核心 | 3-6 月 |
| **C2 — CSCD 扩展库** | 中科院 CSCD 扩展库 | CSCD 候补梯队 | 3-6 月 |
| **C3 — 中国科技核心** | 中国科学技术信息研究所"中国科技核心期刊"（统计源） | 工程技术领域基础收录门槛 | 2-4 月 |
| **D — 普通正式出版物** | 有 CN 刊号的省级期刊、本科学报 | 正式出版但未被核心体系收录。满足毕业/评职称最低要求 | 1-3 月 |

#### Tier Overlap Note

B1/B2/B3 三者有大量重叠——一本顶级 CSSCI 期刊通常也同时被北大核心和 CSSCI 收录。分级时按**用户所在学科的评价主导体系**确定主要等级：
- 人文社科用户 → 以 B1 (CSSCI) 为主要参照
- 理工科用户 → 以 B2 (CSCD) 为主要参照
- 跨学科/不确定 → 以 B3 (北大核心) 为通用参照

#### Strategy Overlay (与等级分离)

等级确定后，在 S8.5 决策时叠加用户需求：

| 需求 | 建议等级范围 | 说明 |
|------|------------|------|
| 冲击好刊 | A ~ B1/B2 | 首选 A，备选 B。可以承受较高拒稿率 |
| 正常发表 | B1/B2/B3 | 在核心体系内稳妥选择 |
| 满足毕业 | B3 ~ C1/C2/C3 | 满足学位要求的最低核心门槛 |
| 评职称/打卡 | C3 ~ D | 时间优先，有正式刊号即可 |

**Decision tree:**

```
Step 1: Determine the objective tier your paper can reach.
  ├── Breakthrough finding or major methodological advance → A
  ├── Solid contribution with incremental innovation → B1/B2/B3 (pick per discipline)
  ├── Modest but sound contribution → C1/C2/C3
  └── Meets minimum publication standard → D

Step 2: Overlay your publishing goal.
  ├── 冲好刊 → target the upper bound of your tier or next tier up
  ├── 正常发表 → target the middle of your tier
  ├── 满足毕业 → target the lower bound of your tier or next tier down
  └── 评职称/打卡 → target D if time-constrained
```

**Ask the user:** "你在哪个学科? 你所在单位的期刊分级标准是什么? (如《XX大学学术期刊分级目录》/ 中科院分区 / 中国科协高质量期刊分级)"

### S8.6 Depth by Tier

S8.6 执行层的检查深度按等级区分：

| Tier | 8.6A 期刊资格 | 8.6B 逆向工程 | 8.6C 定位审计 | 8.6D 创新包装 | 8.6E 结构合规 | 8.6F 审稿人视角 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | 全部检查 | 全部 + 3篇近刊 | 全部 | 全部 | 全部 | 双审稿人 |
| **B1/B2/B3** | 全部检查 | 2篇近刊 | 全部 | 重点检查 | 全部 | 双审稿人 |
| **C1/C2/C3** | 栏目匹配 + 范围 | 1篇近刊 | 跳过 | 标题+摘要 | 参考文献+摘要 | 方法审稿人 |
| **D** | 范围检查 | 跳过 | 跳过 | 仅标题 | 参考文献+字数 | 跳过 |

---

### Stage 8.6: Chinese Journal Execution Layer (中文期刊执行层)

**Insertion:** After S8.5 (Publication Strategy). Before S8 (Format & Compile).
**Trigger:** S8.5 determines target is a Chinese domestic journal. If international, skip directly to S8.
**Goal:** Submission-specific checks for Chinese domestic journals. Not research evaluation — that's already done (S1-S8.5).

**Hard rule — every sub-stage consumes outputs from prior stages.** No second novelty audit. No second contribution discovery. No second literature review.

#### 8.6A. Journal Qualification

**Purpose:** Verify the paper is eligible for the intended journal.

**Input:** S8.5 venue list + S4 manuscript.

**Check:**
- **栏目匹配 (Section/column fit):** Chinese journals organize content by 栏目 (sections). Check the journal's recent tables of contents — which 栏目 would this paper fit under? If no matching 栏目 exists, desk rejection is nearly certain. Return to S8.5 for re-selection.
- Scope fit: does the journal publish this topic/field?
- Article type fit: does the paper match an accepted article type (研究论文/综述/简报)?
- Length limits: word count, figure count, table count within journal limits
- **Funding requirements (基金要求):** Many A/B-tier journals require funded projects — some won't send unfunded papers for review. Ask: does the paper have a funded project with a grant number? If no funding and targeting A/B1/B2, warn: "无基金支撑, 该级别期刊接受率显著降低. 建议确认该期刊是否接受无基金稿件, 或考虑C级/D级." For B3/C-tier: note as recommendation, not blocker. For D-tier: skip.
- **Author qualification (作者资质):** A/B-tier journals may require first author to hold a PhD or associate professor title (博士/副高以上). For C/D-tier: rarely enforced. Ask: "第一作者学历及职称? 如不具备, 该期刊是否接受研究生为第一作者?"
- **查重预检 (Plagiarism check):** All B-tier and above journals use CNKI AMLC or similar systems. Target: <15% repetition rate for A/B-tier, <20% for C-tier, <30% for D-tier. AI-written Chinese text may trigger false positives in CNKI's detection. Ask: "请在知网个人查重服务进行预提交查重. 如重复率超过目标, 先运行 chinese-de-ai-guide.md 的 D16-D18（翻译腔检测：零主语/的-堆叠/被-过度使用）降重处理后返回 S7，再次查重."

STOP-AND-ASK: Never fabricate journal rules, author qualifications, or funding status. If the user hasn't provided the journal's author guidelines, ask for them.

**Output:** Qualified / Needs Adjustment / Not Qualified. If Not Qualified, return to S8.5 for re-selection.

#### 8.6B. Journal Reverse Engineering

**Purpose:** Extract patterns from recent accepted papers in the target journal.

**Input:** User-provided sample papers (2-3 recent issues of the target journal).

**Check:**
- Preferred framing: how do accepted papers open? Problem-driven or policy-driven?
- Preferred structure: does the journal deviate from standard IMRAD? (Many Chinese journals have unique section conventions)
- Preferred evidence style: empirical rigor expectations, table/figure density norms
- Preferred citation patterns: how many references? Chinese/English ratio? Self-citation norms?

Do NOT re-run novelty audit — S2.5 already established the novelty profile (if S2.5 exists). For existing-manuscript entry (skipped S1-S6.5), ask user: "这篇论文相对于已有文献的主要创新是什么？简要描述（2-3 句话）。" Use their description as the novelty profile.

STOP-AND-ASK: If no sample papers are available. *"请提供该期刊近2-3期的目录或论文样本, 我来分析其偏好."*

#### 8.6C. Positioning Audit

**Purpose:** Check whether manuscript positioning matches the selected journal's expectations.

**Input:** S2.5 novelty profile + S8.5 venue decision + S4 manuscript.

**Existing-Manuscript entry:** S2.5 novelty profile does not exist. Skip 8.6C (positioning audit) — proceed directly to 8.6E (structure compliance). **Positioning is NOT handled by 8.5B/8.5C** — those stages only verify venue scope match and submission requirements. For existing-manuscript entry, the positioning audit is omitted entirely. The user must manually verify that the manuscript's framing angle, contribution expression, and emphasized methodologies match the target journal's audience expectations. Recommend: "Have a domain colleague read the abstract and tell you if it fits the journal's typical framing."
- Does the framing angle match what this journal's audience expects?
- Is the contribution expressed in terms this journal's readers care about?
- Are the right methodologies emphasized for this journal's reviewer pool?

**Output:** Positioning adjustment suggestions (framing tweaks, emphasis shifts). Do NOT re-discover contribution — contribution was already established at S1/S2.5.

#### 8.6D. Innovation Packaging

**Purpose:** Improve presentation of the contribution. Not contribution creation.

**Input:** S2.5 novelty profile + S4 manuscript.

**Existing-Manuscript entry:** S2.5 novelty profile does not exist. Skip 8.6D (innovation packaging) — mark as `[SKIPPED: existing-manuscript]`. Innovation claims in the manuscript are assumed to reflect the author's own judgment.
- Is the innovation clearly stated in the title?
- Is it visible in the abstract (first 2 sentences)?
- Is it stated explicitly in the introduction (not buried in paragraph 3)?
- Do the keywords signal the innovation angle?
- Does the conclusion restate the innovation, or just summarize findings?

If the contribution itself is weak, return a warning — but do NOT redesign the research. The pipeline already validated contribution at S2.5.

#### 8.6E. Structure Compliance Audit

**Purpose:** Pure compliance check against journal formatting norms.

**Input:** S4 manuscript + journal guidelines (from 8.6A).

**Check:**
- Abstract format (structured vs. unified, word count, Chinese + English dual abstracts)
- Keyword count and selection (Chinese journals often have specific keyword requirements)
- Heading hierarchy and numbering convention — also verify **Methods 内部节序逻辑**: 实验方法节应排在统计/数据处理节之前，统计方法必须是 Methods 最后一节。如顺序倒置，标记为 P0 必须修复
- Reference style (GB/T 7714 for most Chinese journals)
- Figure/table placement and caption style
- Author bio and funding footnote placement (usually page 1 footer)
- **中图分类号 (CLC):** Must appear on the top-left of page 1. Ask: "你的学科是什么? 我来生成中图分类号." Generate from a simple discipline-to-CLC mapping.
- **文献标识码:** A (理论与应用基础研究) / B (技术报告) / C (综述). Most academic papers are type A.
- **CSTR (China Science and Technology Report):** If the journal requires it, remind user to obtain one.

This is a formatting compliance stage, not a content evaluation stage.

#### 8.6F. Reviewer Perspective Check (Lite)

**Purpose:** Anticipate likely reviewer objections from Chinese journal reviewer personas.

Two personas only:

**Persona A — Domain Reviewer (学科专家):**
- Will this reviewer find the literature coverage adequate for the Chinese context?
- Will they consider the contribution meaningful within the domestic research landscape?
- Top 3 likely concerns.

**Persona B — Method Reviewer (方法专家):**
- Will the methodology meet the journal's standard of rigor?
- Are the empirical choices defensible to a Chinese statistical/methods reviewer?
- Top 2 likely concerns.

**Output:** Top 5 likely objections (merged from both personas). No probability estimates. No acceptance predictions. No reviewer scoring formulas.

This is a lite complement to the full S9/S9.5 review process — focused specifically on Chinese journal reviewer expectations.

#### 8.6G. Submission Readiness

**Purpose:** Final pre-formatting readiness check.

**Pass criteria:**
- Target journal confirmed (单一目标期刊已选定)
- Journal qualification passed (8.6A)
- Positioning aligned (8.6C)
- Innovation packaging reviewed (8.6D)
- Structure compliance checked (8.6E)
- Top reviewer objections documented (8.6F)

**Output:** Ready / Not Ready (advisory only — no blocking gate).

If Not Ready, classify unresolved items by severity:

| Priority | Meaning | Action |
|----------|---------|--------|
| **P0** | Blocks formatting (missing section, wrong reference style) | Must fix before S8 compile |
| **P1** | High risk (weak positioning, missing funding disclosure) | Strongly recommended to fix |
| **P2** | Minor (keyword count off by 1, figure caption style) | Skip or quick fix |

If Not Ready, list unresolved items with their P0/P1/P2 classification and recommend which sub-stage to revisit.

### S8.6 Exit Rule

If the target journal changes during S8.6:

**Minor adjustment** (same tier, same discipline, different journal):
→ Continue within S8.6. Re-run 8.6A qualification for the new journal.

**Major venue change** (e.g., B1-CSSCI → D-普刊, B3-北大核心 → SSCI, 管理学 → 教育学):
→ **Return to S8.5.** The tier system, positioning, and packaging decisions made in S8.6 may not apply to the new venue. Do not re-run S8.6 against a fundamentally different venue profile.

### Domestic-Specific Rules

**DO:**
- Follow GB/T 7713.1 for section logic (not identical to IMRAD — check the journal's author guidelines)
- Write dual abstracts: detailed Chinese + condensed English. Never just translate one into the other. Mismatch between Chinese and English abstracts → major item at Q7 gate (see chinese-de-ai-guide.md dual abstract check).
- Place funding info and author bio in the footnote area of page 1 (as most Chinese journals require)
- Run the full S8.6 execution layer for Chinese domestic journal submissions — journal qualification, reverse engineering, positioning, packaging, compliance, and reviewer check before formatting

**DON'T:**
- Machine-translate an SCI paper into Chinese and submit to a domestic core journal — the abstract logic, lit review structure, and discussion framing are fundamentally different
- Ignore review queue time and publication backlog — some Chinese core journals have longer wait times than mid-tier SCI journals
- Skip S8.6 for domestic targets just because the paper passed S7 polish — international polish readiness ≠ domestic submission readiness

### Domestic Effective Commands

```
D2D (domestic): "Before the full literature review, I need to confirm this exact finding hasn't been published. User: please search [CNKI/万方/维普] for [keywords] and tell me: has this finding been published? If yes, what's your differentiation angle (不同人群/方法/时期/机制)?"
Stage 2 (domestic): "I'll search for Chinese literature. User: please search [CNKI/万方/维普] for [keywords in Chinese], export the title+abstract list, and paste it here. I'll identify the top 10 papers for deep reading."
Stage 2.5 (domestic): "Run the novelty audit on the Chinese papers you've collected. User: what's your target journal tier — A-学科顶刊 / B1-CSSCI / B2-CSCD / B3-北大核心 / C1-C3-扩展版/科技核心 / D-普刊/学报?"
Stage 4 (domestic): "Write this paper in standard academic Chinese. User: send me a recent published paper from your target journal as a style reference. I'll match its prose conventions."
Stage 6 (domestic): "I'll check the reference list. User: provide the GB/T 7714 formatted bibliography. I'll verify author names, years, volumes, and page numbers."
Stage 8 (domestic): "Compile the document. User: does the journal accept LaTeX or only Word? If Word, I'll generate a clean .docx. If LaTeX, I'll use latex-document-skill."
Stage 8.5 (domestic): "Select the domestic journal tier. A/B/C/D based on objective tier evaluation, then overlay publishing goal (冲好刊/正常发表/满足毕业/评职称). List 3-5 candidate journals within the recommended tier range."
Stage 8.6 (domestic): "Run the Chinese journal execution layer. User: provide the target journal's author guidelines and 2-3 sample papers from recent issues. I'll qualify the fit, reverse engineer the journal's preferences, audit positioning and packaging, check structure compliance, and anticipate reviewer concerns."
Stage 10 (domestic): "Prepare the Chinese submission package: cover letter, author declarations, funding acknowledgments. User: confirm whether the corresponding author's signed declaration is needed."
```

## Bilingual Elements Checklist

When targeting Chinese domestic journals, verify all bilingual elements before submission gate (S8.6F). Not all items apply to all journals — check the specific journal's author guidelines.

☐ **Chinese + English title** — Both must be present and semantically equivalent (not machine-translated word-for-word)
☐ **Chinese + English abstract** — English abstract must be grammatically correct, not a raw translation of the Chinese
☐ **Chinese + English keywords** — 3-8 keywords in both languages; English keywords should match standard field terminology, not literal translations
☐ **Author names in Pinyin + Chinese** — Family name first, given name as one word or hyphenated per author's preference
☐ **Author affiliations in Chinese + English** — Full institution name, city, postal code, country in both languages
☐ **Figure/table titles bilingual** — If required by journal; check author guidelines (some require both, some only one language)
☐ **Reference list: Chinese entries with English translation** — If journal requires; format: `[中文条目] (in Chinese)` or full English translation in brackets
☐ **Corresponding author email + ORCID** — Email required; ORCID strongly recommended for all corresponding authors


> **~24 KB reference file.** Prefer on-demand partial reads.
> **Sections:** `## Chinese Domestic Journal Adapter (国内期刊适配)` · `### Core Rule` · `## Chinese Path Summary (中文投稿路径概览)` · `### English Submission to Chinese Journals` · `### Core Rule` · `### Per-Stage Substitutions`
> `### Domestic Journal Tiers (替代 8.5A Route A/B/C)` · `### S8.6 Depth by Tier` · `### Stage 8.6: Chinese Journal Execution Layer (中文期刊执行层)` · `### S8.6 Exit Rule` · `### Domestic-Specific Rules` · `### Domestic Effective Commands` · `## Bilingual Elements Checklist`
