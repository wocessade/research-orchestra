# Research Orchestra — 以 Claude Code 为核心的科研-实验-论文框架（总架构设计）

> 日期：2026-08-18 | 修订：2026-08-19（v2：VRAM 修正 12GB、Pi 任务代理三层架构、微信桥接入、网络分区与离线降级；v3：SSD 直挂存储、重型任务断网=排队断点续传（弃本地小模型硬扛）、主机移动网络方案、宿舍 NAS 待建、采购评估 §14；v4：4B 确认为 2GB（冒烟即升级决策门）、核桃派迁移完成（分机部署定稿）、§15 与 OpenClaw/Hermes 定位澄清；v5：subsystem-2 验收完成（实验卡 Commands 约定 + ingest 闭环）、存储/模板表述与现状同步）
> 术语：CC = Claude Code（本机交互主脑）；dsh = DeepSeek Harness（执行层引擎）；Codex = OpenAI Codex CLI（副脑，后续加入）；Broker = Pi 任务代理服务器

## 1. 背景与目标

用户为 2026-09 入学的 CS 研究生，研究方向待定，需尽快产出科研结果。目标：建立一套**方向无关的科研生产力系统**，以 CC 为编排中枢，将现有三台硬件（Windows 本机、树莓派 4B、核桃派 1B）、已安装 skills（academic-research-engine、nature-* 等）、已运行的 usage-monitor、微信桥接与 dsh/Codex 整合为统一的工作流：

**CC = 大脑（编排+决策+复查），Pi Broker = 常驻调度服务器（队列+派发+中间结果），dsh = 手脚（批量执行），核桃派 = 展示/物理 I/O，Codex = 副脑（交叉验证），haiku 子代理 = 勤杂工（简单工作），微信/邮件/墨水屏 = 人机通道。**

核心模式：**"派任务-执行-复查"闭环 + 控制面与执行面分离**——Windows（控制面）可以脱机，Pi Broker（执行面）7×24 常驻，任务不中断、中间结果落盘。

## 2. 硬件资产与角色分工

| 硬件 | 关键规格（已实测/已核实） | 角色 | 依据与约束 |
|---|---|---|---|
| Windows 本机 | i7-11800H 8C/16T、64GB RAM（2×32GB @3200）、**RTX 3060 Laptop 12GB VRAM**（nvidia-smi 实测 12288 MiB；Win32 AdapterRAM 字段 4GB 截断，不可信）、4 盘共 2.4TB、Win10 19045、Hyper-V 可用 | **指挥中枢 + 重计算 + 本地推理** | CC 驻地；docx/pptx、Playwright、OCR、git、微信桥均在本机；Node v24.15.0 满足 dsh；**12GB VRAM 可跑 7B-8B 量化本地模型**（断网 LLM 降级） |
| 树莓派 4B | BCM2711 quad A72，**2GB 内存（已确认）**，Raspberry Pi OS，SPI0 可用；usage-monitor **已迁至核桃派**，4B 现专职 Broker；**存储：broker 数据落闪迪 16G U 盘（ext4，fstab UUID+nofail 挂载 /mnt/broker，写入/WAL 冒烟通过；金士顿盘写入负载拖死整机已弃用）**；2280 SSD 留作宿舍 NAS/冷备扩容候选 | **Pi Broker：常驻任务代理服务器 + dsh 执行节点** | 7×24 常驻、Node arm64 可用；**2GB 是 dsh 冒烟测试的核心风险——冒烟即升级决策门**（过则留下，吃紧则按 §14 上 Pi 5） |
| 核桃派 1B | 全志 H616/H618，**1GB 内存**，Debian 12，仅 SPI1（`/dev/spidev1.0`），user `pi/pi` | **展示/物理 I/O 层**（usage-monitor **已迁移至此并运行**，墨水屏+LED 在役）+ Broker 冷备候选 | 1GB 跑 dsh 风险高，不推荐；Flask 轻量展示可承载；存储沿用 SD（轻负载） |
| 宿舍/实验室 NAS | Liudfs-NAS **不可用**（用户实验室/宿舍场景）；宿舍 NAS 需另建 | results/logs 异地冷备 | 待定：候选方案见 §12；Broker 主存储已由闪迪 U 盘解决，NAS 是冗余层不是必需层 |

