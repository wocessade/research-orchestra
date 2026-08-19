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

## 部署连接（当前家庭网络）

- 4B：WiFi `liudfs`，静态 IP `192.168.0.250`（NetworkManager 连接名 liudfs；备用：有线 DHCP）
- 用法：`ORCHESTRA_SSH_HOST=192.168.0.250 [ORCHESTRA_REMOTE_ROOT=/mnt/broker] bash scripts/deploy_broker.sh`
- REMOTE_ROOT 默认 `/mnt/broker`（U 盘 ext4，fstab 按 UUID 挂载）；SD 过渡期传 `~/broker-data`
- 开学后宿舍网络需重新探测 IP 并更新本说明

## 冷备链（NAS 方案 A）

- 核桃派（192.168.0.200）为冷备接收端：`~/backup/broker/`（rsync over ssh，免密）+ samba 共享 `\\192.168.0.200\backup`（user pi）
- 4B 每日 03:00 `orchestra-backup.timer` 触发 Pi 上 `/home/liuxfs/broker/backup_to_nas.sh`（repo 副本在 scripts/，deploy_broker.sh 同步传载；增量镜像 + SQLite 快照，源路径随 REMOTE_ROOT 改写）
- 部署拓扑：4B=宿舍（Broker），核桃派=实验室（展示+异地冷备）
- 验收报告：`reports/2026-08-cold-backup-acceptance.md`
