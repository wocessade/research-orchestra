# Bogda Gate 6 工作台与接班进度

日期：2026-08-24

目的：在模型额度和执行者切换后，以本文件作为当前唯一工作入口。不要从聊天记录重新拼装状态。

## 收班补记：下周从这里恢复

本节记录 2026-08-24 晚间最终状态；与下方较早快照冲突时，以本节和后续正式
Gate 报告为准。

- Git `main` 为 `4d8e470`（Task 5 已提交，尚未 push）；当前没有辅助 worktree。
- 3101 已完成 Windows 启动器真实 `start → status → stop → start → status`
  验收，当前由启动器托管且为 `healthy / mock-all`。它不是开机服务，电脑重启或
  睡眠后先运行 `bogda-console/scripts/local-console.ps1 status`。
- 3100 在真实启停验收前后保持不变；3101 仍未连接真实 Prefect。
- Pi 最后确认仍处于 Gate 6 自动观察期；晚间没有为本地软件工作连接或修改 Pi。
- 三档科研模式、`manual` / `supervised` 人工检查点，以及按任务
  `supervised` 科研协调器均已提交。下一项软件难题是 **Task 6：3101
  真实 Prefect S1/S2**，阻塞在 Gate 6 与 owner 批准，不是
  `autonomous` 循环、宿舍机或 3100 切换。

下周恢复顺序：

1. 先读本文件、`bogda/docs/pi-shadow-runbook.md` 和最新 Gate 报告；不要从聊天
   记录拼命令。
2. 对 Pi 做只读检查，确认 Gate 6 样本、每日快照、服务、SSD、Orchestra 和网络
   边界。72 小时已过不等于自动通过。
3. 保存 `bogda.ops.health summarize` 原始 JSON。受控重启和独立 restore 演练仍需
   owner 明确批准；未批准时只读，不改 systemd 或运行状态。
4. Gate 6 证据齐全后交给确定性复核，再由 owner/强模型做 Gate 7 裁决。
5. 软件线停在 Task 6 前门：Gate 6 证据 + owner 分别批准 S1/S2 之前，不接
   真实 Prefect、不写 Pi、不开宿舍机/GPU/3100。Task 4=`41c0e17`，
   Task 5=`4d8e470`。

本地仓库留意事项：根工作树的 `.gitignore`、两份锐评删除、`.codegraph/`、天气
项目和 Orchestra 任务卡是既有用户状态，不得顺手清理或带入 Bogda 提交。
`codex/bogda-gate3-install` 没有 worktree，其补丁已由主线等价提交覆盖；它只是
待 owner 以后确认删除的本地分支，不阻塞下周工作。

## 当前快照

Git `main`：`4d8e470` 本地领先 `origin/main`（含 Task 4–5，尚未 push）。

Pi 快照时间：2026-08-24T08:56:05Z（北京时间16:56）。

| 项目 | 当前事实 |
|---|---|
| Gate 1–3 | 完成：本地验证、Pi预检、安装但不启动 |
| Gate 4 | 完成：Basic Auth已配置；受保护API带鉴权200、无鉴权401；公网4200检查不可达 |
| Gate 5 | 完成：server、单并发worker、快照timer、健康timer已启动并enabled |
| Gate 6 | 进行中：72小时自动采样；尚未受控重启、快照恢复演练或最终摘要 |
| Gate 7 | 未开始 |
| 3100切换 | 未授权、未开始 |
| 宿舍runner | 仅设计与硬件行情记录，未采购、未接入 |

当前四个Bogda运行单元与 `orchestra-broker.service` 均为 active。TCP 4200监听IPv4所有接口；私有LAN和Tailnet可达，受Basic Auth保护，公网检查不可达。

健康试运行编号：`20260824T083454Z`。首个样本为 `2026-08-24T08:34:59Z`；最早完整72小时截止点为 `2026-08-27T08:34:59Z`（北京时间8月27日16:34:59）。

截至 `2026-08-24T08:55:33Z` 已有5个样本：API正常、约39ms、SQLite integrity `ok`、MemAvailable约1.14GB、Swap使用0、OOM计数0、磁盘可用约232.46GB。首个每日快照计划在2026-08-25 00:00 CST执行。

## 产品完成度校正（2026-08-24）

此前“软件主体约90%–95%”只适用于Pi控制面和影子部署，不适用于完整科研产品。当前更准确的口径是：Pi控制面/影子部署约90%，Bogda最小执行内核约85%，完整科研产品约60%–70%。Gate 6通过只证明B-lite控制面适合继续使用，不代表真实 Prefect 写入、宿舍机执行链或3100切换已经完成。

