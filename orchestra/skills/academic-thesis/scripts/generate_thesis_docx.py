#!/usr/bin/env python3
"""
generate_thesis_docx.py — Shipped, reusable thesis .docx assembler.

The AI at T4 time CONFIGURES this script (fills in thesis_structure with actual
chapter titles and source filenames) rather than writing assembly from scratch.

Usage:
    python generate_thesis_docx.py --config thesis_config.yaml --output thesis.docx
    python generate_thesis_docx.py --validate-only --config thesis_config.yaml --output thesis.docx

All 7 known traps from docx.md §275-376 are baked in:
  1. Pt(0) truthiness — use `is not None`
  2. Heading 1/2/3 built-in styles applied
  3. Font color defaults to black
  4. Auto-page-break before chapters starting with "第"
  5. Source file heading dedup — skip structure title if md already has it
  6. TOC 1/TOC 2 styles auto-created
  7. Reference lines always independent paragraphs
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os
import re
import sys
import yaml
import argparse
from datetime import datetime
from copy import deepcopy

# ── Default thesis margins (GB/T 7713.1) ──
DEFAULT_MARGINS = {
    "top": 2.5,
    "bottom": 2.5,
    "left": 3.0,
    "right": 2.5,
}

# ── Heading role → Word style map ──
_HEADING_STYLE_MAP = {
    "chapter_title": "Heading 1",
    "section_h1": "Heading 2",
    "section_h2": "Heading 3",
}


class ThesisDocxBuilder:
    """Thesis .docx assembler with built-in validation."""

    def __init__(self, config: dict, output_dir: str = "."):
        self.config = config
        self.output_dir = output_dir
        self.doc = Document()
        self.generation_log = []
        self._setup_page()
        self._setup_styles()

    # ── Page Setup ──

    def _setup_page(self):
        """Set A4, thesis margins from config or defaults."""
        section = self.doc.sections[0]
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        pg = self.config.get("page", {})
        margins = pg.get("margins", DEFAULT_MARGINS)
        section.top_margin = Cm(margins.get("top", 2.5))
        section.bottom_margin = Cm(margins.get("bottom", 2.5))
        section.left_margin = Cm(margins.get("left", 3.0))
        section.right_margin = Cm(margins.get("right", 2.5))

    def _setup_styles(self):
        """Configure Normal style and create TOC styles if missing."""
        style = self.doc.styles["Normal"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12)
        style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        pf = style.paragraph_format
        pf.line_spacing = 1.5
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        # Trap 6: Auto-create TOC styles
        for name in ["TOC 1", "TOC 2", "TOC 3"]:
            try:
                self.doc.styles[name]
            except KeyError:
                s = self.doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
                try:
                    s.font.name = "Times New Roman"
                    s.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
                except Exception:
                    pass

    # ── Font Helpers ──

    @staticmethod
    def set_run_font(run, font_cn, font_en="Times New Roman", size=Pt(12), bold=False):
        """Set both East-Asian and Latin fonts on a run. Trap 3: default black."""
        run.font.size = size
        run.bold = bold
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        rPr = run._r.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = OxmlElement("w:rFonts")
            rPr.insert(0, rFonts)
        rFonts.set(qn("w:eastAsia"), font_cn)
        rFonts.set(qn("w:ascii"), font_en)
        rFonts.set(qn("w:hAnsi"), font_en)

    # ── Paragraph Helpers ──

    def add_heading(self, text, *, role):
        """Add a heading with Word built-in style.  Trap 2: apply Heading 1/2/3."""
        para = self.doc.add_paragraph()
        style_id = _HEADING_STYLE_MAP.get(role)
        if style_id:
            try:
                para.style = self.doc.styles[style_id]
            except KeyError:
                pass
        pf = para.paragraph_format
        pf.line_spacing = 1.5
        pf.space_before = Pt(12)
        pf.space_after = Pt(6)
        run = para.add_run(text)
        if role == "chapter_title":
            self.set_run_font(run, "黑体", size=Pt(16), bold=True)
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif role == "section_h1":
            self.set_run_font(run, "黑体", size=Pt(14), bold=True)
        elif role == "section_h2":
            self.set_run_font(run, "黑体", size=Pt(12), bold=True)
        return para

    def add_body_para(self, text, indent=True, font_cn="宋体", size=Pt(12)):
        """Add a body paragraph: 宋体 12pt, 1.5x spacing, 0.74cm indent."""
        para = self.doc.add_paragraph()
        pf = para.paragraph_format
        pf.line_spacing = 1.5
        # Trap 1: use `is not None` for Pt(0)
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        if indent:
            pf.first_line_indent = Cm(0.74)
        run = para.add_run(text)
        self.set_run_font(run, font_cn, size=size)
        return para

    def add_reference(self, text, font_cn="宋体", size=Pt(10.5)):
        """Reference entry: 宋体 10.5pt, 1.0 spacing, hanging indent."""
        para = self.doc.add_paragraph()
        pf = para.paragraph_format
        pf.line_spacing = 1.0
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.first_line_indent = Cm(-0.74)
        pf.left_indent = Cm(0.74)
        run = para.add_run(text)
        self.set_run_font(run, font_cn, size=size)
        return para

    @staticmethod
    def clean_md_line(line):
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        return line

    # ── Page/Section Helpers ──

    def add_page_break(self):
        p = self.doc.add_paragraph()
        run = p.add_run()
        br = OxmlElement("w:br")
        br.set(qn("w:type"), "page")
        run._r.append(br)

    def add_toc_field(self):
        """Insert a Word TOC field (user right-clicks → Update Field)."""
        p = self.doc.add_paragraph()
        run = p.add_run()
        fldChar1 = OxmlElement("w:fldChar")
        fldChar1.set(qn("w:fldCharType"), "begin")
        run._r.append(fldChar1)

        run2 = p.add_run()
        instrText = OxmlElement("w:instrText")
        instrText.set(qn("xml:space"), "preserve")
        instrText.text = ' TOC \\o "1-3" \\h \\z \\u '
        run2._r.append(instrText)

        run3 = p.add_run()
        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "separate")
        run3._r.append(fldChar2)

        run4 = p.add_run()
        run4.text = "（请在目录上右键 → 更新域 以自动生成目录）"
        self.set_run_font(run4, "宋体", size=Pt(12))

        run5 = p.add_run()
        fldChar3 = OxmlElement("w:fldChar")
        fldChar3.set(qn("w:fldCharType"), "end")
        run5._r.append(fldChar3)

    def add_header(self, text, font_cn="宋体", size=Pt(9)):
        """Add centered header to the last section."""
        section = self.doc.sections[-1]
        header = section.header
        header.is_linked_to_previous = False
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        self.set_run_font(run, font_cn, size=size)

    def add_page_numbers(self, start=1):
        """Add centered page numbers to the last section."""
        section = self.doc.sections[-1]
        footer = section.footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        run = p.add_run()
        fldChar1 = OxmlElement("w:fldChar")
        fldChar1.set(qn("w:fldCharType"), "begin")
        run._r.append(fldChar1)

        run2 = p.add_run()
        instrText = OxmlElement("w:instrText")
        instrText.set(qn("xml:space"), "preserve")
        instrText.text = " PAGE "
        run2._r.append(instrText)

        run3 = p.add_run()
        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "end")
        run3._r.append(fldChar2)

        sectPr = section._sectPr
        # Remove existing pgNumType if present
        for existing in sectPr.findall(qn("w:pgNumType")):
            sectPr.remove(existing)
        pgNumType = OxmlElement("w:pgNumType")
        pgNumType.set(qn("w:start"), str(start))
        sectPr.append(pgNumType)

    # ── Markdown Processing ──

    def process_markdown_file(self, filepath, body_fn=None, ref_fn=None, heading_fn=None):
        """Process a markdown file into docx paragraphs.

        HARD-FAILS on missing files — does NOT silently skip.
        Traps 5+7: heading dedup, reference line independence.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(
                f"\n{'='*60}\n"
                f"MISSING SOURCE FILE: {filepath}\n"
                f"{'='*60}\n"
                f"This file is listed in the thesis structure config but does\n"
                f"not exist on disk. The stage that should produce this file\n"
                f"may not have completed successfully.\n\n"
                f"Fix: check that the preceding pipeline stage ran correctly\n"
                f"and produced this output file.\n"
                f"{'='*60}\n"
            )

        body_fn = body_fn or self.add_body_para
        ref_fn = ref_fn or self.add_reference

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        body_buf = []

        def flush_body():
            nonlocal body_buf
            if not body_buf:
                return
            text = self.clean_md_line("".join(body_buf))
            body_fn(self.doc, text)
            body_buf = []

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if not line or line.isspace():
                flush_body()
                i += 1
                continue
            if line.startswith("```"):
                flush_body()
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    i += 1
                i += 1
                continue
            # Trap 7: Reference lines — flush immediately as separate paragraphs
            # Must be checked BEFORE body_buf accumulation
            if re.match(r"^\[\d+\]", line):
                flush_body()
                ref_fn(self.doc, self.clean_md_line(line))
                i += 1
                continue
            if line.startswith("# ") and not line.startswith("## "):
                flush_body()
                if heading_fn:
                    heading_fn(self.doc, self.clean_md_line(line[2:]), level=0)
                i += 1
                continue
            if line.startswith("## "):
                flush_body()
                if heading_fn:
                    heading_fn(self.doc, self.clean_md_line(line[3:]), level=1)
                i += 1
                continue
            if line.startswith("### "):
                flush_body()
                if heading_fn:
                    heading_fn(self.doc, self.clean_md_line(line[4:]), level=2)
                i += 1
                continue
            if line.startswith("> "):
                flush_body()
                i += 1
                while i < len(lines) and lines[i].startswith("> "):
                    i += 1
                continue
            body_buf.append(line)
            i += 1

        flush_body()

    # ── Assembly ──

    def _source_has_h1(self, filepath):
        """Check if the source file's first non-empty line is '# '.
        Trap 5: avoid duplicating heading already in source file."""
        if not os.path.exists(filepath):
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("```"):
                    return stripped.startswith("# ") and not stripped.startswith("## ")
        return False

    def _make_heading_fn(self, role):
        """Create a heading_fn closure for process_markdown_file."""
        builder = self

        def hfn(doc, text, level):
            if level == 0:
                builder.add_heading(text, role="chapter_title")
            elif level == 1:
                builder.add_heading(text, role="section_h1")
            elif level == 2:
                builder.add_heading(text, role="section_h2")

        return hfn

    def assemble(self):
        """Build the complete .docx from the structure config.

        Traps 4+5: auto-page-break before '第N章', heading dedup.
        """
        structure = self.config.get("structure", [])
        if not structure:
            raise ValueError("Config has no 'structure' section. Cannot assemble.")

        last_was_break = False
        cover_processed = False

        for item in structure:
            item_type = item.get("type", "")

            # ── Cover ──
            if item_type == "cover":
                self._assemble_cover(item)
                cover_processed = True
                self.generation_log.append("cover")
                last_was_break = False
                continue

            # ── Page Break ──
            if item_type == "page_break":
                self.add_page_break()
                last_was_break = True
                self.generation_log.append("page_break")
                continue

            # ── TOC ──
            if item_type == "toc":
                self.add_toc_field()
                self.generation_log.append("toc")
                last_was_break = False
                continue

            # ── Chapter ──
            if item_type == "chapter":
                title = item.get("title", "")
                source = item.get("source")
                role = item.get("role", "chapter")

                # Trap 4: page break before chapters starting with "第" or "参" or "致" or "A"
                if title and not last_was_break:
                    first_char = title.strip()[0] if title.strip() else ""
                    if first_char in ("第", "参", "致", "A", "摘"):
                        self.add_page_break()

                # Trap 5: skip structure title if source file already has H1
                source_has_heading = False
                if source:
                    src_path = os.path.join(self.output_dir, source)
                    source_has_heading = self._source_has_h1(src_path)

                if title and not source_has_heading:
                    heading_role = "chapter_title" if role in ("chapter", "abstract") else "section_h1"
                    self.add_heading(title, role=heading_role)

                if source:
                    src_path = os.path.join(self.output_dir, source)
                    heading_fn = self._make_heading_fn(role)
                    if role == "references":
                        self.process_markdown_file(src_path, ref_fn=self.add_reference, heading_fn=heading_fn)
                    else:
                        self.process_markdown_file(src_path, heading_fn=heading_fn)

                self.generation_log.append(f"chapter: {title} <- {source}")
                last_was_break = False
                continue

            # ── Header / Footer (applied after all content) ──
            if item_type == "page_numbering":
                start = item.get("start", 1)
                self.add_page_numbers(start=start)
                self.generation_log.append(f"page_numbering(start={start})")
                continue

            if item_type == "header_text":
                text = item.get("text", "")
                self.add_header(text)
                self.generation_log.append(f"header: {text[:30]}...")
                continue

            # Unknown type — warn but don't fail
            print(f"  [WARN] Unknown structure item type: {item_type}")

    def _assemble_cover(self, item):
        """Build the thesis cover page."""
        paper = self.config.get("paper", {})
        title_cn = paper.get("title_cn", item.get("title_cn", "[论文题目]"))
        title_en = paper.get("title_en", "")
        author = paper.get("author", item.get("author", "[姓名]"))
        student_id = paper.get("student_id", item.get("student_id", ""))
        university = paper.get("university", item.get("university", "[学校名称]"))
        department = paper.get("department", item.get("department", "[学院名称]"))
        major = paper.get("major", item.get("major", "[专业名称]"))
        advisor = paper.get("advisor", item.get("advisor", "[导师姓名]"))
        date_str = paper.get("date", item.get("date", datetime.now().strftime("%Y年%m月")))

        # Empty lines for vertical centering (approximate)
        for _ in range(5):
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)

        # University name
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(university)
        self.set_run_font(run, "黑体", size=Pt(22), bold=True)

        # Blank line
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)

        # "本科毕业论文" label
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(item.get("thesis_label", "本科毕业论文"))
        self.set_run_font(run, "黑体", size=Pt(26), bold=True)

        # Spacing
        for _ in range(3):
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)

        # Title
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(title_cn)
        self.set_run_font(run, "黑体", size=Pt(18), bold=True)

        if title_en:
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(title_en)
            self.set_run_font(run, "Times New Roman", size=Pt(14))

        # Spacing
        for _ in range(4):
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)

        # Info fields
        info_lines = [
            f"学    院：{department}",
            f"专    业：{major}",
        ]
        if student_id:
            info_lines.insert(0, f"学    号：{student_id}")
        info_lines.append(f"学生姓名：{author}")
        info_lines.append(f"指导教师：{advisor}")
        info_lines.append(date_str)

        for line in info_lines:
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(line)
            self.set_run_font(run, "宋体", size=Pt(14))

    # ── Validation ──

    def validate(self):
        """Post-generation validation. Returns (passed, report_dict).

        Checks:
        1. All chapters from config are present in docx
        2. No placeholder text (TODO, 待补充, XXX, TKTK)
        3. Character count meets minimum
        4. Page margins are correct
        5. Page breaks present before chapters
        """
        full_text = "\n".join([p.text for p in self.doc.paragraphs])
        errors = []
        warnings = []

        # 1. All chapters present
        structure = self.config.get("structure", [])
        for item in structure:
            if item.get("type") == "chapter" and item.get("title"):
                if item["title"] not in full_text:
                    errors.append(f"MISSING CHAPTER: '{item['title']}' not found in document")

        # 2. No placeholder text
        placeholders = ["TODO", "待补充", "XXX", "TKTK", "[add more here]", "[补充]", "[TODO]"]
        for ph in placeholders:
            if ph in full_text:
                # Count occurrences
                count = full_text.count(ph)
                errors.append(f"PLACEHOLDER FOUND: '{ph}' appears {count} time(s)")

        # 3. Minimum character count
        paper = self.config.get("paper", {})
        min_chars = paper.get("min_chars", 15000)
        char_count = len(full_text.replace("\n", "").replace(" ", "").replace("\r", ""))
        if char_count < min_chars * 0.8:
            errors.append(f"TOO SHORT: {char_count} chars (expected >= {int(min_chars * 0.8)})")
        elif char_count < min_chars:
            warnings.append(f"BELOW TARGET: {char_count} chars (target: {min_chars})")

        # 4. Page margins (verify against config)
        section = self.doc.sections[0]
        pg = self.config.get("page", {})
        margins = pg.get("margins", DEFAULT_MARGINS)
        # python-docx reports margins in EMU; approximate check in cm
        actual_top = section.top_margin / 360000
        actual_left = section.left_margin / 360000
        if abs(actual_top - margins.get("top", 2.5)) > 0.1:
            errors.append(f"WRONG TOP MARGIN: {actual_top:.1f}cm (expected {margins['top']}cm)")
        if abs(actual_left - margins.get("left", 3.0)) > 0.1:
            errors.append(f"WRONG LEFT MARGIN: {actual_left:.1f}cm (expected {margins['left']}cm)")

        # 5. Reference line independence check — each [N] should be its own paragraph
        ref_paragraphs = [p.text for p in self.doc.paragraphs if re.match(r"^\[\d+\]", p.text)]
        merged_refs = [t for t in ref_paragraphs if "\n" in t or len(t) > 300]
        if merged_refs:
            errors.append(
                f"MERGED REFERENCES: {len(merged_refs)} reference paragraph(s) contain multiple entries"
            )

        # Report
        para_count = len(self.doc.paragraphs)
        chapter_count = sum(
            1 for p in self.doc.paragraphs
            if p.style and p.style.name and p.style.name.startswith("Heading")
        )

        report = {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "char_count": char_count,
            "para_count": para_count,
            "chapter_count": chapter_count,
            "generation_log": self.generation_log,
        }

        return report

    # ── Save ──

    def save(self, output_path):
        self.doc.save(output_path)
        size = os.path.getsize(output_path)
        print(f"  [OK] Thesis saved: {output_path}")
        print(f"       Size: {size:,} bytes, {len(self.doc.paragraphs)} paragraphs")


