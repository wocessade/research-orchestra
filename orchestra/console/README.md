# Orchestra 控制台（GUI 汇合面，mission 034 v1）

以双层日历为核心的只读控制台：Homepage（127.0.0.1:3000）+ glue（127.0.0.1:3100）。
设计 spec：`docs/superpowers/specs/2026-08-20-console-design.md`；实施计划：`docs/superpowers/plans/2026-08-20-console-v1.md`。

## 组件

| 路径 | 职责 |
|---|---|
| console_feed.py | CLI 入口：`refresh` 聚合 / `serve` 静态服务 |
| feed_schedule.py | console-schedule.toml 解析 → 双 ICS（显式事件实例，窗口 前30天~后60天） |
| feed_messages.py | messages.md 解析（待决/告警分类）+ 自动告警追加（去重） |
| feed_status.py | usage-monitor GET /api/dashboard 聚合（在线判定/队列/倒计时，降级不报错） |
| feed_radar.py | results/.research 扫描（雷达四阶段+旧单体双布局） |
| feed_serve.py | out/ 服务，messages.json 按 mtime 热重 |
| homepage/ | Homepage 配置（四页 tab），start_homepage.bat 同步到 D:\Apps\homepage\config |
| out/ | 产物（不入库） |
| tests/ | unittest（`python -m unittest discover tests -v`，48 个） |

## 使用

- 手动刷新：`python console_feed.py refresh`（自动档：计划任务每 10 分钟）
- 手动起服务：`python console_feed.py serve`
- 环境变量（凭据仅走环境变量，绝不入库）：`ORCHESTRA_MONITOR_TOKEN`（usage-monitor 鉴权）、`ORCHESTRA_MONITOR_API`（默认 http://192.168.0.200:5000/api/orchestra）、`ORCHESTRA_SSH_HOST`（sync_pull 目标，未设则跳过同步）
- 留言协议：CC 写 `messages.md` 即发布（`## 时间 — 标题` + `- 待决：`/`- 告警：` 行），秒级热重可见
- 日程漂移纪律：system 段是 Pi systemd timer 镜像，权威在 `systemctl list-timers`；改动 timer 时同步改 console-schedule.toml
- 手机访问（v1.5 可选）：serve 改绑 tailnet IP + Homepage 设 `HOMEPAGE_ALLOWED_HOSTS=<tailnet-ip>:3000` + 启用 `HOMEPAGE_AUTH_*` 鉴权门（Homepage v2 内置，密码放环境变量）

## 降级语义

usage-monitor 不可达/token 未配 → 设备区离线 + degraded_reason 展示；sync_pull 跳过 → 雷达/attempt 区沿用旧数据；ICS 生成失败 → 沿用上次产物 + 自动告警留言。
