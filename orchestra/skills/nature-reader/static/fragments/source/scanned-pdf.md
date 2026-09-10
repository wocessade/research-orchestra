# Source: scanned PDF (OCR required)

Use available OCR or vision tools for image-only PDFs. Existing OCR text is also accepted. A missing named provider is not a blocker when another tool can preserve the output contract.

1. Process by page or region, keeping source page/region anchors for the reader's source map.
2. Extract text in reading order; mark uncertain glyphs as `[?]`. Check numerals, units and symbols against the page image.
3. Read figure/table crops separately when labels need higher resolution. Record incomplete or clipped regions in `translation_notes.md`.
4. Feed extracted text through the [pasted-text route](pasted-text.md), retaining original PDF page/region anchors.

An external OCR/vision provider, including deepseek-vision, is optional and must fit the user's data-transfer authorization. If no available tool can read the source, request the missing text or a legible source and continue readable pages. Do not invent unreadable content.
