# Subsystem 4: 仪表盘适配（usage-monitor 增量扩展 × Broker 状态上报）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Broker 队列状态搬上核桃派墨水屏：usage-monitor 增量新增 orchestra 状态块 + `POST /api/orchestra` 上报端点 + 墨水屏「任务面板」视图，激活 4B Broker 已内置的 `report_status` 上报（mission 021 预留 api_url 字段），打通「Broker 执行 → 墨水屏可视」链路。验收：派 demo 任务，墨水屏任务面板出现状态变化，dashboard API 返回 orchestra 块。

**Architecture:** 推送为主的数据通道——Broker `dispatcher.report_status` 是 mission 021 已实现且已部署的现成通道（`POST {api_url}/api/orchestra`，X-Monitor-Token，30s 周期），本次仅激活 config，**零 Broker 代码改动**。usage-monitor 侧按字段合并 + 到达时间戳记录新鲜度，`broker_health` 由上报新鲜度推导（stale 阈值）。任务面板为第三面板：CC 空闲时与闲置面板定时轮换，活跃时让位。`last_sync` 由 Windows sync 脚本上报（可选链）。

**Tech Stack:** Flask + APScheduler（核桃派既有）、PIL 墨水屏渲染（既有，纯绘制不引新依赖）、Broker stdlib urllib（既有，零改动）、unittest（Windows 本地，eink mock 降级路径已有）、Git Bash、paramiko deploy_to_pi.py（既有）。

## 接口约定（本 spec 的核心产出）

### A. orchestra 状态块与上报协议

**状态块** `state["orchestra"]`（五字段 + 上报时间戳）：

```json
{
  "broker_health": "ok",
  "queue_len": 2,
  "active_tasks": 1,
  "last_task": "T-20260819-xxx",
  "last_sync": 1724054400
}
```

- 语义对齐 Broker 现状：`queue_len` = queued + running（report_status 既有计算）；`active_tasks` = running；`last_task` = 最近完成（done）任务 slug；`last_sync` = Windows 最近一次结果同步时间。
- `state["orchestra_last_report"] = {"broker": <epoch>, "sync": <epoch>}` —— 每次 POST 到达刷新对应 source 时间戳；无上报 = 0。
- 初始值：`orchestra` 五字段为 `{"broker_health": "unknown", "queue_len": null, "active_tasks": null, "last_task": null, "last_sync": null}`。

**上报协议** `POST /api/orchestra`：

- 鉴权复用 `@require_token`（X-Monitor-Token；缺/错 token → 401，与现有端点一致）。
- body 为 JSON object，**接受任意子集**（五字段均可缺省），按字段覆盖合并；类型非法的字段忽略（记录 warning）。
- 可选字段 `"source": "broker" | "sync"`（缺省 `"broker"`）决定刷新哪个时间戳。
- 响应 `{"ok": true, "merged": ["queue_len", ...]}`（列出实际合并的字段名，供调试）。
- 现有三端点（`/api/dashboard`、`/api/status`、`/health`）语义不变；`/api/dashboard` 因直接返回 state 自动携带 orchestra 块。

**新鲜度推导**（展示层统一规则）：

- `age = now - orchestra_last_report["broker"]`；`age <= ORCHESTRA_STALE_SEC` → 有效健康（显示 payload 的 broker_health）；`age > ORCHESTRA_STALE_SEC` → `stale`（墨水屏显示「离线」）；无上报 → `unknown`（显示 `--`）。
- 默认 `ORCHESTRA_STALE_SEC = 90`（= 3 × Broker poll_interval 30s，容忍一次上报丢失）。

### B. 面板体系（D9 修订：融合单面板，2026-08-19 用户拍板）

- `config.py` 的 `SHOW_ORCHESTRA`（默认 True；False → 旧闲置面板，代码保留作回退路径）。
- 面板解析纯函数 `_resolve_display_panel(state)`（**无时间桶**）：
  1. 基面板 = 现有 `_resolve_panel(state)`（idle/active 语义不变）。
  2. 基面板 == idle 且 SHOW_ORCHESTRA → `"orchestra"`（融合面板 = 空闲时唯一面板，不再轮换）。
  3. 否则返回基面板。
