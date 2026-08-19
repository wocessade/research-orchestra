# T-nightly-radar-fetch
executor: dsh
net: required
result: T-{{DATE}}-nightly-radar-10-fetch
timeout: 1200
mode: execute
detail: brief
required_outputs: papers_all.json, fetch_summary.json
json_outputs: papers_all.json, fetch_summary.json
validator: radar-fetch
---
你负责文献雷达的抓取阶段。只构建候选论文集，不做评分、排名、摘要或邮件发送。

## 数据源

使用 arXiv API 抓取最近 24 小时提交的论文：

- `cat:cs.CL` 最新 30 篇
- `cat:cs.LG` 最新 30 篇
- 接口：`https://export.arxiv.org/api/query`
- 参数：`max_results=30`、`sortBy=submittedDate`、`sortOrder=descending`

如果同一 arXiv ID 出现在多个分类，只保留一条记录，并合并分类。

## 输出

在工作目录写入 `papers_all.json`，内容为 JSON 数组。每项必须包含：

```json
{
  "title": "论文标题",
  "arxiv_id": "不含版本号的 arXiv ID",
  "url": "abs 页面 URL",
  "categories": ["cs.CL"],
  "submitted_at": "ISO 8601 时间",
  "authors": ["作者"],
  "abstract": "原始摘要"
}
```

同时写入 `fetch_summary.json`：

```json
{
  "date": "{{DATE}}",
  "source_counts": {"cs.CL": 0, "cs.LG": 0},
  "deduplicated_count": 0,
  "fetched_at": "ISO 8601 时间"
}
```

## 验收

使用 Python 读取两个 JSON 文件并验证：

- 均为合法 JSON；
- `papers_all.json` 中 arXiv ID 唯一；
- `deduplicated_count` 等于数组长度；
- 每项必填字段类型正确；
- 不允许凭空补全抓取不到的信息。

最后只报告抓取数量、去重数量和产物路径。
