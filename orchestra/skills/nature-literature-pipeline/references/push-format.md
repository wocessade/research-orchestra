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
| 📊 关键结果 | **Populated by Haiku subagent from PDF**. Specific metrics, benchmark comparisons, ablation numbers. Never vague. |
| 🧭 点评 | Actual value to the research mainline, limitations, full-text recommendation |
| ⭐ 评分 | Coarse-filter score (0-10). Internal six-dimension uses 0-100 with per-dimension cap validation |

All 💡/🔬/📊/🧭 fields come from the Fine Read step (④ in SKILL.md) —
Haiku subagents read each paper's PDF and extract structured output.
Do NOT populate these fields from abstract alone.

## Email Delivery

Use the email MCP server (`mcp__email__send_email`):

```
mcp__email__send_email(
  subject="📅 {YYYY-MM-DD} 文献日报 | CS/AI Research Daily",
  body="<formatted digest per template above>"
)
```

The email MCP is configured in `mcp.json` and uses QQ SMTP (1904134720@qq.com).
Default `to` address is the sender itself — no need to specify.

## Archive Confirmation Footer

Append to the digest body after the last paper:

```

━━━━━━━━━━━━━━━━━━━━

📦 归档状态
  Zotero: {N_added} added, {N_skipped} skipped (already in library)
  Obsidian: {N} notes → D:/MD ideas/20-机器学习/文献/每日推送/{YYYY-MM-DD}/
```
