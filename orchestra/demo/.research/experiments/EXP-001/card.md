---
id: EXP-001
hypothesis_ids: [H-001]
contribution_id: null
rq_id: RQ-001
status: designed
failure_loop: null
tournament_id: null
created: 2026-08-19
updated: 2026-08-19
compute_budget:
  kind: none
  estimate: "≈2 DeepSeek API calls"
  seeds: []
---

# EXP-001 — LLM 抽取执行器对照（single-call vs dsh multi-step）

## Bound hypothesis / contribution

- H: H-001
- Future Ci: (none)

H-001（管线验证性假设，非科研结论）：同一抽取任务（demo 固定文本 extract_text.txt）在两种执行方式下——ctl 单次 LLM API 调用、trt dsh 多步 agent——均能产出符合 metrics.schema.json 的 metrics.json，并经 ingest_run.py 入账。本实验验证「实验卡 → 无头执行 → 入账」管线闭环本身，不比较抽取质量、不产生科研结论。

## Design

| Field | Value |
|-------|-------|
| Dataset / corpus | demo 固定文本 material/extract_text.txt（约 150 字虚构研究公告，含实体/数值/关系字段） |
| Baseline(s) | ctl 臂：单次 LLM API 调用（extract_single.py，deepseek-chat，temperature 0，response_format json_object） |
| Method under test | trt 臂：dsh 多步 agent（Broker dsh executor：规划字段 → 逐字段抽取 → 核对 gold 格式 → 写 result.json → 共享评分） |
| Metrics | 字段级精确匹配正确率 accuracy = fields_correct / fields_total（gold.json 为金标准，两臂共用 score.py） |
| Ablations | none |
| Controls | 两臂共用 score.py、gold.json、extract_text.txt；评分前值做 strip 空白归一化后精确比对 |

## Success criteria (freeze before run)

1. ctl 臂产出符合 metrics.schema.json 的 metrics.json（必填 run_id/exp_id/status/metrics），并经 ingest_run.py 入账（卡 Run log 出现对应 run 行）。
2. trt 臂产出符合 metrics.schema.json 的 metrics.json，并经 ingest_run.py 入账。
3. 两臂 metrics.json 的 exp_id 均与卡 id（EXP-001）一致。

## Failure criteria (freeze before run)

1. 任一臂未能产出合规 metrics.json（缺必填键或 engine schema 校验失败）。
2. 任一臂 ingest 入账失败（含 exp_id 与卡 id 不一致的 HARD 退出）。

## Run log

| run_id | status | metrics path | meets_success | notes |
|--------|--------|--------------|---------------|-------|
| | | | | |

## Failure-loop notes (M4)

If failed: choose `tune` (hyperparams) → `redesign` (protocol) → `rehypothesis` (open NEG + RQ changelog). Do not post-hoc rewrite success criteria.
本卡为管线 demo：执行失败时优先修复执行链路（Commands 段 / 任务文件 / 执行器注入），不重写 Success criteria。

## Artifacts

- Code commit: feat: demo EXP-001 card - LLM extraction executor comparison（orchestra/demo/）
- Config: material/gold.json（金标准字段，评分判定依据）、score.py（共享评分，两臂对照公平性来源）

## Commands

命令用相对路径，执行体须先 cd 到 demo 目录。ctl 臂：单次调用抽取后评分；trt 臂：多步抽取由 dsh 执行器在评分前完成并写 result.json，此处只跑共享评分。

# arm: ctl
```bash
python3 extract_single.py --text material/extract_text.txt --gold material/gold.json --out result.json
python3 score.py --gold material/gold.json --result result.json --exp-id EXP-001 --out $OUTDIR/metrics.json
```

# arm: trt
```bash
python3 score.py --gold material/gold.json --result result.json --exp-id EXP-001 --out $OUTDIR/metrics.json
```
