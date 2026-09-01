# Bogda RK3528 Gate 6 受控 reboot（restore 未完成）

> **历史过程。** 本文件记录 trial `20260830T034154Z` 的 reboot 窗口与 SSH 缺口。Gate 6 **最终通过**见 [`2026-08-31-bogda-rk3528-gate6-final-acceptance.md`](2026-08-31-bogda-rk3528-gate6-final-acceptance.md)。不要把下文「不是通过」读成现网仍未过。

日期：2026-08-30（北京）

trial：`20260830T034154Z`

owner 授权：受控 reboot + 独立 restore 目录。本报告记录 reboot 已发出；**restore 演练未做**，因为 SSH 在约 18 分钟内没有回来。

**不是 Gate 6 通过，也还不能按失败轮收口。** 截止点仍是 2026-08-31T03:41:55Z。

## 重启前（2026-08-30T03:47:00Z）

| 项 | 值 |
|---|---|
| `/mnt/nas` | `/dev/sda1` ext4 UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f` `rw` |
| server / worker | active，`NRestarts=0` |
| snapshot.timer / health.timer | active |
| Orchestra broker / exam-watch / smbd | active |
| `/api/health` | 200 |
| `POST /api/flows/count` 等 | 200，body `0`（影子库无 Flow） |
| live `prefect.db` SHA-256 | `da1868302e5c88214456b738ac826be6b5edaec0e0d57debd336ca4cdbfcd78c` |
| samples.jsonl | 2 行 |
| `mnt-nas.mount.wants` | server + worker symlink 在 |

`sudo reboot` 于 03:47Z 稍后发出；SSH 被对端关闭。

## 重启后观察到的

从 Windows 直连口：

- `10.77.0.1` ICMP 通（TTL=64，约 1 ms）→ 内核网络已起来
- TCP 22 / 2200 / 2222：**Connection refused**（sshd 未在听）
- Tailscale `100.78.158.80`：ICMP 超时（`tailscaled` 未上）

未能核对：六个 Bogda unit、挂载 UUID、Prefect 队列、快照、`restore-drill`。未能执行：

```
python -m bogda.ops.snapshot create ... --keep 7
python -m bogda.ops.snapshot verify ... --restore-dir /mnt/nas/.bogda/restore-drill-...
```

## owner 第二次重启 + RJ45（北京 12:16）

Windows 直连口仍是 `10.77.0.2/30`，盒子 `10.77.0.1` ICMP 1–2 ms。TCP 22 / 445 / 4200 当时拒绝或超时。RJ45 链路本身没问题。

## owner 拔 USB 盘后监听（北京 13:04–13:08）

拔掉西数 USB 之后约 4 分钟：`10.77.0.1` ICMP 一直通。TCP 22 / 445 / 4200 持续 timeout（末次 OpenSSH 出现 banner `Connection refused`，仍无会话）。sshd 没有起来。拔盘**没有**在短时间内解开用户态，更像内核/USB 请求仍卡住，disconnect 没被处理完。

## 断电重启后（北京 13:11，盘仍拔着）

冷启动成功。RJ45 SSH 通（`10.77.0.1` host key 与旧 known_hosts 不一致，用独立 known_hosts 写入）。`uptime` 约 0 min。`lsblk` 无 `sda`。`/mnt/nas` 未挂。

| 服务 | 状态 |
|---|---|
| ssh / smbd / orchestra-broker / exam-watch.timer | active |
| bogda-prefect-server / pi-worker | inactive（无挂载，预期） |
| :4200 | 未监听 |

为避免无盘期间 health timer 再堆 API 失败，已 `stop` `bogda-shadow-health.timer` 与 `bogda-prefect-snapshot.timer`（仍 enabled）。盘插回并确认挂载后再 `start`。独立 restore 仍未做。

## 插回 USB + restore 演练（北京 13:13–13:15）

`sda` 枚举正常。普通 `systemctl start mnt-nas.mount` **失败**：依赖的 `systemd-fsck@uuid-d105381a-…` 起不来——盒子上 `e2fsck 1.46.5` 报 `FEATURE_C12`，要更新 e2fsprogs。用 `systemctl start --job-mode=ignore-dependencies mnt-nas.mount` 挂上：`/dev/sda1` UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f` `rw`。

随后手工 `start` server/worker，并重新 `start` 两个 timer。`:4200/api/health` 200。worker `ProcessWorker a84bdda8-ac82-499f-9bb7-30a18d301cf4`。Orchestra broker 全程 active。

| 项 | 值 |
|---|---|
| live `prefect.db` SHA-256（重启前与 restore 后相同） | `da1868302e5c88214456b738ac826be6b5edaec0e0d57debd336ca4cdbfcd78c` |
| 快照 | `prefect-20260830T051449Z.db`，`integrity_check=ok` |
| 快照 sha256 | `2fa21662f6e00ddb31e82d592b2b693f1ee015cf272a4f7692331a3c93d53b43` |
| restore 目录 | `/mnt/nas/.bogda/restore-drill-20260830T051449Z/`（`integrity_check=ok`） |
| live DB | **未被覆盖** |
| Prefect counts | flows/runs/deployments 均为 0（与重启前一致） |
| 健康样本 | 本 trial `samples.jsonl` 现 3 行；中间有受控 reboot + 卡死 + 拔盘 + 冷启动断档 |

**不是 Gate 6 通过。** 窗未满 24h；采样有批准的缺口；下次带盘冷启动仍会被旧 e2fsck 挡住挂载。

未改 fstab / unit / `bogda.env`。未接 `dorm-x86`。未宣布 Gate 7。

## 还挂

1. 升级盒子 `e2fsprogs`，或改 fstab 让 `mnt-nas.mount` 不 `Requires` 失败的 fsck，否则带盘 reboot 会再次 Dependency failed。
2. LAN `10.77.0.1` host key 与本机默认 known_hosts 仍不一致。
3. trial 收到 24h 后再 `health summarize`；缺档记入本次维护，不能当无缺口通过。
