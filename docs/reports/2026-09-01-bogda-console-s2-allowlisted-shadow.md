# Bogda Console S2 exact-allowlist shadow

日期：2026-09-01（Asia/Shanghai）
范围：本机 loopback `3101` Bogda Console 对 RK3528 Prefect
`http://100.78.158.80:4200/api` 的单副本、专用测试资源写入验收。

## 结论

**S2 PASS。Gate 7 的 real Prefect S1/S2 软件接线成立。**

3101 以 `allowlisted-test` profile 和单副本运行，四组服务端 allowlist 只包含
本轮新建的专用 deployment、schedule、queue 与 work pool。提交、取消、科研
评审、日程恢复/暂停、队列恢复/暂停均通过正常 3101 API 执行。命令服务只有在
Prefect adapter direct-read 和 service post-read 均确认目标状态后才返回 200；
最终状态另由外部 `PrefectClient` 读取确认。对生产 `pi-service/default` 的负路径返回
`403 RESOURCE_NOT_ALLOWLISTED`，其 Prefect 状态前后未变。

前端准确区分专用资源和生产资源：专用 deployment、schedule、queue 及其 run
显示可执行控件；生产 `pi-service/default` 的控件禁用并明确显示“不在测试
白名单”。专用 run 没有 worker，未进入暂停科研检查点，因此 checkpoint
裁决按 `inapplicable` 记录，没有伪造一次成功裁决。

3100 前后均为 HTTP 200。launcher-owned 3101 已正常停止，无 listener；凭据
值扫描命中为 0。测试资源保留在 Prefect 以便审计，未删除、未连接生产 pool、
未触发 worker，也未调用 DeepSeek 或其他付费模型。

## 专用资源

统一前缀：

```text
bogda-s2-acceptance-20260901-20260831-195208-
```

| 对象 | ID / name | 最终状态 |
| --- | --- | --- |
| Flow | `587b8b20-6645-4f03-8e28-1d5f29ed7413` | 仅供本次 deployment |
| Work pool | `26de2498-e44a-4151-862c-3e9005c5163f` / `bogda-s2-acceptance-20260901-20260831-195208-pool` | concurrency `1`，worker `0` |
| Work queue | `e0420042-aa9b-4d49-98d2-42c42dc2d8a7` / `bogda-s2-acceptance-20260901-20260831-195208-queue` | paused |
| Deployment | `c172ed02-5f7f-4559-8a0f-83a953827208` | 绑定专用 pool/queue |
| Schedule | `6c5dae99-e2b5-4127-b716-50a931c28d81` | inactive |
| Run | `d132bafb-7d2b-48fb-8b40-016fc7711f65` | Cancelled |
| 初始 RunResult | `fec44dd1-8b6d-4c85-9bc3-c654668198fa` | unreviewed |
| 评审后 RunResult | `13487c47-0bf4-425d-a210-ceb82bb781a4` | accepted |

Prefect 为每个新 work pool 自动创建一个名为 `default` 的队列；本轮专用 pool
因此另有 `96ebfbe3-6c01-4f82-99b2-dc8f609ae884`。它不是 production
`pi-service/default`，也没有进入 allowlist。生产队列为
`e611fd41-0a2b-4776-9bf8-d793b67c5bac`，前后均未暂停。

## 精确能力边界

启动配置与 `/api/v1/capabilities` 共同证明：

- profile：`allowlisted-test`；launcher 配置 replica count 为 `1`；该 profile
  在配置层会拒绝任何非 `1` 值，`canDecideCheckpoint=true` 也只在解析后的
  `review_enabled`（commands enabled 且 replica count 为 `1`）成立时出现；
- `allowedDeploymentIds`：仅本轮 deployment ID；
- `allowedScheduleIds`：仅本轮 schedule ID；
- `allowedQueueIds`：仅本轮专用 queue ID；
- `allowedWorkPoolNames`：仅本轮专用 pool name；
- submit、cancel、pause schedule、pause queue、review、checkpoint capability 为
  true；policy、model-control 和 paid-run capability 为 false。

能力快照只用于前端表达适用性。真正授权仍由后端在每次命令前从 Prefect
fresh-read 资源关系；浏览器没有 Prefect 凭据，也不能自行扩展 allowlist。

## 命令矩阵与权威回读

| 动作 | 3101 结果 | 权威结果 |
| --- | --- | --- |
| 提交专用 deployment | 200 | 新 run 的 `deploymentId` 精确匹配 allowlist |
| 评审 RunResult | 200 | 新 Artifact 为 `accepted`，旧版本仍保留 |
| 取消 run | 200 | Prefect 最终为 `Cancelled` |
| 恢复专用 schedule | 200 | 回执中的 post-read command version 被下一条 pause 接受 |
| 暂停专用 schedule | 200 | 回执 snapshot 与外部最终读均为 inactive |
| 恢复专用 queue | 200 | 回执中的 post-read command version 被下一条 pause 接受 |
| 暂停专用 queue | 200 | 回执 snapshot 与外部最终读均为 paused |
| 暂停 production queue | 403 `RESOURCE_NOT_ALLOWLISTED` | `pi-service/default` 前后未变 |
| checkpoint 裁决 | inapplicable | 无 worker，run 从未产生开放 checkpoint |

