# Bogda RK3528 Gate 6 启动（24 小时窗）

日期：2026-08-28

执行者：本会话（Cursor / Grok）

主机：`ssh liuxfs@10.77.0.1`（RK3528）

试运行编号：`20260828T064220Z`

## 结论

owner 将 Gate 6 观察窗从 72h 改为 **24h**（须覆盖一次每日快照 timer 与一次受控重启）。归档切机前混用的 jsonl，在 RK3528 上开新 trial。未宣布 Gate 6/7 通过。未改 unit、fstab、并发或防火墙。未做受控重启。

满 24 小时截止点：**2026-08-29T06:42:23Z**（北京时间 2026-08-29 14:42:23）。

## 只读核对

| 项 | 结果 |
|---|---|
| bogda-prefect-server / pi-worker | active |
| snapshot.timer / shadow-health.timer | active |
| `/mnt/nas` | `/dev/sda1` ext4 UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f` LABEL `nas-data` |
| 真机 unit | `RequiresMountsFor=/mnt/nas/.bogda`；**没有** `Requires=mnt-nas.mount` |

## 操作

1. 归档：`/mnt/nas/.bogda/manifests/health/archive/samples-20260827T124429Z.jsonl`（切机前复测 + 搬盘后混样）。
2. 新 `samples.jsonl` mode 640 `bogda:bogda`；`current-trial-id` = `20260828T064220Z`。
3. `systemctl start bogda-shadow-health.service` 取首样本。未碰 Prefect server/worker 的 enable 状态。

## 首样本

`timestamp`: `2026-08-28T06:42:23.501924Z`

| 字段 | 值 |
|---|---|
| api_ok | true |
| api_latency_ms | 约 57.7 |
| database_integrity | ok |
| oom_kill_count | 0 |
| swap_used_bytes | 0 |
| mem_available_bytes | 约 3.09 GB |
| bogda-prefect-server / bogda-pi-worker | active |

## 未做

- 未受控 reboot（窗内仍要做一次，须另开口）
- 未独立 restore 演练
- 未切 3100、未接 3101 真 Prefect 写入
- 未宣布 Gate 7
