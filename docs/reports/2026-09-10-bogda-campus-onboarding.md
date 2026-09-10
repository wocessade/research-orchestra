# Bogda 到校接机现状 — 2026-09-10

本报告更新到用户因额度不足要求交接时。详细恢复入口：[runner 工作交接](2026-09-10-bogda-runner-handoff.md)。任务状态：[STATE](../../.tasks/active/059_bogda-campus-runner/STATE.md)。

## 完成并验证

- Y7000 2021H 已通过 Tailscale SSH 管理；WSL2 Ubuntu、Python 3.11.16、Prefect 3.8.3 安装完成。
- NAS CIFS 挂载及 RK/runner 双向读写通过。systemd worker、NAS 自动挂载、Windows 登录启动任务已配置；WSL 重启后自动恢复通过。
- dorm-x86 worker ONLINE，pool READY，并发 1；专用 queue 和 deployment 已创建。
- 自主 shell smoke Completed，stdout、空 stderr 和 smoke.txt 均已核实。3101 基础设施接口显示新 worker。
- Orchestra broker、雷达、exam-watch、旧冷备、housekeeping 和管理机旧控制台刷新停用；历史数据、Samba、Bogda/NAS 备份保留。

## 未完成

真实 checkpoint 验收因 Artifact key 下划线格式失败。核心与 console 适配器的最小修复已在本地通过回归测试，尚未部署；DEF-03 尚未通过现网验收。3101 仍是 real-readonly / observer，白名单未开放。

共享 SQLite WAL、worker 审批/recovery store 接线，以及本地 shell 日志到 NAS/3101 的发布路径仍存在缺口。未进行付费模型调用或真实科研任务；尚不能宣布完整接替。

## 下载与恢复证据

- WSL MSI 2.7.13：SHA256 `A3505A50F4CC585551D11D9DE824BA4375448D7A68F2E71D3FB315FA986FC754`，Microsoft 签名 Valid，安装退出 0。
- Ubuntu 24.04.4 WSL：SHA256 `9B2F7730DC68227DD04A9F3E5EAB86AD85CAF556B8606AD94F1F29FF5C4FD3F5`，安装完成，发行版 BogdaRunner 位于 C:/WSL/BogdaRunner。
- uv.lock：SHA256 `62FEFDEEEFC3E4C8D8B1C3F5391FD6158624C84D323F9C0D2A515A8A9708B5C5`，管理机与 runner 一致；离线 locked uv 启动通过。
- 下载采用 [TUNA 官方镜像说明](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/)，从原锁文件导出版本与哈希，使用 require-hashes 安装。
- SQLite 跨主机 WAL 限制见 [SQLite 官方说明](https://sqlite.org/wal.html)。目前未更改数据库模式。

完整资源 UUID、失败原因、文件位置、下一步顺序与不应重跑的命令均在交接文档；流水证据保留于任务 RUNLOG.ndjson。
