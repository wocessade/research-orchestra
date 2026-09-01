# Bogda RK3528 Gate 6 新 24 小时 trial 启动

> **历史过程。** 本 trial 最终通过见 [`2026-08-31-bogda-rk3528-gate6-final-acceptance.md`](2026-08-31-bogda-rk3528-gate6-final-acceptance.md)。下文「未宣布通过」是启动当日口径。

日期：2026-08-30（北京）

执行者：本会话（Cursor / Grok）

主机：Tailscale `liuxfs@100.78.158.80`（RK3528）

试运行编号：`20260830T034154Z`

上一轮：`20260828T064220Z` **失败**（见 [`2026-08-29-bogda-rk3528-gate6-failure.md`](2026-08-29-bogda-rk3528-gate6-failure.md)）。8/30 服务恢复（[`2026-08-30-bogda-rk3528-prefect-restore.md`](2026-08-30-bogda-rk3528-prefect-restore.md)）**不是**本 trial。

## 结论

归档了失败轮（含恢复后混采）的 `samples.jsonl`，写入新 trial id，并打了第一枪健康样本：`api_ok=true`。现网 `pi-service` worker 已在跑，未重装、未 reboot、未接 `dorm-x86`。未宣布 Gate 6/7 通过。

满 24 小时截止点：**2026-08-31T03:41:55Z**（北京时间 2026-08-31 11:41:55）。窗内受控 reboot 已于 03:47Z 发出，SSH 未回，独立 restore 未做：[`2026-08-30-bogda-rk3528-gate6-reboot-restore.md`](2026-08-30-bogda-rk3528-gate6-reboot-restore.md)。

## 操作

1. 归档：`/mnt/nas/.bogda/manifests/health/archive/samples-20260828T064220Z.jsonl`（268177 bytes；含失败轮 + 恢复后 timer 混样）。
2. 新 `samples.jsonl` mode 640 `bogda:bogda`；`current-trial-id` = `20260830T034154Z`。
3. `systemctl start bogda-shadow-health.service` 取首样本。未跑 `install.sh`。`/etc/bogda/last-backup` 仍是 `/etc/bogda/backups/20260824T071700Z`。
4. Orchestra broker / exam-watch / smbd 未停。

## 首样本

`timestamp`: `2026-08-30T03:41:55.302602Z`

| 字段 | 值 |
|---|---|
| api_ok | true |
| api_latency_ms | 约 72.4 |
| database_integrity | ok |
| oom_kill_count | 0 |
| swap_used_bytes | 15204352（约 14.5 MiB；开窗观察值，不是当场失败） |
| mem_available_bytes | 约 3.08 GB |
| disk_free_bytes | 约 216 GiB |
| bogda-prefect-server / bogda-pi-worker | active |
| snapshot.timer / shadow-health.timer | active |

首样本里 `bogda-shadow-health.service=activating` 是 oneshot 正在采自己，预期。`bogda-prefect-snapshot.service=inactive` 是 oneshot 空闲，timer 仍 active。

## 未做

- 未受控 reboot（窗内仍要做，须另开口）
- 未独立 restore 演练
- 未离线 fsck / SMART
- 未接 `dorm-x86` worker / Wake Bridge
- 未切 3100、未接 3101 真 Prefect 写入
- 未宣布 Gate 7
