# Zotero Integration Guide

The pipeline uses the `@xevos117/mcp-zotero` MCP server (15 tools) to archive papers.

## Available Tools (pipeline-relevant subset)

| Tool | Use |
|------|-----|
| `search_library` | Check if paper already exists (dedup by title/DOI) |
| `add_items_by_doi` | **Primary**: add paper by DOI — auto-resolves metadata, auto-attaches OA PDF via Unpaywall |
| `add_items` | **Fallback**: add paper with direct metadata when DOI unavailable (arXiv papers) |
| `get_collections` | List existing collections |
| `create_collection` | Create a new collection (e.g. `每日推送`) |
| `get_items_details` | Batch metadata retrieval for multiple items |
| `find_and_attach_pdfs` | Batch OA PDF lookup for items without PDFs |

## Pipeline Archive Flow (per paper, in order)

### Step 1: Dedup check

```
mcp__zotero__search_library(query="<paper title>")
```

- **Found** → skip this paper, record existing key. Log: "已存在 Zotero: <key>"
- **Not found** → proceed to Step 2

If search returns an error, treat as "not found" and proceed — don't block the pipeline.

### Step 2: Ensure collection exists

First, list collections:
```
mcp__zotero__get_collections()
```

Look for `每日推送` in the results. If not found:
```
mcp__zotero__create_collection(name="每日推送")
```

Store the returned collection key. Optionally create a monthly sub-collection:
```
mcp__zotero__create_collection(name="{YYYY-MM}", parent_key="<每日推送的key>")
```

### Step 3: Add paper

**Preferred — DOI available:**
```
mcp__zotero__add_items_by_doi(doi="10.xxxx/...")
```
Returns the item key. Auto-resolves metadata from Crossref. OA PDF auto-attach requires `UNPAYWALL_EMAIL` env var (not currently configured).

**Fallback — arXiv only, no DOI:**
```
mcp__zotero__add_items(items=[{
  "itemType": "journalArticle",
  "title": "Paper Title",
  "creators": [
    {"firstName": "First", "lastName": "Last", "creatorType": "author"}
  ],
  "date": "2024",
  "publicationTitle": "arXiv preprint",
  "DOI": "",
  "url": "https://arxiv.org/abs/XXXX.XXXXX",
  "extra": "arXiv: XXXX.XXXXX",
  "abstractNote": "..."
}])
```

If `add_items_by_doi` fails (network, unknown DOI), fall back to `add_items`.

### Step 4: Attach arXiv PDF (for arXiv papers)

Most pipeline papers come from arXiv. Attach the PDF as a **linked URL** — no file upload needed, Zotero resolves the link at read time:

```
mcp__zotero__add_items(items=[{
  "itemType": "attachment",
  "parentItem": "<parent_item_key>",
  "linkMode": "linked_url",
  "title": "arXiv PDF",
  "url": "https://arxiv.org/pdf/{arxiv_id}.pdf",
  "contentType": "application/pdf"
}])
```

This avoids the complexity of file upload to Zotero Web API (which requires multipart authorization). For arXiv papers, the PDF is always available at this stable URL.

### Step 5: Store returned key

Record the Zotero item key returned in Step 3. This goes into:
- The Obsidian note's `zotero_key` frontmatter field
- The archive confirmation footer in the email digest

### Step 6 (optional): Batch OA PDF

After all 5 papers are added:
```
mcp__zotero__find_and_attach_pdfs(item_keys=["KEY1", "KEY2", ...])
```

Non-blocking — if this fails, papers still have metadata and arXiv linked PDFs in Zotero.

## Error Handling

| Failure | Action |
|---------|--------|
| `search_library` fails | Treat as "not found", proceed to add |
| `get_collections` fails | Skip collection creation, add items directly |
| `add_items_by_doi` fails | Fall back to `add_items` with manual metadata |
| `add_items` fails | Log warning, skip this paper in Zotero but still include in Obsidian + email |
| arXiv PDF attachment fails | Non-blocking, metadata is still stored |
| `find_and_attach_pdfs` fails | Non-blocking, skip silently |

## Dedup Strategy

1. **Pre-search**: `search_library` by title before adding → skip if found
2. **Cross-day**: Zotero library is the authoritative dedup source; `_dedup_index.json` is the fast cache
3. **Zotero desktop**: built-in duplicate detection handles any remaining cases

## Notes

- `UNSAFE_OPERATIONS` defaults to `none` — deletions are blocked, which is correct for pipeline use
- `UNPAYWALL_EMAIL` not configured — OA PDF auto-attach via Unpaywall won't work unless added
- Zotero syncs to desktop client automatically via Web API
- Returned item keys are the bridge between Zotero items and Obsidian notes
