# Bogda Phase C paid-model runtime acceptance

日期：2026-08-29
范围：本地 Phase C vertical slice；fake-only，未接触 live provider 或生产环境。

## 结论

Phase C 的六个集成场景已用 fake usage provider、fake model executor、文件 prompt archive、进程内 budget ledger 和 fake suspension boundary 验收。实现保持 `JobRequest`/`RunBudgetEnvelope` envelope 语义不变；`RunEventV1` 仅有 additive、v1-compatible 扩展，且 Bogda runtime 不导入 Orchestra 或 usage-monitor runtime。

## 六个验收场景

1. `auto` 请求消费预算中冻结的 Flash：prompt 归档后完成路由、快照、原子预留、fake 执行、精确 CNY 对账和释放；完整 prompt 只在 prompt artifact 中，事件只保留 hash/path/reference。
2. `auto` + `audit` 在 Pro 不可用时返回 `pro_required`，写 `tier_upgrade_requested`，不静默降级、不归档、不预留、不调用 executor。
3. 低风险 Pro 请求只有在显式允许且 envelope 冻结 `fallback_tier=flash` 时降级；`tier_downgraded`、started、finished 事件均保留 requested=Pro/effective=Flash。
4. 缺少 usage receipt 返回 `usage_unknown`，保留唯一 active reservation，并让同一 `run_id`/`call_id` 返回 `reconciliation_required`；不会第二次调用 executor，也不会把未知用量当作零。
5. 余额不足返回 `budget_paused`；fake suspender 恢复余额后，Task 5 flow 用同一解析后的 envelope 记录编号 resume key 并重新检查，最终完成一次 fake 调用。
6. prompt archive 失败在 admission 前终止；ledger 没有 reservation，executor 没有调用。

## 模块与运行边界

- `bogda.model_runtime.contracts`：调用、usage、archive 和执行端口。
- `archive.py`：`{root}/{run_id}/{call_id}.prompt.md` prompt artifact。
- `routing.py`：冻结的 Flash/Pro 路由与低风险降级矩阵。
- `dsh.py`：Bogda-owned Flash/Pro patch、headless argv、`stdout.log`、有界 `stderr.log` 和可选 `usage.json` receipt；本验收不运行 dsh。
- `service.py`：route/archive/admit/start/invoke/finish-or-unknown/reconcile 的 paid-call state machine。
- `flows/paid_model_call.py`：Prefect `suspend_flow_run` 适配器；fake 测试通过 injectable `BudgetSuspender` 验证，不连接 Prefect server。
- Phase B `BudgetAdmissionService`、`BudgetGuard`、`SingleFlightBudgetLedger` 和 `RunEventSink`：预算门禁、原子预留、终态对账和结构化事件。

已接入调用的事件顺序为：`route_selected` 或 `tier_downgraded` → prompt archive → `budget_snapshot` → `budget_reserved` → `model_call_started` → `model_call_finished` / `model_call_usage_unknown` → `budget_released`。Pro-required 在任何付费边界前写 `tier_upgrade_requested`；预算暂停写 `budget_paused`，恢复前写 `budget_resumed`。事件不存全文 prompt、模型输出、API key、Authorization 或 `X-Monitor-Token`。

## 恢复、限制与 Stage D/E handoff

`usage_unknown` 是人工对账门禁：先检查 receipt/产物并录入或获取实际费用，完成 reconcile 后才能决定是否重试；自动 retry 不得绕过该 barrier。当前 claim、ledger、终态事件去重和 JSONL sink 都是进程内能力，不能宣称跨进程 exactly-once 或崩溃后自动恢复。

Stage D 接手 owner-facing decision center、创建/确认/详情窗口、requested/effective tier、预算与价格窗口、暂停原因和恢复动作，并保持 stale、insufficient、scheduled、approval、unknown-usage 状态可区分。Stage E 接手真实只读 usage/balance wiring、受限 Flash/Pro dsh smoke、Prefect deployment 与真实 suspend/resume、持久 accounting/outbox、artifact lifecycle 和运维接线。Gate 6 的只读证据收尾可与 Stage D/E 并行；有状态变更的 Stage E/正式切换仍须等待 owner-approved prerequisites、shadow/production、回滚和观察窗证据；本报告不宣布 Gate 6 或 Gate 7 通过。

真实 Prefect 验证需要 registered deployment、可恢复 suspended run 的 worker、持久结果/事件/产物存储和新鲜 usage/balance source。真实 provider 验证还需要 owner 明确 live spend 上限、时段和凭据注入方案。

## 明确排除

本阶段不做 live dsh/DeepSeek 或网络调用、Prefect server/deployment/systemd/device/production mutation、frontend、production writer、secrets/credentials、跨进程 exactly-once ledger/outbox、3100/3101 cutover、Gate 6/7 宣告、push、merge 或 cleanup。

## 本地验证

聚焦验收：`uv run --extra dev --python 3.11 pytest tests/integration/test_paid_model_runtime.py -q` — 6 passed in 2.22s。Affected broad：`uv run --extra dev --python 3.11 pytest --import-mode=importlib tests/integration tests/flows tests/model_runtime tests/budget tests/events tests/contracts -q` — 373 passed, 1 skipped in 24.41s。唯一一次 final default Bogda full suite：`uv run --extra dev --python 3.11 pytest -q` — 545 passed, 11 skipped in 24.92s。

Orchestra compatibility 使用 `D:\pythonProject\.worktrees\bogda-paid-model-runtime\bogda\.venv\Scripts\python.exe -m unittest tests.test_taskfile -q` — 25 tests，OK。对 `bogda/src` 的 forbidden runtime import scan 未发现 `orchestra` 或 `usage-monitor`；`git diff --check` clean。fork point 为 `ac334d08a29390f5dcf063bca5643569136130c3`，授权差异仅含本 Phase C runtime、相关测试、计划、验收文档及 deferred register；Task 6 acceptance test/report 属于本任务新增，ignored task report 不入 commit。

TDD 诚实说明：Task 6 只新增验收/维护文档，Task 1–5 的生产实现已在此前完成并审核；因此新增集成测试首次运行即为绿色，未伪造 feature-RED，也未为制造 RED 修改生产代码。
