# Research Orchestra 项目全景记录（第三方审查版）

> 生成：2026-08-19 ｜ 范围：本项目（Research Orchestra，科研-实验-论文框架）从最初讨论至今的完整过程记录
> **更新：2026-08-20 ｜ 本次覆盖：mission 028-033（GitHub 上传 / 模型路由 / 并发两档实战 / SOL 协作者重构合并与深审 / 修复包落地 / skill 打包与兼容度分析）、教训库机制、阶段定位（工程收尾转道）——状态快照至 mission 033**
> 用途：供第三方审查项目决策链、执行质量与当前状态
> 所有事实均可在文末「原始记录索引」中溯源验证
> 说明：本文档已合并总架构 spec（v7）的前提与背景信息（见 §1.4）；**总 spec 全文本身亦是审查对象**（见 §8 索引），本文档不替代 spec 正文

---

## 0. 一句话概括

**用户在 2026-09 入学 CS 研究生前，搭建一套"方向无关的科研生产力系统"**：以 Claude Code（CC）为编排大脑、树莓派 4B 为 7×24 任务代理（Broker）、DeepSeek Harness（dsh）为无头执行引擎、核桃派为展示/异地冷备，覆盖「夜间文献雷达 → 实验管线闭环 → 论文产出」全链。08-18 ~ 08-19 完成总架构设计与 4 个已验收子系统；08-20 完成：GitHub private 仓协作（协作者 SOL 重构合并 + 深审 + 修复包全落地）、模型路由表（dsh 两档 + codex 三档）、**并发两档工作模式实战**（标准档 4-8 路 030/032、树状档 2 层≤12 叶子 031 首跑）、skill 快照打包与兼容度分析、教训库机制（26 条，三层知识锚）。**阶段定位（用户定调）：工程收尾复核，【术】已足够，转入【道】——新任务优先论文/研究实体。**

---

## 1. 项目起源与目标（最初讨论）

### 1.1 背景

- 用户为 2026-09 入学的 CS 研究生，研究方向待定，需尽快产出科研结果
- 已有资产：Windows 本机（CC 驻地）、树莓派 4B、核桃派 1B、usage-monitor（墨水屏展示）、微信桥接、academic-research-engine 等 skills、DeepSeek Harness（dsh）

### 1.2 核心设计思想

1. **CC = 大脑（编排+决策+复查），Pi Broker = 常驻调度（队列+派发），dsh = 手脚（批量执行），核桃派 = 展示/物理 I/O，Codex = 副脑（交叉验证，已接入），haiku 子代理 = 勤杂工，微信/邮件/墨水屏 = 人机通道**
2. **控制面与执行面分离**：Windows 可脱机，Broker 7×24 常驻，任务不中断、中间结果落盘
3. **总 spec 优先 → 子系统逐一定稿**：先写总架构，再按建议顺序逐子系统细化 spec + 实施 + 验收
4. **执行可替换**：每层可替换（dsh 坏→Bash；Codex 无缝加入），不写死单点依赖
5. **学术诚信硬约束**：数值只来自 ingest artifacts（无手抄数字）、每 gate 人在环、负结果账本

### 1.3 硬件资产与角色

| 硬件 | 规格（已实测） | 角色 |
|---|---|---|
| Windows 本机 | i7-11800H 8C/16T、64GB、RTX 3060 Laptop **12GB VRAM**（nvidia-smi 实测，Win32 API 报 4GB 为字段截断假象）、Win10 | 指挥中枢 + 重计算 + 本地推理 |
| 树莓派 4B | quad A72、**2GB**（已确认）、2 张网卡 | Pi Broker：常驻任务代理 + dsh 执行节点 |
| 核桃派 1B | 全志 H616/H618、1GB、仅 SPI1 | 展示/物理 I/O（usage-monitor 在役）+ 异地冷备接收端 |

### 1.4 前提条件与已有资产（自总 spec §1-3）

**用户背景**（总 spec §1，与本文档 §1.1 一致）：用户为 2026-09 入学的 CS 研究生，研究方向待定，需尽快产出科研结果。目标：建立一套**方向无关的科研生产力系统**，以 CC 为编排中枢，将现有三台硬件（Windows 本机、树莓派 4B、核桃派 1B）、已安装 skills（academic-research-engine、nature-* 等）、已运行的 usage-monitor、微信桥接与 dsh/Codex 整合为统一的工作流。

**已有软件资产与接口对齐清单**（总 spec §3 全表；表中引用号为 spec 内章节号）：

| 资产 | 接口/能力 | 本框架用法 | 不动项 |
|---|---|---|---|
| usage-monitor（Flask :5000） | `GET /api/dashboard`（全量 state）、`POST /api/status`（CC 状态上报）、`GET /health`、**`POST /api/orchestra`（部分字段合并，2026-08-19 上线）**；`X-Monitor-Token` 鉴权（已全链路开启）；APScheduler；墨水屏 worker 带 coalesce/失败退避；无硬件 mock 降级 | 展示层：orchestra 融合面板（spec §6.4 已验收）；上报通道复用同一鉴权模式 | **不动 `~/.claude/settings.json`**（hooks 已停用）；不动现有三端点语义，只增量扩展（已按增量执行） |
| 微信桥接（`.wechat-acp/bridge.mjs`，桌面 `微信桥接.bat` 启动） | 微信 iLink API ↔ Claude CLI **双向桥**（用户微信消息可驱动 CC 会话）；自带 QQ SMTP 邮件兜底（send_email.mjs）；跑在 Windows（依赖 fcc-server.exe 代理） | **通知与远程指挥通道**（spec §6.6）：出站推送任务结果/复查请求，入站接收用户微信指令 | 桥脚本本体不动；接入时只读其发送接口 |
| academic-research-engine | `.research/` 状态机；`validate_experiment_card.py` / `ingest_run.py` / `handoff_sync.py`；硬规则"数值只来自 ingest artifacts"、人在环 | 实验管线闭环的账本与摄入层（spec §6.2），脚本不改 | 不重造雷达/精读/验证 |
| nature-literature-pipeline 等 | 文献雷达 ingest 后端 | 夜间定时任务自然负载（Broker 常驻执行） | 不重写 |
| ~/.codex 残留 | `config.toml`、`auth.json`、`sessions/`、`memories/`、`plugins/`、`computer-use/`；VS Code `openai.chatgpt` 插件 | Codex CLI **0.148 已装回并复用登录与历史**（spec §6.3 已验收，mission 027） | **勿删勿改残留**（验收核过 auth.json md5 零改动） |
| v2rayN 代理 | SOCKS5 `127.0.0.1:10808`（Win） | API 连通性兜底（spec §7） | 不动配置 |
| 缺失项 | ~~dsh~~（已装 0.1.0-rc.7，4B+Windows 双侧）、~~codex CLI~~（已装 0.148.0，复用 ~/.codex 登录）、docker（未装）、Ollama（未装，断网降级用） | 安装方案见 spec §6.1/§6.3/§7 | — |

