# Research Orchestra — 以 Claude Code 为核心的科研-实验-论文框架（总架构设计）

> 日期：2026-08-18 | 状态：总 spec（子系统细化 spec 后续逐个编写）
> 术语：CC = Claude Code（本机交互主脑）；dsh = DeepSeek Harness（执行层引擎）；Codex = OpenAI Codex CLI（副脑，后续加入）

## 1. 背景与目标

用户为 2026-09 入学的 CS 研究生，研究方向待定，需尽快产出科研结果。目标：建立一套**方向无关的科研生产力系统**，以 CC 为编排中枢，将现有三台硬件（Windows 本机、树莓派 4B、核桃派 1B）、已安装 skills（academic-research-engine、nature-* 等）、已运行的 usage-monitor 与 dsh/Codex 整合为统一的工作流：

**CC = 大脑（编排+决策+复查），dsh = 手脚（批量执行），Pi = 躯体（常驻+物理 I/O），Codex = 副脑（交叉验证），haiku 子代理 = 勤杂工（简单工作）。**

核心模式沿用已验证的"派任务-执行-复查"闭环：CC 派任务 → 执行器无头执行 → CC 复查产出与轨迹 → 结果入账（ingest）→ 展示/归档。

## 2. 硬件资产与角色分工

| 硬件 | 关键规格（已实测/已核实） | 角色 | 依据与约束 |
|---|---|---|---|
| Windows 本机 | i7-11800H 8C/16T、64GB RAM（2×32GB @3200）、RTX 3060 Laptop **4GB VRAM**、4 盘共 2.4TB、Win10 19045 | **指挥中枢 + 重计算** | CC 驻地；docx/pptx 生成、Playwright、OCR、git 均在本机；Node v24.15.0 满足 dsh 要求（^22.19 \|\| >=24）；本地推理受 4GB VRAM 限制（详见 §12 风险） |
| 树莓派 4B | BCM2711 quad A72，Raspberry Pi OS，当前跑 usage-monitor（`/home/liuxfs/usage-monitor`），SPI0，Waveshare 3.97″ 墨水屏 + LED 已跑通 | **dsh 执行节点**（候选） | Node arm64 可用；内存型号未确认（2/4/8GB）→ dsh 冒烟测试为子系统 1 第一步；**核桃派未完全验收前保留 4B 现有环境** |
| 核桃派 1B | 全志 H616/H618，**1GB 内存**，Debian 12，仅 SPI1（`/dev/spidev1.0`），user `pi/pi` | **展示 + 物理 I/O 层** | 1GB 跑 dsh 风险高，不推荐；继续承载 usage-monitor（Flask 轻量）；（可选，后续）GPIO/墨水屏 MCP server |

**分派原则：计算重的在本机，7×24 值守在 4B，物理展示在核桃派。** 两 Pi 可通过部署脚本（已有 `deploy_to_pi.py` 经验）双端部署 usage-monitor。

## 3. 软件资产与已有接口（对齐清单）

| 资产 | 接口/能力 | 本框架用法 | 不动项 |
|---|---|---|---|
| usage-monitor（Flask :5000） | `GET /api/dashboard`（全量 state）、`POST /api/status`（CC 状态上报）、`GET /health`；`X-Monitor-Token` 鉴权；APScheduler 定时任务；墨水屏 worker 带 coalesce/失败退避；无硬件时 mock 降级 | 展示层：扩展 orchestra 状态块（§6.4）；上报通道复用同一鉴权模式 | **不动 `~/.claude/settings.json`**（hooks 已停用，勿恢复）；不动现有三个端点语义，只做增量扩展 |
| academic-research-engine | `.research/` 状态机（RQ→H→EXP→NEG→handoff）；脚本 `validate_experiment_card.py` / `ingest_run.py` / `handoff_sync.py`；硬规则"数值只来自 ingest artifacts"、人在环 | 实验管线闭环的账本与摄入层（§6.2），脚本不改，仅作为消费端 | 不重造雷达/精读/验证 |
| nature-literature-pipeline 等 | 文献雷达 ingest 后端 | 夜间定时任务的自然负载（§6.1） | 不重写 |
| ~/.codex 残留 | `config.toml`、`auth.json`、`sessions/`、`memories/`、`plugins/`、`computer-use/`；VS Code `openai.chatgpt` 插件 | Codex CLI 装回后复用登录与历史（§6.3） | **勿删勿改残留** |
| 缺失项 | dsh（未装）、codex CLI（未装）、docker（未装） | 安装方案见 §6.1/§6.3；docker 暂不需要 | — |

