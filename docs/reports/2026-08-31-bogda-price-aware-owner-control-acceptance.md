# Bogda 价格感知与 Owner 恢复控制验收

日期：2026-08-31

范围：Stage E 的价格窗口计划、未知用量持久恢复、Decision Center 后端/前端闭环、DeepSeek 余额语义一致性
结论：**本地实现与 mock owner 闭环通过；生产 transport、RBAC、多 worker outbox 与真实调度接线仍按延期登记册触发。**

## 1. 本轮交付

1. 价格计划器把预计 token 成本、工作量、运行时长、deadline 与北京时间峰谷窗口放在同一个确定性决策中；未来最早开始、跨周窗口、无可行低峰和不可满足 deadline 均有明确语义。
2. 未知用量恢复使用 SQLite 持久保存四个且仅四个状态：`awaiting_reconciliation`、`awaiting_retry_decision`、`retry_approved`、`terminated`。人工对账先调用既有预算权威，再写 `manual_usage_reconciliation`；批准重试必须提供不同于原调用的新 call id。
3. Decision Center 后端通过 `actualCostRequired` / `newCallIdRequired` 声明 owner 输入要求；旧 action payload 仍有效。mock 生命周期为“登记实际费用 → 批准一次新调用或终止”，revision 冲突继续使用既有 409 权威快照。
4. 前端只按后端 flags 显示“实际费用（CNY）”或“新的调用 ID”，不识别 action id；切换动作或收到新权威快照会清空条件字段。普通动作和终止动作不显示无关输入。
5. core 与 console 的 DeepSeek 余额入口共同消费 `contracts/fixtures/deepseek-balance-v1.json`。有效 CNY 字符串通过；不可用、USD-only、畸形列表、数值金额、负数、NaN、Infinity、重复 CNY 均 fail-closed。

## 2. Owner 在前端可裁决的内容

- 对未知用量录入供应商最终结算金额；金额为空、非有限数或小于 0 时不能提交。
- 对账后选择“批准一次重试”或“终止”；批准重试必须输入新 call id，原 call id 不会被复用。
- 所有会改变账本或启动新付费调用的 mock 动作继续要求显式确认；409 后必须重新检查当前修订，旧操作不会自动重放。
- 后端没有声明的字段不会出现，也不会进入请求体。前端不复制费用规则、状态机或 action-name 判断。

## 3. 兼容性与可维护性

- 新字段均为 additive defaults；OpenAPI 与生成 TypeScript 契约一致。
- core 恢复逻辑、console anti-corruption adapter、页面状态各自保持边界，没有让前端成为第二事实源。
- 没有引入通用工作流框架、跨库事务或持久 outbox；现有 JSONL 明确保持 at-least-once。只有在多 worker/跨进程触发 DEF-05 时才增加相应机制。
- `terminated` 加入后，TypeScript 的穷举映射在构建期发现直接消费者缺口并已补齐；不存在静默 fallback。
- DeepSeek 精确 token receipt 按 owner 决定继续延期；余额与人工实际费用已足够支撑当前恢复闭环。

## 4. 验证证据

| 验证面 | 结果 |
|---|---|
| Bogda 全量 | **635 passed, 11 skipped** |
| console backend 全量 | **167 passed** |
| frontend Vitest 全量 | **111 passed** |
| OpenAPI / TypeScript / Vite build | **通过** |
| Playwright 六视口矩阵 | **121 passed, 5 skipped**；1440、1280、768、390、360、320 px |
| DeepSeek core conformance | **35 passed** |
| DeepSeek console conformance | **13 passed** |

一次从仓库根目录启动 console backend 导致 38 个 fixture 相对路径失败；从规定的 `bogda-console` 目录重跑后 167 全部通过，判定为验证命令工作目录错误，不是产品缺陷。

## 5. 提交链

- `469d635`、`7e68047`、`78d6304`：价格窗口计划器及两轮边界修复。
- `dcfb3c2`：未知用量持久恢复。
- `4965ce8`：Decision Center 后端输入契约与 mock 生命周期。
- `f48f9b7`：Owner 条件输入、生成契约与浏览器覆盖。
- 本报告与最终验收记录位于同一提交。

## 6. 独立审计

最终 Luna audit 初审提出两条 HIGH：进程重启后原 call id 的持久阻断，以及人工对账事件顺序。第一条经复现成立：对账释放活动 reservation 后、owner 尚未批准或终止时，重启会丢失进程内 claim；现已在路由、预算和 executor 之前查询持久 recovery gate，并增加 RED→GREEN 重启测试。第二条与本轮明确计划“先调用预算 reconcile，再追加 `model_call_finished`”冲突，保留既定顺序和 at-least-once 边界。Luna 对修复与规格处置的 scoped re-review 结论为 **ACCEPT**。

## 7. 未关闭但必要的后续

- DEF-04：core recovery store 到 real-profile console 的生产 transport。
- DEF-05：多 worker 或跨进程前的持久 outbox / 原子 claim。
- DEF-06：计划器到真实 scheduler/dispatcher 及 owner 三选一动作的接线。
- DEF-02：只有在需要精确 token 对账时补 dsh `usage.json` receipt。
- DEF-18：生产化前在共享 fixture 保护下收敛两套余额运行时解析。
- DEF-19：3101 对多用户或非本机开放前的服务端 RBAC 与审计主体。

本轮未调用真实 DeepSeek、未产生 provider 费用、未修改 Gate 6、Prefect、systemd、部署或生产状态。