- 轮换机制废止（D3 撤销；`ORCHESTRA_ROTATE_SEC` 常量删除，零消费方）。
- `_compute_display_hash` 与 `_compute_data_hash` 均纳入 orchestra 块与 orchestra_last_report（融合面板内容即主数据；内容变化走全刷清残影）。
- **刷新分级（D10）**：`self_status` 与 `orchestra.host` 只进 display_hash（局刷，负载每 60s 变化不引发全刷）；不进 data_hash（防抖动每分钟全刷）；指标采集四舍五入降抖（load 1 位小数、mem 整数）。
- 设计理由（D9 用户反馈）：编排工作流下空闲面板应以任务信息为主内容，计数/两态值用小字状态条呈现；双面板轮换稀释注意力，取消。

### C. 融合面板布局（D9 修订：信息层级内容优先，计数/状态小字）

- `_draw_orchestra(draw, state)` 整体重写（废弃四卡版与 ORCH_CARD_H/value_y 专用常量）：
  - 标题栏沿用（show_date=True；**D10：移除死掉的 CC 状态控件**——hooks 停用后无上报源恒显空闲；标题栏只留品牌+日期+时间，所有面板共用同一标题栏一并生效）
  - **状态条**（一行，font_normal）：`Broker {OK|离线|--} · 队列 {N|--} · 运行 {N|--} · 同步 {Xs前|--}`（健康 = D2 新鲜度推导）
  - **最近任务列表**（主内容）：「最近任务」标题（font_medium）+ 最多 5 行（font_normal，行高 ~36）：每行 = slug 左（像素截断约 60% 宽）+ 状态标签（排队中/运行中/完成/失败）+ `Xs前` 右对齐；数据 = `orchestra.recent_tasks`（[{slug,status,ts}]，D9 Broker 扩展）；空 → 居中「（暂无上报）」
  - **设备区**（D10）：「设备」标题（font_medium）+ 两行（font_normal）：`4B Broker  {在线|离线} · 负载 {x|--} · 内存 {y%|--}`（在线 = 新鲜度推导；负载/内存 = `orchestra.host` 的 load1/mem_pct，Broker payload 扩展）+ `核桃派  OK · 负载 {x|--} · 内存 {y%|--}`（`state.self_status`，本地 /proc 每 60s 采集；OK 恒定 = 进程存活）
  - **DeepSeek/天气小字行**（font_normal）：`¥{余额} · 本期 ¥{x} · {temp}°C {desc}`（字段缺失 `--`；宽度不足省略 desc）
  - 底栏沿用 `_draw_footer`
- 快照 CLI：`python3 eink_dashboard.py --snapshot <out.png> [--panel idle|active|orchestra]` —— 无硬件 mock 下渲染指定面板 PNG 到文件（CC 复查 artifact；复用现有 `epd is None → image.save` 降级路径）。不指定 `--panel` 时按 state 解析。
- 局刷/全刷/失败退避机制全部沿用（不新增刷新路径）。

## Global Constraints

- **零 Broker 代码改动**：仅 4B `config.json` 填 `api_url`/`monitor_token`（report_status 已随 mission 021 部署）。若基线验证发现 4B 在役 `dispatcher.py` 无 report_status，先重部署（`deploy_broker.sh`）再激活，仍不改代码。
- 不动核桃派 usage-monitor 现有三端点语义与采集逻辑（只增量）。
- 不动 `~/.claude/settings.json`；上报者 = Broker dispatcher + Windows sync 脚本，**不是 CC hooks**。
- 密钥不入库：MONITOR_TOKEN 只在核桃派 env（systemd）与 4B config.json（均 600 权限）之间流转，不落 Windows 磁盘。
- 核桃派 user=`pi`、IP 192.168.0.200、代码目录 `/home/pi/usage-monitor`；4B user=`liuxfs`、IP 192.168.0.250。
- 测试无硬件：Flask test client + eink mock 模式（现有降级路径）；Windows 侧命令在 Git Bash 运行。
- 数字纪律：验收报告所有数值引用 artifact 路径（API 响应存档文件、日志、快照 PNG），无手抄。
- commit 不加 Co-Authored-By；实现派 haiku（TDD），opus 审查。
- 内存红线：核桃派 1GB / MemoryMax 512M——任务面板为纯 PIL 绘制，不引新依赖、不开新进程（快照 CLI 为退出式单次进程）。

---

### Task 0: 基线确认与提交（Windows）

**Files:** 无新增（deepseek-usage-monitor 未提交改动作为基线提交）

**Interfaces:**
- Consumes: 无
- Produces: 基线判定结论（DECISIONS 记录）；deepseek-usage-monitor 当前工作区状态入库

