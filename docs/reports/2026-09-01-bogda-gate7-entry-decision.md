# Bogda Gate 7 entry decision

日期：2026-09-01（北京时间）
范围：RK3528 control-plane placement、3101 controlled integration entry；不包含 3100 切换或生产研究写入。

## Decision

**ACCEPT: Gate 6 evidence supports controlled S1 read-only integration.**

这是受边界约束的 Gate 7 接纳，不是无条件的 S1/S2 权限，也不是生产切换批准。S1 在 Task 2 的 server-only auth/capability contract 与 Task 3 的 runbook prerequisites 通过前仍为 **non-executable**。S1 通过后，S2 仍须另行满足本报告的资源、回滚和新鲜证据条件。

## Evidence reconciled

- Gate 6 final acceptance：trial `20260830T154019Z`，覆盖 `24 小时 8 分 56.941453 秒`，`275` 个样本，`bad_lines=0`、`missing_intervals=0`、`api_failure_count=0`、`database_integrity_failure_count=0`、`oom_kill_delta=0`；受控 reboot、正常 fsck/mount、独立 restore 和最终日志复核均通过。最终裁决为 **Gate 6：PASS**。
- Gate 6 remediation：静态 `e2fsck 1.47.0`、正常依赖挂载、受控重启和独立 restore 已完成；live `prefect.db` 未被覆盖。该报告明确说明 Gate 6 不自动授权 3100 切换或真实 Prefect 写入。
- Stage D acceptance：只验收 `3101 mock-all` owner 操作面；不是真 Prefect 写入，不是 3100 切换。
- Stage E evidence：官方余额 `live GET` 成功，本机 Flash/Pro dsh stdout 均为 `pong`；`usage.json` 精确对账仍缺失，按 owner decision 保持 non-blocking；真 Prefect suspend/resume 与 3101 真写入仍未完成。
- Live read-only preflight：`3100 HTTP 200`；launcher-owned `3101` 已停止且无 listener；Prefect health `200`；authenticated admin/version 在无 credentials 时为 `401`；server env names 包含 `PREFECT_API_AUTH_STRING`。未读取或记录任何 secret value。

## Entry conditions

### S1 — read-only, not yet executable

S1 仅可在 Task 2 与 Task 3 prerequisites 通过后启动，并且必须：

- 使用 `real-readonly` profile 访问 live Prefect；所有 mutation capability 为 false；
- 只通过 Bogda server-side adapter/BFF contracts 读取，不向 browser 暴露 Prefect 或 provider credentials，也不发送 Prefect mutation；
- 记录 source freshness、对象清单和数据差异，并保留 fresh S1 evidence；
- 保持 3100 reachable and unchanged，S1 只使用 loopback 3101 的 launcher-owned process；不得杀掉未知 3101 process；
- 若 auth、capability、runbook、freshness 或 compatibility evidence 缺失，则停止，不把缺失证据解释为通过。

### S2 — separately conditioned exact-allowlist test writes

S2 不因本次 ACCEPT 自动开启。只有在 S1 fresh evidence PASS 且 Task 2/3 prerequisites 已通过后，才可由单独的 S2 gate 进入，并且必须：

- 使用 `allowlisted-test`，恰好 one replica；
- 仅使用新建、专用、可识别的 test resources，deployment、schedule、queue、work-pool 使用 exact allowlists，禁止 wildcard；
- 资源身份必须来自 authoritative S1 evidence，不能猜测；不得连接 `pi-service`、`dorm-x86` 或任何现有生产 deployment；
- 每次 mutation 后执行 authoritative Prefect read；submit、cancel、schedule pause/resume、queue pause/resume、review、checkpoint 必须逐项 prove，或以 exact missing runtime precondition 标记 `inapplicable`；
- 先证明 resource-scoped authorization，再让 frontend applicability enable controls；UI disabled 不得被当作 authorization；
- 预先记录 one-replica rollback boundary，任何不在 allowlist 的 mutation 在 mutation 前拒绝并保持错误可见；
- S2 前后复查 3100 与 production object state，恢复 safe state，保留 evidence，不删除 test records。

## Non-blocking deferred work

NOW-03 的 Gate 6 failure wording 已按当前事实更正为 Gate 6 PASS；其余 Stage E 接线缺口继续登记。精确 dsh token/`usage.json` receipts 仍按 owner decision 为 non-blocking，不得被表述为已完成，也不得被用来放宽 Gate 7 的 Prefect auth、capability、resource identity、rollback 或 fresh-evidence gates。

## Ruling and rollback

本裁决接受 RK3528 作为受控集成目标，但不改变 Orchestra 为当前生产 task source，也不授权 3100 replacement、production research Flow mutation、deployment 或 push。若 RK3528 control-plane placement 后续被 fresh evidence 否定，Gate 7 进入 `ROLLBACK`：停止受控集成并返回 documented fallback；若只是 auth/capability/runbook/evidence boundary 未闭合，则保持本 `ACCEPT` 的 bounded status，转为 `REMEDIATE` 该 named prerequisite，不改写 Gate 6 thresholds。

## References

- [Gate 6 final acceptance](2026-08-31-bogda-rk3528-gate6-final-acceptance.md)
- [Gate 6 remediation log](2026-08-30-bogda-rk3528-e2fsck-remediation.md)
- [Stage D acceptance](2026-08-29-bogda-owner-console-acceptance.md)
- [Stage E start](2026-08-30-bogda-stage-e-start.md)
- [Gate 7 plan](../superpowers/plans/2026-09-01-bogda-gate7-real-shadow.md)
