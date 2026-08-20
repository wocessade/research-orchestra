# Source: scanned PDF (OCR required)

The PDF is image-only or has an unreliable text layer. **This skill does not do OCR.**

Tell the user to run **deepseek-vision** first, then paste text back for the `pasted-text` path. Load `static/fragments/source/pasted-text.md` for the rest.

### How to call deepseek-vision (outbound packet)

Do **not** ask DeepSeek to "完整描述这一页 / 请详细描述所有文字与布局". Use short, page- or region-scoped packets:

1. Prefer one page (or one crop: body / figure / table) per call.
2. Outbound example:
   ```
   场景: 扫描 PDF 第 N 页（正文区已裁切，如适用）
   假设: 按阅读顺序 OCR 出可粘贴纯文本；无法确信的字标为 [?]
   请按格式答:
   裁决: PASS | FAIL | UNSURE
   证据: （正文文本；FAIL/UNSURE 时说明模糊/倾斜/裁切原因）
   ```
3. `PASS` → treat evidence text as OCR output for pasted-text. `UNSURE` → tighter crop or same-image follow-up. New page file → **new** DeepSeek chat.
4. Fuzzy figure/table glyphs: separate round with a figure-only crop and a hypothesis about the needed labels/numbers — not a full-page dump.

If the user already has OCR output (e.g. from PaddleOCR or other tools), accept it as pasted-text.

General notes for when OCR output is available:

- Record a confidence level for each block in the source map, and mark low-confidence blocks explicitly in `translation_notes.md` rather than guessing.
- Preserve the original wording where OCR is confident; flag, do not silently "correct", garbled text.
- Be careful with numerals, units, symbols — OCR errors here change meaning. Cross-check against context and mark uncertainty.
- If pages are skewed, rotated, or partly cut off, note the affected pages and translate only what is legible.
