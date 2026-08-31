# Bogda Console S1 real-readonly shadow

日期：2026-09-01（Asia/Shanghai）
范围：本机 loopback `3101` Bogda Console 对 RK3528 Prefect
`http://100.78.158.80:4200/api` 的只读 shadow；不包含 S2 写入、3100
切换、付费模型调用或远端服务变更。

## 结论

**S1 PASS。允许进入 S2 的专用测试资源创建与 exact-allowlist gate。**

`real-readonly` profile 成功通过现有 server-only
`PREFECT_API_AUTH_STRING` 连接真实 Prefect。3101 投影与直接
`PrefectClient` 读回的 deployment、run、pool、queue、worker 身份和
pool/queue/worker 状态一致；所有 `can*` 写能力均为 false。浏览器未发现
console error、page error 或 failed request，基础设施页的写按钮禁用并显示
只读原因。S1 前后对象计数、身份集合和 command version 集合未变化，3100
始终为 HTTP 200，launcher-owned 3101 已停止且无 listener。

真实 Prefect 当前没有 deployment、run 或 Artifact，所以 S1 无法生成一个
真实 Run Detail 样本；本轮明确记录为 `inapplicable`，没有用 mock 或不存在的
run 伪造成功。S2 必须在新建的专用前缀 deployment/run 上补做 Run Detail 的
资源级按钮验收。

## 目标与边界

- 3100 before/after：HTTP 200；未停止、代理、覆盖或重新配置。
- 3101 before：launcher `stopped`，无 listener；状态文件中的 PID `12560`
  已不存在，只是 stale launcher state。
- 3101 during：launcher-owned PID `14448`，`healthy`，profile
  `real-readonly`，绑定 `127.0.0.1:3101`。
- 3101 after：PID `14448` 经 launcher 正常停止，无 listener。
- 远端只执行 health、credential 读取和 Prefect API GET/read；未改 systemd、
  worker、deployment、schedule、queue、run、Artifact 或数据库。
- 所有四组 allowlist 均为空；未设置 DeepSeek key；未调用任何付费 provider。

## Authority / projection 对照

| 对象 | 直接 Prefect | 3101 投影 | 结果 |
| --- | ---: | ---: | --- |
| Deployment | 0 | 0 | 一致 |
| Flow run | 0 | 0 | 一致 |
| Work pool | 1（`pi-service`） | 1 | 身份与状态一致 |
| Work queue | 1（`default`） | 1 | 身份、paused、status、并发字段一致 |
| Worker | 7 | 7 | 身份与 online/offline status 一致 |
| Artifact | 0 | RunResult 投影 0 | 一致 |

直接读回和投影按 ID/name 比较，不依赖列表顺序。pool、queue、worker 的状态
另做逐字段对照，`differences=[]`。run 为空，因此 state type/name 与
command-version 字典均为空，而不是缺失错误。

能力接口返回以下十个 mutation capability，全部为 false：

- `canSubmitRegisteredDeployment`
- `canCancelRun`
- `canPauseSchedule`
- `canPauseWorkQueue`
- `canDecideCheckpoint`
- `canReviewScientificResult`
- `canSetAutonomyMode`
- `canResolveModelDecision`
- `canSetModelPolicy`
- `canPreparePaidRun`

## 前端验收

- `Infrastructure` 页显示 `real-readonly`、Prefect 实时来源、`pi-service`、
  `default` queue 和 7 个 worker。
- 页面唯一匹配 mutation 语义的按钮为禁用状态；可见文案说明当前 profile
  只读、不能执行该操作。
- `Runs` 页准确显示 0 个运行；未导航到虚构 Run Detail。
- console errors = 0，page errors = 0，failed requests = 0。
- Power Agent 卡片仍明确标为“陈旧数据 / 模拟数据”，没有伪装成 Prefect
  实时来源；它不参与本次 Prefect authority 判定。

截图：

- `.tasks/active/052_bogda-gate7-real-shadow/evidence/s1/ui-infrastructure.png`
- `.tasks/active/052_bogda-gate7-real-shadow/evidence/s1/ui-runs.png`
- `.tasks/active/052_bogda-gate7-real-shadow/evidence/s1/ui-home.png`

## 零变更与凭据边界

UI 检查后重新执行完整 authority/projection read。以下内容与检查前完全相同：

- 对象计数；
- deployment/run/pool/queue/worker/Artifact 身份集合；
- run command-version 集合（本轮为空）。

独立复审后又补做了一次完整 launcher lifecycle 边界：在启动 3101 **之前**
直接读取 Prefect 的 counts、全部身份集合、run state/timestamp 和基础设施状态，
随后启动 `real-readonly`、再次确认所有 mutation capability 为 false、停止
launcher，再做同样的直接 Prefect 快照。`lifecycle-before.json` 与
`lifecycle-after.json` 字节级一致，覆盖了“启动前 → 停止后”的零变更证据；
`lifecycle-verification.json` 记录 `directSnapshotEqual=true`、3101 stopped 与
3100 HTTP 200。

credential 只在短期 PowerShell 进程和 launcher child environment 中存在。
未写入 evidence、report、命令文本或 Git；对 evidence JSON 与 launcher
stdout/stderr log 的值匹配扫描结果为 `0`。报告只记录使用了
`PREFECT_API_AUTH_STRING`，不记录其值。

## 执行偏差与裁决

两次执行在任何 3101 启动前安全停止：第一次因 launcher 使用
`[Console]::Out`，脚本不能从 PowerShell pipeline 捕获 status 文本；第二次
因远端 `bash -lc` 触发 Armbian login 初始化而挂起。只终止了这次启动的本地
PowerShell/SSH 进程，未触及未知进程。最终实现收敛为 launcher exit code +
listener 判断，以及非 login `bash -c` 的只读 credential 获取；没有增加设备
身份检查、重试框架或原生输出防护。

本轮浏览器技能的 Python Playwright 依赖在 workspace bundle 中不可用；使用
已安装的 Node Playwright/Chromium 做等价 headless 验收，没有联网安装依赖。

## Evidence

忽略的非 secret 证据位于：

```text
.tasks/active/052_bogda-gate7-real-shadow/evidence/s1/
```

核心文件：

- `prestate.json`
- `authority-projection.json`
- `authority-projection-after-ui.json`
- `infrastructure-state-compare.json`
- `ui-verification.json`
- `final-state.json`
- `lifecycle-before.json`
- `lifecycle-after.json`
- `lifecycle-verification.json`
- 三张 UI PNG

## S2 gate

S2 可继续，但必须保持原计划边界：

1. 新建名称前缀为 `bogda-s2-acceptance-20260901-` 的 flow、pool、queue、
   deployment 与 inactive schedule；不得复用 `pi-service`、`default` 或任何
   既有对象。
2. pool concurrency 为 1、无 worker；3101 只运行一个
   `allowlisted-test` replica。
3. 四组 allowlist 仅使用刚返回的 exact ID/name。
4. S2 新建 run 后补验 Run Detail 的 cancel/review/checkpoint 资源级适用性；
   checkpoint 若缺运行时前置条件，按 `inapplicable` 记录，不伪造成功。
5. 每个 mutation 只执行一次并立即做直接 Prefect post-read；任何 source error、
   non-test identity、receipt 缺失或 post-read 不一致都 hard stop，不自动重试。
