# Reading workflow

Run these six steps for any paper-reading job.

## 1. Identify the source and paper type

The source-format fragment covers how to extract from the specific input. Also identify the paper type:
- discovery or mechanism paper
- methods or algorithm paper
- resource or dataset paper
- conference paper
- review or perspective

## 2. Build a full-document source map before translating

Process the entire document. Do not stop at the abstract or first few pages unless the user explicitly asks for a preview.

Create stable IDs for source blocks:
- `S001`, `S002`, ... for body text
- `C001`, `C002`, ... for captions
- `F001`, `F002`, ... for figures
- `T001`, `T002`, ... for tables

For each block, capture: page number, block type, original text, translation, reading-order index, nearby figure or table references, first substantive figure/table mention, and confidence level when extraction is uncertain.

## 3. Translate conservatively

- preserve technical terms unless a standard Chinese equivalent is clearly better
- keep model names, algorithm names, formulas, and symbols intact
- keep citations, superscripts, subscripts, and numeric values unchanged
- do not collapse methods details into vague prose
- keep paragraph order and section order
- mark uncertain text instead of guessing when OCR or layout extraction is weak
- keep the source's paragraph form; do not convert into bullet-point keywords
- do not silently skip Methods, limitations, data availability, code availability, or competing interests
- if the paper is too long for one pass, write `paper.md` incrementally and mark pending blocks

Build the Terminology Ledger as you translate so recurring terms stay consistent.

## 4. Extract and place figures and tables

Crop each figure/table into `assets/` and place it near its first substantive mention, keeping the caption attached with both original and Chinese caption text. For full placement and tight-crop rules, open `references/figure-extraction.md`.

## 5. Generate the Markdown file

Default output is a single `paper.md`. It must include:
- metadata header
- a short page/section index for long papers
- paragraph-level original/Chinese pairs for all extractable substantive text
- figure and table blocks placed near the relevant discussion
- source anchors on every substantive text, figure, caption, and table block
- a terminology table for recurring technical terms (from the Terminology Ledger)
- a short 阅读提示 section only after the bilingual body

Output directory: `D:/MD ideas/20-机器学习/文献/<paper_slug>/`

## 6. Answer follow-up questions with source grounding

When the user asks a question after the file is created, answer from the paper, not from memory, and cite exact block IDs and page numbers. For full grounding rules, open `references/grounding-rules.md`.