## 4. 总体架构（四层）

```
┌───────────────────── 编排层（Windows）──────────────────────┐
│  Claude Code（交互主脑：设计/审查/裁决/复查）                  │
│   ├─ haiku 子代理：简单机械工作（规则见 §6.5）                 │
│   ├─ 直调 Bash：SSH→dsh、codex exec、本地脚本                 │
│   └─ academic-* skills：实验账本/文献/写作 状态机              │
├───────────────────── 执行层（可替换）───────────────────────┤
│  dsh headless（RPi 4B 主执行器；Windows 本地为降级备份）        │
│  Codex CLI exec --json（Windows，后续）                        │
│  haiku 子代理（Windows，CC 内）                                │
├───────────────────── 数据层（Windows）──────────────────────┤
│  orchestra/ 调度中枢（§5）│ .research/ 实验账本 │ git 仓库      │
├───────────────────── 展示/物理层（核桃派 1B 优先，4B 兼容）──┤
│  usage-monitor：墨水屏 + LED + 告警（扩展 orchestra 视图 §6.4） │
└───────────────────────────────────────────────────────────┘
```

跨层通信只有三条总线，避免点对点耦合：
1. **文件总线**：`orchestra/tasks|results|logs|reports`（所有执行器读写文件，不直接互相调用）
2. **HTTP 上报**：执行器/编排器 → `POST /api/status` 或新增 `POST /api/orchestra`（X-Monitor-Token）
3. **SSH/CLI 直调**：CC Bash → Pi dsh / 本地 codex（仅编排层发起）

## 5. 调度中枢：orchestra 文件夹

仓库内新建专用调度文件夹（用户要求）：

```text
D:\pythonProject\orchestra\
  README.md                # 系统说明、运行手册入口
  config\
    rules.yaml             # 执行器分派规则（dsh/codex/haiku 适用范围与降级顺序）
    model-routing.md       # 模型调度策略表 —【用户另行维护，系统只读引用，见 §7】
  tasks\                   # 任务文件总线：CC 写入，执行器读取
    T-{YYYYMMDD}-{slug}.md
  results\                 # 执行器产出：结果文件、metrics.json、codex JSONL
  logs\                    # dsh/codex 会话日志（回放/分叉/复查用）
  reports\                 # CC 复查记录（复查结论 + 入账引用）
  done\                    # 归档（任务文件 + 结果 + 复查报告同 slug 归档）
```

任务文件模板（`tasks/T-*.md`，唯一的任务接口契约）：

```markdown
# T-20260818-xxx
executor: dsh-rpi4 | codex | haiku | direct
priority: low | normal | high
schedule: now | cron:<expr> | none
prompt: <执行器可无头执行的完整任务描述>
acceptance: <可验证的验收条件>
result: results/T-20260818-xxx/   # 执行器产出目录
```

**规则**：任务文件是唯一派发入口；CC 复查后写 `reports/` 并在任务文件上标注 `reviewed: ok|reject`；拒绝的任务带原因回 queue。

## 6. 子系统接口

### 6.1 子系统 1：dsh 执行层（地基）

