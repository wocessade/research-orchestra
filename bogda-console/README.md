# Bogda Console

Bogda Console 是现有 Orchestra 3100 控制台的独立影子重写。它运行在
`codex/bogda-console` 分支的 `bogda-console/` 目录，不修改 `bogda/` 核心、
`orchestra/console/`、旧控制台数据或真实基础设施。

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

3101 当前是 Windows 主机上的手动进程，不是 Windows 服务，也不会随开机自动
启动。实际运行应以 `D:\pythonProject\bogda-console` 主工作目录为准，不要依赖
`.worktrees` 中残留的虚拟环境、前端产物或 Python import 路径。

### 首次安装或重建依赖

```powershell
Set-Location D:\pythonProject\bogda-console
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
npm ci
npm run build
```

需要运行 Python 测试时，把可编辑安装改为
`.venv\Scripts\python.exe -m pip install -e ".[dev]"`。前端代码变更后必须重新
执行 `npm run build` 并重启后端，否则浏览器可能继续显示旧页面。

### 启动完整页面

当前本地演示使用 `mock-all`。它可以验证完整 UI 和写入交互，但数据来自内存中
的 fixture，不代表 Pi、真实 Prefect 或生产状态。

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

先确认 3101 确实有监听者，再读取能力接口：

```powershell
Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 3101 -State Listen |
    Select-Object LocalAddress, LocalPort, OwningProcess

(Invoke-RestMethod http://127.0.0.1:3101/api/v1/capabilities).data |
    Select-Object profile, canSetAutonomyMode
```

本地演示的预期结果是 `profile=mock-all`、`canSetAutonomyMode=True`。只有端口
监听而能力接口失败时，不应把页面视为可用。

### 停止

优先在启动进程所属的 PowerShell 窗口按 `Ctrl+C`。如果原窗口已经丢失，先查明
3101 的确切 PID，再停止该 PID：

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
| 浏览器显示无法连接 | 先运行 `Get-NetTCPConnection`；没有 3101 listener 就是进程未启动或已退出。 |
| `import bogda_console` 指向 `.worktrees` | 回到主工作目录，使用主目录 `.venv` 重新执行 `pip install -e .`。 |
| 后端启动但页面 404、空白或缺少新功能 | 运行 `npm ci`、`npm run build`，重启后端，再强制刷新浏览器。 |
| `frontend/dist` 不存在 | 前端尚未构建；运行 `npm run build`。 |
| 3101 已被占用 | 先查看 `OwningProcess` 并确认归属；不要停止未知进程，也不要改用 3100。 |
| 能力接口可用但 profile 不是 `mock-all` | 当前进程使用了别的配置；停止它并按“启动完整页面”重新设置环境变量。 |

这套流程只保证本机可重复运行，不包含开机自启、托盘常驻或后台进程管理。后续
本地启动器应封装 `start/status/stop`、PID 和日志管理；在它交付前，本节命令是
权威操作方式。

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
| `PREFECT_API_KEY` | 无 | Prefect API 可选凭据，只保存在服务端 |
| `BOGDA_CONSOLE_REPLICA_COUNT` | `1` | 评审追加仅允许单副本进程 |
| `BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS` | 空 | 精确 Deployment UUID/ID，逗号分隔 |
| `BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS` | 空 | 精确 schedule UUID/ID，逗号分隔 |
| `BOGDA_CONSOLE_ALLOWED_QUEUE_IDS` | 空 | 精确 Work Queue UUID/ID，逗号分隔 |
| `BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES` | 空 | 精确 Work Pool 名称，逗号分隔 |

Allowlist 不支持 `*`。命令提交前和 Prefect 权威回读后都会检查资源；本地不做
乐观状态写入。

### Profile 矩阵

| Profile | Prefect/RunResult | 查询 | 评审 | 执行控制 |
| --- | --- | --- | --- | --- |
| `mock-all` | fixture | 是 | 单副本且命中 allowlist | 命中 allowlist |
| `real-readonly` | 真实 Prefect API | 是 | 否 | 否 |
| `allowlisted-test` | 真实 Prefect API | 是 | 单副本且命中 allowlist | 命中 allowlist |

影子运行只使用 `real-readonly`。只有隔离的 S2 验收环境才使用
`allowlisted-test`，并必须填写精确的 Deployment、schedule、queue 和 pool
allowlist。不能把 S2 指向生产资源。

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
当前只有`mock-all`使用进程内策略适配器并允许修改；修改带revision并发检查，
只影响随后创建的运行。`real-readonly`和`allowlisted-test`没有接入真实Bogda
Policy后端，保持`canSetAutonomyMode=false`，界面显示只读与“策略后端尚未接入”，
不会静默使用mock策略。真实策略接线属于后续S2任务。

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
