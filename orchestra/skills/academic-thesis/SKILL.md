---
name: academic-thesis
description: 学位论文写作辅助：开题建议、文献综述、方法设计、草稿撰写、多维度评审、修改建议、格式排版与答辩准备。适用于本科/硕士学位论文 — 不替代学生完成可直接提交的终稿。
---

# Academic Thesis — 学位论文撰写模块

独立完整的学位论文撰写模块，可从用户指令直接调用。

## 能力范围

适合以下场景：
- **本科毕业论文**（学士）
- **硕士毕业论文**（学硕/专硕）

## 两种模式

| 模式 | 适用 | 流程 |
|------|------|------|
| 本科模式 | 本科毕业论文 | T1(开题)→T2(综述)→T3(方法)→T4(写作)→T5(评估)→T6(修改)→T7(答辩) |
| 硕士模式 | 硕士毕业论文 | T1(开题)→T2(综述)→T3(方法)→T4(写作)→T5(评估)→T6(修改)→T6.5(盲审)→T7(答辩) |

## 核心能力

- **完整 pipeline**: 开题 → 文献综述 → 研究方法 → 写作 → evaluate 评审 → 修改收敛 → 答辩准备
- **evaluate 评审**: 多维度 AI + 人工审稿人模拟（学术不端检测、内容审查、方法学审查等）
- **注水功能** (inflate): T6 收敛后启动 `scripts/inflate_paper.py`，按学位分档目标字数膨胀
- **文风学习**: 通过 `style_learning/` 子模块学习目标学位论文的文风特征
- **断点续写**: 通过 `checkpoint/state_manager.py` 手动按需保存和恢复写作进度（T4 阶段段落级 checkpoint，非自动）
- **术语表**: 通用 pipeline 概念见 `../academic-shared/GLOSSARY.md`

## 与独立技能的关系

本模块包含以下嵌入技能支持：

| 嵌入技能 | 用途 | 关联阶段 |
|---------|------|---------|
| `skills-embedded/latex-thesis-zh.md` | 中文 LaTeX 版式 / GB/T | T4 |
| `skills-embedded/latex-paper-en.md` | → `../academic-latex` 主张-证据与 verify_paper | T4, T7 |
| `skills-embedded/nature-figure.md` / `scientific-visualization.md` | → `../academic-plotting` 数据图 | T1.5, T4 |
| `skills-embedded/scientific-schematics.md` | → `../academic-plotting` 示意图 | T2 |
| `skills-embedded/scientific-slides.md` | 答辩 PPT | T7 |
| `skills-embedded/pptx.md` | PowerPoint 幻灯片生成 | T7 |
| `skills-embedded/docx.md` | python-docx 参考 | T4 |
| `skills-embedded/pdf.md` | PDF 元数据清理 | T6.5 |
| `skills-embedded/scientific-brainstorming.md` | 选题头脑风暴 | T1 |

## 快速开始

```
/academic-thesis 帮我写一篇本科毕业论文，题目是...
/academic-thesis 我要写硕士论文，方向是...
```

> **注意**: 本模块是独立技能，可直接调用。

## Research Engine Handoff

若研究根目录存在 `.research/handoff/`，T1 优先加载 `ready_for_writing.md`（仅 verified 证据 + 禁止硬撑 claim），再开题贡献闸。详见 `../academic-research-engine/`。


## 文件结构

| 文件/目录 | 用途 |
|----------|------|
| `SKILL.md` | 本文件 — 模块入口 |
| `manifest.yaml` | 声明式加载清单 — 定义 stages、axes、references |
| `strategists/` | T1-T7 各阶段详细指令 |
| `static/core/` | 22 个核心规则文件（pipeline 常设规则） |
| `references/` | 条件加载的参考资料（学位论文专用） |
| `evaluate/` | 完整评审子系统（agent 提示词 + 评分脚本 + 校准配置） |
| `scripts/` | 工具脚本（注水、词汇多样性、格式模板等） |
| `skills-embedded/` | 嵌入的独立技能冻结版本 |
| `style_learning/` | 文风学习子系统 |
| `checkpoint/` | 断点续写状态管理器 |

## 断点续写 (T4 阶段)

本模块支持 T4 写作阶段的段落级断点续写：

**支持粒度：**
- 段落/步骤级状态快照
- 每步完成后手动保存到 `.checkpoint/{paper_slug}/state.json`

**触发方式：**
- 手动检测：输入 `/resume` 命令检查未完成项目
- 提示恢复：检测到 checkpoint 文件后询问是否继续

**工具：** `checkpoint/state_manager.py` 提供状态管理 API（手动按需调用，非自动）

## Contribution Gate (P0)

- T1 must produce `.paper/confirmed_contribution.md` with user confirmation (创新点 1–3)
- Protocol: `../academic-shared/contribution/contribution-gate.md`
- T4: Results/empirical chapters need Takeaways + `contribution_experiment_map.md`; rewrite 绪论 after core evidence
- See `references/quick-routing.md` P0 section

## LaTeX & Figures


- Layout/GB/T: `skills-embedded/latex-thesis-zh.md`
- Claim-evidence / citations / verify_paper: `skills-embedded/latex-paper-en.md` -> `../academic-latex/` (Chinese theses: pass --allow-cjk)
- Figures: routers -> `../academic-plotting/`

### Path convention

| From | Use |
|------|-----|
| Module root (`SKILL.md`, `manifest.yaml`) | `../academic-latex`, `../academic-plotting` |
| `skills-embedded/*.md` | `../../academic-latex`, `../../academic-plotting` |

Never use `../academic-latex` from inside `skills-embedded/` — that path does not exist.

## Issues / Rewrite / Citation Bank (P1)

- T2: seed `citation_support_bank.md`
- T4: `issues.csv` + results-backfill for empirical chapters
- T6: `rewrite_matrix.md` for major 修订
- Protocols under `../academic-shared/issues|rewrite|citation/`
