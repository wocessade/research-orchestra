# Composer: docx-assembly

**Purpose:** Generate a complete Chinese academic paper as a .docx file using a python-docx script with proper formatting (SimSun body, SimHei headings, 1.5x line spacing, A4 page).
**Used by:** academic-coursework C3, academic-journal S8 (Chinese domestic journals)
**Parameters:** `{font_cn}` (default: 宋体), `{font_en}` (default: Times New Roman), `{page_margins}` (default: 2.54cm top/bottom, 3.18cm left/right), `{line_spacing}` (default: 1.5)

## Instructions

### 1. Pre-Writing Setup

Before generating the script, confirm:
- Topic sentence + 3+ arguments (from outline stage)
- Merged bibliography (from citation stage)
- Author name and affiliation (STOP-AND-ASK if not pre-specified)
- AI use declaration text (standard template or user-provided)

### 2. Python Script Template

Generate the complete paper in ONE pass using a python-docx script. Write a Python script that generates the .docx, then execute it. Do NOT write prose directly in the conversation context.

```python
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os
import re

doc = Document()

# -- Page Setup --
section = doc.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
section.top_margin = Cm({page_margins_top})
section.bottom_margin = Cm({page_margins_bottom})
section.left_margin = Cm({page_margins_left})
section.right_margin = Cm({page_margins_right})


# -- Font Helpers --
def set_run_font(run, font_cn, font_en='{font_en}', size=Pt(12), bold=False):
    """Set both East-Asian and Latin fonts on a run."""
    run.font.size = size
    run.bold = bold
    # Default to black -- without this, built-in heading styles render blue
    run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:eastAsia'), font_cn)
    rFonts.set(qn('w:ascii'), font_en)
    rFonts.set(qn('w:hAnsi'), font_en)


def add_body_para(doc, text, indent=True, font_cn='{font_cn}', size=Pt(12)):
    """Add a body paragraph with standard formatting."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.line_spacing = {line_spacing}
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if indent:
        pf.first_line_indent = Cm(0.74)  # ~2 chars
    run = para.add_run(text)
    set_run_font(run, font_cn, size=size)
    return para


def add_reference(doc, text, font_cn='{font_cn}', size=Pt(10.5)):
    """Add a reference entry with proper formatting: 宋体 10.5pt, 1.0 line spacing, hanging indent."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.first_line_indent = Cm(-0.74)
    pf.left_indent = Cm(0.74)
    run = para.add_run(text)
    set_run_font(run, font_cn, size=size)
    return para


def add_table_caption(doc, text):
    """Add a table caption: 黑体 10.5pt, left-aligned, above table."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(6)
    pf.space_after = Pt(3)
    run = para.add_run(text)
    set_run_font(run, '黑体', size=Pt(10.5), bold=True)
    return para


def add_figure_caption(doc, text):
    """Add a figure caption: 黑体 10.5pt, centered, below figure."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.space_before = Pt(3)
    pf.space_after = Pt(12)
    run = para.add_run(text)
    set_run_font(run, '黑体', size=Pt(10.5), bold=True)
    return para


def add_image(doc, image_path, width_cm=14.0):
    """Insert an image centered on the page.
    
    Args:
        doc: python-docx Document
        image_path: absolute path to the image file (PNG or JPG)
        width_cm: image width in cm (default 14.0cm, fits within 3.18cm margins)
    """
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.space_before = Pt(6)
    pf.space_after = Pt(3)
    run = para.add_run()
    run.add_picture(image_path, width=Cm(width_cm))
    return para


def clean_md_line(line):
    """Remove markdown bold/italic markers from a line."""
    line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
    line = re.sub(r'\*(.+?)\*', r'\1', line)
    return line


def process_md_to_docx(doc, filepath, body_fn, quote_fn=None, ref_fn=None, heading_fn=None):
    """Process a markdown file into docx paragraphs, merging consecutive body lines.

    Args:
        doc: python-docx Document
        filepath: path to .md file
        body_fn: callable(doc, text) for body paragraphs
        quote_fn: optional callable(doc, text) for blockquotes (default: body_fn)
        ref_fn: optional callable(doc, text) for reference entries (default: body_fn)
        heading_fn: optional callable(doc, text, level) for headings (default: None, skip)

    Key behavior: consecutive lines separated by single newline (no blank line)
    are merged into ONE paragraph. Only blank lines, headings, and blockquotes
    trigger a paragraph break. This prevents md line-wrapping from creating
    unwanted whitespace in the rendered docx.
    """
    if not os.path.exists(filepath):
        return
    quote_fn = quote_fn or body_fn
    ref_fn = ref_fn or body_fn

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    body_buf = []

    def flush_body():
        nonlocal body_buf
        if not body_buf:
            return
        text = clean_md_line(''.join(body_buf))
        if ref_fn and re.match(r'^\[\d+\]', text):
            ref_fn(doc, text)
        else:
            body_fn(doc, text)
        body_buf = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line or line.isspace():
            flush_body()
            i += 1
            continue
        if line.startswith('```'):
            flush_body()
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                i += 1
            i += 1
            continue
        if line.startswith('# ') and not line.startswith('## '):
            flush_body()
            if heading_fn:
                heading_fn(doc, clean_md_line(line[2:]), level=0)
            elif heading_fn is None:
                pass  # skip by default
            i += 1
            continue
        if line.startswith('## '):
            flush_body()
            if heading_fn:
                heading_fn(doc, clean_md_line(line[3:]), level=1)
            i += 1
            continue
        if line.startswith('### '):
            flush_body()
            if heading_fn:
                heading_fn(doc, clean_md_line(line[4:]), level=2)
            i += 1
            continue
        if line.startswith('> '):
            flush_body()
            quote_lines = [line[2:]]
            i += 1
            while i < len(lines) and lines[i].startswith('> '):
                quote_lines.append(lines[i][2:].rstrip())
                i += 1
            quote_fn(doc, clean_md_line(''.join(quote_lines)))
            continue
        # Reference lines -- flush immediately as separate paragraphs
        if re.match(r'^\[\d+\]', line):
            flush_body()
            fn = ref_fn or body_fn
            fn(doc, clean_md_line(line))
            i += 1
            continue
        body_buf.append(line)
        i += 1

    flush_body()


