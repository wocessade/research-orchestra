# Bogda 接班清单：Grok → DeepSeek

日期：2026-08-24
用途：在上下文或模型额度切换后，只凭本文件继续推进 Bogda，不重复已经完成的工作。

## 当前事实

- `main` 当前基线为 `65303c1`，Bogda Console 及科研评审入口改进已合并；3100 端口尚未切换到 Bogda。
- Pi shadow 部署包位于分支 `codex/bogda-pi-shadow-bundle`、工作树 `D:/pythonProject/.worktrees/bogda-pi-shadow-bundle`，尚未合并、尚未部署。
- Pi 分支在 `6fb05ec` 时已集成当时的主线，曝光门禁在 `9eac204` 修复；合并前还需再次合入最新 `main` 的评审入口提交 `65303c1`。
- 没有连接 Pi，没有修改 systemd，没有安装、启动或应用服务，也没有改 Orchestra。
- 根工作树里的两份锐评删除、`.codegraph/` 和两张未跟踪任务卡属于用户现有状态，不得清理或带入 Bogda 提交。

## 已确定的架构边界

- Pi 是常开 Broker/NAS，但此次迁移允许停机；不做零停机迁移、双写或高可用编排。
- Bogda 状态落在 Pi 已挂载 SSD 的 `/mnt/nas/.bogda`，不要把高写入状态放到 SD 卡。
- Orchestra 数据根 `/home/liuxfs/broker-data` 不属于 Bogda；旧路径 `/mnt/broker` 未挂载，不得写入。
- 运行时秘密只放 `/etc/bogda/bogda.env`，不得提交到 Git。
- Prefect API 只能通过预定的局域网/Tailscale 边界访问。任何来自非 Tailnet/非许可地址的 HTTP 响应，包括 401/403，都表示服务已经暴露，必须停止。
- 并发仍为 1；SLC SD、宿舍 runner 唤醒桥、GPU executor、3100 正式切换均为后续事项。
- Windows 契约门禁的 LF/CRLF 假漂移已在 `c57a9ab` 修复：比较仅规范化换行，其他字节变化仍会失败；无需重生成 API 契约。

## Grok 的任务（高判断力阶段）

1. 读取本文件、Pi spec、plan 和 runbook，不重新设计已经批准的范围。
2. 在 Pi 分支确认曝光检测修复：连接失败/无 HTTP 响应才算通过；任意 HTTP 状态都算失败。
3. 将最新 `main` 合入 Pi 分支，解决冲突，并在该工作树运行完整验证。不要反向把未验收分支直接推入 `main`。
4. 记录验证结果；满足合并条件后请求或执行已获授权的本地合并。不得擅自推送远端。
5. 安排一次允许停机的 Pi 部署窗口。先备份和回滚演练，再启动 server；网络边界验证通过后，才启动 worker/timer。
6. 启动 72 小时 shadow 观察并留下结构化证据。观察期未结束前不得宣称迁移完成，也不得切换 3100。

合并前最低验证：

```powershell
cd D:\pythonProject\.worktrees\bogda-pi-shadow-bundle
pytest -q
git diff --check
git status --short
```

部署命令和回滚步骤以 `bogda/docs/pi-shadow-runbook.md` 为准；不要从聊天记录拼命令。真实地址和秘密只在部署现场填写。

## Grok 必须停下并询问的情况

- 需要删除或迁移 NAS/Orchestra 现有数据。
- SSD 挂载点不是 `/mnt/nas`，或检查发现数据盘/根分区身份不明确。
- 非许可网络能得到任何 HTTP 响应。
- 回滚演练失败、快照不可恢复、systemd hardening 导致必要写路径不明确。
- 需要购买硬件、提高并发、接入 GPU、启用宿舍 runner 或正式替换 3100。

Pi 停机本身已经获准，不需要为停机再次询问；但停机不等于获准删除数据或中断 Orchestra 队列中的在途任务。

## 交给 DeepSeek 的条件与任务

只有 Grok 留下以下检查点后才交接：Pi 分支/合并提交号、部署时间、回滚结果、服务状态、shadow 起始时间、证据目录和所有异常。

DeepSeek 负责确定性执行：

- 按 runbook 重跑健康检查、收集 JSON/日志和 72 小时摘要；
- 对照既定门槛报告通过/失败，不调整门槛；
- 更新部署报告和任务状态，保留命令、时间、退出码与产物路径；
- 若出现上述停止条件，保存现场并交回用户，不临时改架构。

DeepSeek 不负责：架构重构、硬件采购、并发调优、公开暴露 API、GPU 注入、删除旧系统或切换 3100。

## 完成定义

第一阶段只有在以下条件全部满足后才算完成：Pi 分支已审查并合并；备份与回滚演练成功；服务仅在许可网络可达；server、worker、timer 按顺序启用；72 小时证据完整且没有假绿；部署报告已提交。之后再单独决策 3100 切换和宿舍 runner，不把它们塞进本阶段。

## 权威入口

- 设计：`docs/superpowers/specs/2026-08-24-bogda-pi-shadow-bundle-design.md`
- 实施计划：`docs/superpowers/plans/2026-08-24-bogda-pi-shadow-bundle.md`
- 部署运行手册（Pi 分支）：`bogda/docs/pi-shadow-runbook.md`
- 本地任务留痕：`.tasks/active/041_bogda-pi-shadow-bundle/`