**与 spec 时点的差异（现状）**：缺失项中，dsh 已在 4B 与 Windows 均安装并锁版本 0.1.0-rc.7（Mission 021，冒烟实测通过）；codex CLI 已装回 0.148.0 并复用 ~/.codex 登录（Mission 027，残留零改动）；docker、Ollama 仍缺。微信桥的邮件兜底已演进为 Pi 直发 24/7（Mission 023 实测；spec §6.6 已含该修正说明）；usage-monitor 已增量新增 `POST /api/orchestra` 并全链路开启鉴权（Mission 026）。总 spec 已迭代至 v7（§13 验收清单勾 subsystem 1/2/4，subsystem-3 状态行定稿）。

**模型调度策略表**（总 spec §8，out of scope）：用户另行安排，后续讨论。本框架只约定：策略表位于 `orchestra/config/model-routing.md`，**用户维护、系统只读**；执行器（dsh/codex）模型选择最终以策略表为准，spec 不预设模型-任务绑定；usage-monitor 已有用量/成本采集，成本量化直接消费现有数据（spec §3 接口不动）。实体背景：用户自建 fcc-server（API 代理/模型路由工具链，管理端 http://127.0.0.1:8082/admin），模型调度由用户自理，本框架勿动其配置。

**与 OpenClaw / Hermes 的定位澄清**（总 spec §15）：本系统与 OpenClaw、Hermes Agent 同属「常驻 7×24 的个人 AI 基础设施」大类（IM 通道 + 定时任务 + 记忆持久化 + MCP 工具 + 模型无关），形态收敛是 2026 年个人 agent 的成熟模式，但实现哲学不同（CC 是脑、本系统只做编排胶水层、定位科研生产线），不构成重复造轮子。**决策：不切换到 Hermes/OpenClaw；借鉴其设计模式（通道网关、hook 机制、记忆设计）；OpenClaw 作为未来通道网关候选仅在微信桥失效时再评估（YAGNI）。**

---

## 2. 总体架构（架构定稿于总 spec v4，总 spec 已迭代至 v7）

三层架构 + 四条总线：

```
┌─ 控制面（Windows，可脱机）─ CC + haiku 子代理 + 微信桥 ─┐
├─ 服务面（4B，7×24）─ Pi Broker：SQLite WAL 队列 + dispatcher + systemd timer + dsh headless ─┤
└─ 展示/物理面（核桃派）─ usage-monitor 墨水屏/LED + 冷备接收 ─┘
```

总线：① 文件总线（tasks/results/logs/reports）② 同步总线（v1 用 scp，见 §3 Mission 021）③ HTTP 上报（POST /api/orchestra，subsystem-4）④ SSH 直调

**六子系统路线图**（总 spec §6/§13，验收 = 各有一个可执行 smoke test）：

| # | 子系统 | 状态 |
|---|---|---|
| 1 | Pi Broker 任务代理 + dsh 执行层（地基） | ✅ 已验收（mission 021） |
| 2 | 实验管线闭环（engine × dsh） | ✅ 已验收（mission 025，对照实验两臂数字全经 ingest 入账） |
| 3 | 双 agent 验证（CC × Codex） | ✅ 已验收（mission 027，独立审命中率 3/3 = 100%） |
| 4 | 仪表盘适配（usage-monitor 扩展） | ✅ 已验收（mission 026，墨水屏融合面板 + 30s 状态上报 + 鉴权） |
| 5 | 编排层（模型路由 + 并发分派规则） | ✅ 已落地（029 路由表 + 030/031/032 并发两档实战；约定 `docs/superpowers/specs/2026-08-20-concurrent-work-modes.md`） |
| 6 | 通知与远程指挥通道（微信桥接入） | ⏳ 未开始（降级链已就绪：QQ 邮件 Pi 直发 + 墨水屏） |

---

## 3. 时间线与各阶段记录

### Mission 020（08-18 ~ 08-19）总架构 spec — ✅ 完成

**目标**：编写总架构 spec，对齐已有资产接口，纳入三台硬件约束。

**关键决策**（全部记录在 mission DECISIONS.md）：
- **三层架构升级**：应「主机脱机任务不中断」需求，从四层收敛为三层；明确不上 Redis/Celery（队列规模个位数，过度设计）、主备自动切换明确不做（手动冷备）
- **VRAM 修正 12GB**：用户指出 3060 无 4GB 版本 → nvidia-smi 实测 12288 MiB → 本地推理边界升级为 7B-8B q4 舒适
- **断网策略**：重型 LLM 任务断网 = 排队断点续传（dsh resume），**不用本地小模型硬扛**，默认不装 Ollama
- **微信桥接接入**（§6.6）：桥本体不动，只读其发送接口
- **模型调度策略表划出 scope**：用户自管（fcc-server 管理端 127.0.0.1:8082/admin），框架只预留只读接口
- **存储决策**：2280 SSD USB3 转接盒直挂 4B（唯一立即推荐采购）——后被 U 盘方案替代（见 mission 024）

**过程**：spec 经 v1→v7 七轮迭代（v2 VRAM/三层、v3 SSD/断网/采购、v4 事实落盘、v5 实验闭环验收、v6 仪表盘验收、v7 双 agent 落地），用户 PASS，最终哨兵审计 PASS（4 个 LOW 全处理）。

---

### Mission 021（08-19）子系统 1：Pi Broker + dsh 执行层 — ✅ 已验收

**目标**：4B 部署常驻任务代理 + dsh，跑通「派任务→执行→复查」闭环，2GB 内存冒烟作 Pi 5 升级决策门。

**关键决策与发现**：

