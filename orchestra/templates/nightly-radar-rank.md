# T-nightly-radar-rank
executor: dsh
net: required
result: T-{{DATE}}-nightly-radar-20-rank
timeout: 3600
depends_on: T-{{DATE}}-nightly-radar-10-fetch
mode: audit
detail: deep
required_outputs: scored_papers.json, ranking_summary.json
json_outputs: scored_papers.json, ranking_summary.json
validator: radar-rank
---
你负责文献雷达的评估阶段。只评估候选论文，不抓取、不生成日报、不发送邮件。

## 输入

从以下目录中选择数字最大的 `attempt-N`，读取其中的 `papers_all.json`：

`{{RESULTS_ROOT}}/T-{{DATE}}-nightly-radar-10-fetch/`

读取后先验证文件存在、JSON 合法且数组非空，并对 `papers_all.json` 的原始字节计算小写
SHA-256。验证失败则明确报错并停止，不生成部分排名。

## 评估方法

逐篇评估以下维度：

1. `topic`，0–40：与大模型、Agent、多模态、信息抽取、舆情分析的相关度
2. `method`，0–25：摘要中可见的方法设计、训练方案和评估信号
3. `applied`，0–20：代码、基准、数据集及落地价值
4. `archival`，0–15：长期参考和基础性价值
5. `novelty`，0–10：相对候选池的新颖性，仅用于探索槽位，不计入 `total`

`total` 仅等于前四项之和。作者名气、机构声望、引用量和数据库来源不得进入总分；新论文窗口中这些信号会形成不公平的来源先验。只把可验证的同行评审、代码和数据集状态写入 `quality_signals`，取值为 `yes|no|unknown`。

在形成判断前，同时记录：

- 支持评分的具体证据；
- 可能削弱该评分的反证；
- 当前输入缺失的信息；
- `confidence`，范围 0.0–1.0。

## 输出

在工作目录写入 `scored_papers.json`，保留全部候选。每项结构：

```json
{
  "title": "论文标题",
  "arxiv_id": "arXiv ID",
  "url": "abs 页面 URL",
  "categories": ["cs.CL"],
  "abstract": "原始摘要",
  "scores": {
    "topic": 0,
    "method": 0,
    "applied": 0,
    "archival": 0,
    "novelty": 0
  },
  "total": 0,
  "quality_signals": {
    "peer_reviewed": "unknown",
    "code_available": "unknown",
    "dataset_available": "unknown"
  },
  "evidence": ["支持判断的事实"],
  "counter_evidence": ["削弱判断的事实"],
  "unknowns": ["缺失信息"],
  "confidence": 0.0,
  "rationale": "完整但不重复字段内容的判断说明"
}
```

同时写入 `ranking_summary.json`，其中 `candidate_count` 是候选数量，`eligible_count`
是通过 `topic >= 10` 的数量，`input_count` 是上游数组长度，`input_sha256` 是读取的
`papers_all.json` 原始字节 SHA-256，并记录各评分维度的最小值和最大值。

## 验收

使用 Python 验证：

- 输出条目数与输入一致，arXiv ID 一一对应；
- `input_count`、arXiv ID 集合和 `input_sha256` 与所读上游文件闭环一致；
- 各维分数不越界；
- `total` 严格等于 `topic + method + applied + archival`；
- `confidence` 位于 0.0–1.0；
- 未知信息保留为 `unknowns`，不能伪造成确定事实。

最后只报告评估数量、通过主题门槛的数量和产物路径。