**分派原则：计算重在本机，调度与常驻在 4B（闪迪 U 盘直挂 /mnt/broker），物理展示在核桃派，冷备在宿舍 NAS（待建，非必需）。**

## 3. 软件资产与已有接口（对齐清单）

| 资产 | 接口/能力 | 本框架用法 | 不动项 |
|---|---|---|---|
| usage-monitor（Flask :5000） | `GET /api/dashboard`（全量 state）、`POST /api/status`（CC 状态上报）、`GET /health`；`X-Monitor-Token` 鉴权；APScheduler；墨水屏 worker 带 coalesce/失败退避；无硬件 mock 降级 | 展示层：扩展 orchestra 状态块（§6.4）；上报通道复用同一鉴权模式 | **不动 `~/.claude/settings.json`**（hooks 已停用）；不动现有三端点语义，只增量扩展 |
| 微信桥接（`.wechat-acp/bridge.mjs`，桌面 `微信桥接.bat` 启动） | 微信 iLink API ↔ Claude CLI **双向桥**（用户微信消息可驱动 CC 会话）；自带 QQ SMTP 邮件兜底（send_email.mjs）；跑在 Windows（依赖 fcc-server.exe 代理） | **通知与远程指挥通道**（§6.6）：出站推送任务结果/复查请求，入站接收用户微信指令 | 桥脚本本体不动；接入时只读其发送接口 |
| academic-research-engine | `.research/` 状态机；`validate_experiment_card.py` / `ingest_run.py` / `handoff_sync.py`；硬规则"数值只来自 ingest artifacts"、人在环 | 实验管线闭环的账本与摄入层（§6.2），脚本不改 | 不重造雷达/精读/验证 |
| nature-literature-pipeline 等 | 文献雷达 ingest 后端 | 夜间定时任务自然负载（Broker 常驻执行） | 不重写 |
| ~/.codex 残留 | `config.toml`、`auth.json`、`sessions/`、`memories/`、`plugins/`、`computer-use/`；VS Code `openai.chatgpt` 插件 | Codex CLI 装回后复用登录与历史（§6.3） | **勿删勿改残留** |
| v2rayN 代理 | SOCKS5 `127.0.0.1:10808`（Win） | API 连通性兜底（§7） | 不动配置 |
| 缺失项 | ~~dsh~~（已装 0.1.0-rc.7，4B+Windows 双侧，mission 021 冒烟通过）；codex CLI（未装）、docker（未装）、Ollama（未装，断网降级用） | 安装方案见 §6.1/§6.3/§7 | — |

## 4. 总体架构（三层）

```
┌────────────────────── 控制面（Windows，可脱机）──────────────────────┐
│  Claude Code（设计/审查/裁决/复查）                                  │
│   ├─ haiku 子代理：简单机械工作（§6.5）                              │
│   ├─ 直调：SSH→Broker、codex exec、本地脚本、本地 dsh（降级）        │
│   ├─ academic-* skills：实验账本/文献/写作 状态机                    │
│   └─ 微信桥接：手机 ↔ CC 双向通道（§6.6）                            │
├────────────────────── 服务面（树莓派 4B，7×24）─────────────────────┤
│  Pi Broker：任务队列(SQLite WAL) + dispatcher + systemd timer        │
│   ├─ dsh headless 执行器（Minimal 起步）                             │
│   ├─ 中间结果落盘：results/T-*/step-NN.json + dsh 会话日志(resume)   │
│   └─ 定时任务：systemd timer（夜间文献雷达等）                       │
├────────────────────── 展示/物理面（核桃派 1B 优先，4B 兼容）────────┤
│  usage-monitor：墨水屏 + LED + 告警（扩展 broker 队列视图 §6.4）     │
└──────────────────────────────────────────────────────────────────┘
存储：4B broker 数据落闪迪 U 盘 /mnt/broker（2026-08-19 迁移完成）；宿舍 NAS（待建）做异地冷备
```

