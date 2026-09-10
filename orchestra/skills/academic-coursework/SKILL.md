---
name: academic-coursework
description: 课程论文写作辅助：选题建议、文献检索、大纲梳理、草稿撰写、批改润色、格式排版。不替代用户完成可直接提交的终稿。Use when you say "帮我写大作业" / "课程论文" / "结课作业" / "course assignment" — delivers structured writing assistance, not one-click submission-ready output.
---

# Academic Coursework — 课程论文写作辅助

执行范围与授权见 [共享执行规则](../academic-shared/references/execution-policy.md)。

提供中文课程论文的选题、文献检索、草稿、评审和排版。完整草稿仍需用户核实与完成作者责任，不自动成为可直接提交的终稿。

## 模式与入口

| 模式 | 流程 |
|------|------|
| 全自动草稿 | 用户要求完整草稿时，读取 [auto_mode/orchestrator.md](auto_mode/orchestrator.md)，执行 C1-PRE → C1 → C2 → C3 → C4 → C5；常规选择与修订不反复确认 |
| 半自动 | 用户要求逐步指导时，读取当前 `strategists/C*-strategist.md`，沿 C1–C5 在约定阶段交付并等待反馈 |
| 已有草稿 | 按请求直接进入 C3 补写或 C4 审查，不重做已完成的选题和检索 |

阶段与质量门禁由 [manifest.yaml](manifest.yaml) 及当前 strategist 定义。C1 选题论点、C2 文献核验、C3 草稿生成、C4 多维评审、C5 修订收敛；最多三轮修订后仍有问题则报告未决项。

## 输出与依赖

- 默认中文 Word `.docx` 草稿与质量报告。生成 Word 时检查 Python 与 python-docx；用当前可用搜索/浏览器检索，不把某个检索服务或模型当作必备依赖。
- 字数扩写和语言润色属于用户明确要求的可选分支，才加载 `strategists/C5.5-strategist.md`；不因“提交版”等含糊词自动执行。不承诺降低检测率，不修改证据与引用以迎合评分。
- 需要 LaTeX 才设置 `writingFormat=latex` 并加载 [academic-latex](../academic-latex/SKILL.md)；学术图表加载 [academic-plotting](../academic-plotting/SKILL.md)。
- 本模块没有自动断点恢复。长任务中断前记录阶段、草稿路径、已核验文献与未决项；恢复时据产物继续，不宣称有自动 checkpoint。

## 按需共享协议

- 声称创新或实证结果：[contribution-gate.md](../academic-shared/contribution/contribution-gate.md)，C3 前准备 `.paper/confirmed_contribution.md`。
- 需要证据跟踪：[issues-contract.md](../academic-shared/issues/issues-contract.md)、[citation-support-bank.md](../academic-shared/citation/citation-support-bank.md)。
- 语言、格式和引用细则：根据 manifest 只加载当前阶段所需 references；脚本与嵌入技能保留原路径。
