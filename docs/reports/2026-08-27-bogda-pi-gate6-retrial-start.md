# Bogda Pi 新 72 小时 trial 启动

日期：2026-08-27

执行者：本会话（Cursor / Grok）

Pi：`ssh liuxfs@100.111.75.58`

新试运行编号：`20260827T124429Z`

上一轮：`20260824T083454Z` **未通过**（见 `docs/reports/2026-08-27-bogda-pi-gate6-acceptance.md`）。本编号不得改口为通过。

## 结论

在 `/mnt/nas` 已挂载、Orchestra 仍 active 的前提下，归档了失败 trial 的 jsonl，启动 Prefect server 与 worker（`--limit 1`），并写入新 trial 的首个健康样本：`api_ok=true`。未改 unit、fstab、并发或防火墙。未宣布 Gate 6/7 通过。

满 72 小时截止点：**2026-08-30T12:44:29Z**（北京时间 2026-08-30 20:44:29）。

## 操作

1. 误伤清理：PowerShell 展开 `$health_root` 曾在根目录留下空文件 `/samples.jsonl`，已 `rm`。原失败 jsonl 未被移动。
2. 归档：`/mnt/nas/.bogda/manifests/health/archive/samples-20260824T083454Z.jsonl`（426062 bytes）。
3. 新文件：`samples.jsonl` mode 640 `bogda:bogda`；`current-trial-id` = `20260827T124429Z`。
4. `systemctl enable --now bogda-prefect-server.service` at `2026-08-27T12:44:37Z`；`wait-api` 约 29s 后 exit 0；`0.0.0.0:4200` LISTEN。
5. `enable --now` worker + 两个 timer。`ExecStart` 含 `--pool pi-service --type process --limit 1`。
6. 立即 `systemctl start bogda-shadow-health.service` 取首样本。

`/etc/bogda/last-backup` 前后均为 `/etc/bogda/backups/20260824T071700Z`。Orchestra `active`。server/worker `NRestarts=0`。

## 首样本

`timestamp`: `2026-08-27T12:45:22.964852Z`

| 字段 | 值 |
|---|---|
| api_ok | true |
| api_latency_ms | 约 49.6 |
| database_integrity | ok |
| oom_kill_count | 0 |
| swap_used_bytes | 0 |
| mem_available_bytes | 1173241856 |
| disk_free_bytes | 232455184384 |
| bogda-prefect-server | active |
| bogda-pi-worker | active |

本机 `POST /api/flows/count` 无鉴权返回 **401**。带鉴权探测因本机引号转义未完成；首样本 `api_ok=true` 已由 unit 的 `EnvironmentFile` 走通健康探针。

## 未做

- 未改 `Requires=mnt-nas.mount`（USB 依赖失败仍会在下次意外重启后复现）
- 未受控 reboot
- 未切 3100、未接宿舍 runner、未提高并发
- 未宣布 Gate 7

## 观察纪律（新 trial）

- 健康 timer 每 5 分钟追加 `samples.jsonl`；不要与归档的失败 trial 混读。
- 任何 API 失败、OOM、integrity 非 ok、UUID 变化、4200 公网可达：保存现场并停止接受判断。
- USB 掉盘后 server 不会自动再起，这是已知缺口，新窗口里一旦再出现即记入报告，不在未批准时改 unit。
