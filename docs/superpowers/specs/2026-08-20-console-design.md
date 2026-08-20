# GUI 控制台设计：以日程日历为核心的汇合面（Homepage 兼容改造）

- 日期：2026-08-20 · 状态：设计定稿（分节已获批），待用户审阅
- 背景痛点：墨水屏信息密度不足 + CC 后台反馈受限，两痛点同源 = 系统缺一个「汇合面」

## 1. 定位与边界

- 控制台 = Research Orchestra 的第 7 个资产，**纯消费端**：只读呈现，不改任何生产链路
- 硬边界：**Pi 侧零改动；既有 API 零改动**（只读消费已有端点）；唯一新增运行件 = Homepage + glue（~200 行 stdlib）
- 决策在对话里做（审批/派任务仍回 CC 会话，保决策留痕），控制台只呈现状态与日程

## 2. 选型结论

| 方案 | 结论 | 理由 |
|---|---|---|
| A 自研 FastAPI | 否决（用户定调） | 不从 0 写，只做兼容修改 |
| Glance | 否决 | 日历 widget 无事件支持（源码实证） |
| Vikunja | 否决 | 项目管理工具，无系统状态面板 |
| **Homepage (gethomepage)** | **采用** | calendar widget 原生 ical 集成（monthly/agenda 双视图、多源分色）；customapi widget 渲染 JSON；Node 直跑免 Docker；页面/布局纯 yaml 配置 |

我方工作量 = 一个 glue 脚本 + 配置 + 测试，其余全部是 Homepage 现成能力。

## 3. 架构与数据流

```
源（零改动）                                    glue（orchestra/console/）              展示
4B reporter → 核桃派 usage-monitor ─ GET /api/dashboard ─┐
   （30s POST，既有链路）                       ──────┴→ refresh ─→ out/status.json ─┐
4B results/logs ─ scp sync_pull.sh（既有脚本，不改）────→ 本地快照 ──→ out/radar.json ──┤
console-schedule.toml（system 定时器镜像 + personal 手录）──→ 双 ICS ──→ out/system.ics ─┤ Homepage
messages.md（CC 留言，入库）───── mtime 热重 ──→ out/messages.json ──────────────────┘ :3000
```

- **Homepage**：node app，监听 127.0.0.1:3000；配置目录挂载 `orchestra/console/homepage/`（services.yaml / settings.yaml / bookmarks.yaml，均入库）；app 本体装 `D:\Apps\homepage`（node_modules 不入库）
- **glue = `orchestra/console/console_feed.py`**（stdlib only，Python 3.11+，两个子命令）：
  - `refresh`：GET 核桃派 usage-monitor `GET /api/dashboard`（既有只读端点，X-Monitor-Token 走环境变量）→ out/status.json；运行 sync_pull.sh（既有脚本，不改）→ 本地 results/logs 快照 → out/radar.json；读 console-schedule.toml → 展开生成 out/system.ics / personal.ics；读 messages.md → out/messages.json
  - `serve`：stdlib http.server 在 127.0.0.1:3100 静态服务 out/；每次 GET messages.json 前检查 messages.md mtime，变了就热重生成（CC 留言秒级可见）
- **调度**：Windows 任务计划每 10 分钟跑一次 `refresh`（+手动随时）；`serve` 常驻
- **展示**：Homepage 各 widget 指向 http://127.0.0.1:3100/

## 4. 日历数据模型

单一事实源 `orchestra/console/console-schedule.toml`（TOML：tomllib 为 3.11 stdlib，保 glue 零依赖；原案 yaml 仅序列化格式不同，结构一致）：

```toml
[system]                          # 系统层：4B systemd timer 的镜像声明
radar = "23:30"                   # 每日夜间雷达注入（orchestra-timer）
cold_backup = "03:00"             # 每日冷备到核桃派（orchestra-backup）
nas_backup = "04:17"              # 每日 NAS 盘内备份（nas-backup）
housekeeping = { time = "04:00", dow = "sun" }   # 周日

[[personal]]                      # 个人层：手录
date = "2026-09-01"
time = "09:00"
title = "开学报到"
note = "宿舍-实验室互通实测待办"
```

- glue 把 system 段展开为 RRULE 循环事件 → **system.ics**（Homepage 配蓝色）；personal 手录 → **personal.ics**（绿色）。分色 = 按源，Homepage 每个 ical 集成一种颜色
- v1 只展示不推送；ICS 已落盘 out/，未来手机日历订阅零改造（需求未定，挂账）
- **漂移纪律**（教训 L18/L26）：system 段是 Pi timer 的**镜像**，权威在 4B `systemctl list-timers`；deploy/运维改动 timer 时同步改 TOML，验收含逐条核对
- 实验 DDL：实测实验卡（EXP-001）front-matter 无 deadline 字段 → **v1 手录进 personal**；自动扫描挂账 v2（给卡 schema 加 deadline 字段属 engine 改动，需单独评审）

## 5. 页面结构与布局

**页 1「今天」＝晨间一屏（默认首页）**

```
┌─ 状态条：4B●在线 核桃派●在线 Win●在线｜队列 2 卡/活动 1｜最近任务：T-…rank done 23:47 ─┐
│ 日历 agenda 视图（昨3天→今天→未7天，maxEvents 15）                              │
│   ● 23:30 夜间雷达（系统层·蓝）    ● 14:00 组会（个人层·绿）                    │
│   ● 09:00 开学报到                ● 03:00 冷备（系统层）                       │
├─ CC 留言（最新 5 条）+ 待决事项（红色徽章）────────────────────────────────┤
└─ 下一触发：雷达 2h13m 后 / 冷备 5h42m 后 ───────────────────────────────────┘
```

