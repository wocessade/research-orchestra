# Bogda Pi Gate 3 安装证据（安装但不启动）

日期：2026-08-24

执行者：本会话（Cursor / Grok）

仓库：`D:\pythonProject`

权威提交：`55b4d9b001c1ddb5fbb27d719309ffde1b19724b`（`git rev-parse HEAD` 于开始时；短号 `55b4d9b`；`docs(bogda): split Gate 2 parse vs Gate 3 command verify`）

Pi：`ssh liuxfs@100.111.75.58`（BatchMode；`sudo -n` 可用，未交互要密码）

Runbook：`bogda/docs/pi-shadow-runbook.md`（该提交）

部署副本：`/home/liuxfs/bogda-stage-55b4d9b/bogda`（`git archive 55b4d9b bogda`，不是脏工作树）

约束：只执行 `sudo deploy/pi/install.sh --install`。未加 `--start`。未运行 `--start-server` / `--start-services`。未 enable/restart 任何 Bogda 服务。未停改 Orchestra。未改防火墙、Tailscale、3100。未进入 Gate 4。未打印 env 秘密。

总判断：**安装完成且服务未启动。`systemd-analyze verify` 对六份已安装 unit 的 `verify_exit=0`。** python/prefect 已可执行。Orchestra 仍 active，队列仍空。这不表示 Pi shadow 已在跑。

---

## 1. 本机基线与部署包

| 检查 | 结果 |
|---|---|
| `git rev-parse HEAD` | `55b4d9b001c1ddb5fbb27d719309ffde1b19724b` |
| `main` | 同一提交 |
| 脏工作树 | `.gitignore`、锐评删除、`.codegraph/`、天气文档等 **未** 进入 tar |
| 归档命令 | `git archive --format=tar -o D:\Temp\bogda-55b4d9b.tar 55b4d9b bogda` |
| tar SHA-256 | `90dce8c1ec6da7a58617b3ae7c5c614fcb07963749a2c29a1fa0a7ef7a1ca3d3`（本机与 Pi `/tmp/bogda-55b4d9b.tar` 一致） |
| 展开 | `tar xf` → `/home/liuxfs/bogda-stage-55b4d9b/bogda/` |
| `pyproject.toml` SHA-256 | `38811eeee4be9edf24608e2a9fc51169d671e40db2667d8b2031010f8c5fbdcd`（本机 blob 与 Pi 文件一致） |
| `uv.lock` SHA-256 | `62fefdeeefc3e4c8d8b1c3f5391fd6158624c84d323f9c0d2a515a8a9708b5c5` |
| `deploy/pi/install.sh` SHA-256（归档原样） | `f1fc8356e2db29bb723b70a6f73d3d204c1972cdcce9d13e79df043b26bf6ca6` |

`55b4d9b` 中的 `install.sh` / `rollback.sh` blob 为 CRLF。Linux `bash` 无法执行。在核对哈希之后，仅对 stage 里这两个 `*.sh` 做了 CRLF→LF，未改仓库、未改 unit 文件。随后 dry-run / `--install` 使用该 LF 副本。

---

## 2. 安装前复核（不符则停止）

窗口：2026-08-24T06:53:48Z。

| 检查 | 实测 | 退出码 | 结论 |
|---|---|---|---|
| `systemctl is-active orchestra-broker.service` | `active`（PID 1029，自 2026-08-23 09:49:15 CST） | 0 | 通过 |
| 在途 Orchestra 任务 | `/home/liuxfs/broker-data/tasks/` 仅 `archive/`，顶层 `T-*.md` 0 个 | 0 | 通过 |
| `/mnt/nas` | `/dev/sda1 ext4 UUID=d105381a-d80e-47b0-8bb4-2a8c4b56600f` | 0 | 通过（与 Gate 2 相同） |
| fstab | `UUID=d105381a-d80e-47b0-8bb4-2a8c4b56600f /mnt/nas ext4 defaults,nofail 0 2` | 0 | 通过 |
| TCP 4200 | `ss -lnt` 无 `:4200` | 0 | 通过 |
| 已有 Bogda | `/opt/bogda` `/etc/bogda` `/mnt/nas/.bogda` 不存在；`bogda-*` unit files 0 | 2 / 1 | 通过 |