跨层通信四条总线，避免点对点耦合：
1. **文件总线**：`orchestra/tasks|results|logs|reports`（执行器读写文件，不直接互相调用）
2. **git 同步总线**：Broker 提交 results → Windows pull 复查 → 复查结论 push 回（版本化中间结果 + 天然备份）
3. **HTTP 上报**：`POST /api/status`、新增 `POST /api/orchestra`（X-Monitor-Token）
4. **SSH/CLI 直调**：仅控制面发起（派任务、查日志）

**Windows 脱机时**：控制面下线，服务面照常（定时任务、队列、LLM 任务不经过 Windows）；复查延后到 Windows 回来（复查本就是人类节奏）；通知降级为墨水屏/LED。

## 5. 调度中枢：orchestra 文件夹

位置：**`D:\pythonProject\orchestra\`（仓库内）**。理由：任务/规则/报告是科研资产，随仓库 git 版本化零成本，CC 工作目录天然可达，且是 Broker 与 Windows 之间 git 同步总线的源目录。若坚持放 `D:\orchestra\`，需单独 git init 并配置 CC 访问——可行但失去"跟随仓库"的便利，默认不采用。

```text
orchestra\
  README.md                # 系统说明、运行手册入口
  config\
    rules.yaml             # 执行器分派规则 + 网络分级（net: required|optional）+ 降级顺序
    model-routing.md       # 模型调度策略表 —【用户另行维护，系统只读，§8】
  tasks\                   # 任务文件总线（文件即队列项，CC 写入，Broker 轮询）
    T-{YYYYMMDD}-{slug}.md
  results\                 # 中间结果：结果文件、step-NN.json checkpoint、metrics.json、codex JSONL
  logs\                    # dsh/codex 会话日志（回放/分叉/恢复用）
  reports\                 # CC 复查记录（复查结论 + 入账引用）
  done\                    # 归档（任务+结果+复查报告同 slug）
```

任务文件模板（唯一任务接口契约，v2 增加网络分级）：

```markdown
# T-20260819-xxx
executor: broker-dsh | codex | haiku | direct
priority: low | normal | high
schedule: now | cron:<expr> | none
net: required | optional        # optional = 断网照跑（本地脚本/文件处理）
prompt: <执行器可无头执行的完整任务描述>
acceptance: <可验证的验收条件>
result: results/T-20260819-xxx/
```

> **v1 落地裁剪（mission 021 DECISIONS）**：priority/schedule/acceptance 三字段 v1 未实现——priority 在个位数队列规模下无意义（YAGNI）、schedule 由 systemd timer 承担、acceptance 由 CC 复查（reports/）承担。Broker v1 严格格式：`executor: dsh|shell`、`net: required|optional`、`result`、`timeout` + 执行体。字段语义保留，后续版本按需加回。

**规则**：任务文件是唯一派发入口；CC 复查后写 `reports/` 并标注 `reviewed: ok|reject`；reject 标注原因留在 tasks/ 待重派或降级重派。

## 6. 子系统接口

### 6.1 子系统 1：Pi Broker 任务代理 + dsh 执行层（地基）

**Broker（4B，Python stdlib + systemd，不上 Redis/Celery——队列规模是个位数任务，勿过度设计）：**

- **队列持久化**：`broker.db`（SQLite WAL，Python 自带 sqlite3）；tasks 表字段：slug、executor、status（queued→running→done/failed）、attempts、net_req、result_path、时间戳；**broker.db 与 results/logs 全部落闪迪 U 盘（/mnt/broker，2026-08-19 迁移完成），不落 SD**
- **任务注入**：CC 写 `orchestra/tasks/T-*.md` → `git push` 或 SSH scp → Broker 轮询 tasks/ 目录（文件即队列项，SQLite 只记状态）
- **dispatcher**：常驻 Python 守护进程（systemd service），取 queued 任务 → 调 dsh headless → 增量写 `results/T-*/step-NN.json` → 更新状态 → 状态上报 `POST /api/orchestra`
- **中间结果持久化**：执行器每步增量落盘 checkpoint；dsh 会话日志天然可 **resume**（断点续跑，原生支持）
- **停机恢复**：Broker 重启 → 扫 status=running → 从 checkpoint / dsh session 恢复或标记 failed 重试
- **定时任务**：systemd timer 直接注入队列（夜间文献雷达、爬虫、长时实验——不依赖 Windows）
- **dsh 安装（方案，spec 阶段不安装）**：4B 装 Node ≥22.19（arm64 tarball）→ `npm i -g @deepseek-ai/dsh`；`DSH_HOME` 凭据文件权限 600；Windows 本机同步安装作为降级执行器；先 `--profile minimal` 冒烟，通过后评估 Standard
- **冒烟测试（验收）**：CC 派"抓取 arXiv 某领域当日新论文并输出 JSON"→ Broker 执行 → Windows 脱机 2 小时任务照跑 → 中间结果可查 → 会话日志可 resume
- **降级链**：4B Broker 挂 → Windows 本地 dsh → CC 直接 Bash

### 6.2 子系统 2：实验管线闭环（engine × dsh）

```
实验卡(card.md, `## Commands` 段可无头执行) ──CC 审查──> Broker 入队 ──> dsh headless 执行
  ──> results/metrics.json ──ingest_run.py──> .research/experiments/EXP-*/runs/
  ──> CC 复查（数值一致性、对照 engine 硬规则）──> handoff_sync.py