- **安装（方案，spec 阶段不安装）**：RPi 4B 装 Node ≥22.19（arm64 tarball）→ `npm i -g @deepseek-ai/dsh`（或 npx）；`DSH_HOME` 凭据文件权限 600；Windows 本机同步安装作为降级执行器
- **模式演进**：先 `--profile minimal`（Shell+文件编辑，1GB 级内存占用小）→ 冒烟通过后评估 Standard
- **触发**：`ssh pi@<4B> "cd ~/orchestra && dsh --profile headless \"$(cat task.prompt)\""`；定时任务用 systemd timer（复用已有 service 经验）
- **夜间负载**：nature-literature-pipeline 定时 ingest、爬虫采集、长时实验挂机
- **冒烟测试（验收）**：CC 派一个"抓取 arXiv 某领域当日新论文并输出 JSON 到 results/"的任务，Pi 执行、会话日志可回放、结果可复查
- **降级链**：4B dsh 不可用 → Windows 本地 dsh → CC 直接 Bash 执行

### 6.2 子系统 2：实验管线闭环（engine × dsh）

```
实验卡(card.md, commands 字段可无头执行) ──CC 审查──> dsh headless 执行
  ──> results/metrics.json ──ingest_run.py──> .research/experiments/EXP-*/runs/
  ──> CC 复查（数值一致性、对照 engine 硬规则）──> handoff_sync.py
```

- **接口约定**：实验卡的 `commands:` 字段必须格式化为 dsh headless 能直接吃的任务串；"卡"是接口，"执行"是可替换实现（人工/dsh/Codex 都能执行同一张卡）
- **engine 三脚本不改**，仅作为消费端；`program.yaml` compute mode 保持 `human_in_loop`
- **本地算力边界**：RTX 3060 4GB 只适合 3B-4B 量化模型或 CPU 推理（64GB RAM 可跑 7B+ CPU offload）；GPU 实验默认人在环，不代跑
- **验收**：跑一个对照实验（如"单次 LLM 调用 vs dsh 多步 agent 做同一抽取任务"），数字全部走 ingest，无手抄数字

### 6.3 子系统 3：双 agent 验证（CC × Codex）

- **安装计划**：Codex CLI 重装（npm 全局），复用 `~/.codex` 残留登录与历史；VS Code `openai.chatgpt` 插件保留不动
- **通信方式**（已核实）：
  - ① `codex exec "任务" --json`：事件 JSONL 流，CC Bash 直调解析复查（主用）
  - ② 文件总线：orchestra/tasks 写任务、results 读产出（异步/长任务）
  - ③ 会话 resume/fork：按 session ID 恢复或分叉
  - ④ dsh 子代理 `-codex` 后端：待 dsh 跑通后启用
- **三种模式**：互审（Codex 审 CC 代码，汇总两边意见，用户裁决）；独立实现（关键函数双实现跑同一测试，分歧处重点查）；claim 核验（adversarial-claim-check 双跑，结论不一致的 claim 人工核查）
- **验收**：找一段历史代码让 Codex 独立审，验证分歧点是否命中真问题

### 6.4 子系统 4：仪表盘适配（usage-monitor 增量扩展）

- **state 新增 `orchestra` 块**：`{active_tasks, queue_len, last_task, executor_health: {dsh_rpi4, codex}}`
- **新增 `POST /api/orchestra`**：上报 orchestra 状态，鉴权复用 `X-Monitor-Token`；`GET /api/dashboard`、`POST /api/status`、`GET /health` 语义不变，仅 state 多一个键
- **墨水屏**：新增"任务面板"视图（活跃任务+状态+执行器健康）；`config.py` 增加 `SHOW_ORCHESTRA` 开关（默认 True），与已停用的 `SHOW_CC_CONTEXT` 并存，互不影响
- **上报者**：orchestra 运行器脚本（Windows 侧），**不是 CC hooks**——不碰 `~/.claude/settings.json`
- **部署影响**：仅改 usage-monitor 代码（app.py / config.py / eink_dashboard.py），systemd 单元不变；核桃派与 4B 双端兼容（应用层与硬件无关，已有 mock 降级）
- **验收**：派一个 demo 任务，墨水屏任务面板出现状态变化，dashboard API 返回 orchestra 块

### 6.5 子系统 5：haiku 分派规则（编排层）

