# Research Orchestra — 以 Claude Code 为核心的科研-实验-论文框架（总架构设计）

> 日期：2026-08-18 | 修订：2026-08-19（v2：VRAM 修正 12GB、Pi 任务代理三层架构、微信桥接入、网络分区与离线降级）
> 术语：CC = Claude Code（本机交互主脑）；dsh = DeepSeek Harness（执行层引擎）；Codex = OpenAI Codex CLI（副脑，后续加入）；Broker = Pi 任务代理服务器

## 1. 背景与目标

用户为 2026-09 入学的 CS 研究生，研究方向待定，需尽快产出科研结果。目标：建立一套**方向无关的科研生产力系统**，以 CC 为编排中枢，将现有三台硬件（Windows 本机、树莓派 4B、核桃派 1B）、已安装 skills（academic-research-engine、nature-* 等）、已运行的 usage-monitor、微信桥接与 dsh/Codex 整合为统一的工作流：

**CC = 大脑（编排+决策+复查），Pi Broker = 常驻调度服务器（队列+派发+中间结果），dsh = 手脚（批量执行），核桃派 = 展示/物理 I/O，Codex = 副脑（交叉验证），haiku 子代理 = 勤杂工（简单工作），微信/邮件/墨水屏 = 人机通道。**

核心模式：**"派任务-执行-复查"闭环 + 控制面与执行面分离**——Windows（控制面）可以脱机，Pi Broker（执行面）7×24 常驻，任务不中断、中间结果落盘。

## 2. 硬件资产与角色分工

| 硬件 | 关键规格（已实测/已核实） | 角色 | 依据与约束 |
|---|---|---|---|
| Windows 本机 | i7-11800H 8C/16T、64GB RAM（2×32GB @3200）、**RTX 3060 Laptop 12GB VRAM**（nvidia-smi 实测 12288 MiB；Win32 AdapterRAM 字段 4GB 截断，不可信）、4 盘共 2.4TB、Win10 19045、Hyper-V 可用 | **指挥中枢 + 重计算 + 本地推理** | CC 驻地；docx/pptx、Playwright、OCR、git、微信桥均在本机；Node v24.15.0 满足 dsh；**12GB VRAM 可跑 7B-8B 量化本地模型**（断网 LLM 降级） |
| 树莓派 4B | BCM2711 quad A72，Raspberry Pi OS，当前跑 usage-monitor（`/home/liuxfs/usage-monitor`），SPI0，Waveshare 3.97″ 墨水屏 + LED 已跑通 | **Pi Broker：常驻任务代理服务器 + dsh 执行节点** | 7×24 常驻、Node arm64 可用；内存型号未确认（2/4/8GB）→ dsh 冒烟测试为第一步；**核桃派未完全验收前保留 4B 现有环境** |
| 核桃派 1B | 全志 H616/H618，**1GB 内存**，Debian 12，仅 SPI1（`/dev/spidev1.0`），user `pi/pi` | **展示/物理 I/O 层**（usage-monitor 迁移目标机）+ Broker 冷备候选 | 1GB 跑 dsh 风险高，不推荐；Flask 轻量展示可承载 |
| Liudfs-NAS（可选） | 桌面快捷方式存在，在线状态与容量待确认 | 冷备存储层（results/logs 异地备份，防 Pi SD 卡损毁） | 接入为可选项，细化 spec 前先与用户确认 NAS 常开状态 |

**分派原则：计算重在本机，调度与常驻在 4B，物理展示在核桃派，备份在 NAS（可选）。**

## 3. 软件资产与已有接口（对齐清单）