1. **同步总线 v1 用 scp 替代 git 同步总线**（偏离总 spec §4，记录在案）：已实测仓库无 git remote、Windows 无 sshd、Git Bash 无 rsync——scp 零新依赖；Windows 侧 git 负责版本化。为匹配措辞而新建 remote/启用 sshd 属过度工程。
2. **任务模板裁掉 priority/schedule/acceptance 三字段**（YAGNI）：priority 在个位数队列无意义；schedule 由 systemd timer 承担；acceptance 由 CC 复查（reports/）承担。
3. **dsh 2GB 冒烟决策门 GO**：3 次 headless 冒烟全部 exit 0，峰值内存 519/497/513 MiB（门槛 1536），无 OOM——**不需要 Pi 5 升级**（省 ~500 元）。E2E 真实任务二次确认峰值 545 MiB。
4. **dsh 沙箱重大发现**（E2E 实战）：workspace-write 仅允许写会话工作区与 /tmp；headless 无审批渠道、升级请求一律 denied。修复：executor 将 dsh 进程 cwd 设为 attempt 输出目录。该发现对后续所有任务设计有约束意义。
5. **安全**：broker 以 liuxfs 运行（修复 root 运行 DB 属主问题）；DEEPSEEK_API_KEY 经 systemd drop-in（env.conf）注入，不进仓库、重部署不丢。

**验收结果**（E2E 三场景全过）：
- dsh 任务全闭环：arXiv 抓取 3 篇 → attempt-2 产出合法 JSON，18 秒
- Windows 脱机 20 分钟：shell 任务 5/5 心跳全齐（用户确认期间关机）
- 中断恢复：systemctl stop 杀运行中任务 → recovered → 自动重试 → done

**期间修复 7 个问题**（npm EACCES、dsh 凭据 600、drop-in 注入 key、User=liuxfs、result 字段约定、PATH 注入、deploy 传 config）。25 测试绿、哨兵审计 PASS（2 MED 4 LOW 全处理）。

---

### Mission 022（08-19）核桃派冷备链（NAS 方案 A）— ✅ 已验收

**目标**：核桃派作为异地冷备接收端，每日增量备份 4B broker 数据 + samba 共享 + 恢复演练。

**关键决策**：
- 备份通道 rsync over ssh（免密密钥、不开新端口）；samba 供 Windows 浏览
- **部署拓扑（用户确认）**：4B=宿舍（Broker），核桃派=实验室（展示+冷备）——异地冷备比同房间高一个安全等级，墨水屏白天在实验室可见

**验收结果**：6/6 通过——每日 03:00 定时备份（Persistent 兜底）、首备 25=25 文件 2s、SQLite 一致性经 `.backup` 快照（哨兵审计修复：此前 live wal/shm 不同步）、恢复演练 md5 完全一致、Samba 映射 Z: 读写验证通过。

---

### Mission 023（08-19）夜间文献雷达管线 — ✅ 已验收（2026-08-19 23:30 首次真实定时注入已启动）

**目标**：每日 23:30 自动注入 arXiv 抓取 → dsh 六维评分 → digest → QQ 邮件投递手机。

**关键决策**：
- 评分标准用 engine 真实六维（Topic 35/Method 20/Source 15/Network 10/Applied 10/Archival 10，topic<10 拒绝）——评分结果可入库复用
- **邮件从 4B 直发**（stdlib smtplib）：实测 Pi 侧发送成功 → 修正总 spec §6.6 "邮件需 Windows" 的过时表述。降级链更新：微信（Windows）→ QQ 邮件（Pi 24/7）→ 墨水屏
- 邮件投递采用持久 at-most-once 状态：发送前写 `sending`，成功后写 `sent`；发送器明确报告未发送时写 `not_sent` 并允许重试，进程中断、锁冲突或模糊结果转为 `unknown` 并拒绝自动重发
- 任务文件终态自动归档（防积压）+ 非法文件 .bad 归档
- housekeeping 周日 04:00：dsh sessions 清理（+14 天）+ 磁盘告警邮件
- **当前实现已阶段化**：单体任务拆为 `fetch → rank → render → notify`，通过可选 `depends_on` 串联；同日期注入原子互斥，Linux owner 以 PID+进程 starttime 防 PID 复用并可接管崩溃遗留 marker 补跑（无 `/proc` 时兼容回退）；rank 按 `arxiv_id` 精确核对 fetch 的 `title/url/categories/abstract`，并校验数量、ID 集合和 SHA-256；上游失败时下游不消耗重试次数，各阶段可独立恢复

**dry-run 全链路验证**：真实抓取 60 篇 → 按 arXiv ID 去重 57 → 六维评分 → 选 5 篇（76/73/72/72/72）→ 邮件发送成功。中断恢复实战：attempt 1 被重启杀死 → 自动重试完成。

**哨兵审计**（对抗性审计）：8 个 CONCERN 全部处置（commit 2e4221f，29 测试通过），包括：
- 高：备份脚本从未随 deploy 传载（迁移后静默备份旧副本）
- 高：deploy 只 enable 不 restart（新代码不生效）
- 中：executor 异常未落库（任务永久卡 running）
- 中：超时只杀子进程（dsh 孤儿）→ Popen + 进程组 killpg
- 中：邮件无幂等 → 重复发信
- 其余：timer 时区、双分区磁盘检查等

---

### Mission 024（08-19）存储迁移：SD → U 盘 — ✅ 完成（含一次硬件事故）

**目标**：broker 数据从 SD 卡迁到 U 盘直挂 /mnt/broker（免 SD 磨损）。起因：用户觉得 512GB SSD 用在此处浪费 → 改插 U 盘。

**金士顿 U 盘事故（重要教训）**：
- 第一次：mkfs 完成后 mount 步骤用户态 D-state 卡死——ICMP 存活、SSH 死
- 第二次：deploy 重启 broker 后 WAL 写入 → 整机失联（ICMP 100% 丢包）
- 证据链指向盘固件/供电组合问题 → **弃盘**（盘内 1.2GB 用户数据已确认无用）
- **暴露的运维纪律**：①迁移分步执行、每步验证；②Pi 失联先 ping 再判死；③宕机恢复后先稳定主路径再尝试新硬件

