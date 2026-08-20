# 科研 Skill 组 × Research Orchestra 兼容度分析（mission 033）

- 日期：2026-08-20 · 范围：orchestra/skills/ 快照 10 个 skill vs 系统（雷达/实验管线/Skill 契约）
- 方法：全量读 10 个 SKILL.md（academic-shared 无 SKILL.md，以 README 代替）、skills.json、run_card.py ingest、executor.py 模式前缀、四阶段雷达模板、SOL 终审报告；`diff -rq` 快照 vs `~/.claude/skills` 活副本

## 1. 功能重叠点

### 1.1 nature-literature-pipeline vs 夜间雷达（高度重叠，雷达为权威）

| 环节 | 雷达（Pi 侧，mission 023 已上线） | pipeline（CC 侧，未集成） |
|---|---|---|
| 调度 | systemd timer 23:30，inject_daily 幂等注入四阶段（README.md:53） | CronCreate 08:30，**进程本地**，会话须运行（SKILL.md:148） |
| 抓取 | arXiv API cs.CL+cs.LG 各 30 篇（fetch 模板:18-21） | arXiv primary + Semantic Scholar 补充（SKILL.md:16） |
| 去重 | 仅 arXiv ID 合并（fetch 模板:22-23） | DOI→arXiv ID→归一化标题三重 + Zotero/_dedup_index.json 交叉（SKILL.md:18-19） |
| 评分 | 五维 0-40/25/20/15/10，`total`=前四维之和；**明令声望/引用/来源不进总分**（rank 模板:28-34） | 六维 0-35/20/15/10/10/10 百分制，**含 Source Quality（venue/citations 声望）**（scoring-system.md:11） |
| 精读 | 无（摘要级） | 5×Haiku 并行 PDF 精读、逐表数字（SKILL.md:24-27,44-62） |
| 邮件 | shell radar_notify.py，at-most-once 状态机（README.md:56） | mcp__email__send_email（SKILL.md:29） |
| 归档 | 无 | Zotero + Obsidian 笔记（SKILL.md:31-33,89-114） |
| 质量门 | validator + SHA-256 闭环 + 确定性 render（README.md:54-56） | 内置 safeguards（score 校验/去重/只写目录） |

**裁决**：抓取/评分/邮件三环节重叠且雷达更强（validator、确定性、at-most-once、已运行）→ **以雷达为准**。pipeline 的独有增量 = PDF 精读 + Zotero/Obsidian 归档，正是 9.8"雷达→Zotero 直连"要补的两块。评分维度冲突（声望）融合时以雷达五维为基，pipeline 六维中的 Source Quality 弃用或降为仅记录。

### 1.2 academic-research-engine 的"雷达/实验编排" vs orchestra

- 引擎自身定位即"orchestrate, do not rebuild"（radar-routing.md:1）：ingest→pipeline、weekly→weekly-review、directed_search→academic-shared/literature_search.py，**明确禁止重造** scoring/邮件/Zotero（radar-routing.md:42）
- 引擎 `.research/radar/` 是 CC 侧 watchlist/inbox **指针层**；Pi 雷达是产物层。衔接点：雷达 digest → 人读 → 引擎 inbox 登记，无冲突
- 实验管线无重叠：orchestra 提供执行面（卡→Broker→metrics.json，README.md:62-63），引擎提供登记面（ingest 入账→handoff 写作）。重叠的"实验卡"产物反而正是两者的**连接件**（见 §3）

## 2. 互补点（纯 CC 侧，orchestra 零重叠，直接用）

| Skill | 能力 | 与系统关系 |
|---|---|---|
| nature-reader | 全文中英对照精读（雷达只有摘要级） | 雷达 top5 的后续深挖，天然衔接 |
| nature-weekly-review | 讨论驱动周报（禁代判） | 雷达日报的周聚合，天然衔接 |
| academic-latex / plotting | 写作+绘图 | 无任何重叠 |
| academic-journal / thesis / coursework | 三种写作管线 | 无重叠；消费引擎 handoff 产物（journal SKILL.md:96-98） |
| academic-shared | 共享协议（gate-chain/ledger/issues/citation） | 无重叠；被其余 9 个 skill 以 `../academic-shared/` 相对路径引用 |

## 3. 强耦合点

### 3.1 run_card ingest → engine 三脚本（唯一硬接线）

