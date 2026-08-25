# Bogda 接班清单：Grok → DeepSeek

日期：2026-08-24
用途：在上下文或模型额度切换后，只凭本文件继续推进 Bogda，不重复已经完成的工作。

## 当前事实

- `main` 当前基线为 `4d8e470`（Task 4–5 已提交，尚未 push）。Bogda Console、科研评审入口、三档模式
  mock 控制、跨平台契约门禁、Pi shadow 部署包、Windows 本地启动器、人工检查点和
  supervised 协调器均已在本地主线；3100 尚未切换到 Bogda。
- Pi 已完成 Gate 1–5：安装、鉴权、server、单并发 worker、快照 timer 和健康
  timer 已启动。Gate 6 的 72 小时自动采样最后确认仍在运行；尚未做受控重启、
  独立 restore 演练、确定性复核或 Gate 7 裁决。
- 曝光门禁修复 `9eac204` 已包含在主线：非许可网络得到任何 HTTP 响应均为失败，只有传输失败且 HTTP 000 才通过。
- 3101 已通过真实 `start → status → stop → start → status`，当前为启动器托管的
  `healthy / mock-all`；它不会开机自启，也没有连接真实 Prefect。3100 在验收中
  未变化。
- 根工作树里的两份锐评删除、`.codegraph/` 和两张未跟踪任务卡属于用户现有状态，不得清理或带入 Bogda 提交。

## 下周恢复顺序

1. 读取 `docs/reports/2026-08-24-bogda-stage6-workboard.md`、Pi runbook 和最新
   Gate 报告，不重复 Gate 1–5。
2. 先对 Pi 做只读检查并保存完整健康摘要；核对样本跨度、间隔、API、OOM、swap、
   SQLite integrity、SSD、快照和 Orchestra。
3. 受控重启与独立 restore 演练仍需 owner 明确批准。没有批准就停在只读证据收集。
4. 证据完成后由 DeepSeek 做确定性复核，再交 owner/强模型做 Gate 7 裁决。
5. 软件线下一项是控制面计划 **Task 6**：3101 真实 Prefect S1/S2，阻塞在
   Gate 6 与 owner 批准。不要先做 `autonomous` 循环、常驻管家 Agent、宿舍
   runner 或 GPU。Task 4=`41c0e17`，Task 5=`4d8e470`。

## 已确定的架构边界

- Pi 是常开 Broker/NAS，但此次迁移允许停机；不做零停机迁移、双写或高可用编排。
- Bogda 状态落在 Pi 已挂载 SSD 的 `/mnt/nas/.bogda`，不要把高写入状态放到 SD 卡。
- Orchestra 数据根 `/home/liuxfs/broker-data` 不属于 Bogda；旧路径 `/mnt/broker` 未挂载，不得写入。
- 运行时秘密只放 `/etc/bogda/bogda.env`，不得提交到 Git。
- Prefect API 只能通过预定的局域网/Tailscale 边界访问。任何来自非 Tailnet/非许可地址的 HTTP 响应，包括 401/403，都表示服务已经暴露，必须停止。
- 并发仍为 1；SLC SD、宿舍 runner 唤醒桥、GPU executor、3100 正式切换均为后续事项。
- Windows 契约门禁的 LF/CRLF 假漂移已在 `c57a9ab` 修复：比较仅规范化换行，其他字节变化仍会失败；无需重生成 API 契约。

## Grok 的任务（高判断力阶段）

1. 不重复部署或重启 Gate 1–5；先收集 Gate 6 只读证据并写新报告。
2. 核对曝光检测仍满足：连接失败且 HTTP 000 才通过；任意 HTTP 状态都失败。
3. 达到 72 小时时先保存原始 summary，不凭“服务仍 active”宣布通过。
4. 获得 owner 明确批准后，才执行受控重启和独立 restore 演练；不得覆盖 live
   SQLite 数据库。
5. 留下当前主线 SHA、操作时间、服务状态、证据目录、异常和回滚结果，再交给
   DeepSeek 确定性复核。

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

只有 Grok 留下以下检查点后才交接：主线提交号、健康摘要、受控重启授权与结果、
restore 结果、服务状态、shadow 起止时间、证据目录和所有异常。

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
