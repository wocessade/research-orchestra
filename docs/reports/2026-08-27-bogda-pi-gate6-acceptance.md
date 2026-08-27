# Bogda Pi Gate 6 验收证据

日期：2026-08-27

执行者：本会话（Cursor / Grok）

Pi：`ssh liuxfs@100.111.75.58`（BatchMode；`sudo -n` 可用）

试运行编号：`20260824T083454Z`

窗口：首样本 `2026-08-24T08:34:59Z` → 满 72 小时 `2026-08-27T08:34:59Z`。采集时刻 `2026-08-27T12:16:26Z`（北京时间 20:16）。

权威：`bogda/docs/pi-shadow-runbook.md` Gate 6 表；工作台 `docs/reports/2026-08-24-bogda-stage6-workboard.md`。

原始摘要：`docs/reports/2026-08-27-bogda-pi-gate6-summary.json`

## 结论

**Gate 6 本轮未通过。不要进入 Gate 7，不要接真实 Prefect S1/S2，不要切 3100。**

原因不是 72 小时不够，而是观察期内发生了**未计划重启**，之后 `bogda-prefect-server` 与 `bogda-pi-worker` 因 `mnt-nas.mount` 依赖失败而从未自动拉起。健康 timer 仍在采样，所以证据链还在，但 API 从 `2026-08-25T09:02:17Z` 起持续失败（592 次）。

未做受控重启：系统已意外重启过一次；Orchestra 仍 active，距 23:30 雷达不足 3 小时。工作台「停止并保留现场」优先于把死掉的 Prefect 再 reboot 一次。

快照 **create + 独立目录 restore** 已做：`integrity_check=ok`，live DB SHA-256 演练前后不变。

## 验收表

| 字段 | 实测（跳过 jsonl 第 221 行 NUL） | 判据 | 结果 |
|---|---|---|---|
| started_at / ended_at | `2026-08-24T08:34:59Z` → `2026-08-27T12:14:47Z` | 覆盖 72h 窗口 | 时间跨度够 |
| sample_count | 812 行可解析；72h 内 769 | 约 5 分钟一条 | 偏少（缺 64 个间隔 + 1 行损坏） |
| missing_intervals | 64 | 0 或每段有批准解释 | **未通过**（意外重启空洞，未经事前批准） |
| api_failure_count | 592 | 0；失败须先调查再接受 | **未通过**（已调查，见下；工作台遇 API 失败即中止接受） |
| api_latency_p95_ms | 42.5（仅成功样本） | ≲ 1000 ms | 成功段通过 |
| min_mem_available_bytes | 997298176（约 951 MiB） | 400 MB 为观察阈 | 记录；未破阈 |
| swap_growth_bytes | 0 | 无持续抖动 | 通过 |
| oom_kill_delta | 0 | 必须 0 | 通过 |
| oom_kill_counter_reset_count | 0 | 只允许记录在案的受控重启 | 计数未复位；重启是意外的 |
| oom_kill_unavailable_span_count | 0 | 必须 0 | 通过 |
| database_integrity_failure_count | 0 | 必须 0 | 通过 |
| min_disk_free_bytes | 232457854976 | Gate 2 约 232 GB 级 | 通过；UUID 未变 |

官方 CLI `python -m bogda.ops.health summarize` 因第 221 行全 NUL 退出 1。上表用同一 `summarize_samples()` 跳过该行。损坏行对应意外重启撕写，不是另一次故障。

## 现场（2026-08-27T12:16Z）

