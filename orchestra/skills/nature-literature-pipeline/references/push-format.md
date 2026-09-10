# Email Push Format

Daily literature digest delivered via QQ email (SMTP: 1904134720@qq.com).

## Template

```
📅 {YYYY-MM-DD} 文献日报 | CS/AI Research Daily

━━━━━━━━━━━━━━━━━━━━

🏅 #{N} | {Title}
{Venue}, {Year} | {Authors} | ⭐ {score}/10 | 分流：{A-E tier}
arXiv: {arxiv_id} | DOI: {doi if available}

💡 一句话：{one-line takeaway}

🔬 方法：{model architecture, training approach, dataset, evaluation setup}

📊 关键结果：{specific metrics, benchmarks, comparisons}

🧭 点评：{value to research direction, limitations, whether worth full-text reading}

📎 {arXiv link}

━━━━━━━━━━━━━━━━━━━━

🏅 #{N+1} | ...
```

## Field Guidelines

| Field | Principle |
|-------|-----------|
| 💡 一句话 | 15-second judgment on whether to open the original; must capture core contribution |
| 🔬 方法 | Model family/scale, training method, dataset, benchmarks, baselines |
| 📊 关键结果 | **Extracted from PDF with source page/table anchors**. Specific metrics, benchmark comparisons, ablation numbers. Never vague. |
| 🧭 点评 | Actual value to the research mainline, limitations, full-text recommendation |
| ⭐ 评分 | Coarse-filter score (0-10). Internal six-dimension uses 0-100 with per-dimension cap validation |

All 💡/🔬/📊/🧭 fields come from the Fine Read step (workflow step 4 in SKILL.md) —
Use available tools to read each paper's PDF and extract structured output.
Do NOT populate these fields from abstract alone.

## Email Delivery

Use an available email tool only when explicit authorization covers the recipient and this run (or the saved recurring task). Verify the actual recipient and tool schema; do not assume the sender is the recipient or that a named MCP is installed. Without sending authorization, deliver a reviewable digest draft.

## Archive Confirmation Footer

Append to the digest body after the last paper:

```

━━━━━━━━━━━━━━━━━━━━

📦 归档状态
  Zotero: {N_added} added, {N_skipped} skipped (already in library)
  Obsidian: {N} notes → D:/MD ideas/20-机器学习/文献/每日推送/{YYYY-MM-DD}/
```
