# Bogda NOW-06 正式研究运行前接线（本地）

日期：2026-09-02  
分支：`codex/bogda-now06-pre-research`（worktree `D:\pythonProject\.worktrees\bogda-gate7-real-shadow`）  
计划：[`docs/superpowers/plans/2026-09-02-bogda-now06-pre-research.md`](../superpowers/plans/2026-09-02-bogda-now06-pre-research.md)

**不是 3100 切换。不是宿舍机。不是 `pi-service` 生产科研。DEF-03 checkpoint 仍缺专用 worker，未冒充验收。**

## Gate 7 审查（GPT 跳过的那一轮）

独立审查 `d05ccd6..a25e4d8`（[Review](c85a282b-9404-4e46-8272-3e6d990c2491)）：无 Critical。S1/S2 后端白名单仍是授权源，3100 未绑定。

**Important 已修：** submit/cancel/review/checkpoint 联合校验 `work_pool_name ∈ allowed_work_pool_names`；通配符 `*` / `pi-service,*` 单测；real-readonly 写操作在 adapter 前 403；只读 `can*` 全字段断言。

## 第四步本地接线

| 条目 | 本轮 | 仍缺 |
|---|---|---|
| DEF-19 身份 | `BOGDA_CONSOLE_ROLE` = owner/observer/operator；observer 即使有 allowlist 也不能 POST；能力快照带 `actorId`/`role`；基础设施页展示 | 非本机 OIDC/会话；不是多用户 RBAC |
| DEF-17 日志 | `SafeLogReader` 路径封闭 + 脱敏 + 截断；`GET /api/v1/runs/{id}/logs`；运行详情日志区 | 现网 worker 需设 `BOGDA_ARTIFACT_ROOT` |
| DEF-13 产物 | `ArtifactLifecycle.cleanup(..., confirm="delete-content")` 删内容留 tombstone 与 events.jsonl | 3101 尚未放清理按钮 |
| DEF-16 >20 CNY | HMAC 单次凭证 + `admit(..., approval=)` 消费；伪造/过期/错 run/重放拒绝 | 决策中心尚未签发凭证 UI |
| DEF-04 usage_unknown | `CoreUsageUnknownAdapter` 把 SQLite case 映到既有 reconcile/retry/terminate；需 `BOGDA_USAGE_UNKNOWN_DB` | 未接到现网 worker 的同一 DB 文件 |
| DEF-06 峰谷 | `PriceAwareDispatcher` 三选一，不调 Prefect | 未接真实 dispatcher/生产队列 |
| DEF-03 checkpoint | 未做 | 需要专用 worker |
| DEF-20 | 保持关闭 | — |

## 验证（本机）

- bogda：`tests/artifacts/test_safe_log.py`、`test_lifecycle.py`、`tests/budget/test_approval.py`、`test_dispatcher.py`、`test_recovery.py` 及相关回归 **84 passed**
- console backend `tests/backend`（不含 launcher）**180 passed**
- console frontend vitest **121 passed**
- 已 `npm run generate:contracts`

## 环境（值不入库）

- `BOGDA_CONSOLE_ROLE`、`BOGDA_CONSOLE_ACTOR`
- `BOGDA_ARTIFACT_ROOT`
- `BOGDA_USAGE_UNKNOWN_DB`（allowlisted-test owner 才打开 recovery 写入）

未 push。未删盒子上 S2 验收资源。
