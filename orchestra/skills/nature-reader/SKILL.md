---
name: nature-reader
description: Build full-paper Chinese-English side-by-side, figure/table-aware, source-grounded Markdown readers from PDF, DOI, arXiv, publisher HTML, or pasted text. Trigger on "读论文", "精读", "全文翻译", "中英对照", "paper reader", "帮我读这篇文章", "translate this paper".
---

# Full-Paper Markdown Reader

执行范围与授权见 [共享执行规则](../academic-shared/references/execution-policy.md)；按当前任务读取阶段细则。

This skill is split into two layers:
- **Static layer** (`static/`): versioned, reusable content fragments (core principles, reading workflow, output contract, per-source-format extraction guidance).
- **Dynamic layer** (this file + `manifest.yaml`): detects the request's source format and loads only the fragments needed.

Do not apply the reading logic from memory. Always load fragments from disk as described below.

## Routing protocol

### 1. Load the manifest and the core layer

Read [manifest.yaml](manifest.yaml) and every file listed under `always_load`.

### 2. Detect the source format

Decide the `source_format` value:
- `pdf-text` — selectable-text PDF. Default.
- `scanned-pdf` — image-only or OCR-required PDF.
- `html` — publisher or preprint HTML page.
- `doi-arxiv` — a bare DOI or arXiv link that must be resolved first.
- `pasted-text` — pasted prose or notes with no retrievable original layout.

State the detected value in one short line before processing, so the user can correct you.

### 3. Load the matching fragment(s)

Read only the file for the detected `source_format`. Do not read every fragment.

### 4. Build the reader

Apply loaded fragments in priority order:
1. Core principles — bilingual reader by default, translate for meaning, never degrade to a summary.
2. Source-format fragment — how to extract text, figures, and tables.
3. Reading workflow — six-step source-map-first process.
4. Output contract — required files and verification checklist.

Build the Terminology Ledger as you translate; it becomes the `paper.md` recurring-term table and the `source_map.json` glossary.

Output to `D:/MD ideas/20-机器学习/文献/<paper_slug>/`.

If constraints prevent full processing, create a draft reader and label missing pages, figures, or low-confidence crops in `translation_notes.md`. Do not switch to summary mode.

### 5. Reach for references only when needed

- Cropping figures/tables and placement → `references/figure-extraction.md`
- Exact field schemas for `paper.md` / `source_map.json` → `references/output-spec.md`
- Answering follow-up questions with source citations → `references/grounding-rules.md`

## Scanned sources

Use available OCR or vision tools for scanned pages, preserving page/region anchors and marking uncertain text. `deepseek-vision` is optional when available and authorized. See [scanned-PDF guidance](static/fragments/source/scanned-pdf.md).
