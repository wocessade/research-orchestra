# Subsystem 2: 实验管线闭环（engine × dsh）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 academic-research-engine 的实验卡接入 Broker 执行层，跑通「实验卡 → CC 审查 → Broker 入队 → dsh/shell 无头执行 → metrics.json → ingest_run.py 入账 → CC 复查」闭环；验收形式为对照实验（同一抽取任务：单次 LLM 调用 vs dsh 多步 agent），两臂数字全部经 ingest 入账、无手抄。

**Architecture:** 卡是接口、执行是可替换实现。卡新增 `## Commands` 段（fenced bash block，无头可执行）；engine 三脚本（validate/ingest/handoff）**零改动**，仅作消费端。执行在 Broker（shell 或 dsh executor），入账在 Windows（`run_card.py` 胶水调 engine 脚本，因 `.research` 在控制面）。demo 研究根隔离在 `orchestra/demo/.research/`，不污染未来真实研究根。

**Tech Stack:** Python 3.11 stdlib only（run_card.py）、engine 三脚本（既有）、dsh 0.1.0-rc.7（4B 已有）、Broker（既有，零改动）、unittest、Git Bash。

## 接口约定（本 spec 的核心产出）

### A. 实验卡 `## Commands` 段约定

- 卡体新增 `## Commands` 段，格式：该标题下若干个 fenced block（```bash 或 ```），每行一条 shell 命令，block 内按顺序逐条执行。
- **臂标记**：block 紧邻前一行可为 `# arm: <id>` 注释（id 为 kebab-case）；无标记 block = 全部臂共享（执行时排在最前）。单臂实验可全无标记。`run_card.py commands --arm <id>` 输出 = 共享块 + 该臂块。
- **无头可执行**：无交互提示、无 GUI、无人工输入；前一条命令非零退出 → 该 run 失败（fail-fast）。
- **数值只来自 run artifact（engine 硬规则）**：命令必须把可量化指标写入文件；run 的最后一条命令必须产出 `$OUTDIR/metrics.json`，其内容须符合 `academic-shared/research/metrics.schema.json`（必填：`run_id`、`exp_id`、`status`、`metrics`）。
- `OUTDIR` 为执行器指定的输出目录：dsh 执行器由 Broker prompt 注入（既有机制）；shell 执行器的任务 body 用绝对路径或任务自身 result 目录。卡内命令用相对路径，任务执行体负责 `cd` 到部署目录。
- **无 `## Commands` 段的卡 = 人工执行卡**（向后兼容）；engine validator 不检查该段（已验证三脚本不碰），加段不破坏校验。

### B. 执行器与责任分界

| 环节 | 谁做 | 产出 |
|---|---|---|
| 卡生成/审查 | CC（人在环） | card.md 合法（engine validate 通过） |
| 任务文件生成 | CC 用 `run_card.py commands` 提取 Commands 段 + 模板填充 | tasks/T-*.md |
| 无头执行 | Broker（shell 单次调用 / dsh 多步） | results/T-*/metrics.json + attempt-N 日志 |
| 入账 | Windows `run_card.py ingest` | 卡 Run log 行 + runs/<run_id>/metrics.json |
| 复查 | CC 写 reports/，数字只引用 ingest artifact 路径 | reviewed: ok/reject |

### C. `run_card.py` 接口（orchestra/scripts/，stdlib only）

- `run_card.py commands <card.md> [--arm <id>]` → 提取并打印 Commands 段内容（共享块 + 指定臂块；无 `--arm` 时列出全部臂 id；CC 生成任务文件用）
- `run_card.py ingest <metrics.json> --card <card.md> [--research-root .research] [--engine-dir ~/.claude/skills/academic-research-engine] [--paper-dir ...] [--open-neg-on-fail]`
  1. 解析 card FM 的 `id`（EXP-xxx）与 metrics.json 的 `exp_id`，不一致 → HARD exit 2（防错卡入账）
  2. 调 engine `validate_experiment_card.py`（card 不合法 → HARD）
  3. 调 engine `ingest_run.py`（engine 自己校验 metrics schema + 写卡 Run log + runs/ 副本 + 可选 paper 更新）
  4. 退出码透传；打印 `OK: ingested <run_id> → <exp_id>`

## Global Constraints

- **engine 三脚本与模板零改动**（验收时 git diff 验证 skills 目录无变化——本仓库内无 engine 文件，约束为：任何新脚本不得修改/包裹 engine 行为，只能以子进程调用）
- demo 研究根 `orchestra/demo/.research/`（隔离；真实研究根待用户研究方向确定后另建，不得在本 mission 创建仓库根 `.research/`）
- `program.yaml` compute mode 保持 `human_in_loop`（demo 根放一份）
- run_card.py 零 pip 依赖；测试用 `unittest`；Windows 侧命令在 Git Bash 运行
- commit 不加 Co-Authored-By；密钥不入 git（Pi 侧脚本用系统环境变量 DEEPSEEK_API_KEY——env.conf 已有）
- 不动 Broker 代码（dsh prompt 注入 outdir 既有机制够用；若有缺口记录 reports/ 不修改 broker）
- 不动核桃派 usage-monitor；模型切换（flash/pro）与 handoff_sync 接入均为本 mission out of scope