- [ ] **Step 1: 核验仓库 vs 在役**（核桃派 192.168.0.200，user pi）：
  - `ssh pi@192.168.0.200` md5sum `/home/pi/usage-monitor/{app.py,config.py,eink_dashboard.py,led_controller.py,usage_scraper.py,weather.py}` 与仓库对应文件逐一比对。
  - 4B（liuxfs@192.168.0.250）：md5 比对 `/home/liuxfs/broker/dispatcher.py` 与 `orchestra/broker/dispatcher.py`，确认 report_status 在役；`cat /home/liuxfs/broker/config.json` 确认 `api_url`/`monitor_token` 为空。
  - 核桃派 `/health`（无 token）：确认 `auth_required` 现状。
- [ ] **Step 2: 不一致处置**：任一 md5 不一致 → DECISIONS 记录差异明细 + 上报用户裁定以谁为准（Trigger Report）；全部一致 → 继续。
- [ ] **Step 3: 基线提交**：`git add deepseek-usage-monitor/ && git commit -m "chore: baseline commit of usage-monitor walnutpi-migration state"`（含全部已跟踪修改与未跟踪文件；`waveshare_epd/`、`waveshare_driver/` 大目录确认 .gitignore 或一并入库，按 Step 1 的在役比对结论处理）。

### Task 1: usage-monitor state + /api/orchestra 端点（TDD）

**Files:**
- Modify: `D:\pythonProject\deepseek-usage-monitor\usage-monitor\app.py`
- Modify: `D:\pythonProject\deepseek-usage-monitor\usage-monitor\config.py`
- Create: `D:\pythonProject\deepseek-usage-monitor\usage-monitor\test_orchestra_api.py`

**Interfaces:**
- Consumes: 约定 A（状态块/上报协议/新鲜度）
- Produces:
  - `config.py`：`SHOW_ORCHESTRA = True`、`ORCHESTRA_ROTATE_SEC = 60`、`ORCHESTRA_STALE_SEC = 90`
  - `state["orchestra"]` 与 `state["orchestra_last_report"]`（初始值见约定 A）
  - `POST /api/orchestra`（部分字段合并，`@require_token`）
  - `/health` 增 `age_seconds` 的 `orchestra_broker`/`orchestra_sync` 两项
  - `_snapshot_state` 补 orchestra 深拷贝（与 balance/usage 同列）

- [ ] **Step 1: 写失败测试** `test_orchestra_api.py`（Flask test client；覆盖：无 token 401、错 token 401、正确 token 部分合并（只发 queue_len 其余不动）、source=sync 刷新 sync 时间戳、非法类型字段忽略且 merged 不含它、全字段合并、dashboard 返回 orchestra 块与 last_report、/health age_seconds 两项、merged 数组回显）
- [ ] **Step 2: 运行确认失败**（`python -m unittest test_orchestra_api -v`，MONITOR_TOKEN 测试用 test 值）
- [ ] **Step 3: 写实现**
- [ ] **Step 4: 运行确认通过** + 现有测试回归（`test_dashboard.py` 等全量）
- [ ] **Step 5: Commit** `feat: usage-monitor orchestra state block and /api/orchestra endpoint`

### Task 2: 墨水屏任务面板（TDD）

**Files:**
- Modify: `D:\pythonProject\deepseek-usage-monitor\usage-monitor\eink_dashboard.py`
- Create: `D:\pythonProject\deepseek-usage-monitor\usage-monitor\test_orchestra_panel.py`

**Interfaces:**
- Consumes: 约定 B（轮换机制）/ C（渲染接口）
- Produces:
  - `_resolve_display_panel(state, now) -> str`（纯函数；`_resolve_panel` 保留为基面板解析，现有调用点语义不变；`render`/`_compute_display_hash` 改用 `_resolve_display_panel`）
  - `_draw_orchestra(draw, state)`
  - `_compute_display_hash` 纳入 orchestra 块与 `_resolve_display_panel`
  - CLI：`--snapshot`/`--panel` 参数（mock 模式渲染 PNG）
  - **Windows 中文字体回退**：`_CJK_FONT_PATHS` 追加 Windows 字体路径（`C:\Windows\Fonts\msyh.ttc`、`C:\Windows\Fonts\simhei.ttf`，`os.path.exists` 守卫）——无硬件 mock 预览时中文可正常渲染（Pi 侧不受影响，Linux 路径优先）