- `run_card.py:169-196` `resolve_ingest_engine`：manifest 严格校验 → `required=true` + `used_by` 声明 → `inspect_skill` 状态必须 `ok`，否则 HARD/exit 2（README.md:49）
- `run_card.py:250-274`：subprocess 调 `validate_experiment_card.py` + `ingest_run.py`，**只调用不改动**（README.md:64）
- 契约文件核对（skills.json:17-22,38-40 vs 快照/活副本）：academic-research-engine 4 个 contract_files、pipeline 1 个，**全部存在且路径一致** ✓

### 3.2 digest 门禁现状（阻断中）

| 项 | 值 | 后果 |
|---|---|---|
| `expected_digest` | 两 skill 均 `null`（skills.json:23,41） | `inspect_skill` → `unlocked`（check_skills.py:165-167） |
| required 门禁 | `unlocked` 视为失败（check_skills.py:179-181） | **真实 ingest 当前 HARD 阻断**（与 CLAUDE.md 挂账一致） |
| 前置条件 | 活副本已装且入口完整（本机实测存在） | 唯一缺口就是锁：`check_skills.py --lock-current --strict` |

**注意**：skills.json `path` 指活副本 `~/.claude/skills/`，快照 `orchestra/skills/` 只是仓库参照，digest 门禁不检查快照——锁定只保护活副本。

## 4. 风格冲突风险

| 风险点 | 证据 | 判定 |
|---|---|---|
| executor 模式前缀 vs skill 内部约束 | executor.py:16-46 统一注入 mode/detail；pipeline 精读 prompt 自定 <400 词/四段格式（SKILL.md:58-62） | **不冲突**：作用面不同（Pi headless vs CC 会话），无重复堆叠 |
| 交互型 skill 进 dsh | weekly-review 依赖 AskUserQuestion/纯文本提纲/用户逐节确认（SKILL.md:233,263-267） | **冲突**：headless 无交互 UI，weekly-review 不可直接编排为 dsh 任务；只可 CC 侧对话执行 |
| 模型硬编码 | pipeline 精读硬编码 `subagent_type="haiku"`（SKILL.md:44-62） | **轻度冲突**：绕过 029 路由表（README.md:84-89）。haiku 恰为低成本默认档，实际无害，但建议记为"精读默认档"而非硬编码 |

## 5. 漂移风险

| 面 | 现状 | 风险 |
|---|---|---|
| 快照 vs 活副本（10 目录 diff） | **零漂移**（仅 `__pycache__`） | 当前健康；但快照无自动同步机制（academic-shared 的 sync-to-modules.py 只服务其内部），需人工维护 |
| 活副本被 ingest 调用版本 | 未锁定 → 无防护 | 锁定后任何改动即 `drifted`→HARD，版本一致性由门禁兜底（check_skills.py:168-169） |

## 6. 集成建议（按 9.8 时间线）

| 优先级 | 事项 | 动作 |
|---|---|---|
| P0（立即） | digest 锁定 | 活副本已就绪，直接 `python orchestra/scripts/check_skills.py --lock-current --strict`，解除 ingest HARD 阻断 |
| P0（立即） | 快照同步纪律 | 每次更新活副本后同步 orchestra/skills/ 快照并 re-lock（可挂 housekeeping 检查） |
| P1（9.8） | 雷达→Zotero | 复用 pipeline `references/zotero-integration.md` 协议；Pi 侧无 MCP，改走 `academic-shared/skills-embedded/pyzotero.md` 的 pyzotero 直连，或 CC 侧以 pipeline 归档 digest top5（二选一，建议前者——数据在 Pi） |
| P1 | 精读衔接 | 雷达 top5 → nature-reader 精读（CC 侧），回填 weekly-review 讨论，闭环 |
| P1 | 重叠裁决固化 | 评分以雷达五维为唯一权威，pipeline 六维（含声望）仅作归档元数据；邮件以雷达 notify 为准，pipeline 的 mcp email 弃用 |
| P2 | 编排边界 | 引擎 radar-routing 维持"编排不重造"；交互型 skill（weekly-review）不设计进 dsh 模板 |

## 7. 结论

- 核心强耦合（ingest→engine 三脚本）契约文件完整、活副本健康，**唯一阻断是 digest 未锁定**，一步可解
- 最大重叠在 pipeline vs 雷达的"抓取/评分/邮件"，裁决为雷达权威 + pipeline 保留精读/归档增量，与既有 9.8 计划方向一致
- 风格冲突仅两处且均为轻度（交互型 skill 不进 dsh、haiku 硬编码记入路由表）
- 快照/活副本当前零漂移，锁定后系统侧漂移防护闭环，剩余为快照人工同步纪律
