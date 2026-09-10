# Bogda runner handshake — 更新至 2026-09-10

本文件保留原链接作为接机入口。真机资源、部署边界和续接顺序以[最新交接](2026-09-10-bogda-runner-handoff.md)为准。

## 当前已接通

Y7000 的 SSH、WSL2 Ubuntu、NAS、dorm-x86 worker 均通过验证；并发 1，自主 shell smoke Completed。Windows 登录启动 WSL、systemd 自动启动 worker，WSL 重启恢复通过。Orchestra 与 3100 已停用。

3101 仍为 real-readonly / observer，仅显示基础设施和结果。真实 checkpoint 在进入暂停前因 Artifact key 下划线格式失败；本地修复与回归测试完成，尚未部署。

## 精确资源

| 配置 | 已创建的目标 |
|---|---|
| work pool | dorm-x86 |
| queue ID | 2e773bf9-cba7-46ed-b93d-f1b2ea65dc27 |
| deployment ID | ebd2b9ce-46e3-4db2-9ad3-1a6e39b5fd02 |
| Prefect API | http://100.78.158.80:4200/api |
| NAS inbox | /mnt/nas/.bogda/inbox |
| NAS artifact root | /mnt/nas/.bogda/runner/artifacts |

这些 ID 已记录，但尚未写入 console 白名单。下一步先部署 checkpoint 修复，用新的幂等键重测实际暂停/恢复，再核对控制台操作范围。不要重新创建 pool/queue/deployment。

## 原共享数据库建议已撤回

原文建议 console 和 worker 直接通过 NAS 共用 SQLite 文件。本次核实两个 store 强制启用 WAL；[SQLite 官方文档](https://sqlite.org/wal.html)要求 WAL 使用者位于同一主机。NAS 双向读写成功不能替代数据库事务验收。

当前 runner.env 中审批/recovery 路径只是预留配置，worker runtime 接线尚未完成。暂不在 console 配置这些库，不开放付费审批/恢复。后续评估由 RK 单点持有 SQLite、runner 经窄接口访问；尚未实现。

## 日志与验收剩余项

shell 的实际日志目录为 WSL 本地 `attempts_root/job_id/run_id/attempt-0001/`，console 读取器期待 `artifact_root/run_id/attempt-*/`。自动发布/归档尚未连接，不能仅设置 artifact root 就声称日志联动通过。

待验收：真实 checkpoint 两次暂停恢复、3101 checkpoint 展示/操作、自动日志发布、一次性付费审批与 usage-unknown 恢复。没有完成这些验收前，不宣布完整接替。HMAC 与 NAS/Prefect 凭据只保留在机器的私有环境文件。