def add_heading_styled(doc, text, level=1):
    """Add a heading with proper Chinese academic formatting.

    Applies Word built-in Heading 1/2/3 style so the TOC field,
    Navigation Pane, and outline-collapse work correctly.
    """
    para = doc.add_paragraph()
    # Map level -> Word built-in heading style for structural semantics
    heading_styles = {0: "Heading 1", 1: "Heading 2", 2: "Heading 3"}
    style_id = heading_styles.get(level)
    if style_id:
        try:
            para.style = doc.styles[style_id]
        except KeyError:
            pass
    pf = para.paragraph_format
    pf.line_spacing = {line_spacing}
    pf.space_before = Pt(12)
    pf.space_after = Pt(6)
    run = para.add_run(text)
    if level == 0:  # Paper title
        set_run_font(run, '黑体', size=Pt(16), bold=True)
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif level == 1:  # First-level heading
        set_run_font(run, '黑体', size=Pt(14), bold=True)
    elif level == 2:  # Second-level heading
        set_run_font(run, '黑体', size=Pt(12), bold=True)
    return para
```

### 3. Required Sections (in order)

1. **Title (题目)** -- centered, 黑体 16pt bold
2. **Author & Affiliation (作者与单位)** -- centered, 宋体 12pt
3. **Abstract (摘要)** -- 宋体 12pt, first-line indent. 200-300 Chinese characters summarizing topic, arguments, and conclusion.
4. **Keywords (关键词)** -- 宋体 12pt, 3-5 keywords separated by semicolons
5. **Introduction (引言)** -- 宋体 12pt, 1.5 line spacing, first-line indent. Background, problem statement, thesis paragraph, roadmap sentence.
6. **Body (正文)** -- One section per argument (3+ sections). 黑体 sub-headings, 宋体 body. Each section: state argument -> present evidence -> analyze -> transition.
   - **Charts/Figures in body (正文图表):** At least 3-5 charts, tables, or diagrams embedded at appropriate positions. Common placements:
     - Comparison tables at section ends for multi-dimension institutional benchmarking
     - Bar/radar charts for quantitative metric comparison
     - Flow diagrams for processes, paths, or frameworks
     - Geographic distribution maps for institutional coverage
   - Generate charts with matplotlib (Python) and insert via `add_image()`. Build tables with python-docx `add_table()`.
   - Each chart/table must have a numbered caption (表N/图N) with descriptive title.
7. **Conclusion (结论)** -- 宋体 12pt. Summarize arguments, state implications, acknowledge limitations.
8. **References (参考文献)** -- 宋体 10.5pt (五号), 1.0 line spacing, left-aligned, space_after=0pt, hanging indent 0.74cm. Numbered per GB/T 7714 format.

   **Citation ordering rule (critical):**
   - References must be numbered by **first appearance in the text** (not grouped by topic, not alphabetical by author)
   - After writing the body, scan the full text to extract all `[N]` citation markers, renumber them 1, 2, 3... by first-appearance order
   - **Keep only** entries cited at least once in the text. Remove uncited entries.
   - The script MUST implement the scan->sort->filter logic above. Do not rely on manual post-processing.

   Use `add_reference` as `ref_fn` for reference markdown files:
   ```python
   def load_bibliography(doc, path):
       process_md_to_docx(doc, path, body_fn=add_body_para, ref_fn=add_reference)
   ```

   Bibliography source `.md` files must NOT contain `# ` title lines (headings will duplicate).

   Reference type formats:
   - Journal articles: `Author. Title[J]. Journal Name, Year, Volume(Issue): Pages.`
   - Books: `Author. Title[M]. Publisher, Year.`
   - Conference papers: `Author. Title[C]//Proceedings Name. Location, Publisher, Year: Pages.`
   - Dissertations: `Author. Title[D]. University, Year.`
   - Online sources: `Author. Title[EB/OL]. URL, Year.`