`sudo -n true` 退出 0，无需人工密码。

---

## 3. Stage 检查与 dry-run

`cd /home/liuxfs/bogda-stage-55b4d9b/bogda`

| 命令 | 时间 (UTC) | 退出码 | 摘要 |
|---|---|---|---|
| `PYTHONPATH=src python3 -m bogda.ops.bundle check deploy/pi` | 07:11:01 | 0 | `CHECK bundle valid` |
| `bash deploy/pi/install.sh --dry-run` | 07:11:01 | 0 | 声明将写 `/opt/bogda` `/etc/bogda` `/mnt/nas/.bogda/...`；`PRESERVE no service starts unless --start is supplied later` |
| `bash deploy/pi/rollback.sh --dry-run`（安装前） | 07:11:01 | 0 | 指针当时 absent（符合未安装） |

说明：用户/runbook Gate 1 写的是 `install.sh --dry-run`。`55b4d9b` 的 `install.sh` 用法是 `--dry-run | --install [--start] | --start-server | --start-services`。实际执行的是 `--dry-run` 与 `--install`。

---

## 4. 安装命令

主机当时没有 `uv`。`install.sh` 把 `uv` 列为 required_command。2026-08-24T07:13:16Z–07:13:52Z：

```
curl -LsSf https://astral.sh/uv/install.sh | sudo -n env UV_INSTALL_DIR=/usr/local/bin sh
```

结果：`uv 0.12.5 (aarch64-unknown-linux-gnu)` → `/usr/local/bin/uv`。这是为了让获准的 `--install` 能跑，不是启动 Bogda。

唯一安装命令（07:17:00Z–07:36:22Z）：

```
sudo -n env PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin bash deploy/pi/install.sh --install
```

**`install_exit=0`。未传 `--start`。**

`uv sync --frozen`：CPython 3.13.5，venv `/opt/bogda/.venv`，Prepared 105 packages in 19m 20s，含 `prefect==3.8.3`、`bogda==0.1.0`（from stage 路径）。

系统用户：`bogda` uid 999 gid 982 shell `/usr/sbin/nologin` home `/opt/bogda`。

---

## 5. 服务未启动 / 未 enable

采集：2026-08-24T07:44:14Z。

| unit | `is-active` | active 退出码 | `is-enabled` | enabled 退出码 |
|---|---|---|---|---|
| `bogda-prefect-server.service` | inactive | 3 | disabled | 1 |
| `bogda-pi-worker.service` | inactive | 3 | disabled | 1 |
| `bogda-prefect-snapshot.service` | inactive | 3 | static | 0 |
| `bogda-prefect-snapshot.timer` | inactive | 3 | disabled | 1 |
| `bogda-shadow-health.service` | inactive | 3 | static | 0 |
| `bogda-shadow-health.timer` | inactive | 3 | disabled | 1 |

server、worker、两个 timer **不是 enabled**。两个 oneshot service 为 systemd `static`（无 `[Install]` 启用点），且 inactive。

`ss -lnt`：无 TCP 4200。Orchestra 仍 `active`。顶层任务卡仍为 0。

---

## 6. Gate 3 `systemd-analyze verify`

07:44:14Z，对 `/etc/systemd/system` 上六份已安装 unit：

```
systemd-analyze verify \
  /etc/systemd/system/bogda-prefect-server.service \
  /etc/systemd/system/bogda-pi-worker.service \
  /etc/systemd/system/bogda-prefect-snapshot.service \
  /etc/systemd/system/bogda-prefect-snapshot.timer \
  /etc/systemd/system/bogda-shadow-health.service \
  /etc/systemd/system/bogda-shadow-health.timer
rc=$?
printf 'verify_exit=%s\n' "$rc"
```

**`verify_exit=0`。**

分类：

- Bogda unit：无 unknown key、无 illegal section、无 python/prefect not executable。
- `/opt/bogda/.venv/bin/python` 与 `prefect`：`test -x` 退出 0。python → `/usr/bin/python3`；prefect 为 302 字节脚本，root:root，`0755`。
- 非 bogda：四条既有 Orchestra/NAS timer `Timezone` ignoring（与 Gate 2 相同）。按修订 runbook **只记录，不算 Bogda 失败**。未改那些 timer。

