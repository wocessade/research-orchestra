# Bogda 落地验收报告 — 2026-09-11

状态：**软件接线全部完成并现网验收通过**；**真实 dsh 已安装并通过真实付费调用验收（2026-09-11 追加）**；**3101 接替 3100 落地，DEF-03 申报通过（2026-09-11 追加，owner 指令）**。
授权：owner「全部权限、全速推进 bogda 落地」+「接上 3101接3100落地 commit 推进所有内容」。约束：不打印凭据、不改模型路由、保留既有未提交学术改动（本轮 owner 授权 commit）；历史约束中"不删文件"继续执行。

## 落地内容（设计 D1–D9 的实现）

| # | 内容 | 落点 |
|---|------|------|
| D1/D3 | store 单机托管 + HMAC 窄接口 | RK `/var/lib/bogda/{approvals,usage-unknown}.sqlite`（ext4 本地）；`/api/v1/store/*` 域分离签名（`bogda-store-api\nts\nmethod\npath\nsha256(body)`，±300s） |
| D2/D4 | 预算权威全在 console 侧 | 真实 DeepSeek 余额 → UsageSnapshotV1；ledger+guard+approval 服务端；runner 持 `RemoteBudgetService`/`RemoteUsageUnknownRecovery` HTTP 适配器 |
| D5 | 日志发布 | 布局去 job_id 层 → `{BOGDA_ARTIFACT_ROOT}/{run_id}/attempt-{n:04d}`；NAS 共享根 runner 写、RK 读；`lifecycle` 修 attempt-1 字面量 |
| D6 | 付费流 | `paid_model_call` 的 service 可空 + env 工厂（`wiring/paid_runtime.py`）；suspend key 冒号→连字符；deployment `72f7fe90`（pool dorm-x86，并发 1） |
| D7 | console 开放 | `profile=allowlisted-test` + `role=owner` + 精确 `ALLOWED_DEPLOYMENT_IDS`/`ALLOWED_WORK_POOL_NAMES`；真实 `/opt/bogda/src` checkout |
| D9 | 开机自启 | **订正为 S4U 方案**（原 Password 方案废弃）：`BogdaRunnerWSLBoot`（S4U + `cmd /c wsl.exe ... --exec /bin/sleep infinity` + AtStartup/AtLogOn + 无限时限）；旧 InteractiveToken 任务保留兜底 |

代码：`bogda/src/bogda/wiring/{store_api,paid_runtime}.py`（新）、`flows/paid_model_call.py`、`executors/shell.py`、`artifacts/lifecycle.py`；`bogda-console/src/bogda_console/{api/store_routes.py（新）,app.py}`；测试：`bogda/tests/wiring/{test_store_api,test_paid_runtime}.py`、`bogda-console/tests/backend/test_store_api.py` 等。

## 部署记录（双机，全部带备份）

- runner WSL：`src/bogda/**`（备份 `.pre-landing-20260911` 及更早 `.pre-keyfix*`）、`~/.config/bogda/runner.env`（去 DB 变量，`BOGDA_STORE_API_URL=http://rk3528.tail6d8b09.ts.net:3101`）。
- RK：`/opt/bogda-console/src/...`（`app.py.pre-landing-20260911`）、`/etc/bogda/console.env.pre-landing-20260911`、`/opt/bogda/src`（真实 checkout）、`/var/lib/bogda`（bogda:bogda 750）。

## 现网验收证据（全部真实端点，非模拟）

| 项 | run / 对象 | 结果 |
|----|-----------|------|
| checkpoint 暂停/恢复 | `11505d2b`（v3） | 两次真实 Paused→resume→Completed；失败证据 `66d4a924`(v1)/`cff1fc6b`(v2) 保留 |
| 日志链路 | `a5048474` | 新布局落 NAS，3101 读 stdout/stderr 通过 |
| console 决定 checkpoint | `5937cbe8` | 从 3101 决定生效 |
| 付费审批链 | `f6ca6906` + 凭证 `46b0ea93` | BUDGET_PAUSED → console 签发 → consume → reserve → 执行 |
| usage-unknown 恢复 | case `e530ab0a` | open_case → /decisions → reconcile → approve-retry；账本 25→0.01 对账 |
| FINISHED 快路径 | `772b94e6` | 0.00036 CNY 对账 |
| 失败过程证据 | `cbeac339` | tailscale serve Host 头 404（裸 IP → 404，改 MagicDNS 名解决） |

资源：shell deployment `ebd2b9ce`、paid deployment `72f7fe90`、pool `dorm-x86` READY。验收用受控 dsh stub 验收后已移除；模型路由未动。

## 开机链（重启实测 + 机制实测）

