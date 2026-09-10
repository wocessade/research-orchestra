# Bogda Console

<!-- campus-runner-status:2026-09-11 -->
> 2026-09-11 现状更新：Orchestra/3100 已停用；Y7000 已接入 WSL2、NAS 和 dorm-x86，并发 1。checkpoint 修复与落地接线（RK 侧 store + HMAC 窄接口、日志发布、付费审批、usage-unknown 恢复、自主策略）已部署并现网验收通过；真实 dsh 已安装并真实验收（run `3157b68c`）；**DEF-03 申报通过：3101 接替 3100 落地**。3101 现为 `allowlisted-test` + 精确白名单（两个 deployment + `dorm-x86`）。详见[落地验收报告](../docs/reports/2026-09-11-bogda-landing-acceptance.md)。
<!-- /campus-runner-status -->

Bogda Console 是旧 Orchestra 3100 控制台的独立继任界面，现网位于 RK3528 的 3101。旧 3100 已停用。现网 profile 为 `allowlisted-test` + `owner`，精确白名单为两个验收 deployment（shell/paid）与 pool `dorm-x86`；store（预算/审批/usage-unknown）HMAC 接口与日志发布已于 2026-09-11 接线验收。

第一版范围是 B：监控、提交已注册 Deployment、取消 Flow Run、暂停/恢复
Deployment schedule 或 Work Queue，以及基于 RunResult Artifact 的科研评审。
Prefect 始终是唯一执行状态源；控制台没有任务数据库、调度器或执行状态机。

## 状态语义

- 执行状态来自 Prefect，保留原始 `state.type` 与 `state.name`。界面明确展示
  Scheduled、Running、Completed、Failed、Crashed、Cancelled；Late、Retrying
  等名称不被本地改写成另一套状态。
- 科研判断只来自相同 `flow_run_id`、精确 key
  `bogda-run-{run_id}`、精确 type `bogda.run-result` 的最新 Artifact。可选值是
  unreviewed、accepted、rejected、inconclusive。
- Completed 只表示执行完成，不表示科研结论成立。
- 最新 Artifact 即权威版本；即使它无效，也不会退回读取较旧的有效版本。

## 本地开发

要求 Python 3.11、Node.js 20+。在本目录执行：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
npm install
```

开发模式使用 mock fixture。BFF 仅绑定回环 3102，Vite 绑定 3101 并代理
`/api`：

```powershell
$env:BOGDA_CONSOLE_PROFILE = "mock-all"
$env:BOGDA_CONSOLE_TEST_MODE = "1"
$env:BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS = "deployment-service,deployment-dorm"
$env:BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS = "schedule-service,schedule-dorm"
$env:BOGDA_CONSOLE_ALLOWED_QUEUE_IDS = "queue-service,queue-cpu,queue-gpu"
$env:BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES = "pi-service,dorm-x86"
.venv\Scripts\python -m bogda_console --api-only
```

另开终端：

```powershell
npm run dev
```

构建并由单个进程在 3101 提供 UI 与 API：

```powershell
npm run build
.venv\Scripts\python -m bogda_console
```

所有入口都会拒绝 3100。3100 保留给旧控制台；不要停止、覆盖或反向代理它。

## 3101 本地运行手册

真实 Prefect 的 S1/S2 验收步骤见 [real-shadow-runbook.md](docs/real-shadow-runbook.md)；
日常开发和演示仍使用下面的 `mock-all` 启动方式。

日常推荐用启动器管理 3101 上的 `mock-all` 演示。它只启动当前工作树或主目录
自己的 `.venv\Scripts\python.exe` 和 `frontend\dist`，状态文件写在
`%LOCALAPPDATA%\BogdaConsole\`，不安装依赖、不跑 `npm ci`、不触碰 3100。

这仍只是本机 mock 演示，不代表已经接通 Pi 或真实 Prefect。启动器不是 Windows
服务，也不会开机自启。

```powershell
Set-Location D:\pythonProject\bogda-console
.\scripts\local-console.ps1 start
.\scripts\local-console.ps1 status
.\scripts\local-console.ps1 stop
```

可从任意工作目录调用；路径按脚本位置解析。`start` 在已由该启动器拉起且健康时
是幂等的。若 3101 被未知进程占用，启动器会拒绝并离开该进程。`stop` 只停止状态
文件中记录、且启动时间匹配的进程。

访问 <http://127.0.0.1:3101/>。`status` 的结果是 `healthy`、`degraded`、
`stopped` 或 `foreign-listener`。健康还要求
`GET /api/v1/capabilities` 成功且 `data.profile` 为 `mock-all`。

实际运行应以当前要使用的 `bogda-console` 目录为准（通常是
`D:\pythonProject\bogda-console`），不要混用 `.worktrees` 里残留的虚拟环境、
前端产物或 Python import 路径。

### 首次安装或重建依赖

启动器发现 `.venv` 或 `frontend\dist` 缺失时会打印下面的命令，需要时手动执行：

```powershell
Set-Location D:\pythonProject\bogda-console
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
npm ci
npm run build
```

需要运行 Python 测试时，把可编辑安装改为
`.venv\Scripts\python.exe -m pip install -e ".[dev]"`。前端代码变更后必须重新
执行 `npm run build`，再重启受管进程。健康服务下 `start` 是幂等的，只再执行
`start` 不会加载新的 `frontend\dist`：

```powershell
.\scripts\local-console.ps1 stop
.\scripts\local-console.ps1 start
```

否则浏览器可能继续显示旧页面。

### 手动启动（故障恢复）

启动器不可用时，仍可用这些命令在前台启动 `mock-all`：

```powershell
Set-Location D:\pythonProject\bogda-console
$env:BOGDA_CONSOLE_PROFILE = "mock-all"
$env:BOGDA_CONSOLE_TEST_MODE = "0"
$env:BOGDA_CONSOLE_PUBLIC_HOST = "127.0.0.1"
$env:BOGDA_CONSOLE_PUBLIC_PORT = "3101"
$env:BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS = "deployment-service,deployment-dorm"
$env:BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS = "schedule-service,schedule-dorm"
$env:BOGDA_CONSOLE_ALLOWED_QUEUE_IDS = "queue-service,queue-cpu,queue-gpu"
$env:BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES = "pi-service,dorm-x86"
.venv\Scripts\python.exe -m bogda_console
```

保持该 PowerShell 窗口开启。看到 Uvicorn 启动日志后访问
<http://127.0.0.1:3101/>。

### 状态确认

启动器：`.\scripts\local-console.ps1 status`。也可以先确认 3101 确实有监听者，
再读取能力接口：

```powershell
Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 3101 -State Listen |
    Select-Object LocalAddress, LocalPort, OwningProcess

