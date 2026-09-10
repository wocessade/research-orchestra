## WEEKLY_DATA JSON Schema

```json
{
  "meta": {
    "year": 2026, "week": 27,
    "monday": "2026-06-30", "sunday": "2026-07-06"
  },
  "stats": {
    "total": 5, "avg_score": 7.3, "median_score": 7.5, "A_count": 2,
    "score_distribution": {...},
    "classification_distribution": {...},
    "tag_frequency": [...]
  },
  "last_week": {
    "total": 3, "avg_score": 6.8
  },
  "papers": [
    {
      "title": "...", "authors": "...", "year": 2026, "venue": "arXiv",
      "arxiv": "2607.xxxxx", "score": 8.0,
      "classification": "A_核心主线",
      "tags": ["标签1", "标签2"],
      "sections": {
        "核心主张": "...", "方法": "...", "关键发现": "...",
        "批判": "...", "Connection to Research": "...", "下一步": "..."
      },
      "discussion": "用户对这篇论文的判断和评价",
      "action": "精读"
    }
  ],
  "cross_paper": {
    "method_comparison": [...],
    "metrics_comparison": [...],
    "user_insights": "用户发现的跨论文联系"
  },
  "theme_clusters": "用户的主题分析文字",
  "critique_synthesis": {
    "code": [...], "data": [...], "generalization": [...],
    "scale": [...], "theory": [...], "other": [...]
  },
  "generated_at": "2026-07-03T23:00:00"
}
```


## 注入与输出

从本技能目录读取 `../templates/weekly-report.html`；不要假定安装在用户主目录的 `.claude/skills`。将 JSON 注入 `WEEKLY_DATA_PLACEHOLDER`；嵌入 script 前将 `<` 转义为 `\u003c`。主题使用用户选择；未指定时使用模板默认主题。

输出 `weekly-report.html` 和 `data.json` 到用户目录，默认 `D:/MD ideas/20-机器学习/文献/每周总结/{ISO年}-W{周:02d}/`。上周目录由当前周周一减 7 天后重新计算 ISO 年/周，不使用 `week - 1`。

`discussion`、`user_insights`、`theme_clusters` 和 `critique_synthesis` 中的用户观点来自已确认材料；未确认项标为待补充。事实对比与模型建议应明确标注来源，不能冒充用户观点。