- **页 2「雷达」**：最近一期 digest 全文（digest.txt）+ top5 列表 + 四阶段状态时间线（10-fetch / 20-rank / 30-render / 40-notify 各自 done/failed 时刻，来自本地 results 各 attempt 的 state.json）
- **页 3「任务/实验」**：queue_len / active_tasks + recent_tasks（monitor 已含，前 8 条）+ 本地最近 attempt 结果（results/ 扫描，绿 done / 红 failed）+ 实验卡状态（扫描 research_root，缺省 `D:\pythonProject\.research`，不存在则显示「未初始化」）
- **页 4「系统」**：三端在线/负载（4B = orchestra 上报，核桃派 = self_status，Windows = 本地 last_sync）+ 各 timer 下次触发 + orchestra_last_report 新鲜度
- 手机：竖屏单列可读（agenda 视图天然适配）；v1 默认仅本机访问（见 §11）

## 6. 状态聚合映射（status.json 字段 → 来源，全部零改动）

| 字段 | 来源 |
|---|---|
| devices.4b | orchestra_last_report 新鲜度（<2min 判在线）+ orchestra.host（load1/mem_pct） |
| devices.walnut | GET /api/dashboard 成功即在线 + self_status |
| devices.windows | 本地恒在线；last_sync 展示 |
| queue.len / queue.active | orchestra.queue_len / active_tasks |
| recent_tasks | orchestra.recent_tasks（Broker 权威，前 8 条） |
| next_triggers | system 段展开计算（雷达/备份倒计时） |
| radar.* | 本地 results 最近一期 digest.txt / top5.json / validation.json + 四阶段 state.json |
| 最近 attempt | 本地 results/ 扫描（sync_pull 已拉） |

（定稿微调：原案页 3 的 pending 卡明细 v1 以 queue_len 计数 + recent_tasks 呈现，不新增拉 tasks/ 目录的链路——monitor 状态已含计数，明细挂账 v2）

## 7. CC 反馈通道协议

文件 `orchestra/console/messages.md`（**入库**——CC 反馈的审计轨迹，符合决策留痕哲学）：

```markdown
## 2026-08-21 08:00 — 雷达日报已出
top5 中 2 篇与你方向相关，建议精读（附 digest 链接）
- 待决：SD 旧副本是否删除？（挂账 #4）

## 2026-08-21 08:05 — deploy 窗口建议
4B 已 14 天未部署，032 修复包待真机验证
```

- 解析规则：每条 `## 时间 — 标题` + 正文；`- 待决：` 行 → 红色待决徽章；`- 告警：` 行 → 黄色
- 发布 = CC 写文件；serve 热重后秒级可见；时间倒序渲染
- **分工纪律**：CLAUDE.md 挂账是待办的权威清单，留言板是它的增量呈现层——留言只放新事件与状态变化，不复制挂账全文（避免双写）

## 8. 错误处理与降级

- glue 拆纯函数（ICS 展开 / 状态聚合 / TOML 解析 / 留言解析），可独立测试
- **降级不报错**：usage-monitor 不可达 → 设备区灰点 + offline + 数据时间戳；token 未配 → 设备区提示「未配置 ORCHESTRA_MONITOR_TOKEN」；sync_pull 失败/快照缺失 → 任务区「无数据」；ICS 生成失败 → 保留上次产物 + 自动写一条告警留言
- 日志：out/feed.log（refresh 每次落一行：各源成功/降级清单）；serve 输出重定向同目录

## 9. 测试与验收

- unittest ~20 个：ICS 往返解析（RRULE 展开窗口/格式断言）、状态聚合（mock GET 响应 + 离线降级路径）、TOML 解析与校验（坏输入报错不崩）、留言解析（徽章分类/时间倒序）
- 验收标准：
  1. 日历事件 vs 4B `systemctl list-timers` 逐条核对一致
  2. 留言写入 → 页面可见 ≤ 5s（热重路径）
  3. 桌面 + 手机（**若启用 v1.5**）各一张截图，手工过四页；仅 v1 时手机项跳过
  4. 断网演练：关 4B/核桃派后控制台各页降级显示、无异常退出

## 10. 分阶段

| 阶段 | 内容 |
|---|---|
| **v1（本次）** | Homepage 部署 + glue + 双层日历 + 状态条 + 留言板 + 四页全量只读 |
| v1.5（可选，数行配置） | Homepage 绑定 tailnet IP 供手机访问（无内置鉴权，仅信任域内使用） |
| v2（开学后） | 事件点击→对话派任务、推送提醒、Zotero 归档按钮、实验 DDL 自动扫描、pending 卡明细、磁盘用量/上次备份时刻（需 4B reporter 扩展字段） |

## 11. 安全与仓库纪律

- 凭据：X-Monitor-Token 走环境变量（与 sync_pull.sh 同约定），绝不入库；Homepage 配置不含敏感项
- Homepage 无内置鉴权 → 默认仅 127.0.0.1；暴露 tailnet 属信任域内操作（v1.5 时明确告知风险）
- 仓库：入库 = console_feed.py + console-schedule.toml + messages.md + homepage 配置 + tests；**不入库** = out/ 产物（.gitignore）、Homepage app 本体（D:\Apps\homepage）
- 目录约定：orchestra/console/

## 12. 挂账（本设计沉淀）

- 手机日历订阅（ICS 架构就绪，需求未定）
- 实验卡 deadline 字段（engine schema 变更，v2 单独评审）
- pending 卡明细、磁盘用量、上次备份时刻（v2，需 4B reporter 扩展字段）