**闪迪 16G 二次尝试（用户换盘）→ 成功**：
- 诊断流程升级：ro 挂载 → dd 直接写测试 → **SQLite WAL 冒烟**（金士顿死点）分步验证，全过才迁移
- fstab 按 UUID + nofail 挂载（U 盘故障开机不挂起，OnFailure 告警链兜底）
- 迁移后独立审查全部通过：broker active、db 路径正确、rsync dry-run 0 差异、冒烟任务 done、三个 timer 在役、金士顿 UUID 行已清除
- **SD 旧副本（636K）保留作回退**，删除待用户确认

---

### Mission 025（08-19）子系统 2：实验管线闭环（engine × dsh）— ✅ 已验收

**目标**：实验卡接入 Broker 执行层，跑通「实验卡 → CC 审查 → Broker 入队 → dsh/shell 无头执行 → metrics.json → ingest_run.py 入账 → CC 复查」闭环。

**核心接口约定**（细化 spec 已定稿，`docs/superpowers/plans/2026-08-19-subsystem-2-experiment-loop.md`）：
- 实验卡新增 `## Commands` 段：fenced bash block、无头可执行、`# arm:` 臂标记（多臂实验）、数值只来自 run artifact（最后一条命令产合规 metrics.json）
- 「卡是接口、执行是可替换实现」（人工/dsh/Codex 都能执行同一张卡）
- engine 三脚本（validate/ingest/handoff）**零改动**，仅作消费端
- demo 研究根隔离在 `orchestra/demo/.research/`（不污染未来真实研究 vault——用户研究方向未定）

**验收结果**（对照实验，验收报告 `orchestra/reports/2026-08-experiment-loop-acceptance.md`，reviewed: ok）：
- 同一抽取任务两臂均经 Broker 执行 done：shell 单次 LLM 调用（1.6s）与 dsh 多步 agent（23.8s），各产出合规 metrics.json
- 两臂 metrics 全部经 `run_card.py ingest`（engine ingest_run.py）入账：卡 Run log 两行 + runs/ 两份 metrics.json——**数字全部来自 ingest artifact，无手抄**
- demo 环境与 EXP-001 对照实验卡（通过 engine validate，program.yaml human_in_loop），研究根隔离 `orchestra/demo/.research/`
- run_card.py 33 单测全绿；engine 三脚本与 Broker 代码零改动
- 关键 commit：9826afd（run_card.py TDD）、395e3dd/182c24c（demo+EXP-001 卡）、7e25ca9（两臂执行 done）、05c0aca（总 spec v5，实验闭环节定稿）
- 哨兵审计通过，mission 归档 completed/

---

### Mission 026（08-19）子系统 4：仪表盘适配（usage-monitor × Broker）— ✅ 已验收

**目标**：把 Broker 队列状态搬上核桃派墨水屏——usage-monitor 增量新增 `POST /api/orchestra` 端点与 orchestra 状态块 + 墨水屏融合面板，Broker 上报扩展 recent_tasks/host，Windows sync 脚本上报 last_sync，打通「Broker 执行 → 墨水屏可视」链路。

**关键决策与亮点**：

1. **融合单面板（D9 转向，用户拍板）**：初版四卡版被用户批评信息层级倒挂 → 融合单面板：状态条 + 最近任务列表 + 设备状态区（4B 在线/负载/内存 + 核桃派自身）+ DeepSeek/天气小字行；标题栏死 CC 控件移除（hooks 已停用、无上报源）。SHOW_ORCHESTRA=False 回退旧闲置面板。
2. **Broker reporter 线程 30s 状态上报**：report_status 拆出 build_payload + 独立 reporter 线程——主循环同步执行期间持续上报，**长任务执行中面板不误报离线**（验收报告含「运行中帧」实测证据）。
3. **D14 修复墨水屏刷屏风暴**：last_report 时间戳原先进刷新 hash → 每 30s 上报即整屏闪烁；将其移出 hash 后**内容变化才全刷**，时间戳/负载抖动只走局刷。
4. **鉴权**：X-Monitor-Token 在两 Pi 间流转（核桃派 override.conf / 4B config.json 600 权限），全链路开启，token 零泄漏不入库。
5. **D17 事故（1A 适配器供电）**：5V1A 适配器导致 4B 用户态整体死亡（ping 活/服务死），用户实机反馈根因，**教训入档**（电源规格核查入运维纪律）。
6. 同 mission 内落地两项基础设施：Tailscale 三端组网（D13，见 §5）、4B 兼职 NAS（西数 250G，见 §5）。

**验收结果**：8/8 全部实测满足——鉴权（无/错 token 401 + 部分字段合并回显）、orchestra 块（recent_tasks/host/last_report）、30-60s 推送刷新（API 响应存档）、融合面板渲染与回退、demo 任务三帧快照 PNG、last_sync 上报（实测 ~13s 新鲜）、零回归（broker 41 单测 = 基线 29 + 仪表盘新增 12；usage-monitor 现有测试全通过，三端点语义不变）、验收报告 reviewed: ok。验收报告 `orchestra/reports/2026-08-dashboard-acceptance.md`。关键 commit：0856976（融合面板 D9）、4e3e73c（D14）、ea0c907（reporter 线程）、d7cd05a（last_sync）、4686c9c（spec v6 + README 仪表盘节）。

---

### Mission 027（08-19）子系统 3：双 agent 验证（CC × Codex）— ✅ 已验收

**目标**：装回 Codex CLI（复用 ~/.codex 残留登录与历史），跑通 `codex exec --json` 直调主通道，把三种双 agent 工作模式（互审/独立实现/claim 核验）脚本化，并以「历史代码独立审」验收分歧点是否命中真问题。

**关键决策与亮点**：

