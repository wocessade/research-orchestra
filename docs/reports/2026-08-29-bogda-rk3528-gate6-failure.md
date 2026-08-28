# Bogda RK3528 Gate 6 失败收口

日期：2026-08-29

试运行编号：`20260828T064220Z`

核对方式：通过 Tailscale `liuxfs@100.78.158.80` 只读检查；远端未启动/停止服务，未 reboot，未创建或恢复快照，未修改 unit、挂载、数据库、认证或密钥。

## 结论

本轮 Gate 6 **失败**。2026-08-28T09:34:57Z，RK3528 上承载 `/mnt/nas` 的 USB SSD 从内核断开，随后出现写 I/O 错误、ext4 journal abort、只读重挂载和卸载。`bogda-pi-worker.service` 与 `bogda-prefect-server.service` 因挂载依赖在 09:34:59Z 停止；SSD 自动重新枚举并于 09:36:45Z 恢复挂载后，这两个服务没有自动恢复。

缺失 SSD 与 API 失败均是 `bogda/docs/pi-shadow-runbook.md` 的硬失败条件。之后重新挂载、采样间隔连续或 SQLite 抽查为 `ok` 都不能抵消已经发生的存储中断，因此不等待 24 小时截止点宣布通过。

## 只读证据

检查时间：`2026-08-28T20:03:05Z`（北京时间 2026-08-29 04:03:05）

| 项 | 观察值 |
|---|---|
| 当前 trial | `20260828T064220Z` |
| 样本 | 153；`2026-08-28T06:42:23.501924Z` 至 `2026-08-28T20:00:24.527620Z` |
| API 失败 | 120 |
| Prefect server / worker | 均 `inactive/dead`；09:34:59Z 停止 |
| snapshot timer / health timer | 均 `active`、`enabled` |
| 挂载现状 | `/dev/sda1`，ext4，`rw`，UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f` |
| 磁盘最小可用 | `231835385856` bytes |
| 数据库完整性失败 | 0 |
| OOM / OOM 证据缺口 | 0 / 0 |
| swap 增长 | 0 |
| 缺失采样间隔 | 0 |

关键 journal 顺序：

1. `09:34:57Z`：`usb 2-1: USB disconnect`；SSD 写请求返回 device offline，出现 Buffer I/O error。
2. `09:34:57Z`：`Aborting journal on device sda1-8`，同步缓存失败。
3. `09:34:59Z`：ext4 检测到 aborted journal，重挂为只读；systemd 停止 worker/server 并卸载 `/mnt/nas`。
4. `09:35:43Z`：YuanTech T250 / inXtron `0dc4:55aa` 重新枚举为 USB 3 存储。
5. `09:36:45Z`：ext4 recovery complete，`/mnt/nas` 恢复挂载。

同一时间段 USB Wi-Fi 也被 hub 以 `disabled by hub (EMI?), re-enabling` 重新枚举。证据确认故障边界在 USB 链路/控制器层，但仅凭日志不能断定起因是供电、线材、端口、电磁干扰还是内核/控制器问题。

## 后续门禁

以下工作必要但会改变运行或设备状态，本次没有执行：

1. 在 owner 批准的维护窗检查 SSD 供电、线材、端口和 RK3528 USB 控制器稳定性，并保存检查结果。
2. 在卸载/维护条件下完成文件系统与 SSD 健康检查；不得对在线 `prefect.db` 直接修复。
3. 根因处理后恢复 Prefect 服务，确认 API、队列、历史、挂载和六个 Bogda unit。
4. 启动全新 24 小时 trial；旧 `samples.jsonl` 必须归档，不能混入复测。
5. 新 trial 仍须覆盖每日快照、owner 批准的受控 reboot，以及独立 restore 目录验证。

本报告只关闭失败轮，不宣布 Gate 7，不授权 3101 真实写入或 3100 切换。