| 资产 | 接口/能力 | 本框架用法 | 不动项 |
|---|---|---|---|
| usage-monitor（Flask :5000） | `GET /api/dashboard`（全量 state）、`POST /api/status`（CC 状态上报）、`GET /health`；`X-Monitor-Token` 鉴权；APScheduler；墨水屏 worker 带 coalesce/失败退避；无硬件 mock 降级 | 展示层：扩展 orchestra 状态块（§6.4）；上报通道复用同一鉴权模式 | **不动 `~/.claude/settings.json`**（hooks 已停用）；不动现有三端点语义，只增量扩展 |
| 微信桥接（`.wechat-acp/bridge.mjs`，桌面 `微信桥接.bat` 启动） | 微信 iLink API ↔ Claude CLI **双向桥**（用户微信消息可驱动 CC 会话）；自带 QQ SMTP 邮件兜底（send_email.mjs）；跑在 Windows（依赖 fcc-server.exe 代理） | **通知与远程指挥通道**（§6.6）：出站推送任务结果/复查请求，入站接收用户微信指令 | 桥脚本本体不动；接入时只读其发送接口 |
| academic-research-engine | `.research/` 状态机；`validate_experiment_card.py` / `ingest_run.py` / `handoff_sync.py`；硬规则"数值只来自 ingest artifacts"、人在环 | 实验管线闭环的账本与摄入层（§6.2），脚本不改 | 不重造雷达/精读/验证 |
| nature-literature-pipeline 等 | 文献雷达 ingest 后端 | 夜间定时任务自然负载（Broker 常驻执行） | 不重写 |
| ~/.codex 残留 | `config.toml`、`auth.json`、`sessions/`、`memories/`、`plugins/`、`computer-use/`；VS Code `openai.chatgpt` 插件 | Codex CLI 装回后复用登录与历史（§6.3） | **勿删勿改残留** |
| v2rayN 代理 | SOCKS5 `127.0.0.1:10808`（Win） | API 连通性兜底（§7） | 不动配置 |
| 缺失项 | dsh（未装）、codex CLI（未装）、docker（未装）、Ollama（未装，断网降级用） | 安装方案见 §6.1/§6.3/§7 | — |

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
（可选）Liudfs-NAS：results/logs 冷备
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

**规则**：任务文件是唯一派发入口；CC 复查后写 `reports/` 并标注 `reviewed: ok|reject`；reject 标注原因留在 tasks/ 待重派或降级重派。

## 6. 子系统接口

### 6.1 子系统 1：Pi Broker 任务代理 + dsh 执行层（地基）

**Broker（4B，Python stdlib + systemd，不上 Redis/Celery——队列规模是个位数任务，勿过度设计）：**

- **队列持久化**：`broker.db`（SQLite WAL，Python 自带 sqlite3）；tasks 表字段：slug、executor、status（queued→running→done/failed）、attempts、net_req、result_path、时间戳
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
实验卡(card.md, commands 字段可无头执行) ──CC 审查──> Broker 入队 ──> dsh headless 执行
  ──> results/metrics.json ──ingest_run.py──> .research/experiments/EXP-*/runs/
  ──> CC 复查（数值一致性、对照 engine 硬规则）──> handoff_sync.py
