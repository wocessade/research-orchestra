# Subsystem 1 端到端验收报告（2026-08-19）

## 场景 1：dsh 任务全闭环（派 → 执行 → 复查）✅

- 任务 `T-20260819-e2e-dsh`：抓取 arXiv cs.CL 最新 3 篇论文写 output.json
- 首次运行暴露关键问题：**dsh 沙箱 workspace-write 仅允许写会话工作区与 /tmp**，输出目录在 workspace 外 → 写入被拒，headless 无审批渠道，dsh 按规则不绕过、保全数据到工作区并完整报告阻塞原因（agent 行为符合预期，验证了 dsh 的选择）
- 修复：executor 将 dsh 进程 **cwd 设为 attempt 输出目录**（workspace=输出目录，写入天然合法）；commit `e3e8222`
- 复跑：18 秒完成，attempt-2 产出 output.json（3 项、title+abstract 齐全、JSON 合法）+ arxiv_response.xml ✅
- 全程内存峰值 545 MiB（2GB 板余量充足）

## 场景 2：Windows 脱机 20 分钟任务照跑 ⏳（进行中）

- 任务 `T-20260819-e2e-offline`：每 240s 写一个心跳时间戳，共 5 个，总时长 20 分钟
- 已推送到 Broker 并确认 running（02:06 前）
- **验证方式**：用户关机 ≥20 分钟后回来，检查 `results/T-20260819-e2e-offline/attempt-1/heartbeat.txt` 是否为 5 行

## 场景 3：中断恢复 ✅

- 任务 `T-20260819-e2e-recover` 运行中被 `systemctl stop` 杀死（模拟断电）
- 重启后 broker 日志：`recovered 1 running task(s) -> failed`
- 自动重试：attempt-2 完整执行（12 心跳 + recover-done），终态 done、attempts=2 ✅

## 期间修复的问题（全部已 commit + 部署）

| 问题 | 修复 | commit |
|---|---|---|
| npm 全局安装 EACCES（/opt 属 root） | chown /opt/node22 树 | Pi 侧操作 |
| dsh 凭据文件模式 644 被拒 | chmod 600（dsh 安全机制按预期工作） | Pi 侧操作 |
| Pi 无 API key（凭据文件仅是路由引用） | systemd drop-in 注入 DEEPSEEK_API_KEY（复用 monitor.service 的 key，不进仓库、重部署不丢） | Pi 侧操作 |
| broker 以 root 运行（DB 文件属 root，liuxfs 只读） | service 增加 `User=liuxfs` + chown | `334ee9b` |
| 任务文件 result 字段与 results 根目录双重叠 | 约定改为相对 results 根（不带 results/ 前缀） | `7a6c375` |
| systemd 默认 PATH 无 /opt/node22/bin（dsh 找不到） | service 增加 Environment=PATH | `6a03103` |
| deploy 脚本未传 config.example.json | 加入 scp 列表 | `6a03103` |

## 遗留

- 场景 2 待用户关机验证
- dsh 会话日志（~/.dsh/sessions）未纳入 sync_pull——后续版本把 session 回放纳入复查材料
- SSD 到位后迁移：REMOTE_ROOT 从 /home/liuxfs/broker-data 切回 /mnt/broker（Task 3）
- 核桃派 usage-monitor 仪表盘展示 Broker 状态：属 subsystem-4（POST /api/orchestra 已按接口预留实现）