- [ ] **Step 1: 写失败测试** `test_orchestra_panel.py`（覆盖：`_resolve_display_panel` 纯函数——CC active 时始终 active；idle 且 SHOW_ORCHESTRA=True 且有上报时按时间桶轮换（同桶稳定、跨桶翻转）；无上报数据不轮换；SHOW_ORCHESTRA=False 不轮换；快照 CLI 渲染 orchestra 面板 PNG 文件存在且可被 PIL 打开）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 写实现**
- [ ] **Step 4: 运行确认通过** + `test_partial_buffer.py` 等现有测试回归
- [ ] **Step 5: Commit** `feat: e-ink orchestra task panel with idle rotation and snapshot CLI`
- [ ] **Step 6: 排版预览图交付用户确认**：用假 state（queue_len=2/active=1/health=ok/last_task 示例）渲染 orchestra 面板快照 → `D:\Temp\subsystem-4\panel-preview.png`，交用户过目排版；用户提排版意见 → 调整 `_draw_orchestra` 布局后重出图，直至确认（用户要求：出面板设计时给渲染图看排版）

### Task 2 修订（D9 融合面板重构，2026-08-19 用户拍板）

用户对四卡版排版批评（信息层级倒挂、未适配研究编排工作流）→ 转向融合单面板（约定 B/C D9 版）。

**Files:**
- Modify: `eink_dashboard.py`（`_resolve_display_panel` 去轮换、`_draw_orchestra` 重写、`_compute_data_hash` 纳入 orchestra、删除 ORCH 专用常量）
- Modify: `app.py` + `test_orchestra_api.py`（recent_tasks 字段合并：list 校验、整表替换、cap 8、merged 回显；state 初始 `recent_tasks: []`）
- Modify: `config.py`（删除 `ORCHESTRA_ROTATE_SEC`，零消费方）
- Modify: `test_orchestra_panel.py`（轮换测试重写为融合决议测试）

**Interfaces:**
- Consumes: 约定 B/C（D9 版）；Broker payload `recent_tasks` 契约（D9：最多 5 条 {slug,status,ts}，ts 为 ISO 时间戳，按 ts 降序）
- Produces: 融合面板渲染 + 状态条 + 任务列表；`--snapshot --panel orchestra` 输出融合面板 PNG

- [ ] **Step 1: 测试先行改写**（test_orchestra_panel.py 轮换用例 → 融合决议：idle+SHOW_ORCHESTRA → orchestra 恒定；active → active；SHOW_ORCHESTRA=False → idle；无上报仍显示融合面板；test_orchestra_api.py 补 recent_tasks 合并用例）→ 运行确认失败
- [ ] **Step 2: 实现**（eink_dashboard.py / app.py / config.py）
- [ ] **Step 3: 全量回归**（discover 无新增失败）
- [ ] **Step 4: 重出预览图**（`D:\Temp\subsystem-4\panel-preview.png` 用含 4 条 recent_tasks 的演示 state；`panel-idle.png` 旧面板仍可渲染对照）→ sonnet 子代理读图复审（信息层级、列表无重叠溢出、中文清晰、无大留白）
- [ ] **Step 5: Commit** `feat: fused orchestra panel - task list primary, status strip compact (D9)`（无 Co-Authored-By）

### Task 3: 部署 usage-monitor 到核桃派 + MONITOR_TOKEN 激活

**Files:**
- Modify: `D:\pythonProject\deepseek-usage-monitor\usage-monitor\deploy_to_pi.py`（`PI_HOST` 默认 192.168.0.200、`PI_USER` 默认 `pi`——与迁移后现状对齐）
- 核桃派侧：`/home/pi/usage-monitor/`（部署产物）、systemd monitor 环境（token）

**Interfaces:**
- Consumes: Task 1/2 产出；`deploy_to_pi.py`（既有）
- Produces: 核桃派在役 usage-monitor 含 orchestra 端点与任务面板；`/api/*` 鉴权开启