```

- **接口约定**：实验卡 `## Commands` 段（fenced bash block + `# arm:` 臂标记）必须可无头执行；"卡"是接口，"执行"是可替换实现（人工/dsh/Codex 都能执行同一张卡）
- **engine 三脚本不改**，仅作为消费端；`program.yaml` compute mode 保持 `human_in_loop`
- **本地算力边界（v2 修正）**：12GB VRAM → 7B-8B 量化模型舒适（q4 ≈ 5-6GB）、14B q4 临界；64GB RAM 可 CPU offload 更大模型。**注意：本地小模型只适合轻量任务，不是重型 LLM 工作的断网降级方案**——重型任务断网时排队断点续传（§7）
- **验收**：对照实验（单次 LLM 调用 vs dsh 多步 agent 同一抽取任务）数字全部走 ingest，无手抄数字
- **状态（2026-08-19）**：细化 spec 与实施见 `plans/2026-08-19-subsystem-2-experiment-loop.md`；对照实验验收通过（验收报告 `orchestra/reports/2026-08-experiment-loop-acceptance.md`）：shell 单次调用与 dsh 多步 agent 两臂均产出合规 metrics.json 并经 ingest_run.py 入账，无手抄数字。

### 6.3 子系统 3：双 agent 验证（CC × Codex）

- **安装计划**：Codex CLI 重装（npm 全局），复用 `~/.codex` 残留登录与历史；VS Code `openai.chatgpt` 插件保留
- **通信方式**（已核实）：① `codex exec "任务" --json`（事件 JSONL 流，CC Bash 直调解析复查，主用）② 文件总线（orchestra 任务/结果）③ 会话 resume/fork（按 session ID 恢复或分叉）④ dsh 子代理 `-codex` 后端（Broker 跑通后启用）
- **三种模式**：互审（Codex 审 CC 代码，两边意见汇总，用户裁决）；独立实现（关键函数双实现跑同一测试，分歧处重点查）；claim 核验（adversarial-claim-check 双跑，结论不一致人工核查）
- **验收**：找一段历史代码让 Codex 独立审，验证分歧点是否命中真问题

### 6.4 子系统 4：仪表盘适配（usage-monitor 增量扩展）

- **state 新增 `orchestra` 块**：`{broker_health, queue_len, active_tasks, last_task, last_sync}`
- **新增 `POST /api/orchestra`**：Broker/编排器上报状态，鉴权复用 `X-Monitor-Token`；现有三端点语义不变
- **墨水屏**：新增"任务面板"视图（队列长度+活跃任务+Broker 健康）；`config.py` 增加 `SHOW_ORCHESTRA` 开关（默认 True），与已停用的 `SHOW_CC_CONTEXT` 并存
- **部署**：usage-monitor 已在核桃派运行（迁移完成），Broker 在 4B——**默认分机部署**：仪表盘定时拉 Broker 状态 API（LAN HTTP）；同机部署仅作降级讨论
- **上报者**：Broker dispatcher / orchestra 运行器脚本，**不是 CC hooks**——不碰 `~/.claude/settings.json`
- **验收**：派 demo 任务，墨水屏任务面板出现状态变化，dashboard API 返回 orchestra 块