1. **Codex CLI 0.148.0 装回，复用 ~/.codex 登录（免重新登录）**；残留零改动（auth.json md5 核一致；config.toml 差异为 codex 自写缓存、无凭据字段，接受为良性）。
2. **codex_exec.py 直调封装**（`orchestra/scripts/codex_exec.py`，410 行 stdlib-only）：NDJSON 事件解析 / 超时树杀（Windows taskkill /T）/ 7 类错误分类 / git 信任检查（非 git 目录自动 `--skip-git-repo-check`），43 mock 测试 + 真实调用复核通过；顺带修复 Windows .cmd shim 管道句柄继承 bug（kill cmd.exe 后 node 孙进程持管道挂死）——即 finding #3 的类证来源。
3. **codex_modes.py 三模式脚本化**（`orchestra/scripts/codex_modes.py`，570 行）：互审（mutual-review，宽容提取 + parse_failed 降级）/ 双实现（dual-implement，同测试集双跑 + 机械分歧三 kind）/ claim 核验（claim-check 双判定 + disagree 单列），48 mock 测试；scripts 全量 124 测试零回归（76 既有 + 48 新）。
4. **验收 = codex 独立审在役 `broker/executor.py`**：3 条 finding 经 CC 逐条源码独立复现判定**全为真问题**——#1 result_dir 路径逃逸（`taskfile.py:48` 原样透传 + `executor.py:29` 直接拼 Path，绝对路径/`..` 可越界写 results 树）、#2 attempt 目录分配 TOCTOU 竞态（当前串行不可触发，修复 ~2 行）、#3 Windows 超时只杀直接子进程留孤儿（Pi 侧已 killpg 修复，Windows 开发路径裸奔）；0 误报 0 风格，全为新问题且与已知缺陷档案三区域（cwd/attempt/超时）吻合无一重复 → **命中率 3/3 = 100%**。
5. **3 条 finding 按「Broker 零改动」约束不修**（path 校验 1 行 / 原子 mkdir 2 行 / Windows taskkill /T 沿用 codex_exec 既有模式），列候选待 Pi 部署窗口（见 §6）。
6. 通信方式②③能力存在性验证：`codex exec resume`（按 UUID/thread name 续接、`--last`）/`fork`（按 UUID fork 新会话）均存在，v1 不脚本化；意外发现内置 `codex exec review` 子命令与 `--ephemeral`、`-o/--output-last-message`、`--output-schema`（v2 候选）。
7. 互审调用史教训：本机 codex 冷启动 ~128s（WS 重连回退 HTTPS）；600s 超时不够 → context 加「只用提供内容、不动工具」抑制仓库探索 + `--timeout 1800` 成功——**抑制仓库探索是本机跑通互审的关键**；后台任务等待禁用长前台 sleep 轮询（harness 误杀教训）。

**验收结果**：AC 8/8 全成立，零回归（broker 41 / scripts 124 全过，usage-monitor/面板/雷达零改动）；验收报告 `orchestra/reports/2026-08-codex-dual-agent-acceptance.md`（reviewed: ok，哨兵终审通过）；codex 原始 findings 逐字存档 `orchestra/reports/artifacts/codex-review-executor.json`。commit 序列：dd23902（计划）→ eb7cf6e（codex_exec.py）→ 980f266（codex_modes.py）→ cf045f6（验收报告）→ 35427f7（spec §6.3 定稿，总 spec v7）→ 2e0a9de（哨兵处置）→ d6e7f61（双 agent 头脑风暴存档待选）。

---

### Mission 028-029（08-19 ~ 08-20）GitHub 上传 + 模型路由表 — ✅ 完成

- **028**：全景记录更新、GitHub private 仓 `wocessade/research-orchestra` 建成推送（1606=1606 文件一致）、协作者 zouxinhao0122 write 邀请、拓扑拆双图（总体架构+实验数据流，双 PASS）、秘密扫描修复（deploy 硬编码密码环境变量化）
- **029**：模型路由表落地——`orchestra/config/model-routing.json`（用户维护、系统只读：dsh 雷达评分 flash / 实验 pro；codex 三档 Luna 杂活含视觉 / Terra 默认 / Sol 关键场景，production-fix 归 CC）；任务卡 `model: flash|pro` 字段 → executor 映射 dsh `--patch`（**实测陷阱：--patch 整体替换非深合并**）；端到端实证 flash 冒烟 26.7s done

### Mission 030（08-20）并发标准档首秀 + executor 027 findings 修复 — ✅ 已验收

- 用户定调并发工作方式：**opus 只接口（分析/派发/收敛审查/统一 commit），agent 不 commit**
- 3 路 haiku 并行修复 027 审出的三条 finding（result_dir 逃逸 / attempt TOCTOU / Windows taskkill 树杀），副本隔离+diff 回流+验收解耦，验收 agent fidelity 逐行核对 100%
- 同日协作者推送 **SOL 输出质量重构**（2974f61，35 文件 +4197/-190：artifact 校验 exit 0≠成功、mode/detail 提示词、雷达四阶段化、depends_on 调度图、注入互斥、Skill ingest 门禁、deploy 预检）——与本地 029 模型路由 8 提交 + 030 修复撞车

### 合并与 Mission 031-032（08-20）SOL 深审 + 修复包 — ✅ 全闭环

- **合并**（a2d31b8）：用户拍板"先 commit 030 再合并"——4 文件 10 冲突块人工裁决，原则"SOL 主体 + 保留 029 路由 + 并入我方 taskkill timeout=10"；修复 4 处 Windows 测试可移植性问题；broker 102 / scripts 154 全绿
- **031 树状档首跑**（2 层×3 opus 子树×≤12 haiku 叶子 + 1 codex 交叉验证 leaf）= SOL 提交深审：**1 HIGH + 12 MED**（HIGH=check_skills Windows 路径逃逸；2 处多视角独立命中、0 假阳性；codex leaf 320s 跑通，GBK 编码坑入档）；验收 agent 亲核全部 HIGH/MED 证据属实；复盘数据回填约定文档（覆盖矩阵/根统一标尺/叶子落盘/GBK 四条新纪律）
- **032 小包 A**（739fdfd）：12 条 finding 全按报告方案修复（TDD 先红后绿，5 路 haiku in-place 并行零冲突），验收 12/12 PASS；broker 116 / scripts 161 全绿
- 教训库机制上线：`docs/lessons-learned.md`（26 条，4+1 类，维护协议=每 mission 归档必须追加）+ CLAUDE.md 锚 + memory 个人层

### Mission 033（08-20）Skill 打包 + 兼容度分析 + 密码整改 — ✅ 完成

