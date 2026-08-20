# Academic Writing — Shared Base

联邦式共享基座，供 `academic-journal`、`academic-thesis`、`academic-coursework` 模块引用。

## 目录

| 目录 | 用途 | 维护者 |
|------|------|--------|
| `skills-embedded/` | 嵌入外部技能的 canonical 副本（38 文件） | 编辑此处的版本，运行 `sync-to-modules.py` 传播到各模块 |
| `static-core/` | pipeline 的 static/core 参考版本 | 仅供对比，各模块保留自己的副本 |
| `evaluate/` | 评估子系统（agents + scripts + configs） | 共享 canonical 副本 |
| `literature/` | 文献工具（literature_search.py, verify_citations.py） | 共享 canonical 副本 |
| `evidence-ledger/` | 证据账本子系统 | 新建 |
| `commands/` | 命令系统（/check-refs, /de-ai, /verify-math, /latex-cleanup） | 新建 |
| `reporting-standards/` | 学科报告规范（CONSORT, STROBE, PRISMA） | 新建 |
| `style_learning/` | 风格学习子系统（共享基础） | 共享 canonical 副本 |
| `references/` | 通用参考文件 | 共享目录 |
| `latex/` | LaTeX 协议索引 → 兄弟 skill `academic-latex/` | 2026-07-27 |
| `plotting/` | 绘图协议索引 → 兄弟 skill `academic-plotting/` | 2026-07-27 |

## 工作流

编辑共享文件 → 运行同步脚本 → 模块获得更新：

```bash
# 同步 skills-embedded 到所有模块
python sync-to-modules.py --component skills-embedded

# 同步 literature 到所有模块
python sync-to-modules.py --component literature
```

## 用户说明书（Obsidian）

联邦总说明（文献·科研发动机·写作·LaTeX/图）放在工作库：

- D:\\MD ideas\\学术技能组说明书.md
- 副本：20-机器学习/、30-工具链/

科研发动机详册：cademic-research-engine/USER-GUIDE.md

## 版本

当前版本: 1.0

变更记录在 `CHANGELOG.md`（待建）。
