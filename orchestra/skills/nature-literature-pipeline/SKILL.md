---
name: nature-literature-pipeline
description: "文献检索、去重、筛选、精读与日报草稿归档。用于文献推送、每日文献或 literature pipeline；发送、外部库写入和定时运行遵循已有明确授权。"
---

# Nature Literature Pipeline

执行范围与授权见 [共享执行规则](../academic-shared/references/execution-policy.md)。

## 项目路由

Research Orchestra 的夜间雷达已于 2026-09-02 冻结，状态见根 AGENTS.md。既有雷达恢复后仍以五维评分为权威。本技能的六维量表仅用于独立精读/归档，不替换雷达排序，也不据此恢复定时任务。Zotero 直连在项目挂账中仍为延期事项。

## 工作流

1. 读取用户已给定的研究方向、关键词、候选数量、TOP N 与输出目录；缺省候选 30、TOP 5。仅配置任务时生成配置，不自动启动定时推送。
2. 检索 arXiv，按需用其他可用学术检索补元数据。按 [dedup-rules.md](references/dedup-rules.md) 去重。
3. 独立精读/归档使用 [scoring-system.md](references/scoring-system.md)，逐维检查上限并重算总分。雷达集成复用项目五维结果，不混合分值。
4. 精读入选论文；需要全文对照读本时调用 `nature-reader`。提取贡献、方法、关键定量结果及表/页来源、作者局限。全文结果提取与短摘要分开，不能为字数限制丢失请求的表格数据。
5. 按 [push-format.md](references/push-format.md) 生成日报草稿，按 [note-template.md](references/note-template.md) 生成 Obsidian 笔记。失败论文记录具体缺失，继续其他论文，不把摘要当作已精读全文。
6. 邮件发送和 Zotero 写入仅在已有明确授权覆盖收件人、库和范围时执行；否则保留可审阅草稿。Zotero 流程见 [zotero-integration.md](references/zotero-integration.md)。

精读可在可用且允许的并发工具中分派独立论文；不锁定 Haiku、5 路并发或 30 秒超时。按实际工具预算安排，保留每篇来源与完成状态。

## 归档契约

- 默认目录：`D:/MD ideas/20-机器学习/文献/每日推送/{YYYY-MM-DD}/`。仅写授权目录；覆盖已有笔记须有明确授权。
- Zotero 若获准接入：查重 → 查 collection → 按需创建 → DOI/元数据新增 → 记录返回的 `zotero_key`。工具以当前实际 schema 为准。
- 邮件和归档分别记录成功/失败；重试前核对是否已经发送/新增，避免重复副作用。
- 定时创建、恢复和验证见 [cron-setup.md](references/cron-setup.md)；手动跑一次不等于授权新增持续调度。

## 参考

- 配置：[config-template.yaml](templates/config-template.yaml)
- 按需汇编：[review-compilation.md](references/review-compilation.md)
