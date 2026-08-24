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
