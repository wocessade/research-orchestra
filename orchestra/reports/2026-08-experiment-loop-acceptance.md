# Subsystem 2 实验管线闭环验收报告（2026-08-19）

> 权威约定：`docs/superpowers/plans/2026-08-19-subsystem-2-experiment-loop.md` Task 5。
> 数字纪律（engine 硬规则）：本报告所有数值均引用 artifact 路径，全文无脱离 artifact 的手抄数字。

## 验收项

| 项 | 结果 | 证据 |
|---|---|---|
| EXP-001 卡通过 engine validate | 通过 | ingest 内嵌 validate 输出 `OK: card.md status=designed hyps=['H-001'] (0 soft)`；卡 FM `status` 仍为 designed（engine 不自动改 status） |
| ctl 臂（shell 单次 LLM 调用）执行 | done | `orchestra/logs/broker.log`：`task T-20260819-ctl-single -> done`；`results/T-20260819-ctl-single/attempt-1/state.json` 的 `status`=done |
| trt 臂（dsh 多步 agent）执行 | done | `orchestra/logs/broker.log`：`task T-20260819-trt-dsh -> done`；`results/T-20260819-trt-dsh/attempt-1/state.json` 的 `status`=done |
| 两臂 metrics.json 合规（四键 + exp_id=EXP-001） | 通过 | ingest 前人工核验：两臂 metrics.json 均含 `run_id`/`exp_id`/`status`/`metrics` 四键，`exp_id`==EXP-001，`metrics` 内含 `fields_total`/`fields_correct`/`accuracy`（Task 5 Step 2 输出） |
| 两臂经 run_card.py ingest 入账 | 通过 | 两次 ingest 均 exit 0 并输出 `OK: ingested <run_id> → EXP-001`；卡 Run log 两行；`demo/.research/experiments/EXP-001/runs/` 两份 metrics.json |
| 数字无手抄 | 通过 | 本报告所有数值均引用 `demo/.research/experiments/EXP-001/runs/<run_id>/metrics.json` 或 `results/T-20260819-*/attempt-1/state.json` 路径 |

## 对照结果（仅管线事实，非科研结论）

- ctl 臂 accuracy：`demo/.research/experiments/EXP-001/runs/run-20260819-100117/metrics.json` 的 `metrics.accuracy` = 0.8333（同文件 `metrics.fields_correct`/`metrics.fields_total` = 5/6）
- trt 臂 accuracy：`demo/.research/experiments/EXP-001/runs/run-20260819-100135/metrics.json` 的 `metrics.accuracy` = 1.0（同文件 `metrics.fields_correct`/`metrics.fields_total` = 6/6）
- 执行方式差异（均为 attempt-1）：ctl = shell 单次 API 调用，耗时见 `results/T-20260819-ctl-single/attempt-1/state.json` 的 `elapsed_s` = 1.6；trt = dsh 多步 agent，耗时见 `results/T-20260819-trt-dsh/attempt-1/state.json` 的 `elapsed_s` = 23.8
- 结论仅限：两种执行方式（shell 单次调用 / dsh 多步 agent）均可产出合规 metrics.json 并经 `run_card.py ingest` 可靠入账；**不比较模型质量、不产科研结论**（Success criteria 冻结为「两臂均可产出合规 metrics.json 并入账」，与计划一致）

## 遗留

- dsh 臂产出路径在 attempt-1 内：trt 的 metrics.json 位于 `results/T-20260819-trt-dsh/attempt-1/metrics.json`，而 ctl 臂在任务根目录 `results/T-20260819-ctl-single/metrics.json`。ingest 与卡 Run log 已如实记录各自路径，路径差异对入账无影响；是否需在 Broker/dsh prompt 注入层统一 outdir 位置留待总 spec 复盘，本 mission 不修改 broker（与计划风险预案一致）。
- 远端拉回的 `results/`、`logs/` 中除两臂外还有其它任务产物（如 `T-20260819-usb-smoke`、`T-20260819-nightly-radar` 等，为 sync_pull 全量拉回的正常现象），均未入账、未纳入本验收范围。
- 方法学不对称（哨兵审计 LOW）：trt 臂任务 prompt 向 dsh agent 暴露了含金标准值的 gold.json，而 ctl 臂（extract_single.py）只取字段名、值不进 prompt——两臂 accuracy 不可作质量对比；本 mission 成功标准冻结为管线入账、报告不产科研结论，不破坏验收。未来复用该模式时给 agent 只提供字段名文件。
- 4B demo 目录的 ctl 中间产物 result_ctl.json 已清理（哨兵审计后）；未来重跑 ctl 臂需先清理该文件或把 --out 指向 result 目录。

## 复查结论

reviewed: ok（2026-08-19，CC 复查：本报告所有数字已逐项追溯 ingest artifact 实测一致；哨兵审计独立复核实测一致，无手抄数字。）
