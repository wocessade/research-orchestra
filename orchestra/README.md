# Orchestra — 科研编排调度中枢

以 Claude Code 为核心的科研-实验-论文框架（总 spec：docs/superpowers/specs/2026-08-18-research-orchestra-design.md）。

| 目录 | 用途 |
|------|------|
| config/rules.yaml | 执行器分派规则与降级顺序（CC 分派前读） |
| config/model-routing.md | 模型调度策略表（**预留**：用户另行维护，见总 spec §8） |
| tasks/ | 任务文件总线：CC 写入，Broker 轮询 |
| results/ | 执行器产出（attempt-N/ 目录：stdout/stderr/state.json） |
| logs/ | broker.log 与执行日志 |
| reports/ | CC 复查记录 |
| scripts/ | sync_push.sh / sync_pull.sh / deploy_broker.sh / backup_to_nas.sh |
| broker/ | Broker 源码（stdlib only，scp 部署到 4B） |
| templates/ | dsh 任务模板（nightly-radar 等，inject_daily 填充日期后注入） |

任务文件格式（严格）：

    # T-YYYYMMDD-<slug>
    executor: dsh | shell
    net: required | optional
    result: T-YYYYMMDD-<slug>
    timeout: <秒，默认 3600>
    ---
    <执行体：dsh 任务的 prompt 全文，或 shell 任务的命令>

快速流程：写 tasks/T-*.md → sync_push.sh → 等 Broker 执行 → sync_pull.sh → CC 复查写 reports/。任务终态后 broker 自动把任务文件移入 tasks/archive/（本地 tasks/ 经 sync_pull 同步该状态）。

## 夜间文献雷达（mission 023）

- 每日 23:30 `orchestra-timer.timer` 触发 `inject_daily.sh`：`templates/nightly-radar.md` 填日期 → 注入 `tasks/T-<日期>-nightly-radar.md`（幂等）
- dsh 执行：arXiv cs.CL/cs.LG 各 30 篇 → 按 arXiv ID 去重 → 六维评分（35/20/15/10/10/10，topic<10 淘汰）→ 选 5 篇
- 产出：digest.json / digest.txt / top5.json / papers_all.json；邮件投递有 /tmp/radar-sent-<日期> 幂等标记（防重试重复发信）
- 周日 04:00 housekeeping：清理 14 天前 dsh 会话、磁盘余量告警（邮件）；日志 logrotate 7 天

## 实验管线闭环（mission 025 / 总 spec §6.2）

- 实验卡（`.research/experiments/EXP-*/card.md`）新增 `## Commands` 段：无头可执行命令、`# arm: <id>` 臂标记、数值只来自 run artifact（最后一条命令产 metrics.json，符合 metrics.schema.json）
- 闭环：卡 → CC 审查 → Broker 入队 → shell/dsh 无头执行 → metrics.json → `run_card.py ingest` 入账（engine ingest_run.py）→ CC 复查写 reports/（数字只引用 ingest artifact 路径）
- `scripts/run_card.py commands <card.md> [--arm ID]` 提取卡命令生成任务文件；`scripts/run_card.py ingest <metrics.json> --card <card.md> --research-root <root>` 入账（engine 三脚本只被调用不改动）
- 验收 demo：`orchestra/demo/`（EXP-001 对照实验，研究根隔离在 demo/.research/）；验收报告 `reports/2026-08-experiment-loop-acceptance.md`

## 仪表盘链路（mission 026 / 总 spec §6.4）

- 数据流：4B Broker reporter 线程每 30s `POST /api/orchestra`（recent_tasks + host 负载/内存）→ 核桃派 usage-monitor 融合面板（状态条 + 最近任务 + 设备区 + DeepSeek/天气行）；Windows sync 脚本上报 last_sync
- 鉴权：`X-Monitor-Token`（两 Pi 间流转；核桃派 override.conf / 4B config.json，均不入库）
- 面板刷新纪律：内容变化才全刷；last_report 时间戳与负载抖动只走局刷（D10/D14）
- 验收：`reports/2026-08-dashboard-acceptance.md`（reviewed: ok，含 D15 运行中帧）

## 部署连接（当前家庭网络）

- 4B：WiFi `liudfs`，静态 IP `192.168.0.250`（NetworkManager 连接名 liudfs；备用：有线 DHCP）
- 用法：`ORCHESTRA_SSH_HOST=192.168.0.250 [ORCHESTRA_REMOTE_ROOT=/mnt/broker] bash scripts/deploy_broker.sh`
- REMOTE_ROOT 默认 `/mnt/broker`（U 盘 ext4，fstab 按 UUID 挂载）；SD 过渡期传 `~/broker-data`
- **Tailscale 已装（三端同 tailnet）**：4B=`liuxfs`(100.111.75.58)、核桃派=`walnutpi`(100.64.2.60)、Windows=`laptop-w0cessade`；`ORCHESTRA_SSH_HOST` 为 env 驱动，切 tailnet 名零代码改动
- **学校网络切换：见 `docs/school-network-switch.md`**（入学前必读）

## 冷备链（NAS 方案 A）

- 核桃派（192.168.0.200）为冷备接收端：`~/backup/broker/`（rsync over ssh，免密）+ samba 共享 `\\192.168.0.200\backup`（user pi）
- 4B 每日 03:00 `orchestra-backup.timer` 触发 Pi 上 `/home/liuxfs/broker/backup_to_nas.sh`（repo 副本在 scripts/，deploy_broker.sh 同步传载；增量镜像 + SQLite 快照，源路径随 REMOTE_ROOT 改写）
- 部署拓扑：4B=宿舍（Broker），核桃派=实验室（展示+异地冷备）
- 验收报告：`reports/2026-08-cold-backup-acceptance.md`
