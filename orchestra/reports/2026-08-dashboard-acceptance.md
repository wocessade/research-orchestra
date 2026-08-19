# Subsystem-4 融合面板端到端验收报告（demo 任务三帧证据）

- 日期：2026-08-19（epoch 1787117xxx 区间）
- 任务：`T-20260819-dashboard-demo`（shell executor，`sleep 90 && date >> heartbeat.txt && echo done`）
- 证据目录：`D:\Temp\subsystem-4\`
- 数字纪律：本报告所有数值均引自所标注 artifact 文件内容；epoch→CST 换算由 Python `datetime.fromtimestamp` 计算（换算值标注「换算」）

## 一、执行时间线（数字均引自文件）

| 时间 (CST) | 事件 | 来源 |
|---|---|---|
| 13:09:50（换算 1787116190.7） | 激活后 dashboard 快照：orchestra 块在役，broker_health=ok | `D:\Temp\subsystem-4\dashboard-after-activation.json` `orchestra_last_report.broker` |
| 13:25:30（换算 1787117130.1） | 帧1 balance 缓存时间 | `D:\Temp\subsystem-4\e2e-frame1-state.json` `last_updated.balance` |
| 13:25:54（换算 1787117154.8） | 帧1 最新 broker 上报 | 同文件 `orchestra_last_report.broker` |
| 13:26:36（换算 1787117196.4） | sync_push 的 last_sync 上报 POST（源 IP .186） | `D:\Temp\subsystem-4\e2e-broker-post-gap.txt` |
| 13:26:39（e2e-push-time.txt=1787117199） | sync_push 本地执行时刻 | `D:\Temp\subsystem-4\e2e-push-time.txt` |
| 13:26:40（1787117200） | last_sync 面板写入值 | 帧2/帧3 state `orchestra.last_sync` |
| 13:26:54（=started_at 05:26:54+00:00） | demo 任务开始执行（push 后 15s 被 30s 轮询拾取） | 远端 `attempt-1/state.json` |
| 13:27:30（换算 1787117250.0） | 帧2 balance 缓存时间 | `D:\Temp\subsystem-4\e2e-frame2-state.json` `last_updated.balance` |
| 13:27:54 起 | 帧2 采集（任务执行窗口 13:26:54–13:28:24 内） | sleep 75（e2e-push-time.txt）+ 采集命令 |
| 13:28:24 | 任务完成（done） | 远端 `attempt-1/state.json` `elapsed_s=90.0` + `heartbeat.txt` + `D:\Temp\subsystem-4\e2e-broker-log.txt` |
| 13:28:25 | 执行后首个 broker 上报（与 13:26:24 相隔 121s，正常 30s 节奏恢复） | `D:\Temp\subsystem-4\e2e-broker-post-gap.txt` |
| 13:28:27 / 13:28:33 | 面板 FULL refresh `data=True`（状态变化刷屏） | `D:\Temp\subsystem-4\e2e-full-refresh.txt` |
| 13:30:25（换算 1787117425.5） | 帧3 最新 broker 上报 | `D:\Temp\subsystem-4\e2e-frame3-state.json` `orchestra_last_report.broker` |
| 帧3 后 | sync_pull 拉回结果，本地同构路径可读 | `D:\pythonProject\orchestra\results\results\T-20260819-dashboard-demo\attempt-1\` |

## 二、验收项表（8 条标准）

| # | 验收标准 | 证据 | 结果 |
|---|---|---|---|
| 1 | POST /api/orchestra 鉴权 | `dashboard-401.txt`（无 token）与 `dashboard-badtoken.txt`（错误 token）均返回 `{"error":"unauthorized","ok":false}`；`health-after-token.json` `auth_required=true` | PASS |
| 2 | dashboard orchestra 块 | `dashboard-after-activation.json`：orchestra 块含 active_tasks / broker_health / host / last_sync / last_task / queue_len / recent_tasks 7 字段，`broker_health=ok`，host.load1/mem_pct 有值 | PASS |
| 3 | push 链路 30-60s 刷新 | 上报节奏 30s：`e2e-broker-post-gap.txt` 中 13:17:22→13:26:24 相邻 POST 均为 ~30s 步进；last_report.broker 步进 13:09:50 → 13:25:54 → 13:26:24 → 13:30:25（激活快照 + 三帧）。push→面板可见：last_sync 在帧2（13:27:54 采集）已可见（push 13:26:36-40，约 75s）；任务状态变化在 done（13:28:24）后 1s 上报（13:28:25）+ 2-8s 全刷（13:28:27/33） | PASS（任务状态上报延迟的机制说明见「五、遗留」） |
| 4 | 融合面板渲染 | 三帧 PNG `e2e-frame1/2/3.png`（800x480 eink 渲染，ink 覆盖率 14.47% / 14.55% / 14.58%，非空白）；`health-after-token.json` `eink_ready=true` | PASS |
| 5 | demo 任务面板变化 | 三帧 state JSON 前后对照（见下表）+ 三帧 PNG + 日志行（`e2e-broker-log.txt`、`e2e-full-refresh.txt`） | PASS（运行中状态原不可观测，D15 修复后实测补齐：见「五、遗留与发现」D15 段落） |
| 6 | last_sync 链 | 帧1 `last_sync=null` → 帧2/帧3 `last_sync=1787117200`；`orchestra_last_report.sync` 帧1=0 → 帧2/帧3=1787117196.4；sync 上报 POST（源 .186，13:26:36）见 `e2e-broker-post-gap.txt` | PASS |
| 7 | 零回归 | 测试记录见「四、测试记录」 | PASS |
| 8 | reviewed | 留空待 CC 复查 | — |

## 三、三帧状态对照（数值均引自三份 state JSON 原文）

| 字段 | 帧1（派发前）`e2e-frame1-state.json` | 帧2（执行中采集）`e2e-frame2-state.json` | 帧3（完成后）`e2e-frame3-state.json` |
|---|---|---|---|
| active_tasks | 0 | 0 | 0 |
| queue_len | 0 | 0 | 0 |
| last_sync | null | 1787117200 | 1787117200 |
| last_task | T-20260819-trt-dsh | T-20260819-trt-dsh | **T-20260819-dashboard-demo** |
| recent_tasks[0] | T-20260819-trt-dsh / done | T-20260819-trt-dsh / done | **T-20260819-dashboard-demo / done / ts=2026-08-19T05:28:24+00:00** |
| orchestra_last_report.broker | 1787117154.8 | 1787117184.9 | 1787117425.5 |

帧图：`e2e-frame1.png`、`e2e-frame2.png`、`e2e-frame3.png`（核桃派 `eink_dashboard.py --snapshot --panel orchestra --state` 实机渲染）。

注：帧2 采集于任务执行窗口内（13:26:54–13:28:24），但面板呈现的 broker 上报停留在 13:26:24（派发前）——Broker 主循环为「每轮 `one_cycle()` 同步执行全部任务 → 之后 `report_status()` → sleep 30」（`/home/liuxfs/broker/dispatcher.py` 155-158 行），执行期间 121s 无任何上报（`e2e-broker-post-gap.txt`：13:26:24 → 13:28:25）。因此「running」帧在面板上不可观测，active_tasks 恒为 0，任务状态以 done 一次性呈现。系统行为自洽（started_at 13:26:54 + elapsed_s 90.0 = done 13:28:24，与 heartbeat.txt、broker.log 三处一致），非故障；面板状态变化证据为 帧1（前）→ 帧3（后）完整跳变。

## 四、测试记录（零回归，命令输出存证）

- **Broker：39 passed** — `D:\Temp\subsystem-4\e2e-test-broker.txt`（`39 passed in 30.98s`，命令：`cd orchestra/broker && python3 -m pytest tests/ -q`）
- **usage-monitor：62 passed + 1 既有基线 error** — `D:\Temp\subsystem-4\e2e-test-usage-monitor.txt`（62 passed；test_dashboard.py 采集期 FileNotFoundError [WinError 3] 为既有基线，自 Task 1 起记录于 `.tasks/active/026_subsystem-4-dashboard/STATE.md` 第 23 行「回归唯一失败为既有基线 test_dashboard ImportError，非新增」，D10 历史记录「56/57 仅既有基线失败」同见 STATE.md 第 26 行；本次套件已扩至 63 项，基线性质未变）

## 五、遗留与发现

- **demo 任务文件归档**：本地 `D:\pythonProject\orchestra\tasks\T-20260819-dashboard-demo.md` 保留为源记录（与其它已完成任务一致，供 sync_push 幂等重推）；Broker 侧消费后已移入 `/mnt/broker/tasks/archive/`（本次同步重推的 3 个旧任务文件同样归档，slug 幂等未重跑——broker.log 在 13:26-13:29 间无新增执行行，仅 demo 一条 done）
- **发现 → 已修复（D15，commit ea0c907）**：Broker 执行期间无上报，面板无法呈现任务「running」帧 → dispatcher 新增独立 reporter 线程（自持 WAL 连接，每 30s 上报，与主循环解耦；主循环移除 report_status 防双报）。**实机验证**：派 150s 任务 T-20260819-d15-running，执行中 `D:\Temp\subsystem-4\d15-running-state.json` 的 `active_tasks=1`、`recent_tasks[0]=T-20260819-d15-running/running`、上报新鲜 28s；渲染帧 `D:\Temp\subsystem-4\d15-running-frame.png`；任务终态 done（`orchestra/results/results/T-20260819-d15-running/attempt-1/state.json`，elapsed_s=150.0）。修复后长任务期间面板不再误报「Broker 离线」
- **结果路径**：任务文件 `result: results/T-20260819-dashboard-demo` 相对 results 根解析，落地 `/mnt/broker/results/results/`（嵌套目录，语义正常）；sync_pull 同构拉回本地
- **结果物**：远端 `attempt-1/` 含 `state.json`（status=done、elapsed_s=90.0）、`heartbeat.txt`（`Wed 19 Aug 13:28:24 CST 2026`）、`stdout.log`（5B）、`stderr.log`（0B）；已 `sync_pull` 至本地 `D:\pythonProject\orchestra\results\results\T-20260819-dashboard-demo\attempt-1\`（内容逐字节一致）

## Reviewed

| 复查人 | 结论 | 日期 |
|---|---|---|
| CC | reviewed: ok（2026-08-19 复查：三帧 state JSON 关键值、full-refresh 日志行、broker.log done 行已逐项核对实测一致；三帧 PNG 非空白渲染；无手抄数字。验收项 5 的「运行中不可观测」已由 D15 修复任务承接，本报告遗留段如实记录。） | 2026-08-19 |
| CC | reviewed: ok（D15 补充复查 2026-08-19：reporter 线程 16:05 实机部署（日志 `reporter thread started`）；d15-running-state.json 关键值逐项核对一致；d15-running-frame.png 为核桃派实机渲染；D17 事故（1A 适配器）与本次验收无关。） | 2026-08-19 |
