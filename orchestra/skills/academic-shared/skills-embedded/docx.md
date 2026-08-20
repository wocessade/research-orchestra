---
name: docx
description: "Word document (.docx) creation and editing via docx-js and python-docx. Used at S8 for Word output, C3/T4 for course-assignment/thesis .docx generation."
source: docx v1.0 | snapshot: 2026-06-06
---

# DOCX Creation & Editing (Pipeline Extract)

## Thesis Docx Generation (T4)

For thesis .docx generation (T4 stage, Word path), use the shipped `scripts/generate_thesis_docx.py` script. This script includes all 7 known traps from the "运行时生成 assemble_thesis.py 的已知陷阱" section below. Do NOT write thesis assembly from scratch — configure the shipped script via a YAML config file instead.

Usage:
```bash
python "{pipeline_root}/scripts/generate_thesis_docx.py" \
    --config "{output_dir}/thesis_config.yaml" \
    --output "{output_dir}/thesis.docx"
```

The Format Template System (`scripts/format_template.py` + `StyleEngine`, documented below) is available for advanced users who want to extract formatting from a previous thesis .docx, but the DEFAULT path for T4 is `generate_thesis_docx.py`.

## Quick Reference

| Task | Approach |
|------|----------|
| Read/analyze content | `pandoc document.docx -o output.md` or unpack for raw XML |
| Create new document | docx-js (`npm install -g docx`) — see below |
| Edit existing document | Unpack → edit XML → repack |

## Creating New Documents (docx-js)

```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, PageOrientation, LevelFormat,
        TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
        PageNumber, PageBreak } = require('docx');

const doc = new Document({ sections: [{ children: [/* content */] }] });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

### Page Size (DXA units, 1440 DXA = 1 inch)

```javascript
// US Letter (set explicitly — docx-js defaults to A4)
sections: [{
  properties: {
    page: {
      size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
    }
  },
  children: [/* content */]
}]
```

| Paper | Width | Height | Content Width (1" margins) |
|-------|-------|--------|---------------------------|
| US Letter | 12,240 | 15,840 | 9,360 |
| A4 | 11,906 | 16,838 | 9,026 |

**Landscape:** pass portrait dimensions + `orientation: PageOrientation.LANDSCAPE` (docx-js swaps internally).

### Styles

```javascript
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } }, // 12pt
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
    ]
  },
  // ...
});
```

### Lists (use numbering config, NOT unicode bullets)

```javascript
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  // paragraphs use: numbering: { reference: "bullets", level: 0 }
});
```

### Tables (must set dual widths)

```javascript
new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [4680, 4680],
  rows: [
    new TableRow({
      children: [
        new TableCell({
          width: { size: 4680, type: WidthType.DXA },
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun("Cell")] })]
        })
      ]
    })
  ]
});
```

### Images

```javascript
new Paragraph({
  children: [new ImageRun({
    type: "png",  // Required: png, jpg, gif, svg
    data: fs.readFileSync("image.png"),
    transformation: { width: 200, height: 150 },
    altText: { title: "Title", description: "Desc", name: "Name" }
  })]
});
```

### Headers/Footers & Page Numbers

```javascript
sections: [{
  properties: {
    page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } }
  },
  headers: {
    default: new Header({ children: [new Paragraph({ children: [new TextRun("Header")] })] })
  },
  footers: {
    default: new Footer({ children: [new Paragraph({
      children: [new TextRun("Page "), new TextRun({ children: [PageNumber.CURRENT] })]
    })] })
  },
  children: [/* content */]
}]
```

### Page Breaks & TOC

```javascript
// PageBreak must be inside Paragraph
new Paragraph({ children: [new PageBreak()] })