(Invoke-RestMethod http://127.0.0.1:3101/api/v1/capabilities).data |
    Select-Object profile, canSetAutonomyMode
```

本地演示的预期结果是 `profile=mock-all`、`canSetAutonomyMode=True`。只有端口
监听而能力接口失败时，不应把页面视为可用。

### 停止

优先 `.\scripts\local-console.ps1 stop`。若必须手动恢复，优先在前台启动窗口按
`Ctrl+C`。如果原窗口已经丢失，先查明 3101 的确切 PID，再停止该 PID：

```powershell
$bogdaListener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 3101 -State Listen
$bogdaListener | Select-Object LocalAddress, LocalPort, OwningProcess
Stop-Process -Id $bogdaListener.OwningProcess
```

不要按进程名批量停止 Python，也不要对 3100 执行同样操作。PID 是临时状态，
不应抄进文档或长期记录。

### 故障定位

| 现象 | 判断与处理 |
| --- | --- |
| 浏览器显示无法连接 | 先运行 `.\scripts\local-console.ps1 status` 或 `Get-NetTCPConnection`；没有 3101 listener 就是进程未启动或已退出。 |
| `import bogda_console` 指向 `.worktrees` | 回到主工作目录，使用主目录 `.venv` 重新执行 `pip install -e .`。 |
| 后端启动但页面 404、空白或缺少新功能 | 运行 `npm ci`、`npm run build`，再 `.\scripts\local-console.ps1 stop` 然后 `.\scripts\local-console.ps1 start`（健康时 `start` 幂等，不会自行换上新构建），再强制刷新浏览器。 |
| `frontend/dist` 不存在 | 前端尚未构建；运行 `npm run build`。 |
| 3101 已被占用 | 先查看 `OwningProcess` 并确认归属；不要停止未知进程，也不要改用 3100。 |
| 能力接口可用但 profile 不是 `mock-all` | 当前进程使用了别的配置；用启动器 `stop`（仅当它是受管进程）或按“手动启动”重新设置环境变量。 |
| 启动器报告 missing `.venv` / `frontend\dist` | 按“首次安装或重建依赖”执行对应命令。 |

本启动器不包含开机自启、任务计划程序、Windows 服务、托盘常驻或 `restart`。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BOGDA_CONSOLE_PROFILE` | `mock-all` | `mock-all`、`real-readonly` 或 `allowlisted-test` |
| `BOGDA_CONSOLE_PUBLIC_HOST` | `127.0.0.1` | 3101 监听地址；Tailnet 验收时显式设置 |
| `BOGDA_CONSOLE_PUBLIC_PORT` | `3101` | UI/API 公共端口；3100 被拒绝 |
| `BOGDA_CONSOLE_BFF_PORT` | `3102` | 开发 BFF 端口，只绑定回环；3100 被拒绝 |
| `BOGDA_CONSOLE_FIXTURE` | `normal-active` | mock 启动场景 |
| `BOGDA_CONSOLE_TEST_MODE` | `0` | 为 `1` 时开放 mock 场景切换端点 |
| `PREFECT_API_URL` | 无 | 两个 real profile 必填 |
| `PREFECT_API_AUTH_STRING` | 无 | real profile 的服务端认证字符串，只保存在服务端环境 |
| `PREFECT_API_KEY` | 无 | Prefect API 可选凭据，只保存在服务端 |
| `BOGDA_CONSOLE_REPLICA_COUNT` | `1` | 评审追加仅允许单副本进程 |
| `BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS` | 空 | 精确 Deployment UUID/ID，逗号分隔 |
| `BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS` | 空 | 精确 schedule UUID/ID，逗号分隔 |
| `BOGDA_CONSOLE_ALLOWED_QUEUE_IDS` | 空 | 精确 Work Queue UUID/ID，逗号分隔 |
| `BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES` | 空 | 精确 Work Pool 名称，逗号分隔 |
| `BOGDA_AUTONOMY_POLICY_PATH` | 空 | 盒子本地自主策略文件（core `PolicyStore` JSON）。配置后 allowlisted-test + owner 接入真实策略后端；留空保持只读 |

Allowlist 不支持 `*`。命令提交前和 Prefect 权威回读后都会检查资源；本地不做
乐观状态写入。

### Profile 矩阵

| Profile | Prefect/RunResult | 查询 | 评审 | 执行控制 |
| --- | --- | --- | --- | --- |
| `mock-all` | fixture | 是 | 单副本且命中 allowlist | 命中 allowlist |
| `real-readonly` | 真实 Prefect API | 是 | 否 | 否 |
| `allowlisted-test` | 真实 Prefect API | 是 | 单副本且命中 allowlist | 命中 allowlist |

只读比较仍用 `real-readonly`。现网 3101 自 2026-09-11 起使用 `allowlisted-test`，
配置精确的 Deployment/pool allowlist（`dorm-x86` 与其上的两个验收 deployment，
owner 授权）；写入仍只允许命中的白名单资源，不放宽。

## Mock 场景

`fixtures/` 提供六个确定性场景：

- `normal-active`：运行中、已完成待评审、Late，以及两个工作池。
- `sleep-queued`：宿舍机 sleep 与排队任务。
- `gaming-paused`：gaming 模式和暂停资源。
- `degraded-stale`：Prefect/RunResult/Power 不可达或陈旧。
- `result-missing-invalid-conflict`：RunResult 缺失、最新无效和评审冲突。
- `mobile-dense`：手机窄屏的高密度数据。

Power Agent 尚未实现，所有 profile 的宿舍机 sleep、compute、gaming、
maintenance 数据都来自 `MockPowerAdapter`，界面始终标注“模拟数据”。mock
适配器不复制 Prefect 调度逻辑。

## 科研自主模式控制

3101总览页提供“手动 / 监督执行 / 范围内自主”三档控制，以及项目“继承全局”。
修改带revision并发检查，只影响随后创建的运行。`mock-all`使用进程内策略适配器；
`allowlisted-test`在配置了 `BOGDA_AUTONOMY_POLICY_PATH`（盒子本地 core
`PolicyStore` 文件，如 `/var/lib/bogda/autonomy-policy.json`）且角色为 owner 时
接入真实策略后端并允许写入；其余情况保持 `canSetAutonomyMode=false`，界面显示只读与
“策略后端尚未接入”，不会静默使用 mock 策略。`real-readonly` 始终只读。

## 验证

```powershell
py -3.11 -m pytest -q
npm run test:frontend
npm run build
npm run test:browser
```

集成测试使用 Prefect 官方本地 test harness、临时 SQLite 和随机端口；它不会
启动 Worker 或执行 Flow。浏览器验收固定访问 3101，截图保存在
`tests/browser/screenshots/`。

重点验收 API 不可达、Worker 离线、RunResult 缺失/无效和陈旧数据。项目没有
通用重试层、备用任务存储、全文证据扫描器、Hermes/OpenClaw 或插件系统。

## 影子运行与回退

1. 保持旧 3100 和 Orchestra 数据不变。
2. 在 3101 以 `real-readonly` 连接相同 Prefect API，比较原始状态、Pool、Queue、
   Worker 和 RunResult 投影。
3. 在 mock 与隔离 S2 完成交互、移动端、可访问性和截图验收。
4. 记录差异并修正 3101；3100 继续作为即时回退。

本项目不包含 3100 切换、部署 Pi 或操作真实宿舍机的步骤。完成影子验收后，
仍需获得明确批准，才能另行设计 3100 切换方案。
