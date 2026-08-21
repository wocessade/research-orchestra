# 科研发动机说明书（Academic Research Engine）

> 联邦总说明（文献·发动机·写作·LaTeX/图）：D:\\MD ideas\\学术技能组说明书.md

> 适用版本：`academic-research-engine` v1.0  
> 安装：`~/.claude/skills/academic-research-engine/`  
> 共享协议：`~/.claude/skills/academic-shared/research/`  
> 面向用户；Agent 细节见 `references/*.md`。

---


## 1. 它是什么 / 不是什么

### 是什么

**科研发动机**是「研究状态机 + 编排器」技能。它帮你：

1. 把文献雷达、精读、RQ、假设、实验、负结果登记在 `.research/`；
2. 用同一套 ID 串起「读过的证据 → 跑出的结果 → 可写进论文的 claim」；
3. 证据足够时 **handoff** 给写作技能（`academic-journal` / `academic-thesis` / `academic-latex`）。

一句话：**制造并登记 verified 证据**；写作技能只负责把它们写成稿。

### 不是什么

| 误解 | 实际 |
|------|------|
| 一键顶刊 | 不替代 novelty与导师决策 |
| 替代 nature-reader/日推 | 只调用，不重造 |
| 默认代跑 GPU | 默认 `human_in_loop` |
| 编造实验数字 | **禁止**；只来自 `metrics.json` |
| Deep Research=结果 | `deep_synthesize` 只进 inbox/reads |


## 2. 在学术技能组中的位置

```text
nature-* / literature_search / agent-reach
        -> .research/ (RQ H EXP NEG)
        -> handoff -> .paper/
        -> academic-journal / thesis / latex
```

| 技能 | 关系 |
|------|------|
| nature-literature-pipeline | 雷达 ingest |
| nature-reader | Deep Read Bridge |
| nature-weekly-review | 周讨论回写队列 |
| academic-shared/literature | 定向检索/引用核验 |
| P0/P1 | handoff 写出 `.paper/*` |
| journal/thesis | `.research/handoff` 预载 |


## 3. 怎么启动

```text
/pick academic-research-engine
```

自然语言：初始化 .research、雷达本周、开 RQ、设计 EXP、摄入 run、负结果、准备 handoff、组会、深度综述、对抗核验。

### 首次使用

1. 初始化 `.research/`
2. 填 `program.yaml`
3. 配 `watchlist.yaml`
4. RQ-001 → H-001 → EXP-001（先冻成败标准）
5. 跑实验 → metrics.json → ingest
6. handoff_sync → journal/thesis


## 4. 目录结构

```text
.research/
  program.yaml
  rq/  hypotheses/  radar/inbox/  reads/
  experiments/EXP-*/card.md + runs/*/metrics.json
  negatives/  handoff/ready_for_writing.md
```

模板：`templates/`。多项目：共享 `.research/` + 多个 `{paper_dir}/.paper/`。


## 5. ID 对齐

```text
RQ-* → H-* → EXP-*/NEG-* → Ci → ISS-* → CLM-*
```

精读锚点：nature-reader `S/C/F/T`。见 `academic-shared/research/schemas.md`。


## 6. 人格与算力

`persona`: explorer | focused_paper | multi_project | lab_lead  
`compute_budget.mode`: human_in_loop（默认）| ci_cpu | optional_gpu  
`active_rq` 必须在 EXP 前确认。见 `references/personas.md`。


## 7. 端到端工作流

**A 探索** 雷达→精读桥→可选对抗核验→RQ/H（不写正文）  
**B 收敛** EXP 卡+冻结成败标准+validate  
**C 出数** 人/CI 跑→metrics→ingest；失败 tune/redesign/rehypothesis+NEG  
**D 负结果** 账本  
**E 成稿** handoff_sync→journal/thesis P0/P1  


## 8. 六大子系统

| 子系统 | 文档 |
|--------|------|
| Radar | radar-routing.md |
| Deep Read | templates/read-bridge.md |
| RQ/H | rq-hypothesis.md |
| EXP | experiment-card.md |
| NEG | negative-results.md |
| Handoff | handoff-to-writing.md |

Radar：ingest / directed_search / community / weekly / deep_synthesize（仅文献侧）。


## 9. 脚本

```bash
py -3 academic-research-engine/scripts/validate_experiment_card.py .research/experiments/EXP-001/card.md

py -3 academic-research-engine/scripts/ingest_run.py path/to/metrics.json --research-root .research --paper-dir {paper_dir} --open-neg-on-fail

py -3 academic-research-engine/scripts/handoff_sync.py --research-root .research --paper-dir {paper_dir} --module academic-journal
```

必须 `pip install jsonschema`；schema 文件缺失或未安装时 ingest 失败。


## 10. metrics.json

Schema：`academic-shared/research/metrics.schema.json`  
必填：run_id, exp_id, status, metrics。

```json
{
  "run_id": "20260727-seed0",
  "exp_id": "EXP-001",
  "hypothesis_ids": ["H-001"],
  "status": "completed",
  "metrics": {"accuracy": 0.812},
  "meets_success_criteria": true
}
```


## 11. 与写作咬合

探索不写正文 → 收敛可起草贡献 → verified 后强结论 → NEG 改 Ci → handoff 走 journal/thesis。


## 12. 硬规则

1. 不伪造  2. 人在环  3. 不默认代跑 GPU  4. 禁 planned 强数字  5. abstain  6. 不重造 nature-*  7. 禁事后改成功标准


## 13. FAQ

- Deep Research？→ 可进 inbox，不当 Results。
- 只写综述？→ 雷达+精读+RQ，勿宣称定量结果。
- 学位论文？→ handoff 到 thesis。
- 实验室？→ lab_lead。
- Overleaf？→ 状态在 `.research/`，paper_dir 本地同步。


## 14. 文件索引

`SKILL.md` · `USER-GUIDE.md` / `说明书.md` · `manifest.yaml` · `references/*` · `templates/*` · `scripts/*.py` · `../academic-shared/research/`


## 15. 实验前清单

- [ ] active_rq 已确认
- [ ] 成败标准已冻结 + validate
- [ ] 真实 metrics + ingest
- [ ] 失败已记 NEG
- [ ] handoff + user_confirmed: true

---

*协议变更以 schemas.md 与脚本 --help 为准。*
