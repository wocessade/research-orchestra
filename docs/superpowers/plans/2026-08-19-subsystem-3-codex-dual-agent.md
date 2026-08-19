# Subsystem 3: 双 agent 验证（CC × Codex）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 装回 Codex CLI（复用 `~/.codex` 残留登录与历史），跑通 `codex exec --json` 直调主通道，把三种双 agent 工作模式（互审 / 独立实现 / claim 核验）脚本化，并以「历史代码独立审」验收——分歧点是否命中真问题，数字全部走文件证据。

**Architecture:** CC = 主脑（编排+裁决），Codex = 副脑（交叉验证）。通信主用总 spec §6.3 方式 ①：`codex exec --json`（事件 JSONL 流），由 stdlib 封装脚本子进程调用并解析复查；方式 ②（文件总线）与 ③（resume/fork）在验收期验证能力存在性，v1 不脚本化；方式 ④（Broker codex executor）列为 out of scope（Pi→OpenAI 网络路径未验证，见 DECISIONS D20）。

**Tech Stack:** Codex CLI（npm 全局，@openai/codex）、Python 3.11 stdlib（封装脚本）、unittest、Git Bash。Codex 侧模型选择**用户自理**（--model 透传，默认不指定用 codex 默认）。

## 接口约定（本 spec 的核心产出）

### A. `codex_exec.py`（orchestra/scripts/，stdlib only，直调主通道）

```
codex_exec.py run <prompt-file|-> [--model X] [--timeout N] [--out DIR] [--json-out PATH]
```

- 子进程：`codex exec --json [--model X] < prompt`（prompt 从文件或 stdin 读，**不进 argv**，避免 shell 历史泄漏）
- 解析 `--json` 输出的 NDJSON 事件流：`item.completed`（assistant 最终文本、session_id）、`turn.completed`、错误事件（authentication / rate_limit / network / sandbox / trust 类）
- stdout 输出结构化 JSON：`{"status": "ok|error|timeout", "text": str, "session_id": str, "model": str, "elapsed_s": float, "events": int, "error_type": str|null}`
- 退出码：0 成功；1 codex 执行失败；2 codex 未安装；3 超时；4 认证失败（提示 `codex login` 并上报 Trigger Report）
- 可选 `--out DIR` 落盘全文与事件日志（复查 artifact）
- 信任检查：cwd 不在 git 仓库内时自动附加 `--skip-git-repo-check`（实测非 git 目录被 trusted directory 检查拒绝）；CLI 提供 `--skip-git-check` 强制开关
- 事件流容忍：实测含 WS 重连超时等传输噪音事件——解析器只认已知事件类型，未知一律忽略
- 错误分类字段供上层脚本与 CC 判断（认证失败不得静默重试）

### B. `codex_modes.py`（orchestra/scripts/，基于 codex_exec.py，三模式）

| 模式 | 命令 | 输入 | 输出（结构化 JSON） |
|---|---|---|---|
| 互审 | `mutual-review <diff-file> [--context FILE]` | CC 的代码 diff（+可选上下文说明） | `review.json`：`[{severity: high|med|low, file, line, issue, suggestion}]` |
| 独立实现 | `dual-implement <spec-file> --impl-dir DIR --tests DIR` | 功能规格 + CC 实现目录 + 测试目录 | 在 DIR 内生成 `codex_impl/`，与 CC 实现**同跑同一测试集**，产出 `dual.json`：`{cc_tests: {...}, codex_tests: {...}, divergences: [{kind: behavior|interface|style, file, detail}]}` |
| claim 核验 | `claim-check <claims-file>` | 断言清单（JSON 数组） | `claims.json`：每条 `{claim, cc_verdict: true|false|unsure, codex_verdict, agree: bool}`；`disagree` 项单列供人工核查 |

- 三模式均封装超时/错误分类透传；输出文件路径打印到 stdout（CC 复查入口）
- prompt 模板内置（三模式固定协议文本 + 用户输入内容），保证双 agent 判定口径一致

### C. 验收协议（历史代码独立审）

