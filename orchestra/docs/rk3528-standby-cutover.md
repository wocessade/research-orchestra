# RK3528 切机记录（Orchestra + NAS + Bogda）

> 2026-08-28 已切完。现网调度 = RK3528。4B 可断电。SMB：`\\10.77.0.1\nas`。Prefect：`http://10.77.0.1:4200`。Windows SSH 优先 Tailscale `100.78.158.80` / `rk3528`（直连 `10.77.0.1` 可能 host key 失败）。

## 现网

| 项 | 值 |
|---|---|
| SSH | 优先 Tailscale `rk3528` / `100.78.158.80`；直连 `liuxfs@10.77.0.1` 可能 host key 失败 |
| 数据根 | `/home/liuxfs/broker-data`，`/mnt/broker` → 该目录 |
| Broker / timers | enabled（含 exam-watch） |
| NAS | `/mnt/nas` USB3；Samba `[nas]` |
| Prefect | `bogda-prefect-server` + `bogda-pi-worker`；池名 `pi-service`；`BindsTo=mnt-nas.mount`（2026-08-30 起） |

2026-08-30：Prefect 曾从 USB 失败后的 `inactive` 拉起，server/worker 绑 `mnt-nas.mount`。那次恢复**不是** Gate 6 通过。Gate 6 最终于 2026-08-31 通过：`docs/reports/2026-08-31-bogda-rk3528-gate6-final-acceptance.md`。过程记录：`docs/reports/2026-08-30-bogda-rk3528-prefect-restore.md`。

Windows 直连口静态 `10.77.0.2/30`（无网关）。盒子 `eth0` `10.77.0.1/30` never-default，上网走 USB Wi-Fi `liudfs`。

## 当时一次切步骤（已执行，仅作回退参考）

1. 4B：停 Orchestra timers + umount NAS + 停 Bogda/Samba。
2. 数据与 env 拷到 RK3528；SSD 插 USB3；fstab UUID 挂 `/mnt/nas`。
3. 新机 enable broker/timers/Samba/Prefect。
4. Windows `ORCHESTRA_SSH_HOST=10.77.0.1`；映射 `\\10.77.0.1\nas`。

回退：新机 disable timer + stop broker/bogda/smbd；4B 再挂盘并 `enable --now`；Windows host 改回 `192.168.0.250`（仅当 4B 仍开机）。