- [ ] **Step 1: 更新 deploy_to_pi.py 默认值**（`PI_HOST=192.168.0.200`、`PI_USER=pi`）
- [ ] **Step 2: 部署**：`py -3 deploy_to_pi.py`（或按 env 覆盖）；FILES_TO_UPLOAD 不含测试文件（tests 留在 Windows）
- [ ] **Step 3: 激活 MONITOR_TOKEN**（核桃派）：生成 token（`openssl rand -hex 16`，Pi 侧生成）→ `sudo systemctl edit monitor` 追加 `Environment="MONITOR_TOKEN=<值>"` → `sudo systemctl daemon-reload && sudo systemctl restart monitor`。token 值仅存于核桃派会话与后续 4B config，不落 Windows 磁盘。
- [ ] **Step 4: 验证**：`curl http://192.168.0.200:5000/health` → `auth_required=true`；无 token `curl /api/dashboard` → 401；带 token → 200 且含 orchestra 初始块（unknown/null）；错误 token → 401。输出存档到 `D:\Temp\subsystem-4\`（临时文件按约定放 D:\Temp）。
- [ ] **Step 5: Commit** deploy_to_pi.py 默认值修改

### Task 4: 4B Broker 上报扩展部署 + 激活

**Files:**
- 4B `/home/liuxfs/broker/{db.py,dispatcher.py}`（D9 扩展代码，随 deploy_broker.sh 部署）
- 4B `/home/liuxfs/broker/config.json`（远程文件，**不入库**）

**Interfaces:**
- Consumes: D9 扩展代码（Task 2 修订的 W2 工作流已 commit）；Task 3 的核桃派端点与 token
- Produces: 4B Broker 每 poll 周期 POST 一次 /api/orchestra（payload 含 recent_tasks）

- [ ] **Step 0: 重部署 broker 代码**：`ORCHESTRA_SSH_HOST=192.168.0.250 bash orchestra/scripts/deploy_broker.sh`（含 D9 的 db.py/dispatcher.py）——避开 23:30 雷达注入窗口执行（Persistent timer 会补跑，风险仅是 running 任务 recover 重试）
- [ ] **Step 1: 确认现状**：`ssh liuxfs@192.168.0.250` 查 config.json（api_url/monitor_token 应为空，与 Task 0 结论一致）
- [ ] **Step 2: 写配置**：ssh 4B 上执行 `python3 -c`（json 读改写）：`api_url = "http://192.168.0.200:5000"`、`monitor_token = <Task 3 的 token>`；`chmod 600 config.json`
- [ ] **Step 3: 重启并验证**：`sudo systemctl restart orchestra-broker`；30-60s 后核桃派 `/api/dashboard`（带 token）orchestra 块 `queue_len` 等字段变为数值、`last_report.broker` 更新——响应存档 `D:\Temp\subsystem-4\dashboard-after-activation.json`；`tail /mnt/broker/logs/broker.log` 无 `status report failed` 行。**注意**：避开夜间雷达注入窗口（23:30）执行重启——重启瞬间 running 任务会被 recover_running 标记 failed 后重试，尽量选无任务执行时段
- [ ] **Step 4: DECISIONS 记录激活完成**（含验证证据路径；token 不记录）

### Task 5: Windows sync 脚本上报 last_sync（可选链）

**Files:**
- Modify: `D:\pythonProject\orchestra\scripts\sync_push.sh`
- Modify: `D:\pythonProject\orchestra\scripts\sync_pull.sh`

**Interfaces:**
- Consumes: 约定 A 上报协议
- Produces: sync 脚本完成同步动作后 POST `{"last_sync": <epoch>, "source": "sync"}`（仅当 env `ORCHESTRA_MONITOR_TOKEN` 设置时；`ORCHESTRA_MONITOR_API` 默认 `http://192.168.0.200:5000/api/orchestra`；失败静默不阻塞同步）

- [ ] **Step 1: 修改两脚本**（末尾追加上报函数 + 调用；`curl -s -m 5 -X POST -H "Content-Type: application/json" -H "X-Monitor-Token: $ORCHESTRA_MONITOR_TOKEN" -d "{\"last_sync\": $(date +%s), \"source\": \"sync\"}" "$ORCHESTRA_MONITOR_API" || true`）
- [ ] **Step 2: 语法检查**：`bash -n` 两脚本
- [ ] **Step 3: 冒烟**：设 env 后跑一次 sync_pull.sh → 核桃派 `/api/dashboard` 的 `last_sync`/`last_report.sync` 更新（存档响应）；未设 env 时跑一次确认跳过（不报错）
- [ ] **Step 4: Commit** `feat: sync scripts report last_sync to orchestra dashboard`

### Task 6: 端到端验收（demo 任务 → 墨水屏任务面板变化）

**Files:**
- Create: `D:\pythonProject\orchestra\tasks\T-<date>-dashboard-demo.md`（shell，net optional，`sleep 90 && date >> heartbeat.txt && echo done`）
- Create: `D:\pythonProject\orchestra\reports\2026-08-dashboard-acceptance.md`

**Interfaces:**
- Consumes: Task 3/4 全链路
- Produces: 验收报告 + 面板变化 artifact 三帧

