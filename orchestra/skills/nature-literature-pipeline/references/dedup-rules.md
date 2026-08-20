# Deduplication Rules

## Triple Deduplication

Apply in this order when building candidate pool:

1. **DOI** — canonical identifier, most reliable
2. **arXiv ID** — unique within arXiv namespace
3. **Normalized title** — lowercase, strip punctuation, strip spaces, compare

When duplicates are found, prefer the richer metadata record while preserving all stable links.

## Implementation

```python
seen = set()
unique_papers = []

for paper in candidates:
    keys = []
    if paper.get("doi"):
        keys.append(("doi", paper["doi"].lower()))
    if paper.get("arxiv_id"):
        keys.append(("arxiv", paper["arxiv_id"]))
    if paper.get("title"):
        norm = paper["title"].lower().strip()
        norm = "".join(c for c in norm if c.isalnum())
        keys.append(("title", norm))

    is_dup = any(k in seen for k in keys)
    if not is_dup:
        seen.update(keys)
        unique_papers.append(paper)
    else:
        # Merge metadata: prefer richer record
        ...
```

## Zotero Library Dedup

Before scoring, check each candidate against Zotero library:

```
mcp__zotero__search_library(query="<paper title>")
```

If the paper already exists in Zotero, skip it — it was already delivered in a previous run.
This is the most reliable dedup signal because it reflects what was actually archived.

## Cross-Day Deduplication

Supplement Zotero check with a local dedup index at `D:/MD ideas/20-机器学习/文献/每日推送/_dedup_index.json`:

```json
{
  "seen_ids": ["10.xxxx/...", "2405.12345", ...],
  "last_updated": "2026-07-03"
}
```

Use this as a fast cache — Zotero search is authoritative, the JSON index is the fallback.
