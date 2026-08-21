# 科研 Skill 快照包

本目录是**本机 `~/.claude/skills/` 科研相关 skill 的快照**（2026-08-20 打包），供协作者在 private 仓库内取用。

## 内容（10 个）

| skill | 用途 | 与 orchestra 关系 |
|---|---|---|
| academic-research-engine | 科研发动机：RQ/实验卡/run 摄入/负结果账本/雷达编排/写作 handoff | **runtime-integrated**：`run_card.py ingest` 三脚本（skills.json 契约） |
| nature-literature-pipeline | arXiv 多源→六维评分→邮件摘要→Zotero+Obsidian 归档 | **distribution-only**（可选 digest）：与 Pi 夜间雷达功能重叠；Zotero 方向 9.8 后设计 |
| nature-reader | 论文全文双语精读（PDF/DOI/arXiv/publisher） | **reference-only**：纯 CC 侧 |
| nature-weekly-review | 周报/组会文献综述 HTML | **reference-only**：纯 CC 侧 |
| academic-latex / academic-plotting | LaTeX 写作 / 学术绘图 | **reference-only**：写作侧 |
| academic-journal / academic-thesis / academic-coursework | 期刊/学位/课程写作辅助 | **reference-only**：写作侧 |
| academic-shared | 共享层；`research/metrics.schema.json` 为 ingest 传递依赖 | **runtime-integrated**：skills.json 必锁定 digest（审查后） |

## 重要：快照与漂移

- 本机原目录 `C:\Users\19041\.claude\skills\` 是**活副本**，会持续演化；仓库内是**快照**，不会自动同步（教训：事实漂移必须显式勘误，见 docs/lessons-learned.md L18）
- 刷新方式：由 owner 重新打包替换，并在本 README 更新快照日期
- `orchestra/config/skills.json` 的 engine digest 已于 2026-08-20 锁定；2026-08-22 新增 required `academic-shared`（`metrics.schema.json`）且 `ingest_run.py` fail-closed，**两处 digest 均须 owner 审查后重新 `--lock-current --strict`**——仓库快照的 digest 仅供参照，**不要用快照的 digest 替代本机校验**

## 扫描声明

打包前已做凭据秘密扫描（API key/token/password 模式），干净。

## 重新锁定流程（2026-08-20 已首次锁定）

- 锁定后 contract_files 任何改动 → `check_skills.py --strict` 显示 `drifted` → `run_card.py ingest` HARD 阻断
- **恢复流程**：审查改动 → 重新执行 `python orchestra/scripts/check_skills.py --lock-current --strict` → 同步本快照目录（快照=上次审查基线，diff 可回答"自上次锁定改了什么"）
- 审查深度与改动成正比：文案微调看 diff 即可；脚本逻辑改动需重过行为面（无网络/无 exec/写入范围/退出码契约）