```

- **接口约定**：实验卡 `commands:` 字段必须可无头执行；"卡"是接口，"执行"是可替换实现（人工/dsh/Codex 都能执行同一张卡）
- **engine 三脚本不改**，仅作为消费端；`program.yaml` compute mode 保持 `human_in_loop`
- **本地算力边界（v2 修正）**：12GB VRAM → **7B-8B 量化模型舒适**（q4 ≈ 5-6GB）、14B q4 临界；64GB RAM 可 CPU offload 更大模型；本地推理同时是断网 LLM 降级器（§7）
- **验收**：对照实验（单次 LLM 调用 vs dsh 多步 agent 同一抽取任务）数字全部走 ingest，无手抄数字

### 6.3 子系统 3：双 agent 验证（CC × Codex）

- **安装计划**：Codex CLI 重装（npm 全局），复用 `~/.codex` 残留登录与历史；VS Code `openai.chatgpt` 插件保留
- **通信方式**（已核实）：① `codex exec "任务" --json`（事件 JSONL 流，CC Bash 直调解析复查，主用）② 文件总线（orchestra 任务/结果）③ 会话 resume/fork（按 session ID 恢复或分叉）④ dsh 子代理 `-codex` 后端（Broker 跑通后启用）
- **三种模式**：互审（Codex 审 CC 代码，两边意见汇总，用户裁决）；独立实现（关键函数双实现跑同一测试，分歧处重点查）；claim 核验（adversarial-claim-check 双跑，结论不一致人工核查）
- **验收**：找一段历史代码让 Codex 独立审，验证分歧点是否命中真问题

### 6.4 子系统 4：仪表盘适配（usage-monitor 增量扩展）

- **state 新增 `orchestra` 块**：`{broker_health, queue_len, active_tasks, last_task, last_sync}`
- **新增 `POST /api/orchestra`**：Broker/编排器上报状态，鉴权复用 `X-Monitor-Token`；现有三端点语义不变
- **墨水屏**：新增"任务面板"视图（队列长度+活跃任务+Broker 健康）；`config.py` 增加 `SHOW_ORCHESTRA` 开关（默认 True），与已停用的 `SHOW_CC_CONTEXT` 并存
- **部署**：usage-monitor 与 Broker 同机（4B）或分机（核桃派）均支持——分机时仪表盘定时拉 Broker 状态 API（LAN HTTP）
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
- **降级链**：微信（需 Windows+iLink 外网）→ QQ 邮件（需 Windows+SMTP）→ 墨水屏/LED（纯 Pi 侧 LAN，最终兜底）
- **验收**：Broker 完成一个定时任务后，手机微信收到结果摘要；微信发"查任务"收到队列状态回复

## 7. 网络分区与离线降级

**LAN 是控制面骨干**（SSH 22、Flask :5000、Broker 任务 API）——本机↔路由器↔两 Pi 同网段，几乎不会断。**外网依赖清单**：LLM API（DeepSeek/Anthropic/OpenAI）、微信 iLink、QQ SMTP、arXiv/文献源、天气。

| 场景 | 降级策略 |
|---|---|
| 外网不稳/断 | ① 任务按 `net` 分级：optional（本地脚本/实验/文件处理）断网照跑；required（LLM/抓取）排队+指数退避重试（复用已有 USAGE_LOGIN_BACKOFF 模式）② API 连通性兜底：v2rayN SOCKS5（Win 127.0.0.1:10808）；Pi 可配 HTTPS_PROXY 走本机 ③ **LLM 本地降级**：Ollama 7B-8B q4（12GB VRAM），产出标注"本地模型降级" |
| Windows 脱机 | Broker 照常（队列/定时/LLM 任务不经 Windows）；复查延后；微信/邮件停用，告警走墨水屏/LED |
| LAN 断 | 系统停摆（最不可能）；Broker 侧任务状态已持久化，LAN 恢复后续跑，不丢队列 |
| 网络错峰 | 需外网的批量任务（文献抓取、大模型跑量）排在夜间网络稳定时段（systemd timer 定时） |

**原则：执行不依赖外网质量——任务要么断网照跑（optional），要么排队等网（required），没有"半途挂死"。**

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
| LLM API 不可达 | Ollama 本地模型（标注降级）或 required 任务排队 |
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
| 4B 内存型号未确认，dsh 内存占用未实测 | 冒烟测试为子系统 1 第一步；Minimal 起步 |
| Pi SD 卡写磨损（队列/checkpoint 频繁写） | SQLite WAL + checkpoint 低频落盘；NAS 冷备（可选，待确认 NAS 常开） |
| Broker 单点（4B 挂则常驻层停） | 核桃派冷备；队列目录 git 同步，手动切换（自动化主备切换明确不做，过度设计） |
| 核桃派 1GB 明确不跑 dsh | 角色定为展示层；usage-monitor 迁移是否完成需用户确认 |
| dsh 开发者预览（rc.7）接口可变 | 锁版本；升级看 changelog；执行层可替换（降级链） |
| Windows 无 docker | headless 流程不需要；Hyper-V 可用，未来需要再评估 |
| 开放问题 | 4B 内存容量、dsh 在 4B 实测内存、Codex CLI 登录方式、NAS 在线状态、bridge.mjs 推送接口、核桃派迁移状态——各子系统细化 spec 的 smoke test 解决 |

## 13. 验收标准（总 spec 级）与后续细化清单

总 spec 验收 = 六子系统各有一个可执行 smoke test 定义（§6 已列），用户审阅本 spec（v2）通过。

后续细化 spec（逐个编写，建议顺序）：
1. `subsystem-1-pi-broker`（Broker 部署：队列/dispatcher/checkpoint/resume + 4B dsh 安装与冒烟）★最先
2. `subsystem-2-experiment-loop`（实验卡命令字段约定 + ingest 对接）
3. `subsystem-3-codex-dual-agent`（CLI 安装 + 三模式脚本化）
4. `subsystem-4-dashboard-orchestra`（state/orchestra + 墨水屏面板 + 上报脚本）
5. `subsystem-5-haiku-dispatch`（rules.yaml 结构与判定清单）
6. `subsystem-6-wechat-channel`（读 bridge.mjs 确认推送接口 + 出站/入站接入）