- [ ] **Step 1: 快照帧 1**（派发前）：`--snapshot` 渲染 orchestra 面板 PNG → `D:\Temp\subsystem-4\frame-1-before.png`；`/api/dashboard` 存档
- [ ] **Step 2: 派 demo 任务**：写任务文件 → `sync_push.sh`（带 ORCHESTRA_MONITOR_TOKEN，顺带验证 Task 5 链）→ 4B 执行
- [ ] **Step 3: 快照帧 2**（执行中，约 30-60s 后）：orchestra 面板 PNG + API 响应存档——预期 `queue_len`/`active_tasks` 变化
- [ ] **Step 4: 等待 done 后快照帧 3**：`sync_pull.sh` 拉结果；任务面板/API 显示队列回零、`last_task` = demo slug；核桃派 app 日志 grep `[eink] FULL refresh` 含 `→ orchestra` 行
- [ ] **Step 5: 用户肉眼确认**：墨水屏在 CC 空闲时于「闲置面板 ↔ 任务面板」间轮换，任务面板四卡内容正确
- [ ] **Step 6: 写验收报告**：所有数字/证据引用 artifact 路径（三帧 PNG、API 响应存档、日志行）；结论限「链路可视」事实，不产科研结论；`reviewed: ok` 落款
- [ ] **Step 7: Commit** `docs: subsystem-4 dashboard acceptance report`

### Task 7: 文档收尾 + 归档

**Files:**
- Modify: `docs/superpowers/specs/2026-08-18-research-orchestra-design.md`（§6.4 标记细化完成 + 验收结果，修订行升 v6；§13 清单勾掉第 4 项；§3 表格 usage-monitor 行补 `POST /api/orchestra`）
- Modify: `D:\pythonProject\orchestra\README.md`（新增「仪表盘链路」节：上报协议、token 配置点、任务面板说明）

- [ ] **Step 1: 更新文档**
- [ ] **Step 2: Commit** `docs: spec §6.4 finalized with acceptance result`

---

## Self-Review 记录

- **Spec 覆盖**：§6.4 逐项——state 新增 orchestra 块（Task 1，五字段含 last_sync）；新增 POST /api/orchestra 且鉴权复用 X-Monitor-Token（Task 1/3）；墨水屏任务面板（队列长度+活跃任务+Broker 健康，Task 2）；SHOW_ORCHESTRA 开关默认 True（Task 1）；分机部署（核桃派 usage-monitor × 4B Broker，Task 3/4）；上报者不是 CC hooks（Task 4/5）；验收 = demo 任务面板状态变化 + dashboard API orchestra 块（Task 6）。
- **与总 spec 的偏差（已记录 DECISIONS 026）**：① §6.4「仪表盘定时拉 Broker 状态 API」——v1 实现为推送为主（Broker report_status 是 mission 021 已部署现成通道；Broker 是纯 stdlib 守护进程无 HTTP 端点，拉取需加端点触及稳定服务，列为 out of scope），「定时拉」解释为仪表盘侧 APScheduler 定时检查刷新；② `broker_health` 展示以新鲜度推导为准而非 payload 直显（stale 阈值 90s = 3×poll）；③ `last_sync` 上报源为 Windows sync 脚本；④ D9 用户拍板：面板体系从「双面板轮换」转向「融合单面板」，Broker payload 扩展 `recent_tasks`（原「零 Broker 改动」约束废止，改为带测试的小改动）；⑤ §6.4「墨水屏任务面板（队列长度+活跃任务+Broker 健康）」按 D9 落实为状态条+任务列表的融合布局。
- **占位符扫描**：`<date>`/`<token>`/`<epoch>` 均为部署期变量（执行时取实际值）；无代码占位。
- **风险预案**：核桃派 1GB/512M 上限——快照 CLI 是退出式单次进程、任务面板零新依赖；部署后观察 `systemctl status monitor` 内存（MemoryMax 触发则回滚 panel 轮换改纯 API 模式并上报）；墨水屏轮换全刷频率 60s/次可调 ORCHESTRA_ROTATE_SEC，残影由 30min 强制全刷兜底；token 泄漏——只在两 Pi 之间 ssh 会话流转，D:\Temp 存档仅存 API 响应（响应不含 token）。
- **不动项复核**：Broker 代码零改动（仅 config.json）；usage-monitor 三端点语义不变；`~/.claude/settings.json` 不碰；`/api/status` 上报链（已停用 hooks）不恢复。