### 6.5 子系统 5：haiku 分派规则（编排层）

- **适用判定**：简单机械、原子可验证、无独立设计判断——单文件小改、文本提取、格式转换、数据清洗、清单式检索
- **规则落盘**：`orchestra/config/rules.yaml`，CC 每次分派前读
- **边界**：haiku 分派是 **CC 子代理选择**，与模型 API 路由策略表（§8）无关；视觉任务按已有经验用 sonnet 子代理
- **验收**：rules.yaml 生效后一周，简单工作 haiku 覆盖率 ≥80% 且无独立判断翻车事件

### 6.6 子系统 6：通知与远程指挥通道（微信桥接入）

- **微信桥接**（已核实存在，`.wechat-acp/bridge.mjs`，WeChat iLink API ↔ Claude CLI 双向桥 + QQ 邮件兜底，跑 Windows）：
  - **出站**：任务完成/失败/复查请求 → 微信消息推送到用户手机（人在校园也能收）
  - **入站**：用户微信发指令 → 桥启动 CC 会话 → CC 操作编排器（派任务/查状态/批准复查）——"人在环"的远程形态
  - **接入方式**：orchestra 运行器脚本复用桥的发送接口（细化 spec 时读 bridge.mjs 确认推送函数，**不改桥本体**）
- **降级链**：微信（需 Windows+iLink 外网）→ QQ 邮件（**Pi 直发，24/7**——023 已部署 send_email.py 并实测成功，原"需 Windows+SMTP"表述作废）→ 墨水屏/LED（纯 Pi 侧 LAN，最终兜底）
- **验收**：Broker 完成一个定时任务后，手机微信收到结果摘要；微信发"查任务"收到队列状态回复

## 7. 网络分区与离线降级

**LAN 是控制面骨干**（SSH 22、Flask :5000、Broker 任务 API）——本机↔路由器↔两 Pi 同网段，几乎不会断。**外网依赖清单**：LLM API（DeepSeek/Anthropic/OpenAI）、微信 iLink、QQ SMTP、arXiv/文献源、天气。

| 场景 | 降级策略 |
|---|---|
| 外网不稳/断 | ① 任务按 `net` 分级：optional（本地脚本/实验/文件处理）断网照跑；required（LLM/抓取）排队+指数退避重试（复用已有 USAGE_LOGIN_BACKOFF 模式）② API 连通性兜底：v2rayN SOCKS5（Win 127.0.0.1:10808）；Pi 可配 HTTPS_PROXY 走本机 ③ **重型 LLM 任务断网 = 排队断点续传**（dsh 会话 resume 原生支持，网络恢复自动续跑），**不用本地小模型硬扛**——8B 量化对重型任务不够，默认不装 Ollama（仅当出现轻量本地推理需求时再评估） |
| Windows 脱机 | Broker 照常（队列/定时/LLM 任务不经 Windows）；复查延后；微信停用、**邮件正常（Pi 直发）**，告警走墨水屏/LED |
| LAN 断 | 系统停摆（最不可能）；Broker 侧任务状态已持久化，LAN 恢复后续跑，不丢队列 |
| 主机移动（宿舍↔实验室） | 见下方"主机移动与远程访问"专段 |
| 网络错峰 | 需外网的批量任务（文献抓取、大模型跑量）排在夜间网络稳定时段（systemd timer 定时） |

**原则：执行不依赖外网质量——任务要么断网照跑（optional），要么排队断点续传（required），没有"半途挂死"。**

**主机移动与远程访问（宿舍↔实验室）**：默认假设校园网内宿舍-实验室互通（同一园区网，**入学后实测**，若互通则 LAN 方案天然支持主机移动，零额外配置）。若不通，候选方案按优先级：① Tailscale/ZeroTier（WireGuard mesh，免公网暴露，首选）② 公网 IPv6 直连（可达但不稳、暴露面大，必须 SSH 密钥-only + token 鉴权 + 防火墙白名单，仅作备选）。安全原则先行：**任何暴露面最小化**——SSH 禁密码仅密钥、API 全部 token、端口白名单。细化 spec 阶段按实测网络拓扑定稿。