| 项 | 结果 |
|---|---|
| `/mnt/nas` | `/dev/sda1` ext4 `UUID=d105381a-d80e-47b0-8bb4-2a8c4b56600f`（与 Gate 2 相同） |
| `orchestra-broker.service` | active / enabled |
| `bogda-prefect-server.service` | **inactive** / enabled；`NRestarts=0`；本 boot 无 ActiveEnterTimestamp |
| `bogda-pi-worker.service` | **inactive** / enabled；同上 |
| `bogda-prefect-snapshot.timer` | active / enabled |
| `bogda-shadow-health.timer` | active / enabled |
| oneshot `.service` | inactive/static（timer 触发之间的正常态） |
| TCP 4200 | 本机无监听 |
| 公网 4200 | curl `114.222.12.87:4200` HTTP 000 / timeout 8s |
| `/etc/bogda/bogda.env` | mode 640，`root:bogda`；未打印内容 |
| `last-backup` 指针 | 不存在 |
| boot | `who -b`：2026-08-25 12:55 本地；`uptime` 约 2d 7h；`boot_id` `cd2e8ac4-46a3-4af5-855f-03c4bbe1b40d` |
| live `prefect.db` | 1277952 bytes，`integrity_check=ok` |

## 时间线（已解释的 API 失败）

1. `2026-08-24T08:34:59Z`：Gate 5 首样本，server/worker 均为 active。
2. 连续成功样本至 `2026-08-25T03:36:22Z`（北京时间 11:36）。
3. jsonl **第 221 行被写成 NUL**（撕写）。
4. 本机时间 **2026-08-25 12:55** 意外重启（不是 Gate 6 受控 reboot）。
5. `2026-08-25 12:59`：`bogda-prefect-server` / `bogda-pi-worker` **Dependency failed**（`Requires=mnt-nas.mount`）。
6. `mnt-nas.mount` 在 15:55–16:53 多次 dependency failed，**16:57 才 Mounted**。USB SSD 未在 boot 时就绪。
7. NAS 起来之后 **unit 没有自动再试**。此后每日可见 umount/remount（8/25 20:09、8/26 17:09、8/27 11:32），影子服务仍停着。
8. 健康采样从 `2026-08-25T09:02:17Z` 恢复，但 `api_ok=false`、server/worker=`inactive`，直到本次采集。

成功 220 / 失败 592 / 可解析 812。

## 快照与 restore 演练

每日 timer 快照仍在（server 停着，DB 内容冻结）：

- `prefect-20260824T160010Z`
- `prefect-20260825T160008Z`
- `prefect-20260826T160006Z`

本次演练（server 已停，无 live 写入者）：

```
sudo /opt/bogda/.venv/bin/python -m bogda.ops.snapshot create \
  --source /mnt/nas/.bogda/prefect/prefect.db \
  --destination /mnt/nas/.bogda/snapshots --keep 7
```

结果：`prefect-20260827T121850Z.db`，`integrity_check=ok`，`sha256=6446e404959c90c8c69b7173f38510675ab21d01af15409522c62dbcb1163db2`。

```
sudo ... snapshot verify \
  --snapshot .../prefect-20260827T121850Z.db \
  --manifest .../prefect-20260827T121850Z.json \
  --restore-dir /mnt/nas/.bogda/restore-drill-20260827T121850Z
```

结果：`integrity_check=ok`。live DB SHA-256 演练前/后均为 `ddabe4ee7e87bc995437c7c74a5232fc7d958d90e1b389e5ca885c4ae451af0b`（与快照文件哈希不同，因为快照做了 checkpoint；live 文件未被覆盖）。

## 明确没做

- 未受控 `reboot`（避免叠一次 Orchestra 停机，且 23:30 雷达将至）
- 未 `systemctl start` Prefect server/worker（工作台：保存现场、不临时改运行态当验收）
- 未改 unit、fstab、并发、防火墙、Tailscale
- 未切 3100、未接宿舍 runner
- **未宣布 Gate 7 通过**

## 下一步（需 owner 另口）

1. **DeepSeek 确定性复核**本报告字段与证据路径。
2. 复核后若同意恢复影子：在 NAS 已挂载时 `systemctl start bogda-prefect-server.service bogda-pi-worker.service`，确认 4200 与 worker limit=1，然后 **新开 72 小时 trial**（轮换 `samples.jsonl`）。本轮编号 `20260824T083454Z` 不得改口为通过。
3. 另开设计：`Requires=mnt-nas.mount` 在 USB 未就绪时会 dependency-fail 且不再自动重试。这是架构/unit 问题，不要在未批准时改 Pi unit。
4. Gate 7 只在「新 trial 通过」或 owner 书面接受本轮缺陷之后才做。
