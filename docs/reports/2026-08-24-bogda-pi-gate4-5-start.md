# Bogda Pi Gate 4–5 启动证据

日期：2026-08-24

部署基线：Pi 现有安装来自 `55b4d9b`；主线在启动前已推进到 `108b593`，新增内容仅涉及部署归档 LF 契约、runbook 和测试，不改变已安装服务的运行逻辑。

Pi：`liuxfs@100.111.75.58`

试运行编号：`20260824T083454Z`

## 结论

Gate 4 和 Gate 5 已按顺序执行。Prefect server、单并发 Pi worker、每日快照 timer 和五分钟健康采样 timer 已启动并启用。首个健康样本通过；Orchestra 保持 active。72 小时 shadow 从 `2026-08-24T08:34:59Z` 的首个样本开始计时。

这不是 Gate 6 验收完成，也不授权切换 3100、接入宿舍 runner 或提高并发。

## Gate 4：鉴权与 server

- `/etc/bogda/bogda.env` 的哨兵已在 Pi 内原子替换为随机 Basic Auth；凭据未打印、未提交。
- env 仍为普通非 symlink 文件，mode 640、owner root、group bogda。
- `last-backup` 指针在 start-only 操作前后不变。
- 仅启动 `bogda-prefect-server.service`；启动后 worker 与两个 timer 仍为 inactive。
- Prefect 冷启动约 37 秒后监听 `0.0.0.0:4200`。
- Tailnet 上对受保护端点 `POST /api/flows/count`：带鉴权返回 200；不带鉴权返回 401。
- LAN 上同一受保护端点不带鉴权返回 401。
- `/api/health` 不带鉴权返回 200，这是 Prefect 的匿名健康探针，不能用于证明鉴权失效或生效；runbook 已据此修正。
- 从本机经公网 IPv4 负向探测得到 HTTP 000、curl exit 28；外部 `portchecker.io` 对公网 IPv4 的 TCP 4200 检查返回 `False`。
- Tailscale Serve 未配置。主机 nftables/iptables INPUT policy 为 accept，Tailscale规则不单独限制4200，因此当前边界是“Tailnet与私有LAN可达、Basic Auth保护、NAT公网不可达”，不是“仅Tailnet接口监听”。

Gate 4 通过。若未来宿舍网络不能被视为受信私网，应在迁移前另行设计仅Tailnet/防火墙限制，而不是默认为现状继续安全。

## Gate 5：worker、timer 与证据轮换

启动前创建新的健康证据文件：

- `/mnt/nas/.bogda/manifests/health/samples.jsonl`
- mode 640、owner/group `bogda:bogda`
- prior sample 若存在则移动到 `archive/`；本次为首次正式trial

启动后状态：

| 单元 | active | enabled |
|---|---|---|
| `bogda-prefect-server.service` | active | enabled |
| `bogda-pi-worker.service` | active | enabled |
| `bogda-prefect-snapshot.timer` | active | enabled |
| `bogda-shadow-health.timer` | active | enabled |

worker 命令包含 `--pool pi-service --type process --limit 1 --create-pool-if-not-found`，并发保持1。

快照 timer 下一次计划为 2026-08-25 00:00 CST；健康 timer 每五分钟运行。Orchestra broker 启动前后均为 active，未改其任务、服务或数据根。

## 首个健康样本

首个样本时间：`2026-08-24T08:34:59.036496Z`

| 指标 | 结果 |
|---|---:|
| API | ok |
| API latency | 约58 ms |
| SQLite integrity | ok |
| database bytes | 737280 |
| free disk bytes | 232464596992 |
| MemAvailable | 1182900224 bytes |
| swap used | 0 |
| OOM kill count | 0 |

## 已知观察项

1. Prefect server 尝试在 root-owned venv 中生成内置 UI 静态文件时得到 permission denied；API正常，Bogda使用独立3101控制台。不要为了消除日志直接递归 chown整个venv。是否禁用Prefect内置UI或指定独立可写目录，作为后续小修评估。
2. `python -m bogda.ops.health` 会打印 runpy RuntimeWarning，因为 `bogda.ops.__init__` 预先导入 health 模块。首次采样仍 exit 0，证据有效；该警告作为代码清理项，不阻塞shadow。
3. 主机4200绑定所有IPv4接口，安全性依赖Basic Auth、私网边界和NAT。72小时期间不得配置路由器端口映射或 Tailscale Funnel/Serve。
4. 外部端口检查只证明检查时公网4200不可达，不替代持续防火墙策略。

## Gate 6 前禁止事项

- 不切换3100。
- 不提高worker并发。
- 不接入GPU或宿舍runner。
- 不删除旧Orchestra。
- 不把执行成功解释为科研结论成立。
- 72小时证据不足时不得宣布Pi shadow通过。