## 8. 模型调度策略表（接口预留，out of scope）

用户另行安排，后续讨论。本框架只约定：
- 策略表位于 `orchestra/config/model-routing.md`，**用户维护，系统只读**
- 执行器（dsh/codex）模型选择最终以策略表为准；本 spec 不预设模型-任务绑定
- usage-monitor 已有用量/成本采集，成本量化直接消费现有数据（§3 接口不动）

## 9. 任务生命周期（数据流，v2 经 Broker）

```
CC 写 tasks/T-*.md ──git push/SSH──> Broker 队列(SQLite) ──dispatcher──> dsh headless
  ──增量写 results/T-*/step-NN.json + 会话日志──> 状态更新 → POST /api/orchestra → 墨水屏
  ──Broker 提交 results 到 git──> Windows pull ──> CC 复查（logs 回放/resume）
  ──> reports/T-*.md（ok/reject）
──> ok: ingest 入账（实验任务）/ 归档 done/；reject: 标注原因留在 tasks/ 待重派，或降级重派
（Windows 脱机时省略 git pull/复查环节，Broker 侧完整跑完并落盘）
```

## 10. 错误处理与降级

| 故障 | 降级路径 |
|---|---|
| 4B Broker 挂/离线 | Windows 本地 dsh → CC 直接执行；核桃派冷备 Broker（队列目录 git 同步过去，手动切换） |
| dsh 未装/损坏 | 同左 |
| codex CLI 未装 | haiku 或 CC 自查 |
| LLM API 不可达 | required 任务排队断点续传（dsh resume）；不用本地小模型硬扛重型任务 |
| 墨水屏 SPI 失败 | 已有 mock/退避/恢复机制（app.py 现成） |
| Pi 断电重启 | dispatcher 扫 running → checkpoint/resume 恢复 |
| 同一任务失败 ≥2 次 | 升级用户（sustained-development 规则），不停留自查 |
| 任务无人审批（headless） | CC 复查即验收环节，复查记录必写 reports/ |

## 11. 安全与边界

- `MONITOR_TOKEN` 必设；Broker 任务 API（如暴露）同鉴权模式；密钥/凭据不入 git
- `~/.codex` 残留、核桃派验收环境：**勿删勿动**；删除任何文件前先问用户
- Pi 上 `DSH_HOME` 凭据文件权限 600；SQLite broker.db 权限 600
- 微信桥的 token.json/login_state.json 不入库；桥日志不 commit

## 12. 风险与开放问题

| 风险 | 缓解 |
|---|---|
| **4B 仅 2GB，dsh 内存占用未实测** | 冒烟测试即升级决策门：Minimal 模式跑通且稳定 → 留下；吃紧 → §14 上 Pi 5 8GB（触发条件已明确） |
| Pi 存储可靠性（SD 写磨损） | **已解决**：闪迪 16G U 盘 ext4 直挂 /mnt/broker（fstab UUID+nofail，写入/WAL 冒烟通过；金士顿盘写入负载下拖死整机已弃用）；SSD+转接盒留作宿舍 NAS/冷备扩容候选 |
| Broker 单点（4B 挂则常驻层停） | 核桃派冷备；队列目录 git 同步，手动切换（自动化主备切换明确不做，过度设计） |
| 宿舍 NAS 待建（异地冷备缺失期） | git 同步 + 闪迪 U 盘直挂已覆盖主要风险；NAS 是冗余层非必需层，方案见 §14 |
| 校园网宿舍-实验室是否互通未知 | 入学后实测；不通则 Tailscale/ZeroTier（§7 已定优先级） |
| dsh 开发者预览（rc.7）接口可变 | 锁版本；升级看 changelog；执行层可替换（降级链） |
| Windows 无 docker | headless 流程不需要；Hyper-V 可用，未来需要再评估 |
| 开放问题 | dsh 在 2GB 4B 的实测内存、Codex CLI 登录方式、bridge.mjs 推送接口、校园网拓扑——各子系统细化 spec 的 smoke test 解决 |

