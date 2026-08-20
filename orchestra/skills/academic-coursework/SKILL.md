---
name: academic-coursework
description: 课程论文写作辅助：选题建议、文献检索、大纲梳理、草稿撰写、批改润色、格式排版。不替代用户完成可直接提交的终稿。Use when you say "帮我写大作业" / "课程论文" / "结课作业" / "course assignment" — delivers structured writing assistance, not one-click submission-ready output.
---

# Academic Coursework — 大作业全自动/半自动写作

This skill generates complete course papers (课程论文/大作业) in two modes:

| Mode | Description |
|------|------------|
| **全自动模式 (Auto Mode)** | One-command: topic input -> complete .docx output. Auto-generates literature search, full draft, review, and revision. |
| **半自动模式 (Semi-Auto Mode)** | Step-by-step guidance through C1-C5 stages with user checkpoints at each gate. Full control over every decision. |

Both modes support the **C5.5 padding workflow** (注水/降AI) as a post-convergence hidden branch.

> **Language note:** The Course-Assignment pipeline is Chinese-only. All stages assume Chinese-language output (宋体/黑体 .docx, CNKI search, Chinese AI-tone detection).

## 工作流程

```
                  ┌──────────────────────────────────────┐
                  │    What do you want to write?         │
                  │    大作业 / 课程论文 / 结课作业        │
                  └──────────────────┬───────────────────┘
                                     │
                         ┌───────────┴───────────┐
                         │    Choose your mode    │
                         └───────────┬───────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
   │   全自动模式      │    │   半自动模式      │    │    注水隐藏分支   │
   │   Auto Mode      │    │   Semi-Auto Mode  │    │   C5.5 (触发式)  │
   │   C1→C5→交付     │    │   C1→C2→...→C5   │    │   AIGC padding   │
   └──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 全自动模式 (Auto Mode)

**One command: provide a topic, get a complete paper.**

When user says "帮我写一篇关于X的大作业" or anything that suggests full automation:

1. Load `auto_mode/orchestrator.md` for the auto orchestration protocol
2. Run C1-PRE (reference availability check) -> C1 (topic/arguments) -> C2 (lit search) -> C3 (write draft) -> C4 (auto review) -> C5 (auto fix) in sequence
3. Auto triggers: topic brainstorming (no user confirmation needed), literature search (automated), draft writing (one-pass), review (auto check), revision (auto fix)
4. Deliver final .docx + quality report

**Auto decisions:** Topic selection, argument structure, literature prioritization, and revision strategy are all determined by the auto-orchestrator based on built-in quality checks. The user only needs to provide the initial topic.

**Checkpoints (all optional, user can override):**
- Before C3 writing: "Here's the topic and references. Write now?"
- After C5 convergence: "Paper ready at {path}. Run padding (注水)?"

### 半自动模式 (Semi-Auto Mode)

**Step-by-step: user confirms at each gate.**

1. Load `strategists/C1-strategist.md` ... C2 ... C3 ... C4 ... C5
2. At each STAGE gate, present results and ask for confirmation
3. User can intervene at any point: adjust topic, override literature selection, edit draft, accept/reject review findings, guide revision direction

**User checkpoints:**
- C1: topic + argument selection (user picks from 2-3 candidates)
- C2: bibliography review (user confirms reference pool)
- C3: draft review (user edits .docx before gate)
- C4: review results (user reviews issue list)
- C5: convergence (user accepts or requests more revisions)
- C5.5: padding trigger (user decides yes/no)

### 注水隐藏分支 (C5.5 Padding)

Both modes support the post-convergence padding workflow. Triggered when user mentions 注水/降AI/查重/AIGC/提交版 after C5 convergence. See `strategists/C5.5-strategist.md`.

## Prerequisites

| Requirement | Purpose | Auto Mode | Semi-Auto Mode |
|-------------|---------|-----------|----------------|
| Python 3.8+ | python-docx for .docx generation | Required | Required |
| `pip install python-docx` | .docx writing + reading | Required | Required |
| Tavily API key | Web context search (C2E) | Recommended (falls back to browser) | Recommended |
| Playwright MCP | CNKI/Wanfang Chinese search (C2D) | Recommended | Optional |
| DeepSeek Chat access | Web context fallback (C2E) | Optional | Optional |

**Python-docx check:**
```bash
python -c "from docx import Document; print('python-docx available')"
```

## Pipeline Stages

| Stage | Name | Gate | Description |
|-------|------|------|-------------|
| C1 | Topic & Arguments | QC1 (BLOCK) | Select topic (auto or guided), define 3+ arguments |
| C2 | Literature Search | QC2 (BLOCK) | Multi-agent parallel search, quality matrix, snowballing |
| C3 | Write Draft | QC3 (BLOCK) | One-pass .docx generation via python-docx script |
| C4 | Review | QC4 (BLOCK) | 6-dimension auto review (content, structure, AI-tone, format, logic, facts) |
| C5 | Revision & Convergence | QC5 (BLOCK) | Fix -> re-review loop (max 3 rounds) |
| C5.5 | Padding (hidden) | QC5.5 (COND. BLOCK) | Post-convergence AIGC padding/de-AI (keyword-triggered) |

## 常见疑问

**Q: 全自动模式和半自动模式有什么区别？**
A: 全自动模式一次生成完整论文，不打断用户。半自动模式在每一步都让用户确认和调整。全自动适合时间紧、对质量要求不高的场景；半自动适合有特定要求的课程论文。

**Q: 注水是什么意思？**
A: 指在论文完成后，通过规则层变换 + LLM 层改写来增加字数、降低 AI 检测率。是一个可选的后处理步骤，不影响质量评分。详见 `strategists/C5.5-strategist.md`。

**Q: 可以自己上传已有草稿吗？**
A: 可以。启动后选择"从已有内容继续"，直接进入 C3（撰写阶段）或 C4（审查阶段）。全自动模式会自动读取并分析你的草稿。

## 文件说明

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 本文件 — 入口描述 |
| `manifest.yaml` | 声明式加载配置 |
| `strategists/` | 6 个 strategist 文件 (C1-C5, C5.5) |
| `static/core/` | 核心规则（22 文件） |
| `auto_mode/` | 全自动模式编排器 + 自动质量检查 |
| `references/` | 按需加载参考（中文 De-AI、浏览器自动化等） |
| `scripts/` | Python 脚本（注水、词汇多样性等） |
| `skills-embedded/` | 嵌入技能快照 |

## 断点续写（未实现）

本模块的断点续写功能尚未实现。当前全自动模式下不可中断恢复，请一次性完成流水线。

## LaTeX / figures (optional)

Default coursework output remains **Word (.docx)**. When the user asks for LaTeX:

- Set `writingFormat=latex` → C3 loads `skills-embedded/latex-paper-en.md` → `../academic-latex/`
- Figures: `nature-figure` / `scientific-visualization` / `scientific-schematics` → `../academic-plotting/`
- Smoke: `../academic-shared/SMOKE-LATEX-PLOTTING.md`

## Contribution gate (optional but recommended)

For graded coursework that claims "创新" or empirical results, reuse:

- `../academic-shared/contribution/contribution-gate.md`
- `.paper/confirmed_contribution.md` before C3 body generation

## P1 (optional for empirical coursework)

Reuse `.paper/issues.csv` + citation_support_bank when the assignment needs evidence tracking:
`../academic-shared/issues/issues-contract.md`, `../academic-shared/citation/citation-support-bank.md`.
