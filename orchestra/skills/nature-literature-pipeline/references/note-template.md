# Literature Note Template (v2)

Standardized template for Obsidian literature notes. Used for pipeline daily archive.

## YAML Frontmatter

```yaml
---
title: "Original English Title"
authors: "Last, F.; Last, F."
year: 2024
venue: "Conference/Journal Name"
arxiv: "2405.12345"
doi: "10.xxxx/..."
score: 8.5
classification: "A_核心主线"
zotero_key: "ABC123"
tags: [关键词1, 关键词2, 关键词3]
date_read: 2026-07-03
---
```

### Field Rules

| Field | Format | Example |
|-------|--------|---------|
| `title` | Original English, double-quoted | `"Attention Is All You Need"` |
| `authors` | `Last, F.; Last, F.` — semicolon-separated, >3 use `et al.` | `"Vaswani, A.; Shazeer, N.; Parmar, N.; et al."` |
| `year` | 4-digit integer, no quotes | `2017` |
| `venue` | Full name, double-quoted | `"NeurIPS"` |
| `arxiv` | arXiv ID | `"1706.03762"` |
| `doi` | Full DOI starting with `10.` | `"10.xxxx/..."` |
| `score` | Float, 0-10 | `8.5` |
| `classification` | One of: `A_核心主线`, `B_章节支撑`, `C_工程背景`, `D_方法借鉴`, `E_暂存低优先` | `"A_核心主线"` |
| `zotero_key` | Zotero item key from `add_items_by_doi` or `add_items` | Returned by MCP tool after adding |
| `tags` | YAML list, 3-5 Chinese keywords | `[注意力机制, Transformer, 序列建模]` |
| `date_read` | ISO date | `2026-07-03` |

## Body Structure (6 sections)

Sections 核心主张/方法/关键发现/批判 are populated by the Fine Read step
(Haiku subagent reads PDF). See SKILL.md §④ for the spawn pattern.

```markdown
## 核心主张
[1-3 sentences. Evidence strength: 成熟共识 / 学界共识 / 争议 / 推测]

## 方法
[Model architecture, training approach, dataset, key techniques]

## 关键发现
[Bullet points of key results/metrics/benchmarks]

## 批判
[Strengths, weaknesses, relevance gaps, evidence reliability]

## Connection to Research
[How this connects to the user's research direction]

## 下一步
[Actionable: read which section, follow up which reference, try which idea]
```

## File Naming

Format: `{FirstAuthorLast}{Year}_{关键词}.md`

Examples:
- `Vaswani2017_注意力机制_Transformer.md`
- `Brown2020_语言模型_少样本学习.md`

## Output Location

Pipeline daily archive: `D:/MD ideas/20-机器学习/文献/每日推送/{YYYY-MM-DD}/`