---

### Task 1: 细化 spec 文档（本文档）

**Files:** `docs/superpowers/plans/2026-08-19-subsystem-2-experiment-loop.md`

**Interfaces:** Consumes 总 spec §6.2；Produces 上文接口约定 A/B/C（Task 2-5 的依据）

- [ ] **Step 1: 完成**（coordinator 已写，随任务推进按需修订）

### Task 2: run_card.py 胶水脚本（TDD）

**Files:**
- Create: `D:\pythonProject\orchestra\scripts\run_card.py`
- Test: `D:\pythonProject\orchestra\scripts\tests\test_run_card.py`

**Interfaces:**
- Consumes: 约定 A/C；engine 脚本路径（`--engine-dir`，默认 `Path.home()/".claude/skills/academic-research-engine"`）
- Produces:
  - `extract_commands(text: str, arm: str | None) -> str`（返回 Commands 段内容：无 `--arm` 时列出臂 id（一行一个，无臂块则原样输出共享块）；指定 arm 时输出共享块 + 该臂块；无 Commands 段返回 ""）
  - `parse_card_id(text: str) -> str`（FM `id`，无则 raise）
  - `subcommands: commands|ingest`（`ingest` 按约定 C 三步执行，engine 调用用 `[sys.executable, engine_script, ...]` 子进程）

- [ ] **Step 1: 写失败测试**（覆盖：extract 无 Commands 段、单块无臂、共享块+两臂块、--arm 过滤、未知臂报错；parse_card_id；ingest 的 exp_id 不匹配 HARD、engine validate 失败 HARD、ingest 成功路径 mock 子进程）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 写实现**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit** `feat: run_card.py - experiment card commands extractor and ingest glue`

### Task 3: demo 研究根 + EXP-001 对照实验卡

**Files:**
- Create: `D:\pythonProject\orchestra\demo\.research\program.yaml`（`compute_budget.mode: human_in_loop`）
- Create: `D:\pythonProject\orchestra\demo\.research\experiments\EXP-001\card.md`
- Create: `D:\pythonProject\orchestra\demo\material\extract_text.txt`（抽取素材，固定文本）
- Create: `D:\pythonProject\orchestra\demo\material\gold.json`（金标准字段，判定依据）
- Create: `D:\pythonProject\orchestra\demo\score.py`（共享评分脚本，stdlib only，两臂共用保证对照公平）
- Create: `D:\pythonProject\orchestra\demo\extract_single.py`（ctl 臂：单次 LLM 调用抽取，stdlib only）

**Interfaces:**
- Consumes: 约定 A；engine 卡模板
- Produces: 通过 engine validate 的 EXP-001 卡（FM: id/hypothesis_ids [H-001]/status designed/compute_budget kind none；body: Design/Success/Failure criteria + `## Commands` 段含 ctl/trt 两个臂块）；`score.py --gold <g> --result <r> --exp-id <e> [--run-id <id>] --out <metrics.json>`（缺省 run-id 用 `run-YYYYMMDD-HHMMSS`；result.json 格式 `{"fields": {"<字段名>": "<抽取值>"}}`，与 gold.json 逐字段精确比对，产出合规 metrics.json：run_id/exp_id/status=completed/metrics={fields_total, fields_correct, accuracy}）；`extract_single.py --text <t> --out <result.json>`（读 DEEPSEEK_API_KEY 环境变量，POST api.deepseek.com/chat/completions，model deepseek-chat，temperature 0，prompt 要求输出严格 JSON）

- [ ] **Step 1: 设计抽取任务**：固定文本（≥3 个字段：如实体、数值、关系各若干），gold.json 给出标准答案；字段名与 result.json 格式在 score.py 注释中写明（两臂共用同一评分函数，保证对照公平）
- [ ] **Step 2: 写 score.py 与 extract_single.py**（stdlib；score.py 无 API 依赖，可在 Windows 本地用假 result.json 自测）
- [ ] **Step 3: 写卡**（卡中 Commands 段：`# arm: ctl` 块 = extract_single + score 两命令；`# arm: trt` 块 = 仅 score 命令（多步抽取由 dsh 执行器在评分前完成并写 result.json）；Success/Failure criteria 冻结：**管线 demo，criteria 以"两臂均可产出合规 metrics.json 并入账"为准**，不设虚假科研结论）
- [ ] **Step 4: engine validate 验证**：`py -3 C:\Users\19041\.claude\skills\academic-research-engine\scripts\validate_experiment_card.py <card>` → OK；score.py 本地自测（假 result 对 gold 出 100% 与 0% 各一例）
- [ ] **Step 5: Commit** `feat: demo EXP-001 card - LLM extraction executor comparison`

