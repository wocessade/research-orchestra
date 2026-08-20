---
name: nature-literature-pipeline
description: Automated daily literature discovery pipeline. Multi-source search (arXiv) → six-dimension scoring → formatted email digest → Zotero + Obsidian archival. Trigger on "文献推送", "每日文献", "literature pipeline", "arXiv 推送", "daily paper digest", "配置文献推送".
---

# Nature Literature Pipeline

A structured engine that searches, scores, classifies, and delivers research papers daily.

## What It Does

```
Cron (Claude Code CronCreate, daily 08:30 BJT)
  │
  ├── ① SEARCH (30 candidates)
  │   arXiv API (primary) + Semantic Scholar (supplementary metadata)
  │
  ├── ② DEDUP (DOI → arXiv ID → normalized title)
  │   Cross-reference Zotero library + local _dedup_index.json
  │
  ├── ③ COARSE FILTER (30 → 5)
  │   Six-dimension scoring per references/scoring-system.md
  │
  ├── ④ FINE READ (5 PDFs, Haiku subagents)
  │   Download PDF → extract experiment/results sections → parse tables
  │   Spawn 5 Haiku agents in parallel (one per paper)
  │
  ├── ⑤ DELIVER
  │   Formatted digest via mcp__email__send_email
  │
  └── ⑥ ARCHIVE
      ├── Zotero: add_items (or add_items_by_doi) → linked_url arXiv PDF
      └── Obsidian: write YAML frontmatter notes with zotero_key + key results
          to D:/MD ideas/20-机器学习/文献/每日推送/{YYYY-MM-DD}/
```

## Fine Read Protocol (④ in detail)

After scoring selects the TOP 5, download each PDF and extract key results
using Haiku subagents. This is the default behavior — no user confirmation needed.

### Spawn pattern

For each of the 5 papers, spawn one Haiku agent in parallel:

```
Agent(
  subagent_type="haiku",
  description="Read paper: <arXiv ID>",
  prompt="
    Download https://arxiv.org/pdf/<arxiv_id>.pdf
    Extract:
    1. Core contribution (1 sentence)
    2. Method summary (2-3 sentences)
    3. **All quantitative results**: every table with metrics, every
       comparison number, every ablation result. Copy exact numbers.
    4. Key limitations mentioned by authors
    Output in Chinese, keep numbers in original format.
    Be concise — under 400 words total.
  "
)
```

### Output format expected from Haiku

```
## 核心贡献
[一句话]

## 方法
[2-3句]

## 关键结果
[逐表列出所有定量结果，保留原始数字]

## 局限
[作者提及的局限，若无则写"未提及"]
```

### Merge

After all 5 agents return, merge their output into:
- **Email digest**: the 📊关键结果 field
- **Obsidian notes**: the 关键发现 + 批判 sections

Non-blocking: if a Haiku agent fails or times out (>30s), mark that paper's
key results as "PDF reading failed, check manually" and proceed.

## Archive Protocol (⑥ in detail)

For each of the TOP 5 papers, in order:

**Zotero — Step A: Dedup check**
```
search_library(query="<paper title>")
```
If found → skip Zotero add, note existing key. If not found → proceed.

**Zotero — Step B: Ensure collection exists**
```
get_collections()
```
If no `每日推送` collection → `create_collection(name="每日推送")`.

**Zotero — Step C: Add paper**
- DOI available → `add_items_by_doi(doi="10.xxxx/...")` (auto-resolves metadata + OA PDF)
- arXiv only → `add_items(items=[{...}])` with full metadata

**Zotero — Step D: Record key**
Store the returned item key for cross-referencing in the Obsidian note's `zotero_key` field.

**Obsidian — Step E: Write note**
Create `{FirstAuthorLast}{Year}_{关键词}.md` with YAML frontmatter including `zotero_key`, to `D:/MD ideas/20-机器学习/文献/每日推送/{YYYY-MM-DD}/`.

See `references/zotero-integration.md` for full tool signatures and error handling.

## Two Modes

| Mode | Trigger | What Happens |
|------|---------|--------------|
| **Config** | "配置文献推送" | User sets keywords, weights, delivery email, archive path. Creates config file. |
| **Daily run** | Cron or manual "跑一次文献推送" | Full pipeline: search → score → deliver → archive |

## Quick Start

```
我的研究方向是 [计算机视觉/大语言模型/...]，关键词: [transformer, attention, ...]
```

The agent will configure keywords, weights, and archive path. Then:

```
设置每日文献推送，每天早上8:30北京时间，检索30篇，推送TOP 5
```

## Archive Strategy

| Store | What | How |
|-------|------|-----|
| **Zotero** | Full metadata (title, authors, DOI, arXiv ID, abstract) | `@xevos117/mcp-zotero` MCP tools |
| **Obsidian** | Literature notes with scores, one-liner, methods, key results, commentary | Write to `D:/MD ideas/20-机器学习/文献/每日推送/` |

## Built-in Safeguards

- **Score validation**: Each dimension capped, total recalculated
- **Deduplication**: DOI / arXiv ID / normalized title
- **Read-only archive**: Pipeline writes to `每日推送/` directory only; never modifies existing notes without user approval
- **Cron locality**: Claude Code CronCreate is process-local — the Claude session must be running for the cron to fire

## References

| Reference | Purpose |
|-----------|---------|
| `references/scoring-system.md` | Six-dimension scoring rubric with weights, caps, and rules |
| `references/push-format.md` | Email digest message template with field guidelines |
| `references/note-template.md` | Standardized Obsidian literature note format with YAML frontmatter |
| `references/cron-setup.md` | Claude Code CronCreate guide and verification checklist |
| `references/dedup-rules.md` | Triple deduplication rules |
| `references/review-compilation.md` | Manual review compilation workflow (on-demand) |
| `references/zotero-integration.md` | Concrete Zotero MCP tool calls, error handling, and archive flow |
| `templates/config-template.yaml` | User configuration template |