// Table of Contents (headings must use HeadingLevel only)
new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" })
```

## Critical Rules

- **Set page size explicitly** — docx-js defaults to A4
- **Never use `\n`** — use separate Paragraph elements
- **Never use unicode bullets** — use `LevelFormat.BULLET` with numbering config
- **PageBreak must be in Paragraph** — standalone creates invalid XML
- **Tables need dual widths** — `columnWidths` AND cell `width`, both DXA
- **Use `ShadingType.CLEAR`** — never SOLID for table shading
- **TOC requires HeadingLevel only** — no custom styles on heading paragraphs
- **Override built-in styles** — use exact IDs: "Heading1", "Heading2", etc.

## Format Template System (scripts/format_template.py)

A YAML-driven typesetting engine that decouples formatting rules from code.

### Architecture

```
用户输入 (学长论文DOCX / 规范文档 / 已有YAML)
       │
       ▼
  ┌─────────────┐
  │  适配器解析   │  docx_adapter / spec_adapter (预留)
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │ 统一YAML模板 │  page + styles + structure
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │ StyleEngine  │  读取模板 → 应用于 DOCX 元素
  └─────────────┘
         ▼
     final .docx
```

### Default Template (16 styles)

| Style Role | 用途 | 默认值 |
|-----------|------|--------|
| `body` | 正文 | 宋体 12pt, 1.5行距, 首行缩进2字符 |
| `chapter_title` | "第1章 绪论" | 黑体 16pt 居中加粗 |
| `section_h1` | "1.1" | 黑体 14pt 加粗 |
| `section_h2` | "1.1.1" | 黑体 12pt 加粗 |
| `blockquote` | 引用块 | 宋体 10.5pt, 左缩进 |
| `table_number` | "表1-1" | 黑体 10.5pt, 表上方 |
| `table_title` | 表题 | 宋体 10.5pt |
| `figure_number` | "图1-1" | 黑体 10.5pt, 图下方 |
| `figure_title` | 图题 | 宋体 10.5pt |
| `reference` | 参考文献条目 | 宋体 10.5pt, 1.0行距, 左对齐, space_after=0pt, 悬挂缩进0.74cm |
| `page_header` | 页眉 | 宋体 9pt 居中 |
| `page_footer` | 页脚(页码) | Times New Roman 9pt 居中 |
| `toc_title` | "目  录" | 黑体 16pt 居中 |
| `abstract_title` | "摘  要" / "Abstract" | 黑体 16pt 居中 |
| `declaration_title` | 声明页标题 | 黑体 16pt 居中 |
| `acknowledgement_title` | "致  谢" | 黑体 16pt 居中 |

### Status Marking

Each style entry has a `status` field:
- `confirmed` — 从源文件明确解析
- `defaulted` — 未找到，使用内置默认值（流程不打断）
- `conflict` — 多个源冲突，使用第一个源的值

生成完成后通过 `generate_report()` 汇总 ⚠️ defaulted / ❌ conflict 项供用户裁决。

### Template API

```python
# In output-dir assemble script:
import sys
sys.path.insert(0, "~/.claude/skills/academic-thesis/scripts")
from format_template import (
    build_default_template, load_template, save_template,
    get_style, merge_template, generate_report, print_report,
)
from format_adapters import run_adapter

# 1. 获取默认模板
tpl = build_default_template()

# 2. 从学长论文提取格式
parsed = run_adapter("docx", "path/to/thesis.docx")

# 3. 合并: 提取到的覆盖默认值
tpl = merge_template(tpl, parsed)

# 4. 查看未确认项
report = generate_report(tpl)
print_report(report)

# 5. 保存模板
save_template(tpl, "thesis_format.yaml")

# 6. 下次直接加载
tpl = load_template("thesis_format.yaml")
```

### StyleEngine (for assemble script)

The `StyleEngine` class consumes a template dict and applies formatting. This class is defined in `assemble_thesis.py` — a script generated by the pipeline at T4 stage for each specific thesis (not shipped as a pre-existing file).

```python
# Inside the pipeline-generated assemble_thesis.py (output dir):
from format_template import build_default_template
from assemble_thesis import StyleEngine  # defined in the same file

doc = Document()
tpl = build_default_template()
engine = StyleEngine(doc, tpl)

# Add paragraphs with automatic formatting
engine.add_body_para("正文内容")
engine.add_heading("第1章 绪论", role="chapter_title")
engine.add_heading("1.1 研究背景", role="section_h1")
engine.add_quote("引用内容")
engine.add_reference("[1] 作者. 标题[J]. 期刊, 2023.")
engine.add_table_element("表1-1 数据对比", role="table_number")
engine.add_figure_element("图1-1 实验流程", role="figure_number")
engine.add_toc_field()
engine.add_header("XX大学本科毕业论文")
engine.add_footer()
```

### 运行时生成 assemble_thesis.py 的已知陷阱（必须包含在生成脚本中）

当 T4 阶段生成 `assemble_thesis.py` 时，必须包含以下修复，否则输出的 DOCX 会出现排版错误：

**1. `_apply_para_format` 中的 `Pt(0)` 假值陷阱**
```python
# ❌ 错误：Pt(0) 在 Python 中为假值，space_after=0 会被跳过
if sb:   para.paragraph_format.space_before = sb
if sa:   para.paragraph_format.space_after = sa