---

## 7. env 元数据（未输出值）

`/etc/bogda/bogda.env`：普通文件，非 symlink；mode `640`；owner `root`；group `bogda`；`sentinel_present=true`；4 行。未 cat、未打印赋值。

---

## 8. 回滚指针、inventory、权限

`/etc/bogda/last-backup` → `/etc/bogda/backups/20260824T071700Z`（在 `/etc/bogda/backups/` 下）。文件 mode `644` root:root。

`inventory.tsv` **恰好 7 行**，安装前状态全部为 `absent`（与预检“未安装”一致）：

```
/etc/bogda/bogda.env	absent
/etc/systemd/system/bogda-prefect-server.service	absent
/etc/systemd/system/bogda-pi-worker.service	absent
/etc/systemd/system/bogda-prefect-snapshot.service	absent
/etc/systemd/system/bogda-prefect-snapshot.timer	absent
/etc/systemd/system/bogda-shadow-health.service	absent
/etc/systemd/system/bogda-shadow-health.timer	absent
```

备份目录内只有 `inventory.tsv`（357 字节），无被覆盖的旧 unit，符合首次安装。

| 路径 | mode | owner | group | 类型 |
|---|---|---|---|---|
| `/opt/bogda` | 755 | bogda | bogda | directory |
| `/opt/bogda/.venv` | 755 | root | root | directory |
| `/etc/bogda` | 750 | root | bogda | directory |
| `/etc/bogda/backups` | 750 | root | bogda | directory |
| 六份 unit | 644 | root | root | regular file |
| `/mnt/nas/.bogda` | 755 | root | root | directory |
| `/mnt/nas/.bogda/prefect` | 750 | bogda | bogda | directory |
| `/mnt/nas/.bogda/snapshots` | 750 | bogda | bogda | directory |
| `/mnt/nas/.bogda/manifests` | 755 | root | root | directory |
| `/mnt/nas/.bogda/manifests/health` | 750 | bogda | bogda | directory |

`/mnt/nas/.bogda` 与 `manifests`、`.venv` 为 root:root，不是 `bogda:bogda`。`install.sh` 只把三个叶子目录 `install -d -o bogda`。**未改脚本去纠正。** 记为观察项。

`/home/liuxfs/broker-data` 仍为 `liuxfs:liuxfs`，mtime Aug 20 01:22。`/mnt/broker` 仅 `ls -ld`，未写入。

---

## 9. 安装后 rollback dry-run（未 apply）

07:44:15Z：`bash deploy/pi/rollback.sh --dry-run`，**`rollback_dry_after_exit=0`**。未 `--apply`。

dry-run 打印 `CHECK backup pointer /etc/bogda/last-backup absent`。安装脚本写入的是 `/etc/bogda/last-backup`。这是 dry-run 检查名与真实指针不一致，**未改脚本**。真实指针存在且有效。

---

## 10. Orchestra 未受影响

- `orchestra-broker.service` 安装前后均为 `active`，同一 Main PID 1029、同一 Invocation。
- 未 stop/restart/edit Orchestra unit。
- 任务目录仍无在途 `T-*.md`。
- verify 中的 Timezone 警告来自既有 timer，未修改。

---

## 11. Gate 4 前剩余阻塞（本次停止）

1. `bogda.env` 仍是哨兵（`sentinel_present=true`）。Gate 4 才允许换成真实 Basic Auth；不得在日志里打印。
2. 服务故意未启动；shadow 尚未运行。
3. 未做 Tailscale/防火墙/非 tailnet 暴露实测（Gate 4）。
4. `/mnt/nas/.bogda` 与 `.venv` 所有权观察项：是否要在启动前 chown。
5. 已提交 shell 脚本 CRLF：下次从 Windows `git archive` 仍需 LF 化才能在 Pi 上跑。
6. 主机新增 `/usr/local/bin/uv` 0.12.5。

**未进入 Gate 4。未启动 Prefect。**

---

## 12. 仓库

本报告：`docs/reports/2026-08-24-bogda-pi-gate3-install.md`。

拟在独立 `codex/` 分支提交；不合并 main、不 push。