### Task 4: 两臂任务文件生成并推送 Broker

**Files:**
- Create: `D:\pythonProject\orchestra\tasks\T-<date>-ctl-single.md`（shell，单次 LLM 调用）
- Create: `D:\pythonProject\orchestra\tasks\T-<date>-trt-dsh.md`（dsh 多步 agent）

**Interfaces:**
- Consumes: `run_card.py commands`（Task 2）；demo 素材（Task 3）
- Produces: 两个合法任务文件（严格格式：executor/net/result/---）；推送后 4B Broker 入队

- [ ] **Step 1: 生成 ctl（shell）任务**：body = `cd /mnt/broker/demo && ` + `run_card.py commands --arm ctl` 输出（extract_single + score 两命令；run-id 用 score.py 缺省时间戳生成，不传 --run-id）；`net: required`；result 目录用任务自身 slug
- [ ] **Step 2: 生成 trt（dsh）任务**：body = 「cd /mnt/broker/demo；读取 extract_text.txt 与 gold.json → 多步抽取（先规划字段、再逐字段抽取、最后核对 gold 格式）→ 写 result.json → 执行 `run_card.py commands --arm trt` 的输出命令（score.py）→ metrics.json 写入指定输出目录」；prompt 明确：metrics.json 必须含 run_id/exp_id/status/metrics 四键；`executor: dsh`、`net: required`
- [ ] **Step 3: demo 目录上传 4B**（scp orchestra/demo/{extract_single.py,score.py,material/} → /mnt/broker/demo/；dsh 任务 prompt 中给出素材绝对路径）
- [ ] **Step 4: 推送任务文件**（sync_push.sh）并确认 Broker 入队（ssh 查 tasks 目录/日志）

### Task 5: 执行 → 拉回 → ingest → 复查（验收核心）

**Files:**
- Create: `D:\pythonProject\orchestra\reports\2026-08-experiment-loop-acceptance.md`

**Interfaces:**
- Consumes: Task 4 任务执行结果（Broker attempt-N + metrics.json）；`run_card.py ingest`
- Produces: 卡 Run log 两行（ctl-single 与 trt-dsh 各一）；`demo/.research/experiments/EXP-001/runs/<run_id>/metrics.json` 两份；验收报告

- [ ] **Step 1: 等待两臂 done/failed**（sync_pull 拉 results/；state.json 判定）
- [ ] **Step 2: ingest 两臂**：`run_card.py ingest results/T-<date>-ctl-single/metrics.json --card <card> --research-root orchestra/demo/.research`（trt 同）；任一 HARD → 按错误修任务重派（attempts ≤ 2，再败上报用户）
- [ ] **Step 3: 验证入账**：卡 Run log 两行、runs/ 两份 metrics.json、engine 校验通过
- [ ] **Step 4: CC 复查写验收报告**：报告内所有数字必须引用 ingest artifact 路径（如 `runs/run-*/metrics.json` 的 `metrics.*`），**全文不得出现手抄数字**；对照结论只描述管线事实（两臂均可入账、差异仅为执行方式），不写科研结论；reviewed: ok
- [ ] **Step 5: Commit** `docs: subsystem-2 experiment loop acceptance report`

### Task 6: 总 spec 与 README 更新 + 归档

**Files:**
- Modify: `docs/superpowers/specs/2026-08-18-research-orchestra-design.md`（§6.2 标记细化完成 + 验收结果；§13 清单勾掉第 2 项）
- Modify: `D:\pythonProject\orchestra\README.md`（新增"实验管线闭环"节：卡 Commands 约定入口、run_card.py 用法、demo 根位置）

- [ ] **Step 1: 更新文档**
- [ ] **Step 2: Commit** `docs: spec §6.2 finalized with acceptance result`

---

## Self-Review 记录

- **Spec 覆盖**：总 spec §6.2 的「commands 字段无头约定」（Task 1 约定 A）、「卡是接口执行可替换」（Task 2 commands 子命令 + 两臂不同 executor）、「engine 三脚本不改」（全程子进程调用 + 零修改约束）、「program.yaml human_in_loop」（Task 3）、「验收对照实验数字全走 ingest」（Task 4/5 验收条件）。§6.2「本地算力边界」段为背景知识，本 mission 不涉本地模型（对照实验走 API）——无需动作。
- **占位符扫描**：`<date>` 为部署期变量（Task 4 执行时取当天日期）；无代码占位。
- **与总 spec 的偏差**：总 spec 任务文件模板含 priority/schedule/prompt/acceptance 字段，Broker v1 严格格式为 executor/net/result/timeout（DECISIONS 021 已记录该取舍）——本 mission 沿用 Broker v1 格式，不新增字段。
- **风险预案**：dsh 臂若产出路径偏离注入约定 → 按 subsystem-1 e2e 先例记录 reports/，不修改 broker；dsh 抽取质量差 → 不影响验收（验收对象是管线入账纪律，非模型质量），报告中如实记录。