- 协作者反馈找不到 skill → 10 个科研 skill 快照入仓库 `orchestra/skills/`（秘密扫描干净、漂移声明 README）
- 兼容度分析（`docs/reports/2026-08-skills-orchestra-compat.md`）：pipeline vs 雷达裁决雷达为权威（validator/SHA/at-most-once 已上线）；pipeline 独有增量（PDF 精读/Zotero 归档）并入 9.8 计划；ingest→engine 强耦合唯一阻断=digest 未锁定；weekly-review 交互型不可进 dsh
- 4B 登录+samba 密码整改完成（非交互链：密钥认证+sudo -S+chpasswd，反验通过）；NAS 经 Tailscale 外网可用（445 实测 P2P 直连）
- nature-image2ppt（上游 nature-skills 新 skill）审查并安装：图片→可编辑 PPT 重建，与 PPTSkill 互补（重建 vs 新做）

---

### Mission 034（08-20）GUI 控制台 v1 — ✅ 完成（终审 READY TO MERGE，已 push）

**目标**：以双层日历为核心的只读控制台，解决墨水屏信息密度不足 + CC 后台反馈受限（两痛点同源=缺汇合面）。设计 spec `docs/superpowers/specs/2026-08-20-console-design.md`，实施计划 `docs/superpowers/plans/2026-08-20-console-v1.md`。

- **选型**：现成方案调研后定 Homepage（gethomepage v2.0.0 源码装 D:\Apps\homepage，node 直跑）——calendar widget 原生 ical 集成 + customapi + iframe 三件套；自研 FastAPI 被否决（用户：只做兼容修改不从 0 写）；Glance 日历无事件、Vikunja 无状态面板被否决
- **glue**：`orchestra/console/` stdlib-only（console_feed.py refresh/serve + feed_schedule/messages/status/radar/serve 五模块，69 unittest 全绿）；四页 tab（今天/雷达/任务实验/系统）；双层日历双 ICS（system 定时器镜像 + personal 手录）；messages.md 留言/待决/告警（热重秒级）；Pi 侧零改动（只读 GET /api/dashboard + sync_pull 本地快照）
- **关键决策**：只读+决策面板（审批/派任务回对话留痕）；Windows 本机 web（v1.5 可开 tailnet）；自启=schtasks refresh 每 10 分钟 + 启动文件夹 serve/Homepage（onlogon 计划任务非提权被拒，用户拍板）；Homepage v2 内置鉴权门留作 v1.5
- **验收**：日历 vs Pi timer 逐条核对 / 留言往返 ≤5s / 断网降级演练 / 四页截图（D:\Temp\console-acceptance\）全 PASS
- **过程收获**（8 任务 subagent-driven，15 轮审查+修复循环）：终审抓出 mock 夹具契约错位（4B 永远离线的隐形雷，读 monitor 真源码才暴露）；计划示例代码 4 处内在矛盾全部收敛修复；ICS 双 CR（Windows write_text 换行翻译）字节级实证并防回归；教训入库 L27-L31

---

## 4. 关键议题与用户决策记录

### 4.1 手机桥接（讨论后暂缓）

- 设想：7×24 平台能否承接手机桥接？结论：微信桥不能搬（依赖 Windows iLink），NapCat QQ bot 可行
- **用户决定：QQ bot 暂缓**，其他继续推进

### 4.2 模型切换（dsh Pro/Flash）— ✅ 已落地（mission 029）

任务卡 `model: flash|pro` 字段 → executor 映射 dsh `--patch /mnt/broker/dsh-patches/{model}.yml`（patch 缺失任务 failed）。统一模型路由表 `orchestra/config/model-routing.json`（用户维护、系统只读）；codex 三档由 CC 查表传 `--model`。

### 4.3 工作方式演变

2026-08-19 用户强调「原子化操作给 haiku，你只负责大方向和审查」→ 定型分工 **opus 定方向 → haiku 执行 → opus 审查**（已写入持久记忆，mission 024 起严格执行）。

### 4.4 采购评估（零必购原则）

- 转接盒（~50 元）已购待用；Pi 5 升级（~500 元）被冒烟测试否决；N100 宿舍 NAS（~500-800 元）触发式待建；UPS（~100 元）断电频发时再买
- **原则：先用现成硬件跑出真实瓶颈，再按触发条件采购**

---

## 5. 当前基础设施状态（可现场验证）

| 组件 | 状态 |
|---|---|
| 4B Broker | systemd 常驻 active；db=/mnt/broker/db/broker.db（闪迪 U 盘 ext4）；WiFi 静态 192.168.0.250 |
| dsh（4B） | 0.1.0-rc.7 锁版本；冒烟峰值 545 MiB（2GB 板余量充足） |
| 定时任务 | 23:30 夜间雷达注入 / 每日 03:00 冷备到核桃派 / 每日 04:17 nas-backup（4B 盘内备份）/ 周日 04:00 housekeeping（均含 Persistent + Asia/Shanghai） |
| 冷备链 | 核桃派 192.168.0.200（实验室）：rsync over ssh + samba Z:；恢复演练通过 |
| 仪表盘链路 | 4B reporter 线程每 30s `POST /api/orchestra`（recent_tasks + host 负载/内存）→ 核桃派融合面板（队列/活跃任务/最近任务/设备状态区）；X-Monitor-Token 鉴权（两 Pi 间流转，不入库）；Windows sync 脚本上报 last_sync（实测 ~13s 新鲜） |
| 4B 兼职 NAS | 西数 250G（sdb）ext4 挂 /mnt/nas（fstab UUID+nofail）+ samba `\\192.168.0.250\nas`（**Tailscale 外网可用：`\\100.111.75.58\nas`，2026-08-20 实测 445 P2P 直连**）+ nas-backup.timer 每日 04:17 rsync `/mnt/broker/{results,logs}` → `/mnt/nas/backup/broker/`；压测 31.7MB/s 写 / 33.1MB/s 读；源码 `orchestra/nas/`；定位：冷备 NAS（宿舍 NAS 预演）。**登录/samba 密码已整改（2026-08-20）** |
| Tailscale | 三端同 tailnet：4B=liuxfs 100.111.75.58 / 核桃派=walnutpi 100.64.2.60 / Windows=laptop-w0cessade 100.103.79.3；宿舍↔实验室互通方案就绪，入学后切换实测（决策树见 `orchestra/docs/school-network-switch.md`） |
| 告警链 | 服务失败 OnFailure 告警 → 磁盘/备份邮件告警（Pi 直发 QQ 邮件） |
| 降级链 | 微信（Windows 在线）→ QQ 邮件（Pi 24/7）→ 墨水屏（Pi） |
| usage-monitor | 核桃派在役（本项目只增量扩展：已新增 POST /api/orchestra，三端点语义不变） |
| GUI 控制台 | Homepage 127.0.0.1:3000 四页 tab（今天/雷达/任务实验/系统）+ glue serve 127.0.0.1:3100（stdlib）；refresh 每 10 分钟（schtasks）+ 自启走启动文件夹；只读消费 GET /api/dashboard + 本地 results 快照，Pi 零改动；使用说明 `orchestra/console/README.md` |

