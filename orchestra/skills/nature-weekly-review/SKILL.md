---
name: nature-weekly-review
description: "从 Obsidian 每日文献笔记生成讨论驱动的文献周报 HTML。用于文献周报、论文组会汇报或 weekly literature review；普通工作周报不触发。"
---

# Nature Weekly Review

执行范围与授权见 [共享执行规则](../academic-shared/references/execution-policy.md)。

周报中的个人判断来自用户。默认按讨论、提纲、生成三个阶段推进；已提供或确认的观点和提纲直接复用，不要求重复确认。

## 工作流

1. 确定日期范围，默认当前 ISO 周。按 [scan-logic.md](references/scan-logic.md) 扫描每日笔记、去重并聚合；展示总数、均分、中位数、A 类数量、论文摘要和标签。上周快照存在时再比较。
2. 讨论重点论文及跨论文联系，使用 [cross-paper-analysis.md](references/cross-paper-analysis.md) 组织事实和待讨论问题。记录用户观点；未精读项明确标注，不编造批判或研究关联。
3. 以文本列出重点论文、讨论要点、主题、批判与下周计划，取得用户对提纲的确认。用户已经提供获准提纲并要求生成时，直接进入下一步。
4. 按 [weekly-data.md](references/weekly-data.md) 组织数据，使用 [HTML 模板](templates/weekly-report.html) 生成 HTML 与 `data.json`。生成请求不自动授权外发报告。
5. 在浏览器检查数据一致性、图表、表格排序、Obsidian 链接、导航高亮和打印样式。未完成检查如实报告。

默认输入为 `D:/MD ideas/20-机器学习/文献/每日推送/`；输出到 `D:/MD ideas/20-机器学习/文献/每周总结/{ISO年}-W{周:02d}/`。用户指定目录优先。

## 按需参考

| 场景 | 参考 |
|------|------|
| 扫描、解析、聚合 | [scan-logic.md](references/scan-logic.md) |
| JSON 字段与注入 | [weekly-data.md](references/weekly-data.md) |
| 页面结构 | [html-template-spec.md](references/html-template-spec.md) |
| 图表与主题 | [chart-spec.md](references/chart-spec.md)、[themes.md](references/themes.md) |
| 讨论框架 | [cross-paper-analysis.md](references/cross-paper-analysis.md) |
| 空周、单篇、占位符、损坏笔记等 | [edge-cases.md](references/edge-cases.md) |

空周可直接生成空报告；单篇跳过跨论文讨论；研究方向未定时保留“待补充”。
