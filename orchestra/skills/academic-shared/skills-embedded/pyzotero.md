# Pyzotero (Embedded)

**Source:** `pyzotero` | **Snapshot:** 2026-06-06
**Pipeline usage:** S2, S6 — Zotero library integration

## Purpose
Interface with Zotero reference management library via pyzotero Python library.
Requires: Zotero API key + library ID.

## Usage
```python
from pyzotero import zotero
zot = zotero.Zotero(library_id, library_type, api_key)
items = zot.top_items(limit=100)
```

## Capabilities
- Read items from Zotero library
- Search by tag, collection, or date
- Add/update items
- Export in various formats (BibTeX, RIS, etc.)
