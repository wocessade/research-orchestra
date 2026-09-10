---
name: academic-research-engine
description: >
  科研发动机：RQ/假设生命周期、实验卡与 run 摄入、负结果账本、文献雷达编排、
  写作 handoff（写入 .paper P0/P1 产物）。编排 nature-literature-pipeline /
  nature-reader / nature-weekly-review 与 academic-shared literature_search，
  不重造精读/日推。默认不代跑 GPU。触发词：开 RQ、设计实验、雷达、摄入 run、
  负结果、handoff、research engine、实验登记、文献雷达。
---

# Academic Research Engine — 科研发动机

执行范围与授权见 [共享执行规则](../academic-shared/references/execution-policy.md)；按当前任务读取阶段细则。

**一句话：** 研究状态机 + 编排器 — 生产并登记「可写进论文的 verified 证据」；
`academic-journal` / `academic-thesis` 只消费这些证据。

不替代 novelty 判断与导师决策；不伪造实验结果。

## 与 sibling skills 的边界

| 已有资产 | 引擎怎么用 | 禁止 |
|----------|------------|------|
| `nature-literature-pipeline` | 雷达默认 `ingest` 后端 | 重造 scoring/邮件/Zotero |
| `nature-reader` | Deep Read Bridge；`S/C/F/T` → reads | 重写对照精读流水线 |
| `nature-weekly-review` | 周讨论 → watchlist/reads 队列 | 代用户做批判结论 |
| `academic-shared/literature` | 定向检索 / verify_citations | 第二套 verify |
| P0/P1 contribution / issues / bank | handoff **写出**同构产物 | 平行第二套 ID |
| `academic-journal` / `thesis` | `.research/handoff` 后进 S1/S3/T1 | 复制 gate-chain/evaluate |

共享协议：`../academic-shared/research/schemas.md` + `metrics.schema.json`。

## ID 对齐（强制）

```text
RQ-* → H-* → EXP-* / NEG-* → Ci → ISS-* → CLM-*
```

精读锚点复用 nature-reader 的 `S/C/F/T`。

## 项目落盘

```text
.research/
  program.yaml
  rq/  hypotheses/  radar/  reads/
  experiments/EXP-*/card.md + runs/
  negatives/  handoff/ready_for_writing.md
```

## 意图路由（先读再做）

| 意图 | 首先加载 |
|------|----------|
| 总览 / 状态机 | [references/workflow.md](references/workflow.md) |
| 雷达 / 日推 / 深挖 | [references/radar-routing.md](references/radar-routing.md) |
| RQ / 假设 | [references/rq-hypothesis.md](references/rq-hypothesis.md) |
| 实验卡 / 摄入 | [references/experiment-card.md](references/experiment-card.md) |
| 负结果 | [references/negative-results.md](references/negative-results.md) |
| 写作 handoff | [references/handoff-to-writing.md](references/handoff-to-writing.md) |
| persona / lab_lead | [references/personas.md](references/personas.md) |
| 对抗 claim 核验 | [references/adversarial-claim-check.md](references/adversarial-claim-check.md) |
| deep_synthesize 模式 | [references/deep-synthesize.md](references/deep-synthesize.md)（只进 inbox/reads） |

## 脚本

```bash
# 校验实验卡
py -3 scripts/validate_experiment_card.py .research/experiments/EXP-001/card.md

# 摄入 metrics（schema: academic-shared/research/metrics.schema.json）
py -3 scripts/ingest_run.py runs/metrics.json --research-root .research --paper-dir {paper_dir}

# 同步到 .paper/*（无 verified 时拒绝强数字）
py -3 scripts/handoff_sync.py --research-root .research --paper-dir {paper_dir}
```

## 硬规则

1. **数值只来自 ingest 的 artifacts** — 禁止编造 metrics。
2. **默认人在环** — RQ 激活、成功/失败标准、handoff 均需用户确认。
3. **默认不代跑 GPU** — `program.yaml` compute mode 默认 `human_in_loop`。
4. **handoff 禁 planned 强数字** — 与 P1 results-backfill 一致。
5. **证据不足则 abstain** — 尤其 deep_synthesize / adversarial check。

## 用户说明书

完整说明：[USER-GUIDE.md](USER-GUIDE.md) （同内容：[说明书.md](说明书.md)）

## 快速开始

```
/pick academic-research-engine
```

自然语言示例：「初始化 .research」「雷达本周」「开 RQ-001」「设计 EXP-003」「摄入这次 run」「准备手稿 handoff」。

复制模板：

- `templates/program.yaml` → `.research/program.yaml`
- `templates/rq.md` / `hypothesis.md` / `experiment-card.md` / `negative.md`
- `templates/watchlist.yaml` → `.research/radar/watchlist.yaml`