## 13. 验收标准（总 spec 级）与后续细化清单

总 spec 验收 = 六子系统各有一个可执行 smoke test 定义（§6 已列），用户审阅本 spec（v4）通过。

后续细化 spec（逐个编写，建议顺序，编号与 §6 一一对应）：
1. `subsystem-1-pi-broker`（Broker 部署：队列/dispatcher/checkpoint/resume + 4B dsh 安装与冒烟 + SSD 挂载）★最先
2. ~~subsystem-2-experiment-loop~~（✅ 已细化并验收，见 §6.2 状态行）
3. `subsystem-3-codex-dual-agent`（CLI 安装 + 三模式脚本化）
4. `subsystem-4-dashboard-orchestra`（state/orchestra + 墨水屏面板 + 上报脚本）
5. `subsystem-5-haiku-dispatch`（rules.yaml 结构与判定清单）
6. `subsystem-6-wechat-channel`（读 bridge.mjs 确认推送接口 + 出站/入站接入）

## 14. 采购与硬件升级评估（适当采购，非必需项按需触发）

**结论：近期零必购。** 现有硬件跑通全流程后再按瓶颈采购。

| 候选采购 | 触发条件 | 预估 | 建议 |
|---|---|---|---|
| USB3 M.2 转接盒（2280） | ~~立即（唯一推荐现在买，几十元）~~ **已购**；存储现走闪迪 U 盘，SSD 留作宿舍 NAS/冷备扩容 | ~40-60 元 | 已购待用 |
| Pi 5 8GB/16GB（替换 4B 作 Broker） | 4B 内存 <4GB 且 dsh 冒烟吃紧 | ~500 元 | 性能翻数倍、PCIe 原生；4B 退役为实验节点 |
| 宿舍 NAS：N100 小主机（二手/准系统） | 异地冷备需求 + 宿舍常驻设备 | ~500-800 元 | 同价位性能远强于品牌 NAS；还能兼作备用执行节点/跑本地小模型 |
| 品牌 NAS（群晖等） | 不推荐 | — | 溢价高，N100 方案更优 |
| UPS（Pi 断电保护） | 宿舍断电频繁时 | ~100 元 | 可选；checkpoint+resume 已覆盖多数场景 |
| GPU/云算力 | 不买 | — | 3060 12GB 学生阶段够；入学后导师组服务器优先 |

**原则：先用现成硬件把流程跑通、跑出真实瓶颈，再按触发条件采购——避免"设备先行、流程滞后"。**

## 15. 与 OpenClaw / Hermes 的关系（定位澄清）

本系统与 OpenClaw、[Hermes Agent](https://hermes-agent.nousresearch.com/)（Nous Research 自托管个人助理）**属于同一大类**：常驻 7×24 的个人 AI 基础设施（IM 通道 + 定时任务 + 记忆持久化 + MCP 工具 + 模型无关）。形态收敛是必然——这是 2026 年个人 agent 的成熟模式，方向正确。

**但实现哲学不同，不构成重复造轮子：**

| 维度 | Hermes / OpenClaw | 本系统 |
|---|---|---|
| 脑 | 自带 agent loop（独立运行时，下载即用） | **CC 是脑**，本系统只做编排胶水层（broker+文件总线+git 同步），不写 agent loop |
| 定位 | 通用个人助理（记忆、聊天、生活化任务） | **科研生产线**：RQ→实验→ingest→论文，学术诚信硬约束（数值只来自 artifacts、每 gate 人在环、负结果账本） |
| 通道 | 主流 IM 全家桶（Telegram/WhatsApp/Discord…） | 现成微信桥（国内场景更实用）+ 邮件 + 墨水屏 |
| 物理 I/O | 无 | 墨水屏/LED/GPIO 展示层 |
| 形态 | 一体产品 | **组合架构**：每层可替换（dsh 坏→Bash；Codex 无缝加入；engine 账本独立） |

**决策**：不切换到 Hermes/OpenClaw（agent 能力弱于 CC、无科研管线、无微信通道）；借鉴其设计模式（通道网关、hook 机制、记忆设计）；OpenClaw 作为未来通道网关候选仅在微信桥失效时再评估（YAGNI）。