**夜间雷达**：2026-08-19 23:30 首次真实定时注入已验证通过（60 篇 → 去重 57 → 评分 → 选 5 → 邮件成功），此后每夜自动运行。

---

## 6. 遗留与待办清单

### 进行中
- 034-v2 控制台美化：已移交 SOL（任务书 `docs/superpowers/specs/2026-08-20-console-v2-beautify.md`，owner 授权不局限于 Homepage、红线五条、过度谨慎提示已写）

### 已归档
- mission 028-034 均已归档

### 已承诺后续
- **Pi 部署窗口（合并为一）**：SOL 重构（四阶段雷达/artifact 校验/taskkill 树杀）+ 小包 A 修复（notify 锁接管/send_email 拒信分类/inject 死循环防护/deploy stop 时序等 12 条）真机部署验证；notify 崩溃残留演练、inject 真实 /proc 首跑
- **digest 锁定**：skills.json expected_digest=null → 真实 ingest 当前 HARD 阻断；skill 快照已入仓库（`orchestra/skills/`），待用户审查后 `--lock-current --strict`（兼容度分析 docs/reports/2026-08-skills-orchestra-compat.md）
- **Broker codex executor**（总 spec §6.3 通信方式④ dsh 子代理 `-codex` 后端：Pi→OpenAI 网络路径未验证，需代理方案——DECISIONS 已记录，单独任务）
- **入学前（2026-09）**：宿舍-实验室互通实测 + Tailscale 切换执行（决策树见 `orchestra/docs/school-network-switch.md`）；**弱密码整改 4B 已完成，核桃派 pi 密码待上线后同步**
- **雷达→Zotero 直连（9.8 开学后设计）**：方向已定——Pi 侧 pyzotero 直连（复用 pipeline skill 协议），兼容度分析 P1
- subsystem-6（微信桥接入）

### 待用户拍板
- SD 旧副本 ~/broker-data（636K 回退副本）是否删除
- 512GB SSD 用途（宿舍 NAS/冷备扩容候选）
- 宿舍 NAS 何时建（N100 触发式）
- QQ bot 是否重启立项
- nature-image2ppt 已安装（2026-08-20），是否纳入正式工作流

---

## 7. 已知风险与开放问题（总 spec §12 摘录）

| 风险 | 状态 |
|---|---|
| 4B 2GB dsh 内存 | ✅ 已解（实测峰值 545 MiB，决策门 GO） |
| Pi 存储可靠性 | ✅ 已解（闪迪 U 盘，写入+WAL 冒烟通过；金士顿已弃用） |
| 墨水屏刷屏风暴 | ✅ 已解（D14：last_report 移出刷新 hash，内容变化才全刷） |
| 4B 供电（1A 适配器事故） | ✅ 已解（5V1A 适配器致 4B 用户态整体死亡——ping 活/服务死；用户实机反馈根因，教训入档：电源规格核查） |
| Broker 单点 | 核桃派冷备 + git 同步（自动化主备切换明确不做） |
| 校园网宿舍-实验室互通 | 降级为观察项：**Tailscale 三端已部署**，入学后实测切换（school-network-switch.md 互通决策树） |
| executor.py 路径逃逸/竞态/树杀缺口（027 codex 审出） | ✅ 已修（030 修复 + SOL 等价实现合并 a2d31b8 + 032 小包 A 加固；待 Pi 部署窗口验证） |
| SOL 重构安全边界（031 深审 1 HIGH + 12 MED） | ✅ 已修（032 小包 A，739fdfd，验收 12/12 PASS；Pi 部署验证挂账 B） |
| dsh 开发者预览接口可变 | 锁版本 0.1.0-rc.7；升级看 changelog |
| dsh 沙箱限制（workspace-write） | 已适配（cwd=attempt 目录）；对后续任务设计有约束 |

---

## 8. 原始记录索引（审查溯源）

### 设计文档
- 总架构 spec（**v7**）：`D:\pythonProject\docs\superpowers\specs\2026-08-18-research-orchestra-design.md`
- **总架构 spec 全文（审查对象本身**——本文档 §1.4 仅合并其前提与背景，spec 正文须逐节独立审查**）**
- 子系统 1 实施计划：`D:\pythonProject\docs\superpowers\plans\2026-08-19-subsystem-1-pi-broker.md`
- 子系统 2 细化 spec + 实施计划：`D:\pythonProject\docs\superpowers\plans\2026-08-19-subsystem-2-experiment-loop.md`
- 子系统 3 实施计划：`D:\pythonProject\docs\superpowers\plans\2026-08-19-subsystem-3-codex-dual-agent.md`；头脑风暴存档：`D:\pythonProject\docs\superpowers\plans\2026-08-19-dual-agent-brainstorm.md`（commit d6e7f61 归档，待选）
- 子系统 4 实施计划：`D:\pythonProject\docs\superpowers\plans\2026-08-19-subsystem-4-dashboard-orchestra.md`
- 对外拓扑图：`D:\pythonProject\docs\cc-workflow-topology.md`
- 学校网络切换预案（IP 依赖盘点/互通决策树/回退步骤）：`D:\pythonProject\orchestra\docs\school-network-switch.md`

