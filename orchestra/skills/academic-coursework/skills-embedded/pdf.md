---
name: pdf
description: "PDF processing — merge, split, extract, watermark, encrypt/decrypt, OCR. Used at S8 for PDF output and T6.5 for blind review PDF anonymization."
source: pdf v1.0 | snapshot: 2026-06-06
---

# PDF Processing (Pipeline Extract)

## Libraries

| Library | Purpose |
|---------|---------|
| `pypdf` | Basic ops: merge, split, rotate, metadata, encrypt |
| `pdfplumber` | Text/table extraction with layout preservation |
| `reportlab` | Create new PDFs from scratch |

## Basic Operations (pypdf)

```python
from pypdf import PdfReader, PdfWriter
```

### Merge
```python
writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)
with open("merged.pdf", "wb") as output:
    writer.write(output)
```

### Split
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

### Extract Metadata
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
# meta.title, meta.author, meta.subject, meta.creator
```

### Rotate Pages
```python
page = reader.pages[0]
page.rotate(90)
writer.add_page(page)
```

## Text & Table Extraction (pdfplumber)

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        tables = page.extract_tables()
        for row in tables:
            # process table rows
```

## Creating PDFs (reportlab)

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("output.pdf", pagesize=letter)
width, height = letter
c.drawString(100, height - 100, "Title")
c.save()
```

For multi-page documents:
```python
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []
story.append(Paragraph("Title", styles['Title']))
story.append(PageBreak())
doc.build(story)
```

**CRITICAL:** Never use Unicode subscript/superscript chars (₀₁₂₃, ⁰¹²³) in ReportLab — built-in fonts don't include them. Use `<sub>` and `<super>` XML tags in Paragraph objects instead.

## Password Protection

```python
writer = PdfWriter()
for page in PdfReader("input.pdf").pages:
    writer.add_page(page)
writer.encrypt("userpassword", "ownerpassword")
with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## Add Watermark

```python
watermark = PdfReader("watermark.pdf").pages[0]
writer = PdfWriter()
for page in PdfReader("document.pdf").pages:
    page.merge_page(watermark)
    writer.add_page(page)
with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

## OCR (Scanned PDFs)

```python
# pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

images = convert_from_path('scanned.pdf')
text = ""
for i, image in enumerate(images):
    text += f"Page {i+1}:\n"
    text += pytesseract.image_to_string(image)
```

## Blind Review Anonymization (T6.5)

For thesis blind review (T6.5), remove identifiers from PDF:
1. Strip metadata: create new PDF from pages (discards old metadata)
2. Remove author/advisor names from text (search-and-replace in extracted content, regenerate)
3. Remove fund numbers, lab names, self-citations from visible text

## Command-Line Quick Ref

```bash
# qpdf: merge, split, rotate
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf

# pdftotext: extract text
pdftotext -layout input.pdf output.txt
```

## Dependencies

- `pip install pypdf pdfplumber reportlab` — core
- `pip install pytesseract pdf2image` — OCR (optional)
- `qpdf` / `poppler-utils` — CLI tools
