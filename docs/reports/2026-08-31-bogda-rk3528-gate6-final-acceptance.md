# Bogda RK3528 Gate 6 最终验收

日期：2026-08-31（北京时间）

结论：**通过**。

本结论只关闭 RK3528 Gate 6，不自动授权 3100 切换、真实 Prefect 写入、付费 Flow 或 Gate 7 产品迁移裁决。

## 验收对象与边界

- 主机：`rk3528`，aarch64。
- trial：`20260830T154019Z`。
- 原始证据：`/mnt/nas/.bogda/manifests/health/samples.jsonl`。
- 首样本：`2026-08-30T15:40:20.419427Z`。
- 最终验收样本：`2026-08-31T15:49:17.360880Z`。
- 覆盖跨度：86,936.941453 秒，即 24 小时 8 分 56.941453 秒。
- 检查方式：SSH 严格 host key、`sudo -n`、只读摘要/日志/文件系统/SQLite 检查；未重启服务、未修改数据库、未触发付费调用。

## 24 小时健康摘要

权威命令：

```text
/opt/bogda/.venv/bin/python -m bogda.ops.health summarize \
  --input /mnt/nas/.bogda/manifests/health/samples.jsonl
```

| 字段 | 实测 | 判据 | 结果 |
|---|---:|---:|---|
| sample_count | 275 | 约 5 分钟一条并覆盖至少 24h | 通过 |
| bad_lines | 0 | 0 | 通过 |
| missing_intervals | 0 | 0，或每段有批准解释 | 通过 |
| api_failure_count | 0 | 0 | 通过 |
| api_latency_p95_ms | 87.052628 | ≤ 1000 ms | 通过 |
| min_mem_available_bytes | 3,289,448,448 | 不低于 400 MB 观察阈 | 通过 |
| swap_growth_bytes | 0 | 无持续增长 | 通过 |
| oom_kill_delta | 0 | 0 | 通过 |
| oom_kill_counter_reset_count | 0 | 0，或仅批准重启 | 通过 |
| oom_kill_unavailable_span_count | 0 | 0 | 通过 |
| database_integrity_failure_count | 0 | 0 | 通过 |
| min_disk_free_bytes | 231,826,849,792 | 无异常下降，保持约 232 GB 级 | 通过 |

额外解析 275 行 JSONL，全部可解析。以下 unit 在每一个样本中的状态异常数均为 0：

- `bogda-prefect-server.service=active`
- `bogda-pi-worker.service=active`
- `bogda-prefect-snapshot.service=inactive`（timer 触发的 oneshot 预期状态）
- `bogda-prefect-snapshot.timer=active`
- `bogda-shadow-health.timer=active`

## 当前运行与存储状态

- `/mnt/nas`：`/dev/sda1`，ext4，`rw`，UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f`。
- Prefect server/worker：`active/running`、`Result=success`、`NRestarts=0`。
- snapshot/health timers：`active/waiting`、`Result=success`。
- 数据盘 fsck unit：`loaded`、`active/exited`、`Result=success`、`ExecMainStatus=0`。
- `/sbin/fsck.ext4`：e2fsck 1.47.0。
- trial 期间内核日志未匹配 USB disconnect、I/O error、ext4 error、buffer I/O、SuperSpeed reset、OOM kill 或 Out of memory。
- 四个 Bogda unit 在 trial 期间没有 warning 及以上级别日志。

## 重启与恢复证据

受控重启、正常 systemd fsck/mount 和独立 restore 已在 trial 启动时完成，本次最终检查重新以只读方式核验：

| 对象 | 字节 | SHA-256 | SQLite integrity_check |
|---|---:|---|---|
| snapshot `prefect-20260830T154230Z.db` | 1,351,680 | `4fd08d2369bda0b4650719c95fdca2adfe105d539364d109cfedcab30dd8365f` | `ok` |
| restore `restore-drill-20260830T154019Z/prefect-restored.db` | 1,351,680 | `4fd08d2369bda0b4650719c95fdca2adfe105d539364d109cfedcab30dd8365f` | `ok` |

两者字节数与哈希完全一致；live `prefect.db` 未被覆盖。

## 检查过程记录

- 部署中的 `python -m bogda.ops.health|snapshot` 仍输出已知 `runpy` 重复导入 warning；摘要退出码为 0，源代码修复已在 commit `81dc92d` 合并，未在观察窗内热更 Pi。
- 一次附加 curl 探测因本地引号展开错误进入密码提示，未提交密码、未输出秘密，也未改变远端；最终以健康样本和权威摘要为准。
- 一次 `snapshot verify` 使用了不完整参数，命令在 argparse 阶段退出，未执行恢复或文件写入；随后改用只读 SQLite URI、SHA-256 与 `PRAGMA integrity_check` 完成核验。

## 裁决

Gate 6 的持续运行、API、数据库、内存、swap、OOM、磁盘、受控 unit、正常 fsck/mount、重启恢复与独立 restore 条件全部有新鲜证据支持，且没有未解释的缺口或错误。

**Gate 6：PASS。**