1. 目标：`orchestra/broker/executor.py`（mission 021-025 已验收在役代码，已知缺陷档案存在：dsh cwd 注入、attempt 目录、超时处理等）
2. `codex_modes.py mutual-review` 对 executor.py 独立审 → `review.json` 分歧清单
3. CC 逐条判定：真问题（对应已知档案或新发现）/ 误报 / 风格建议 → 判定表入验收报告
4. 命中率 = 真问题数 / 清单总数，数字引用 artifact 路径；同时记录 codex 发现的**新问题**（若有）

## Global Constraints

- **`~/.codex` 残留勿删勿改**（auth.json / config.toml / sessions / memories / skills 全部只读；auth.json 绝不 copy、绝不 commit）
- 模型选择用户自理；封装脚本只透传 --model，不预设任何策略绑定
- Broker / usage-monitor / 墨水屏 / 雷达零改动；commit 不加 Co-Authored-By
- 脚本零 pip 依赖；测试 mock codex 子进程（JSONL 样例 fixture），真实调用最小化（Task 1 冒烟 1 次 + Task 4 验收 1 次为主）
- 费用意识：互审/claim 模式的真实调用以验收最小集为准，不做跑量实验
- Windows 侧命令在 Git Bash 运行；数字纪律同 025/026

---

### Task 0: 基线核验（本设计轮已完成）

~/.codex 清单 + auth.json/config.toml 关键文件 md5 存档至 `D:\Temp\subsystem-3\codex-residual-baseline.txt`；codex CLI 未装确认；node v24.15.0。

### Task 1: 安装 Codex CLI + 冒烟（auth 复用验证）

**Files:** 无仓库改动（npm 全局安装）

**Interfaces:**
- Consumes: Task 0 基线
- Produces: 全局 `codex` 命令（记录安装版本）；冒烟结论（auth 复用 OK / 需用户 login）

- [x] **Step 1: 安装**：`npm install -g @openai/codex` → codex-cli 0.148.0（npm list -g 一致）
- [x] **Step 2: 冒烟**：`/d/Temp` 非 git 目录首试被 trusted directory 检查拒绝（exit 1，非 auth 错误）→ 加 `--skip-git-repo-check` 重试 exit 0，item.completed 文本 = codex-smoke-ok，无认证错误
- [x] **Step 3: 记录**：存档 `D:\Temp\subsystem-3\smoke.txt`（+原始事件流 `D:\Temp\codex-smoke-events.jsonl`）；auth.json md5 一致；config.toml 被 codex 自写（marketplace 时间戳/hook 信任哈希，无凭据字段）→ D22 接受为良性

### Task 2: codex_exec.py（TDD）

**Files:**
- Create: `D:\pythonProject\orchestra\scripts\codex_exec.py`
- Test: `D:\pythonProject\orchestra\scripts\tests\test_codex_exec.py`

**Interfaces:**
- Consumes: 约定 A；codex CLI（Task 1）
- Produces:
  - `run_codex(prompt: str, model: str|None, timeout: int, cwd: str|None) -> dict`（子进程 + NDJSON 解析 + 错误分类；测试注入 fake 子进程 runner）
  - `parse_events(lines: list[str]) -> dict`（纯函数：item.completed 文本/session_id、错误事件分类）
  - CLI 层 `main()`（argparse 按约定 A；prompt 走 --prompt-file 或 stdin）

- [x] **Step 1: 写失败测试**（fixture 以真实冒烟流 `D:\Temp\codex-smoke-events.jsonl` 校准：正常 item.completed 流、认证失败事件、rate_limit 事件、超时、codex 未装、空流、WS 传输噪音事件、trusted-directory 拒绝）
- [x] **Step 2-4: 红→绿→回归**（scripts/tests/ 下 unittest，从 orchestra/scripts/ 目录运行；discover 全量 Ran 76 OK = 36 新 + 39 既有 run_card 零回归）
- [x] **Step 5: 一次真实调用验证**（首轮 120s 超时暴露 Windows 管道句柄 bug→修复；复核 `--timeout 420` 通过：status=ok / text=codex-exec-real-ok / elapsed_s=127.9 / events=9 / exit 0，存档 `D:\Temp\subsystem-3\codex_exec-real.json`，超时证据备份 codex_exec-real-timeout.json）
- [x] **Step 6: Commit** `feat: codex_exec.py - codex exec JSONL wrapper with error classification`（eb7cf6e，仅两新文件，无署名行）

