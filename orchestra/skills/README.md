# 科研 Skill 快照包

本目录是**本机 `~/.claude/skills/` 科研相关 skill 的快照**（2026-08-20 打包），供协作者在 private 仓库内取用。

## 内容（10 个）

| skill | 用途 | 与 orchestra 关系 |
|---|---|---|
| academic-research-engine | 科研发动机：RQ/实验卡/run 摄入/负结果账本/雷达编排/写作 handoff | **强耦合**：`run_card.py ingest` 的 engine 三脚本来自它（skills.json 契约） |
| nature-literature-pipeline | arXiv 多源→六维评分→邮件摘要→Zotero+Obsidian 归档 | **功能重叠**：orchestra 夜间雷达是 Pi 侧自动化实现；本 skill 是 CC 侧交互实现，且带 Zotero 归档（雷达→Zotero 方向 9.8 后设计） |
| nature-reader | 论文全文双语精读（PDF/DOI/arXiv/publisher） | 互补：纯 CC 侧 |
| nature-weekly-review | 周报/组会文献综述 HTML | 互补：纯 CC 侧 |
| academic-latex / academic-plotting | LaTeX 写作 / 学术绘图 | 互补：写作侧 |
| academic-journal / academic-thesis / academic-coursework | 期刊/学位/课程写作辅助 | 互补：写作侧 |
| academic-shared | 共享文献检索等公共层 | 被 engine/pipeline 依赖 |

## 重要：快照与漂移

- 本机原目录 `C:\Users\19041\.claude\skills\` 是**活副本**，会持续演化；仓库内是**快照**，不会自动同步（教训：事实漂移必须显式勘误，见 docs/lessons-learned.md L18）
- 刷新方式：由 owner 重新打包替换，并在本 README 更新快照日期
- `orchestra/config/skills.json` 的 `expected_digest` 目前为 null（unlocked 状态）；**锁定动作（`--lock-current --strict`）由 owner 审查后自行执行**，不要用仓库快照的 digest 替代本机校验

## 扫描声明

打包前已做凭据秘密扫描（API key/token/password 模式），干净。