3101当前是B-lite影子控制台，不是完整科研驾驶舱。以下是已批准但尚未实现的产品能力：

| 能力 | 当前事实 | 进入条件 |
|---|---|---|
| `manual` / `supervised` / `autonomous`切换 | 本地 mock 可改全局/项目策略；真实 profile 仍 `canSetAutonomyMode=false` | 真实写入须单独S2批准 |
| 全局默认与项目覆盖策略 | 单文件 JSON 策略存储 + 创建时冻结 | 已落地；Run 不回读可变策略 |
| 模式驱动Flow行为 | shell 暂停 experiment/science；research cycle 另加 plan_approval。autonomous 本波不暂停 | 真实 Prefect 写入仍要 S2 |
| 研究计划/关键实验人工批准 | 3101 详情页可批准/拒绝；列表无一键批准。协调 Flow 会停在三道 Type-B 门 | 真实 profile 写操作仍禁 |
| 科研协调Agent | 已提交 `4d8e470`：按任务 `supervised`，mock 模型，只写计划/提实验 | 不是 7×24 管家；`autonomous` 仍是 Task 9 |
| 自主预算与迭代上限 | `supervised` 四墙已落地；无 edit-whitelist、无自批循环 | Task 9 才开放 `autonomous` |
| 真实Prefect上的3101写操作 | `real-readonly`禁写；写操作只在mock/隔离allowlist | Gate 6通过并批准S2 |
| Wake Bridge / WoL | 未实现 | Gate 6通过；可先用当前笔记本模拟 |
| Windows Power Agent与四档电源控制 | UI数据仍是mock | Win10/WSL测试节点可用 |
| `dorm-x86` CPU/GPU Worker | 未接入 | 先CPU，GPU等硬件到位后再开 |
| 雷达、通知、备份及真实研究Flow迁移 | 仍主要在Orchestra | 每类工作流独立验收后迁移 |
| 3100正式切换 | 未设计、未授权 | 3101真实shadow及回退证据完成 |

架构决定：不增加7×24自主思考的通用“管家Agent”。Pi常驻Prefect、Wake Bridge、健康/快照等确定性服务；科研协调Agent由Flow按任务启动，轻量推理调用云模型，需要本地代码、数据或GPU时由宿舍Worker执行。Pi不运行无人监督agent loop，宿舍机休眠时也不要求Agent常驻。

上述工作的执行级拆分、文件边界和验收命令见 `docs/superpowers/plans/2026-08-24-bogda-research-control-plane.md`。

## 现在不要做什么

- 72小时窗口内不升级Prefect、不重装Bogda、不修改unit、不调整并发。
- 不处理Prefect内置UI权限警告和runpy警告；先保持观察变量稳定。
- 不切换3100，不接入GPU，不接入宿舍runner。
- 不配置路由器端口映射、Tailscale Serve或Funnel。
- 不删除 `/home/liuxfs/bogda-stage-55b4d9b`，当前运维与回滚仍依赖它。
- 不清理健康样本、快照、env、last-backup或inventory。
- 不把Prefect Completed解释为科研结论成立。

## 任务安排

### 自动系统：现在至72小时截止

- `bogda-shadow-health.timer` 每5分钟追加一个样本。
- `bogda-prefect-snapshot.timer` 每日00:00生成快照。
- worker并发固定为1。
- 任何API失败、OOM、数据库integrity失败、SSD消失或服务反复重启都中止接受判断并保留现场。

### Grok：24小时与48小时只读检查

在约2026-08-25 16:35和2026-08-26 16:35执行，只读、不改状态：

1. 四个Bogda运行单元与Orchestra仍active。
2. 计算健康样本数、缺失间隔、API失败、OOM、Swap和最小内存。
3. 确认每日快照文件及其manifest出现，但不恢复。
4. 检查4200公网端口仍不可达。
5. 将证据追加到新报告，不修改本文件中的手写计数。

若没有异常，只报告“继续观察”；不要为了显得有工作而改代码。

### Grok：72小时后Gate 6操作

首先生成 `bogda.ops.health summarize` 的原始JSON并保存。受控重启、快照创建和恢复演练会改变运行状态，必须获得owner对Gate 6操作的明确批准后才能执行。

获批后的顺序：