### Mission 档案（含 MISSION 目标/STATE 进度/DECISIONS 决策链/BRIEF 简报/AUDIT 审计）
- `.tasks\completed\020_research-orchestra-spec\` ～ `.tasks\completed\033_skill-pack-upload\`（完整编号链：020-033；028 GitHub 上传 / 029 模型路由 / 030 并发标准档 / 031 树状档首跑 / 032 修复包 / 033 skill 打包）

### 验收报告与审查报告
- `orchestra\reports\2026-08-e2e-acceptance.md`（子系统 1 E2E 三场景）
- `orchestra\reports\2026-08-cold-backup-acceptance.md`（冷备链 6 项）
- `orchestra\reports\2026-08-experiment-loop-acceptance.md`（子系统 2 对照实验，数字全部引用 ingest artifact 路径，无手抄）
- `orchestra\reports\2026-08-dashboard-acceptance.md`（子系统 4，8/8，含长任务「运行中帧」实测证据）
- `orchestra\reports\2026-08-codex-dual-agent-acceptance.md`（子系统 3，命中率 3/3 判定表 + 口径与局限）
- `orchestra\reports\2026-08-output-quality-refactor.md`（SOL 输出质量重构自述报告；M-10 勘误已落地）
- `orchestra\reports\artifacts\codex-review-executor.json`（codex 原始 findings 逐字存档）
- `docs\reports\2026-08-sol-refactor-review.md`（031 树状档深审：1 HIGH + 12 MED，验收 agent 亲核证据）
- `docs\reports\2026-08-skills-orchestra-compat.md`（033 skill 组兼容度：重叠裁决/耦合/集成 P0-P2）

### 代码与运行配置
- `orchestra\broker\`（db/taskfile/executor/dispatcher、雷达校验/渲染/通知/迁移门禁，stdlib only；**当前 116 单测**）
- `orchestra\scripts\`（sync_push/pull、deploy_broker、backup_to_nas、run_card、check_skills、codex_exec、codex_modes 等；**当前 161 单测**）
- `orchestra\config\skills.json`（外部 Skill 严格 manifest；`run_card.py ingest` 在外部调用前执行摘要门禁）
- `orchestra\config\model-routing.json`（统一模型路由表：dsh 两档 + codex 三档）
- `orchestra\skills\`（科研 skill 快照包：10 个，2026-08-20，含漂移声明 README）
- `orchestra\nas\`（4B 兼职 NAS：nas_backup.sh 等）
- `orchestra\templates\nightly-radar-*.md`（雷达四阶段任务模板）
- `orchestra\README.md`（系统运行手册，含实验闭环/仪表盘链路/双 agent/4B NAS 节）
- `orchestra\docs\school-network-switch.md`（学校网络切换预案）
- `docs\lessons-learned.md`（系统运行教训库 26 条：每 mission 归档必须追加）
- `docs\superpowers\specs\2026-08-20-model-routing-design.md`、`2026-08-20-concurrent-work-modes.md`（路由/并发两档约定）
- 4B 侧：`/home/liuxfs/broker/`、`/mnt/broker/`、`/mnt/nas/`、systemd units + env.conf drop-in

### 协作记忆（跨会话）
- `C:\Users\19041\.claude\projects\D--pythonProject\memory\MEMORY.md`（索引）及同目录各 memory 文件

### git 提交链
- `D:\pythonProject`（早期关键 commit：0e659b7 spec v1、1a6c920 spec v4、e3e8222 dsh cwd 修复、2e4221f 哨兵审计修复、334ee9b User=liuxfs；027 区间：7e25ca9~d6e7f61；**028-033 关键：eee8589 030 三修复、a2d31b8 SOL 合并、0aa606d 并发约定、c236a4f/3c6fa62 031 深审报告、739fdfd 032 小包 A、180f1cb 教训库、9df8f00 skill 快照、3708d4d 兼容度分析、edfe665 密码整改收尾**）

---

## 9. 第三方审查建议关注点

1. **决策链完整性**：每项偏离 spec 的决定是否记录在 DECISIONS.md 并有理由（如 scp 替代 git 总线、模板字段裁剪、D9 融合面板转向）
2. **学术诚信机制**：ingest artifact 硬规则、「人在环」gates、负结果账本——已在 subsystem-2 对照实验完成首次实战（两臂数字全经 ingest 入账、无手抄），subsystem-3 验收判定亦全部引用 artifact 路径
3. **运维可靠性**：金士顿事故暴露的纪律（分步验证、WAL 冒烟、nofail、告警链）与 1A 适配器供电事故（ping 活/服务死判断法）是否已沉淀为长期纪律
4. **成本控制**：分工原则（haiku 执行/opus 审查）、模型路由用户自管、零必购采购原则
5. **可替换性**：执行层、存储层、通道层是否都留有降级路径

---

## 10. 审查者备注（历次合并时发现；2026-08-19 深夜复核）

1. **总 spec §2/§4 存储描述未同步**：spec 正文 §2（4B 行「存储」列）与 §4（存储注释）仍写「2280 SSD 经 USB3 转接盒直挂，系统与 broker 数据落 SSD」；实际已改为闪迪 U 盘 ext4 直挂 /mnt/broker（本文档 §3 Mission 024、§5）。spec §12/§14 已更新为 U 盘方案，但 §2/§4 未同步——审查 spec 时注意两处矛盾表述。**【2026-08-19 深夜复核】已解决**：总 spec v5 起 §2/§4 已同步为闪迪 U 盘表述（v7 现状一致），本条不再构成审查关注点。
2. **总 spec §5 任务模板未同步**：模板仍含 priority/schedule/acceptance 三字段；Mission 021 已裁掉这三字段（偏离记录在案，见本文档 §3 Mission 021 关键决策第 2 条）。审查 spec 时注意。**【复核】部分保留**：模板块仍展示三字段（规范形态），但 spec §5 正下方已加「v1 落地裁剪（mission 021 DECISIONS）」说明块——偏差已在 spec 内记录，本条降级为历史记录。
3. **本文档内部交叉引用指向有误**：§2 总线② 注「（v1 用 scp，见 §4.2）」，而 §4.2 实为「模型切换」章节，scp 偏离实际记录在 §3 Mission 021——该引用错误仅在此指出，原文未改动。**【复核】已解决**：本文档 §2 总线② 引用已修正为「见 §3 Mission 021」（mission 025 副线处置）。
4. **【2026-08-20 复核，协作者协作相关】**：协作者 SOL 重构（2974f61）与本地 029/030 工作撞车，合并裁决原则与过程见 §3「合并与 Mission 031-032」——同文件双轨改动的人工逐块裁决模式已入教训库 L17。SOL 自述报告存在 4 类"声称 vs 实现"偏差（notify 恢复原则、Windows 路径拒绝、traceback 泄漏、Skill 状态漂移），全部经 031 深审核实并已修复（032 小包 A）或勘误（M-10）。skill 快照包 `orchestra/skills/` 为 2026-08-20 快照，与 owner 本机活副本的关系见其 README 漂移声明。