# ================================================================
# CLI
# ================================================================

def print_validation_report(report):
    """Pretty-print validation results."""
    print()
    print("=" * 60)
    print("POST-GENERATION VALIDATION")
    print("=" * 60)
    status = "PASSED" if report["passed"] else "FAILED"
    print(f"  Status:        {status}")
    print(f"  Characters:    {report['char_count']:,}")
    print(f"  Paragraphs:    {report['para_count']}")
    print(f"  Heading paras: {report['chapter_count']}")
    print(f"  Items written: {len(report['generation_log'])}")
    print()

    if report["warnings"]:
        print("  Warnings:")
        for w in report["warnings"]:
            print(f"    - {w}")
        print()

    if report["errors"]:
        print(f"  Errors ({len(report['errors'])}):")
        for e in report["errors"]:
            print(f"    X {e}")
        print()
        print("  ACTION REQUIRED: Fix the errors above before proceeding to QT4 gate.")
        print()
    else:
        print("  All checks passed. Ready for QT4 gate.")

    if not report["passed"]:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate thesis .docx from config YAML (shipped script — configure, don't rewrite)"
    )
    parser.add_argument("--config", required=True, help="Path to thesis_config.yaml")
    parser.add_argument("--output", required=True, help="Path for output .docx file")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation on existing .docx (don't regenerate)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Base directory for resolving relative source paths (default: .)",
    )
    args = parser.parse_args()

    # Load config
    if not os.path.exists(args.config):
        print(f"ERROR: Config file not found: {args.config}")
        sys.exit(1)

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        print("ERROR: Config file is empty or invalid YAML")
        sys.exit(1)

    output_dir = args.output_dir or config.get("output_dir", ".")

    if args.validate_only:
        # Validate existing .docx
        if not os.path.exists(args.output):
            print(f"ERROR: Output file not found for validation: {args.output}")
            sys.exit(1)
        # Re-load with python-docx to validate
        from docx import Document as DocReader
        doc = DocReader(args.output)
        full_text = "\n".join([p.text for p in doc.paragraphs])
        structure = config.get("structure", [])
        errors = []
        for item in structure:
            if item.get("type") == "chapter" and item.get("title"):
                if item["title"] not in full_text:
                    errors.append(f"MISSING CHAPTER: '{item['title']}' not found")
        for ph in ["TODO", "待补充", "XXX", "TKTK"]:
            if ph in full_text:
                errors.append(f"PLACEHOLDER: '{ph}' found")
        char_count = len(full_text.replace("\n", "").replace(" ", "").replace("\r", ""))
        passed = len(errors) == 0
        print_validation_report({
            "passed": passed,
            "errors": errors,
            "warnings": [],
            "char_count": char_count,
            "para_count": len(doc.paragraphs),
            "chapter_count": sum(1 for p in doc.paragraphs if p.style and p.style.name and p.style.name.startswith("Heading")),
            "generation_log": [],
        })
    else:
        # Generate
        builder = ThesisDocxBuilder(config, output_dir=output_dir)

        try:
            builder.assemble()
        except FileNotFoundError as e:
            print(str(e))
            sys.exit(1)

        builder.save(args.output)

        # Mandatory validation
        report = builder.validate()
        print_validation_report(report)


if __name__ == "__main__":
    main()
