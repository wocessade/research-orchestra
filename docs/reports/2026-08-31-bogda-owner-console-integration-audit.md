# Bogda Owner Console 前后端结合审查

日期：2026-08-31
范围：`bogda-console` 3101、本地 Stage E budget/runtime；不含真实 Prefect 写入、RK3528 变更和付费 DeepSeek 调用。

## 结论

本轮关闭了两个明确的端到端缺口：

1. 后端已有全局模型策略写接口，前端此前只能修改项目策略；现在前端明确区分“全局默认 / 项目覆盖”，分别读取、提交和冲突处理各自的 revision。
2. Run Budget 的 `remainingCost` 不是账户余额；现在新增独立的 `/api/v1/usage-balance` 契约、real-readonly 适配器和余额卡片，显示 CNY 余额、观测时间与来源新鲜度，失败时不拖垮策略页。

另外补齐：model policy/autonomy 的非冲突写入错误可见性、陈旧权威快照禁写、Deployment 查询故障不再伪装成空列表。所有实现均使用 mock/fake 验证，没有调用真实余额或改动 Gate 6。

## Owner 操作矩阵

| Owner 意图 | Backend/API | Frontend | 当前判定 |
|---|---|---|---|
| 提交已注册 Deployment | `POST /deployments/{id}/runs` | Infrastructure → 运行准备 → 二次确认 | 已覆盖；真实 profile 受 allowlist/capability 限制 |
| 取消运行 | `POST /runs/{id}/cancel` | Run Detail 确认窗口 | 已覆盖 |
| 暂停/恢复日程 | schedule pause/resume routes | Infrastructure 每条日程按钮 | 已覆盖 |
| 暂停/恢复队列 | queue pause/resume routes | Infrastructure 每条队列按钮 | 已覆盖 |
| 科学结果 accepted/rejected/inconclusive | `POST /runs/{id}/reviews` | Run Detail review | 已覆盖，绑定 Artifact/version |
| checkpoint 批准/拒绝 | `POST /runs/{id}/checkpoints` | Run Detail checkpoint | 已覆盖；批准时内部调用 `resume_run` |
| 全局/项目科研自主模式 | autonomy global/project routes | Overview autonomy panel | mock 已覆盖；真实写入见 DEF-07/19 |
| 通用模型/预算决策 | `POST /decisions/{id}` | Decision Center 按后端 actions 渲染 | 已覆盖 revision、理由、确认和冲突重审 |
| 全局模型策略 | `POST /model-policy/global` | Model Policy“全局默认”作用域 | 本轮关闭缺口 |
| 项目模型策略/恢复继承 | `POST /model-policy/projects/{id}` | Model Policy“项目覆盖”作用域 | 已覆盖；本轮修正为显式读取 projectId 对应快照 |
| 付费运行预览/确认 | run preparation preview + deployment submit | Run Preparation | 已覆盖 mock；真实 model-control 仍未接线 |
| 账户余额观察 | `GET /usage-balance` | Model Policy 余额卡 | 本轮本地闭环；真实只读验收见 DEF-01 |
| 预算事件/产物引用 | run budget/result/version queries | Run Detail / Run Budget | metadata 与结构化事件已覆盖；原始日志内容见 DEF-17 |

### 不应伪装成按钮的项

- `PrefectCommandPort.resume_run` 是 checkpoint 批准的内部执行机制，不是一个已经定义好的普通“恢复运行”owner 命令；在独立语义、allowlist、revision 和 post-read 规则确定前不增加泛化按钮。
- withdraw/dismiss 当前没有 backend command/contract，因此前端不应出现仅改变本地状态的假动作。
- `/test/scenario` 是 test-mode fixture 控制，不是生产 owner 操作。

## 耦合与可维护性

- 前端依赖 OpenAPI 生成类型和统一 `ApiEnvelope`，不直接依赖 Prefect/DeepSeek payload；provider 与调度细节留在 BFF adapter 后面。
- 所有 mutation 由 capability、权威 revision/command version 和 envelope error 共同控制；禁用按钮不是服务端授权的替代品。
- balance、model-control、Prefect 均通过独立 port 注入。余额失败只降级余额卡，不能污染模型策略读写状态。
- `ModelPolicyPage` 同时协调 global/project/balance 三个查询，复杂度仍可读；若后续继续加入 provider/价格编辑，应拆成 `AccountBalanceCard` 与 `PolicyEditor`，不要继续堆进单页组件。
- console 与 core 目前各有一个 DeepSeek balance payload adapter，已登记 DEF-18，生产前收敛，避免供应商字段变化时双点维护。

## 易用性审查

- 全局与项目策略使用显式双作用域开关，切换时清空未提交 draft，避免把项目草稿误写到全局。
- 余额用独立深色信息带突出，明确“账户余额”而非 run-level remaining，并显示观测时间和来源。
- stale policy snapshot 会禁用编辑并说明刷新条件；unavailable balance 不会禁用仍然新鲜的策略编辑。
- 非冲突 mutation rejection 会保留在页面上；409 仍要求采用最新权威资源后人工重确认，不自动重放。
- Deployment 来源失败显示错误面板，不再显示“— 个”或空列表暗示真的没有 Deployment。
- 现有 840px/narrow、dialog keyboard、skip-link 和 axe 浏览器测试继续作为回归基线；本轮最终浏览器矩阵覆盖 1440/1280/768/390/360/320 六种视口，结果为 `115 passed, 5 skipped`。320px 初次发现的策略作用域横向溢出已按实际 DOM 尺寸定位并修复。

## 独立审查与最终证据

Luna 终审发现冻结 envelope 可通过显式小额 reservation 绕过 run 级自动审批门槛，以及 console/core 对 provider 金额类型的解析不一致。本轮已修正：门禁同时检查 envelope 授权额与实际预留额；20 CNY 安全线允许运行时收紧但不能提高；余额适配器只接受字符串金额。20.00 CNY 是自动准入上限的含边界值，只有超过 20 CNY 才进入 `owner_approval_required`。

- Bogda：`593 passed, 11 skipped`
- Console 后端：`152 passed`
- Frontend：`108 passed`
- OpenAPI 契约、TypeScript、Vite build：通过
- Playwright 全矩阵：`115 passed, 5 skipped`；最终模型策略改动另在六种视口全部通过
- Provider/生产调用：0 次；Gate 6 运行状态未被本轮改变

## 必要延期

权威清单见 [延期工作登记册](2026-08-29-bogda-deferred-work-register.md)：DEF-02 精确 token receipt、DEF-03 真实 suspend/resume、DEF-04 usage-unknown 人工对账、DEF-07 真实写入、DEF-16 超 20 CNY 审批凭证、DEF-17 原始运行日志、DEF-18 balance adapter 收敛、DEF-19 生产身份/RBAC。