- **适用判定**：简单机械、原子可验证、无独立设计判断——单文件小改、文本提取、格式转换、数据清洗脚本、清单式检索
- **规则落盘**：`orchestra/config/rules.yaml`，CC 每次分派前读
- **边界**：haiku 分派是 **CC 子代理选择**（Agent tool），与模型 API 路由策略表（§7）无关；视觉任务按已有经验用 sonnet 子代理
- **验收**：rules.yaml 生效后，一周内简单工作 haiku 覆盖率 ≥80%，且无 haiku 独立判断翻车事件

## 7. 模型调度策略表（接口预留，out of scope）

用户另有安排，后续讨论。本框架只约定：
- 策略表位于 `orchestra/config/model-routing.md`，**用户维护，系统只读**
- 执行器（dsh/codex）的模型选择最终以策略表为准；本 spec 不预设任何模型-任务绑定
- usage-monitor 已有用量/成本采集，未来成本量化直接消费现有数据（§3 接口不动）

## 8. 任务生命周期（数据流）

```
CC 写 tasks/T-*.md ──分派（rules.yaml + 策略表）──> 执行器：
  dsh-rpi4（SSH headless）/ codex（exec --json）/ haiku（Agent）/ direct（Bash）
──> 产出写 results/T-*/ ──> 执行器回报状态 POST /api/orchestra ──> 墨水屏更新
──> CC 复查（results + logs 会话回放）──> reports/T-*.md（ok/reject）
──> ok: ingest 入账（实验任务）/ 归档 done/；reject: 标注原因留在 tasks/ 待重派，或降级重派
```

## 9. 错误处理与降级

| 故障 | 降级路径 |
|---|---|
| 4B 离线/dsh 未装 | Windows 本地 dsh → CC 直接执行 |
| codex CLI 未装 | haiku 或 CC 自查 |
| 墨水屏 SPI 失败 | 已有 mock/退避/恢复机制（app.py 现成） |
| 同一任务失败 ≥2 次 | 升级用户（sustained-development 规则），不停留自查 |
| 任务无人审批（headless） | CC 复查即验收环节，复查记录必写 reports/ |

## 10. 安全与边界

- `MONITOR_TOKEN` 必设；密钥/凭据不入 git（迁移手册已有警告，延续执行）
- `~/.codex` 残留、核桃派验收环境：**勿删勿动**；删除任何文件前先问用户
- Pi 上 `DSH_HOME` 凭据文件权限 600
- 局域网 HTTP 上报保持现有鉴权模型，不降级为明文开放

## 11. 风险与开放问题

| 风险 | 缓解 |
|---|---|
| 4B 内存型号未确认，dsh 内存占用未实测 | 冒烟测试为子系统 1 第一步；Minimal 起步 |
| 核桃派 1GB 明确不跑 dsh | 角色已定为展示层，不做尝试 |
| dsh 为开发者预览（rc.7），接口可能破坏性变更 | 锁定版本；升级前看 changelog；执行层可替换（降级链） |
| RTX 3060 4GB 限制本地模型 | 本地推理只做 3B-4B 量化/CPU offload；大模型走 API |
| Windows 无 docker | 当前 headless 流程不需要；如未来需容器沙箱再评估（winget） |
| 开放问题：4B 实际内存容量、dsh 在 4B 的实测内存占用、Codex CLI 登录方式 | 各子系统细化 spec 的 smoke test 解决 |

## 12. 验收标准（总 spec 级）与后续细化清单

总 spec 验收 = 五子系统各有一个可执行的 smoke test 定义（§6 已列），用户审阅本 spec 通过。

后续细化 spec（逐个编写，建议顺序）：
1. `subsystem-1-dsh-executor`（4B 部署 + 冒烟）
2. `subsystem-2-experiment-loop`（实验卡命令字段约定 + ingest 对接）
3. `subsystem-3-codex-dual-agent`（CLI 安装 + 三模式脚本化）
4. `subsystem-4-dashboard-orchestra`（state/orchestra + 墨水屏面板 + 上报脚本）
5. `subsystem-5-haiku-dispatch`（rules.yaml 结构与判定清单）