### Task 3: codex_modes.py（TDD）

**Files:**
- Create: `D:\pythonProject\orchestra\scripts\codex_modes.py`
- Test: `D:\pythonProject\orchestra\scripts\tests\test_codex_modes.py`

**Interfaces:**
- Consumes: 约定 B；codex_exec.run_codex（mock 注入）
- Produces:
  - `build_prompt(mode, payload) -> str`（三模式模板，纯函数可测）
  - `mutual_review(diff, context, run=None) -> dict`（调用 run_codex + 解析 review 意见为结构化列表；解析失败降级为原始文本+error 标记）
  - `dual_implement(spec, impl_dir, tests_dir, run=None) -> dict`（codex 实现落盘 + 与 CC 实现同跑测试（子进程 pytest/unittest 按 tests 目录类型探测）+ 分歧清单）
  - `claim_check(claims, run=None) -> dict`（逐条双判定；CC 判定由用户提供 or 本地规则？——**v1：CC verdict 由调用方传入**（CC 是编排者），codex verdict 走 run_codex）
  - CLI 层 main()（三个子命令 + 输出文件路径打印）

- [x] **Step 1-4: TDD**（全部用 mock run，不做真实调用；discover 全量 Ran 124 OK = 76 既有零回归 + 48 新）
- [x] **Step 5: Commit** `feat: codex_modes.py - mutual review, dual implement, claim check`（980f266，仅两新文件，无署名行）

### Task 4: 验收（历史代码独立审）

**Files:**
- Create: `D:\pythonProject\orchestra\reports\2026-08-codex-dual-agent-acceptance.md`
- Create: `D:\pythonProject\orchestra\reports\artifacts\codex-review-executor.json`（审阅产物存档）

**Interfaces:**
- Consumes: Task 2/3；`orchestra/broker/executor.py`
- Produces: 验收报告（分歧清单逐条判定 + 命中率 + reviewed: ok）

- [x] **Step 1: 互审真实调用**：`codex_modes.py mutual-review orchestra/broker/executor.py` → review.json 存档（第 3 次调用成功：context「不动工具」+ --timeout 1800；前两次 600s 超时/误杀，证据备份）
- [x] **Step 2: CC 逐条判定**：每条分歧标 真问题/误报/风格建议（对照已知缺陷档案：cwd 注入、attempt 递增、断网门、超时语义）；发现的新问题如实记录（3/3 真问题，全为新问题）
- [x] **Step 3: 写验收报告**：判定表 + 命中率（数字引用 artifact）；顺带记录方式②③能力存在性验证结果（resume/fork 仅验证不脚本化）
- [ ] **Step 4: Commit** `docs: subsystem-3 codex dual-agent acceptance report`

### Task 5: 文档收尾

**Files:**
- Modify: `docs/superpowers/specs/2026-08-18-research-orchestra-design.md`（§6.3 状态行 + §13 勾 3 + 版本行 v7）
- Modify: `D:\pythonProject\orchestra\README.md`（双 agent 节：脚本入口 + 模式说明 + 验收结论）

- [ ] **Step 1-2: 更新 + Commit** `docs: spec §6.3 finalized with acceptance result`

### Task 6: 哨兵审计 + 归档

（8 维度，同 025/026 模板；归档至 completed/，ACTIVE_POINTER 更新）

---

## Self-Review 记录

- **Spec 覆盖**：§6.3 安装（Task 1）、通信方式①主用（Task 2）、三模式（Task 3）、验收「找一段历史代码让 Codex 独立审，验证分歧点是否命中真问题」（Task 4 逐字对应）、④ 延后（D20 out of scope）、②③ 验证存在性（Task 4 Step 3）。
- **占位符扫描**：`--model X` 等为透传参数；无代码占位。
- **风险预案**：auth 失效 → Trigger Report 用户 login（不尝试任何自动登录）；codex --json 格式与预期不符 → 以实测事件流为准调整解析器（Task 2 fixture 按真实冒烟输出校准）；codex 审出 executor.py 大量风格建议 → 判定表分三类处理，风格类不计入命中率分母（报告注明口径）。
- **与总 spec 的偏差**：④ 通信方式列为 out of scope（网络路径未验证）——DECISIONS D20 记录；「模型调度」透传用户自理，不落策略。