9. **Acknowledgement / AI Use Declaration (致谢/AI使用声明)** -- 宋体 10.5pt.

   Default template:
   > 致谢：本文在写作过程中使用了AI辅助工具（Claude）进行文献检索、初稿撰写和格式排版。所有AI生成内容均经过作者审阅、修改和确认，文责由作者承担。

### 4. Formatting Rules

| Element | Font | Size | Spacing | Other |
|---------|------|------|---------|-------|
| Paper title | 黑体 (SimHei) | 16pt | 1.5x | Centered, bold |
| L1 heading | 黑体 (SimHei) | 14pt | 1.5x | Bold |
| L2 heading | 黑体 (SimHei) | 12pt | 1.5x | Bold |
| Body text | 宋体 (SimSun) | 12pt (小四) | 1.5x | First-line indent 0.74cm |
| References | 宋体 (SimSun) | 10.5pt (五号) | 1.0x | Hanging indent 0.74cm |
| English text | Times New Roman | Match surrounding | Match surrounding | -- |
| Table caption | 黑体 (SimHei) | 10.5pt (五号) | 1.5x | Above table, left-aligned: "表N 标题" |
| Table body | 宋体 (SimSun) | 10.5pt (五号) | 1.0x | -- |
| Figure caption | 黑体 (SimHei) | 10.5pt (五号) | 1.5x | Below figure, centered: "图N 标题" |
| Page margins | -- | -- | -- | 2.54cm top/bottom, 3.18cm left/right |
| Em dash | -- | -- | -- | <=1 per paragraph, <=10 per 10K chars; NEVER paired ---- |

### 5. Execute & Verify

1. Run the Python script to generate the .docx file
2. Verify:
   - File exists and is > 20KB (rough content check)
   - Open with python-docx to count paragraphs and characters; target 15,000+ Chinese characters
   - All 9 sections are present
   - At least 3-5 charts/tables embedded with numbered captions
   - No placeholder text ("[add more here]", "TODO", etc.)
   - Every citation in body has a corresponding reference entry

## Verification

- [ ] python-docx script generated and executed
- [ ] All 9 sections present (Title, Author, Abstract, Keywords, Introduction, Body, Conclusion, References, Acknowledgement)
- [ ] Title: centered, 黑体 16pt bold
- [ ] Author & affiliation: centered, 宋体 12pt
- [ ] Abstract: 200-300 Chinese characters, first-line indent
- [ ] Keywords: 3-5 items, semicolon-separated
- [ ] Body: 3+ argument sections with 黑体 sub-headings
- [ ] At least 3-5 charts/tables with numbered captions (表N/图N), placed at semantically appropriate positions
- [ ] References: numbered by first appearance in text, GB/T 7714 format
- [ ] No uncited references (every entry cited at least once)
- [ ] 宋体 body, 黑体 headings
- [ ] 1.5x line spacing throughout
- [ ] First-line indent 0.74cm on body paragraphs
- [ ] File > 40KB, 15,000+ Chinese characters
- [ ] No placeholder text
- [ ] Em dash limit respected

## Common Pitfalls

- **`Pt(0)` is falsy in Python:** Use `is not None`, not `if sb:` / `if sa:` when checking paragraph spacing. `Pt(0)` evaluates to False in a boolean context.
- **Headings must use Word built-in styles (Heading 1/2/3):** Without built-in styles, the Table of Contents field and Navigation Pane will not work. Always apply `para.style = doc.styles["Heading N"]`.
- **Blue heading color:** python-docx built-in heading styles default to blue. Always set `run.font.color.rgb = RGBColor(0, 0, 0)` explicitly.
- **Source `.md` files must not contain `# ` heading lines:** If the assembler adds headings from structure, `# ` lines in the source will cause duplicate headings.
- **Reference `[N]` lines must be flushed individually:** The `process_md_to_docx` function must treat `[N]` lines as immediate single-line paragraphs (via `flush_body()` + direct call), NOT merged into body paragraph buffers.
- **TOC styles must be created programmatically:** Fresh documents do not have TOC 1/TOC 2 styles. Create them via OxmlElement if a Table of Contents is needed.
- **Citation ordering post-processing:** References must be renumbered by first-appearance order AFTER the body is written. The script must implement this scan->sort->filter logic; do not rely on manual reordering.
- **Em dash overuse:** Paired em dashes (----) are extremely rare in academic Chinese. Use parentheses or colons instead. Single em dashes are acceptable but must be limited.
