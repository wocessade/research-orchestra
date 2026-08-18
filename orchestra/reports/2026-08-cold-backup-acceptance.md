# 冷备链（NAS 方案 A）验收报告（2026-08-19）

## 验收项

| 项 | 结果 | 证据 |
|---|---|---|
| 核桃派备份接收端 | ✅ | rsync over ssh（4B→pi@192.168.0.200 免密）；备份目录 ~/backup/broker/{results,logs,db} |
| 每日定时备份 | ✅ | `orchestra-backup.timer` OnCalendar 03:00 + Persistent（错过补跑）；commit `6fcf8ab` |
| 首次全量备份 + 校验 | ✅ | 源 25 文件 = 目标 25 文件，耗时 2s，backup.log 记录 done OK |
| SQLite 一致性 | ✅ | 备份前 `.backup` 快照，防 WAL 边写边拷损坏 |
| 恢复演练 | ✅ | attempt-2 恢复到 4B /tmp/restore-drill，output.json md5 与源完全一致（129e3cf2...） |
| Samba Windows 访问 | ✅ | New-SmbMapping Z: → \\192.168.0.200\backup，db/logs/results 可读，user pi |

## 部署拓扑（用户已确认）

- **4B（Broker+执行层）→ 宿舍**：7×24 调度，供电网络稳定
- **核桃派（展示+冷备）→ 实验室工位**：墨水屏白天可见 + 冷备与主数据物理分离（异地灾备）
- 校园网互通待入学实测；不通则 Tailscale（总 spec §7）

## 遗留

- 备份日志与备份结果未接微信通知（subsystem-6 落地时的真实用例）
- SSD 挂载后备份源路径随 REMOTE_ROOT 迁移（`backup_to_nas.sh` 默认源参数已可传）
- 核桃派 SD 58G 余 53G，当前备份 184K，容量余量充足（可多年累积）
- 021 遗留：usage-monitor 在 4B 上还有一套旧实例在跑（核桃派迁移后未停）——是否停掉待用户确认（subsystem-4 时处理）