供电→sshd/Tailscale AUTO_START（无登录恢复，实测）→ `BogdaRunnerWSLBoot` 拉起 WSL（S4U，机制实测可无交互启动；AtStartup 真机首启验证待 runner 回网）→ systemd 启 `bogda-runner-worker.service`（enabled；首启 NAS automount 竞态由 Restart 自愈，NRestarts=1）→ pool READY。远程触发兜底：SSH 后 `schtasks /run /tn BogdaRunnerWSLBoot` 或 `wsl -d BogdaRunner -u root ...`。

## 真实 dsh 落地（2026-09-11 追加，run `3157b68c`）

| 项 | 落点 |
|---|---|
| Node | 22.23.2 → `/opt/node22`（镜像 RK 布局；npmmirror/nodejs.org tarball），`/usr/local/bin` 软链 |
| dsh | `@deepseek-ai/dsh@0.1.0-rc.7`（**钉版与 RK 现网一致**）；headless profile 首启自动初始化 |
| 认证 | `DEEPSEEK_API_KEY` 注入 `~/.config/bogda/runner.env`（600 bogda；值不落文档），worker 重启生效 |
| usage.json 桥 | `~/.local/bin/dsh` wrapper（node 脚本，影子真实 dsh）：调用后从 `~/.dsh/sessions/<cwd-slug>/session-*/session.jsonl.zstd` 按 zstd magic 切帧解码，汇总所有子会话（含标题调用）的 token 写 `usage.json`；`actual_cost_cny` 留空由 bogda 定价目录自算 |
| 验收证据 | run `3157b68c` Completed：`status=finished`、`actual_cost_cny=0.02271`、`usage_reference=dsh-session:...`；账本三事件（同一 reservation `0ef3743b`）：snapshot 余额 34.12 allow → reserve 2 CNY → 2.5s 后 reconcile actual 0.02271、released 1.97729、overspend 0；attempt 产物 stdout/stderr/usage.json 落 NAS，3101 可读 |

过程要点：会话日志为**追加式多帧 zstd**（node 一次性解码只出第一帧）；dsh 的 `inputTokens` 是 cache-miss 部分、`cacheReadTokens` 是命中部分，两者相加才是 bogda 契约的总输入。

## 3101 自主策略接线（2026-09-11 追加）

console 新增 `LocalAutonomyPolicyAdapter`（`adapters/local_autonomy_policy.py`）：直读盒子本地 core `PolicyStore` 文件，`GET/POST /api/v1/autonomy-policy` 由此落地；`BOGDA_AUTONOMY_POLICY_PATH` 配置后 allowlisted-test + owner 放开写（`autonomy_writes_enabled` 与 recovery 同型 fail-closed），未配置保持只读"策略后端尚未接入"。部署：三个文件（app/config/新适配器）+ `/etc/bogda/console.env` 追加路径 + `maintain.sh restart`，备份 `.pre-policy-20260911`。
现网验证：capabilities `canSetAutonomyMode=true`；GET `sourceMode=real` revision 0 → POST 写 supervised → revision 1 → 回读一致；策略文件落盘 `/var/lib/bogda/autonomy-policy.json`（80B，bogda:bogda）；陈旧 revision 写入被 409 `RESOURCE_CHANGED` 拒绝。测试：console 后端全量 231 passed（含 3 个新增真实存储用例）。

## DEF-03：3101 接替 3100 落地（2026-09-11 申报，owner 指令）

**结论：控制台接替完成**。旧 3100 已停用（broker/刷新任务 disabled、无监听），3101 承担全部控制面。验收证据链（全部真机）：
- 决定检查点（`5937cbe8`）、签发并消费付费凭证（`f6ca6906`/`46b0ea93`）、decision center reconcile（`e530ab0a`）、读运行日志（`a5048474`/`3157b68c`）、自主策略写入（revision 0→1，`/var/lib/bogda/autonomy-policy.json`）。
- 白名单保持精确（两个 deployment + `dorm-x86`）；`real-readonly`/observer 仍只读。
剩余运维项（不阻塞接替结论）：AtStartup 冷开机确认、宿舍–实验室跨网络实测、首个真实科研任务实投、宿舍网络需人工恢复（校园网）、`model-budget` 视图 NOT_FOUND 观察项。

## 未闭环 / 剩余运维项

- AtStartup 真机首启验证（任务已注册且 AtLogOn/远程触发实测可用；冷开机触发待下一次真实开机确认）。
- 宿舍网络掉线需人工恢复（不自愈）；宿舍–实验室跨网络实测。
- 真实研究任务实投（付费链已真实验收，但尚无真实科研工作负载）。
- 观察项：3101 的 `/api/v1/runs/{id}/model-budget` 视图对已验收 run 返回 NOT_FOUND（新旧 run 一致，非回归；账本事件为权威源）。
