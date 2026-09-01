# Bogda RK3528 Prefect 恢复与 remount 自愈

> **历史过程。** 08-30 这次拉起 **不是** Gate 6 通过。最终通过见 [`2026-08-31-bogda-rk3528-gate6-final-acceptance.md`](2026-08-31-bogda-rk3528-gate6-final-acceptance.md)。USB remount 合同（`BindsTo=mnt-nas.mount`）仍有效。

日期：2026-08-30（北京）  
主机：RK3528 `rk3528`  
SSH：本次用 Tailscale `liuxfs@100.78.158.80`（直连 `10.77.0.1` host key 对不上）

**当时口径：不是 Gate 6 通过，不是 Gate 7，不是 3101 真写入，不是新 24h trial。**

失败轮仍以 [`2026-08-29-bogda-rk3528-gate6-failure.md`](2026-08-29-bogda-rk3528-gate6-failure.md) 为准。本报告只记录失败轮之后的服务恢复与 unit 契约。

## 现场

| 项 | 值 |
|---|---|
| `/mnt/nas` | `/dev/sda1` ext4 `rw,relatime`，UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f` |
| 盘 | USB 西数 `WDC WDS250G2B0A` 232.9G，约 1% 已用 |
| dmesg I/O | 本次检查窗口无新的 `I/O error` / `ext4-fs error` |
| `smartctl` | 未安装；未做离线 fsck |
| Orchestra | **未停**：`orchestra-broker`、exam-watch、`smbd` 全程 active |
| Prefect | 自 `2026-08-28T09:34:59Z` 起 `inactive`；`2026-08-29T19:00:06Z` 起 server/worker 再 active |
| 本机 `/api/health` | 200 |
| worker | `ProcessWorker 25431997-df2a-4771-b126-f45c31e369b4` started |
| 健康 / 快照 timer | 仍 active；**未** `BindsTo` 挂载（掉盘样本要留下） |
| `/etc/bogda/last-backup` | 仍指向 `20260824T071700Z`（未跑 `install.sh --install`） |
| 旧 unit 副本 | `/etc/bogda/backups/20260829T185500Z/`（手工 `cp`，不是 installer 备份） |
| `/opt/bogda` Python | **未** `uv sync`；盒子代码仍是上一轮安装 |

根因（失败轮已写）：`ConditionPathIsMountPoint` 失败 ≠ unit Failed，`Restart=on-failure` 不触发；盘回来时 `WantedBy=multi-user.target` 已满足，server/worker 不会再起。

## 已装上的 unit 契约

`bogda-prefect-server.service` 与 `bogda-pi-worker.service`：

- 保留 `RequiresMountsFor=/mnt/nas/.bogda`
- 增加 `BindsTo=mnt-nas.mount`、`After=mnt-nas.mount`
- `[Install]` 同时 `WantedBy=multi-user.target` 与 `WantedBy=mnt-nas.mount`
- 已 `daemon-reload` + `enable`，存在 `/etc/systemd/system/mnt-nas.mount.wants/` 两份 symlink

部署方式：从仓库 `bogda/deploy/pi/systemd/` 拷这两份文件到 `/etc/systemd/system/`。没有跑 `deploy/pi/install.sh`（会 `uv sync` 并改 `last-backup`）。

回滚：把 `/etc/bogda/backups/20260829T185500Z/` 里的两份 unit 拷回，`daemon-reload`，再 `systemctl enable --now`。

## 仍挂

- 新 24h Gate 6 trial、受控 reboot、独立 restore 目录
- 离线文件系统检查 / SSD SMART（需卸载或装 `smartctl`）
- 仓库内核改动（Type-A → Prefect Failed、信封钉死价目）同步进 `/opt/bogda`
- LAN SSH `10.77.0.1` known_hosts 与 Tailscale 密钥不一致

owner 已授权：Orchestra 停机由执行者自决；工作重心向 Bogda。本次恢复未停 Orchestra。
