---
name: academic-journal
description: 期刊论文写作辅助：结构化写作、文风学习、多维度评审与投稿材料准备。支持步进与标准两种模式。辅助构思、检索、组织证据与修订 — 不替代作者完成可直接投稿的稿件。Journal article writing assistance — supports stepping/standard mode, style learning, and full evaluate review for SCI/SSCI/A&HCI/Chinese core journal or conference papers.
---

# Academic Journal — 期刊论文写作模块

执行范围与授权见 [共享执行规则](../academic-shared/references/execution-policy.md)；按当前任务读取阶段细则。

独立模块，用于撰写和打磨期刊论文。支持两种写作模式和完整的 evaluate 评审体系。

## 能力范围

| 能力 | 说明 |
|------|------|
| 步进模式 | 每写完一个二级节停下来等作者核对，确认通过/小改/打回后再继续（参见 `stepping/`） |
| 标准模式 | 一路写完再总核对，适合有经验的写作者 |
| 文风学习 | 分析目标期刊已发表论文的风格特征，自动适配写作（参见 `style_learning/`） |
| 术语表 | 通用 pipeline 概念见 `../academic-shared/GLOSSARY.md` |
| 完整 evaluate | 多 Agent 平行评审系统，覆盖结构、内容、方法、创新、伦理等维度（参见 `evaluate/`） |

## 模式选择

### 步进模式 (Stepping Mode)
适用于：初次写作、需要频繁核对、对内容一致性要求高的场景

流程：按 Core-First 顺序推进，每写完一节停下来等作者核对，确认后继续。作者可随时指定跳到其他节（如"先写 §3.2"）。

> **默认写作顺序（Core-First Protocol）：**
> Methods → Results → Discussion → Introduction → Abstract → Title
>
> 默认在主体证据稳定后定稿 Introduction 和 Abstract；已有草稿、局部修订或作者指定顺序时直接进入对应章节。
>
> 作者可按需要调整顺序（如数据图表已就绪则先写 Results），AI 跟随作者的指定，不强制纠正。但默认按 Core-First 推进。

### 标准模式 (Standard Mode)
适用于：经验丰富的写作者、时间紧张、已有成熟草稿

流程：按 Core-First 写完所有章节→统一核对修改

### 部分手稿模式 (Partial Manuscript)
适用于：写到一半的论文——有的节已完成、有的节部分完成、有的只有占位符或缺失

流程：SP(评估分类每节→生成缺口填补计划)→S4(跳过 Complete 节，增量补充 Partial 节，从零写 Missing/Placeholder 节)→S5+S6+S6.5→S7(梯度风险确认：作者节低风险、AI 节高风险)→…后续标准 pipeline

> **核心原则：** 不动已有内容。Complete 节原样保留；Partial 节只补缺失部分，不重写已有段落。新增内容自动匹配已有 Complete 节的写作风格（术语、句长、引文格式、语域）。

## 子模块说明

| 模块 | 文件 |
|------|------|
| 步进编排器 | `stepping/orchestrator.md` |
| 质量监控 Agent | `stepping/quality_monitor.md` |
| 作者核对清单 | `stepping/review_checklist.md` |
| 文风学习 | `style_learning/` |

## 使用方式

直接使用本 Skill 名称启动。不经过分类器。

```
/pick academic-journal
```

首次启动时告知 AI 写作目标（投稿期刊、主题、已有材料等），由 AI 判断入口点和推荐模式。

## Contribution Gate & CS Conference (P0)

Before body drafting (S4):

1. Confirm 1–3 contributions → `{paper_dir}/.paper/confirmed_contribution.md` (`user_confirmed: true`)
2. Protocol: `../academic-shared/contribution/contribution-gate.md`
3. CS conference / `discipline=stem`: `../academic-shared/conference/cs-conference-path.md` (Draft0 → Method/Results+Takeaway → Final Intro)
4. Keep `.paper/contribution_experiment_map.md` in sync with Results

Routing table: `references/quick-routing.md` (CS conference rows updated).

## LaTeX & Figures (2026-07-27)


When `writingFormat=latex`, load sibling skills:

- `../academic-latex/` — claim-evidence LaTeX writing, verified citations, `verify_paper.py`
- `../academic-plotting/` — figure contracts, data charts vs schematics, journal sizing

Embedded routers under `skills-embedded/` point to these canonical protocols.

## Issues / Rewrite / Citation Bank (P1)

| Artifact | Protocol |
|----------|----------|
| `.paper/issues.csv` | `../academic-shared/issues/issues-contract.md` + `results-backfill.md` |
| `.paper/rewrite_matrix.md` | `../academic-shared/rewrite/rewrite-matrix.md` (S7 major rewrites) |
| `.paper/citation_support_bank.md` | `../academic-shared/citation/citation-support-bank.md` (S2 seed → S6 verify) |

Validate: `python ../academic-shared/issues/validate_issues.py .paper/issues.csv`

## Research Engine Handoff

When `{research_root}/.research/handoff/` exists, S1/S3 **preload** `ready_for_writing.md` (verified evidence + forbidden claims) before inventing a parallel RQ/contribution story. Skill: `../academic-research-engine/`. Sync: `py -3 ../academic-research-engine/scripts/handoff_sync.py --paper-dir {paper_dir}`.


## Evidence and Review Contract

Writing/revision uses [the evidence ledger](../academic-shared/evidence-ledger/ledger-protocol.md): include uncited evidence-requiring claims and internal results; changes invalidate prior support checks.
Use [citation support rules](../academic-shared/citation/citation-support-bank.md) to separate bibliographic verified from source entailment.
Review follows [convergence-loop](static/core/convergence-loop.md): stable feedback is not READY while Critical/Major defects remain. Apply [anti-defensive writing rules](static/core/do-dont.md#避免防御性写作) while retaining material uncertainty.