# ✅ 正确：使用 is not None 判断
if sb is not None:  para.paragraph_format.space_before = sb
if sa is not None:  para.paragraph_format.space_after = sa
```

**2. `add_heading()` 必须应用 Word 内置标题样式（Heading 1/2/3）**
```python
_HEADING_STYLE_MAP = {
    "chapter_title": "Heading 1",
    "section_h1": "Heading 2",
    "section_h2": "Heading 3",
}

def add_heading(self, text, *, role):
    para = self.doc.add_paragraph()
    style_id = _HEADING_STYLE_MAP.get(role)
    if style_id:
        try:
            para.style = self.doc.styles[style_id]
        except KeyError:
            pass
    # 接着应用 run-level 格式覆盖
    run = para.add_run(text)
    self.set_run_font(run, role)
    return para
```

**3. `set_run_font()` 的颜色默认值**
```python
# 模板中无 color 字段时，默认黑色而非蓝色
run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
```

**4. 第N章前自动分页**
```python
# 在 assemble() 的 chapter 分支中，检测标题是否以"第"开头
last_was_break = False
for item in structure:
    if item["type"] == "chapter":
        title = item.get("title", "")
        if title.startswith("第") and not last_was_break:
            doc.add_paragraph().add_run(PageBreak())  # 或 add_page_break()
        # ... 写入标题和内容
        last_was_break = False
    elif item["type"] == "page_break":
        engine.add_page_break()
        last_was_break = True
    # ...
```

**5. 源文件已有标题时避免重复**
```python
# 如果 markdown 源文件第一行是 "# "，则跳过 structure 中的 title
source_has_heading = False
if source:
    src_path = os.path.join(OUTPUT_DIR, source)
    if os.path.exists(src_path):
        with open(src_path, encoding="utf-8") as _f:
            if _f.readline().strip().startswith("# "):
                source_has_heading = True
if title and not source_has_heading:
    engine.add_heading(title, role="chapter_title")
```

**6. TOC 1/TOC 2 样式自动创建**
```python
# Word 新文档中没有 TOC 1/TOC 2 样式，必须程序化创建
try:
    _ = doc.styles["TOC 1"]
except KeyError:
    s = doc.styles.add_style("TOC 1", WD_STYLE_TYPE.PARAGRAPH)
    # 应用模板中的 toc_entry_1 设置
try:
    _ = doc.styles["TOC 2"]
except KeyError:
    s = doc.styles.add_style("TOC 2", WD_STYLE_TYPE.PARAGRAPH)
    # 应用模板中的 toc_entry_2 设置
```

**7. 参考文献每行独立成段（bibliography.md）**

`process_markdown_file` 默认合并连续行为一段，但参考文献必须每行单独一段。在主循环中提前拦截 `[N]` 行：

```python
# Reference lines — flush immediately as separate paragraphs
if re.match(r"^\[\d+\]", line):
    flush_body()
    engine.add_reference(clean_md_line(line))
    continue
```

把此检测放在 body_lines 积累**之前**，位于 heading 检测之后、bold-line 检测之前。

### Adapters

**DOCX adapter** (`format_adapters/docx_adapter.py`):
- Extracts: page setup, named styles (Normal, Heading 1-3)
- Fallback: paragraph sampling (clusters paragraphs by formatting signature)
- Skips cover-page noise (short centered text)

**Spec adapter** (`format_adapters/spec_adapter.py`):
- Reserved for future use (规范文档/操作文档解析)
- Currently returns empty dict (stub)

## Dependencies

- `pip install pyyaml python-docx` — format template + docx generation
- `npm install -g docx` — creating new documents (docx-js path)
- `pandoc` — text extraction
- LibreOffice — PDF conversion (for validation)