1. 保存重启前unit、队列、挂载、内存和摘要。
2. 执行一次受控重启。
3. 恢复后核对SSD UUID、四个Bogda单元、Orchestra、队列与历史。
4. 创建新SQLite快照并使用独立restore目录验证；不得覆盖live数据库。
5. 保存最终摘要、journal、快照manifest和restore验证输出。
6. 写 `docs/reports/2026-08-27-bogda-pi-gate6-acceptance.md`，不要自行宣布Gate 7通过。

### DeepSeek：确定性复核

在Grok完成Gate 6证据后：

- 对照runbook逐字段复核摘要和证据路径；
- 检查样本时间跨度、缺失间隔、API失败、OOM、Swap、数据库integrity和磁盘；
- 检查受控重启前后证据是否连续；
- 检查恢复演练没有碰live数据库；
- 只报告通过/失败/证据不足，不修改阈值和架构。

### Owner / 最强模型：Gate 7裁决

只在Gate 6报告和DeepSeek复核均完成后做接受、整改或回滚决定。Gate 7通过后，才分别规划：

1. 3101连接真实Prefect并shadow；
2. 3100切换；
3. 宿舍runner与休眠唤醒；
4. GPU executor；
5. Prefect内置UI权限与runpy警告清理；
6. 主机4200是否收紧为仅Tailnet。

### 软件建设队列（与Gate 6运行态隔离）

1. **已完成（2026-08-24）**：三档模式策略权威存储、全局默认、项目覆盖/取消覆盖、revision冲突、损坏策略fail-closed，以及创建运行时冻结`autonomy_mode + policy_revision`；仅本地实现，未连接或修改Pi。
2. **已完成（2026-08-24）**：3101模式查询/命令契约、mock三档切换、项目继承全局、revision冲突、确认文案、只读降级和320/360px验收；真实profile仍禁写且不回退mock。
3. **已完成（2026-08-24）**：3101 Windows 本地启动器、PID/日志管理与真实
   `start/status/stop` 闭环；仍为 `mock-all`，不是开机服务。
4. **已完成（2026-08-26，`41c0e17`）**：`manual`/`supervised` 人工检查点。
   Prefect 原生 pause/resume + `ResearchDecision` Artifact；拒绝为
   `Cancelled` 而非 `Failed`；Type-A 完成不能把 `scientific_status` 写成
   `accepted`。3101 仅详情页批准/拒绝。
5. **已完成（2026-08-26，`4d8e470`）**：按任务 `supervised` 科研协调器。
   目标→计划→`plan_approval`→实验建议→`experiment_approval`→执行→科研评审；
   四墙触顶停给人；模型不能把 `scientific_status` 写成 `accepted`。
6. **下一项（阻塞）**：Gate 6 通过且 owner 分别批准 S1/S2 后，3101 连接真实
   Prefect；S2 仅对测试资源开放精确 allowlist 写操作。
7. **笔记本模拟阶段**：Wake Bridge、Power Agent协议、CPU Worker、睡眠/游戏模式；不承担7×24职责。
8. **宿舍机到位后**：真实WoL、WSL Worker和CPU队列；GPU不作为接入前置条件。
9. **最后**：逐类迁移科研工作流、完成3101 shadow证据，再单独设计3100切换。
10. **更后**：`autonomous` 受限循环（计划 Task 9），四墙 + edit-whitelist。

## 停止条件

以下任一出现，执行者保存现场并停止，不临时修架构：

- `/mnt/nas`不是已批准的ext4 SSD或UUID变化；
- OOM增量大于0；
- 数据库integrity不是`ok`；
- API失败无法解释；
- 4200从公网可达；
- Basic Auth失效；
- Orchestra出现异常或在途任务受影响；
- 回滚指针、env或快照证据丢失；
- 需要删除数据、修改防火墙、提高并发或购买硬件。

## 权威资料

- 运行手册：`bogda/docs/pi-shadow-runbook.md`
- Gate 2：`docs/reports/2026-08-24-bogda-pi-gate2-preflight.md`
- Gate 3：`docs/reports/2026-08-24-bogda-pi-gate3-install.md`
- Gate 4–5：`docs/reports/2026-08-24-bogda-pi-gate4-5-start.md`
- 3101 启动器真实验收：`docs/reports/2026-08-24-bogda-console-local-launcher-live-acceptance.md`
- 接班清单：`docs/reports/2026-08-24-bogda-grok-deepseek-handoff.md`
- 硬件行情：`docs/reports/2026-08-24-bogda-dorm-runner-hardware-market.md`