运行日志 `command-log-excerpt.txt` 保留了上述七次命令的 HTTP 结果。每个成功
写入只发生一次；执行脚本在证据持久化问题后没有重放已成功的命令，而是从
当前 Prefect 状态恢复证据并只继续尚未执行的步骤。

限制：临时驱动在四条 schedule/queue 命令全部成功后、写 evidence 前硬停，
因此没有把两个瞬时 resume snapshot 的完整 JSON 单独保留下来。`200` 的成立
仍要求 adapter 在写后 direct-read，并要求 service 再次 post-read；下一条
pause 又使用前一条 resume receipt 的 command version 并通过版本检查。最终
inactive/paused 状态另有外部 Prefect 读取。这个链条证明命令及权威回读发生过，
但 evidence package 不声称拥有两个已丢失的瞬时 JSON snapshot。

## 前端验收

基础设施页证明：

- 专用 pool、queue、deployment 与 schedule 均可见；
- 专用 queue 恢复按钮、deployment 提交按钮、schedule 恢复按钮可用；
- production `pi-service/default` 队列按钮禁用，原因是“不在测试白名单”；
- page error、failed request 均为 0。

Run Detail 在命令前证明专用 run 的取消与科研评审按钮可用，且没有错误显示为
“不在测试白名单”。命令后页面显示 Prefect `Cancelled` 和科研状态
`accepted`，终态 run 不再显示取消按钮。checkpoint 控件未出现，与真实 run
状态一致。

Run Detail 另有一个预期的 `503`：`allowlisted-test` 有意未接 model-control
backend，因此 `/model-budget` 返回 `MODEL_CONTROL_UNAVAILABLE`，页面明确显示
“运行预算暂不可用”。这是已设计的来源降级，不是 S2 命令失败，也没有为消除
浏览器网络提示而添加假数据或泛化兜底。真实 core→console model-control
transport 仍由延期项 DEF-04/DEF-07 管理。

截图：

- `.tasks/active/052_bogda-gate7-real-shadow/evidence/s2/s2-ui-scope.png`
- `.tasks/active/052_bogda-gate7-real-shadow/evidence/s2/s2-ui-run-detail.png`
- `.tasks/active/052_bogda-gate7-real-shadow/evidence/s2/s2-ui-final-run-detail.png`

## 执行偏差与不过度防御裁决

验收脚本暴露了四个仅属于临时执行器的假设：Prefect 不保证 queue name 全局
唯一、Artifact 默认列表首项不代表最新版本、Console 没有 deployment detail
GET 路由、新建 pool 会新增一个默认队列。所有问题都在命令边界硬停，并依据
已写入状态从下一条尚未执行的命令继续；没有盲目重试 review、cancel、schedule
或 queue 命令。

这些问题没有被包装成产品级重试框架、设备身份仪式、跨进程流复制或额外前端
开关。最终判定按可达事实收敛为：按 pool + queue 定位生产对象、用最新
RunResult 投影验证评审、从 deployment 列表读取 schedule、只比较 S2 前已存在
对象的 ID 与状态。

## 收尾与秘密边界

- 3100 before/after：HTTP 200；before 来自资源创建前 controller preflight，
  after 来自 `final-local-check.json`；
- 3101 after：launcher-owned PID `38576` 已停止，listener `0`；
- 3101 before 为 stopped、无 listener；因此需要恢复的是 stopped runtime state，
  不存在一个先前运行中的 profile 要切回；
- 专用 schedule：inactive；专用 queue：paused；专用 run：Cancelled；
- production `pi-service/default`：未变；
- S2 前存在的 deployment/run 身份均保留；
- evidence、临时脚本和 launcher 日志共扫描 52 个文件，凭据值命中 `0`；
- 未回显或写入 `PREFECT_API_AUTH_STRING`；未设置 DeepSeek key。

## Evidence

忽略的非 secret 证据位于：

```text
.tasks/active/052_bogda-gate7-real-shadow/evidence/s2/
```

核心文件：

- `inventory-before.json`、`inventory-final.json`
- `prestate.json`、`replica-and-receipt-reconciliation.json`
- `resources.json`、`capabilities.json`、`setup-projection.json`
- `submit-seed.json`、`receipts.json`、`final-prefect-state.json`
- `command-log-excerpt.txt`
- `s2-ui-scope.json`、`s2-ui-run-detail.json`、`s2-ui-final-run-detail.json`
- 三张 UI PNG

## 后续边界

Gate 7 证明了 3101 的真实 Prefect 读取和专用测试写入边界，不等于生产切换：

1. 保持 3100 事实源不变，直到 owner 单独批准迁移；
2. 不把本轮 acceptance deployment/pool 变成生产科研执行资源；
3. 真正 checkpoint 裁决随 DEF-03 的 worker suspend/resume 场景补验；
4. real profile 的 model-control、usage、RBAC、日志内容 API 与生产运维继续按延期
   登记册执行；
5. 不删除本轮 Prefect 记录，待 owner 依据报告决定保留或清理。
