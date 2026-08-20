# Stage C3: 撰写初稿 [Strategist]

**Gate:** QC3 (BLOCK)
**Goal:** Generate first draft of the paper via Python script execution, with proper formatting and reference handling
**Needs Composers:** [evidence-ledger-gen, docx-assembly, format-routing, citation-anchor-format, claim-to-paragraph]

## Decisions

### Format Routing (writingFormat)

Inspect `passport.writingFormat` (default `word`):

| writingFormat | Action |
|---------------|--------|
| word (default) | Existing script → python-docx path below. Charts via matplotlib OK; prefer academic-plotting routers for publication-looking figures. |
| latex | Do **not** force .docx. Load `skills-embedded/latex-paper-en.md` → `../../academic-latex/`. Chinese layout tips: `latex-thesis-zh.md`. Run `python ../../academic-latex/scripts/verify_paper.py {tex_root} --allow-cjk` before QC3. Figures: `nature-figure` / `scientific-visualization` / `scientific-schematics` → `../../academic-plotting/`. |
| markdown | Draft in Markdown + Mermaid (`markdown-mermaid-writing.md`); convert later if user asks. |

**QC3:** word → .docx checklist; latex → compilable project + verify_paper CLEAN (or waived).

### Tool Commands (C3)

- Figures: follow academic-plotting figure-contract before plotting.
- IF latex: `/latex-cleanup` → `../academic-shared/commands/latex-cleanup.md` after first clean compile.
- Citations: prefer `/check-refs` after building bibliography (bib bridge: `../academic-shared/literature/bib_to_bibliography.py`).


### Axis Routing

#### Setup: Confirm Prerequisites
- Check if topic sentence, reference list, and author info are available
- If NOT pre-specified → STOP-AND-ASK: prompt user for:
  - Topic sentence (or confirm existing)
  - Author name(s) and student ID(s)
  - Course name and instructor
  - Any formatting preferences

#### Methodological Choice: Script-Based Generation
- **CRITICAL RULE:** Do NOT write prose directly into the draft document. Write a Python script that generates the .docx file using `python-docx`.
- The script must:
  1. Use `evidence-ledger-gen` composer to generate the evidence ledger
  2. Use `claim-to-paragraph` composer to expand outline claims into topic-sentence + evidence + bridge paragraphs — **every paragraph must have exactly one claim backed by evidence; claims with weak or missing evidence must be downgraded or removed**
  3. Use `citation-anchor-format` composer to enforce two-layer citation tagging (ref + anchor) — every body citation must carry a traceable anchor locator (quote/page/section); top-5 most-cited references undergo claim alignment audit
  4. Build the document with proper section headers, font, spacing
  5. Include reference placeholder scheme for later renumbering
  6. Generate at least 3-5 charts/figures (via matplotlib) and embed them at semantically appropriate positions with numbered captions (图N/表N)
  7. Target 15,000+ Chinese characters for the body text

#### Required Script Functions

Include these helper functions in the generation script:

```python
def clean_md_line(line):
    """Remove markdown bold/italic markers from a line."""
    line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
    line = re.sub(r'\*(.+?)\*', r'\1', line)
    return line

def process_md_to_docx(doc, filepath, body_fn, quote_fn=None, ref_fn=None, heading_fn=None):
    """Process a markdown file into docx paragraphs, merging consecutive body lines.

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
        # Reference lines — flush immediately as separate paragraphs
        if re.match(r'^\[\d+\]', line):
            flush_body()
            fn = ref_fn or body_fn
            fn(doc, clean_md_line(line))
            i += 1
            continue
        body_buf.append(line)
        i += 1

    flush_body()
```

#### Writing Order
- Write core analysis sections first, then introduction and conclusion, then abstract last. This ensures substance exists before framing.

#### Reference Numbering
- After body text is written:
  1. Scan all citations in text for first-appearance order
  2. Renumber references sequentially (`[1]`, `[2]`, ...) by first appearance
  3. Remove any bibliography entries not cited in text
  4. Update both in-text citations and the reference section

#### AI Use Declaration
- Default template: "本课程作业由AI辅助完成，使用 Claude (Anthropic) 进行内容生成与修订"
- User may customize the declaration text
- Declaration goes after the conclusion, before references

#### Em Dash Constraints
- Max 1 em dash (—) per paragraph
- Max 15 em dashes per 15,000 characters (1.5万字)
- Post-generation scan: if violated, replace excess em dashes with commas or parentheses

#### Text Processing Script Development Norm

**CRITICAL RULE:** 所有对文档执行批量文本处理的脚本（引号修复、去重、格式化检查等），必须先在前 3 个段落的小样本上验证逻辑正确性，确认无误后再全量执行。禁止在未验证的情况下直接操作全文档。

```
开发流程：
  1. 编写脚本，添加 --dry-run 或 --sample 参数
  2. 在前 3 个段落上运行，手动检查输出
  3. 确认逻辑正确 → 全量执行
  4. 确认有误 → 修正后回到步骤 2
```

违反此规范的后果：错误逻辑批量应用到全文档（如引号修复脚本方向写反导致 LEFT=168/RIGHT=17），修复成本高且可能引入新问题。

### Composer Sequence
1. **composer:** evidence-ledger-gen {stage: C3B-EL, source_refs: <current_refs>}
2. **composer:** claim-to-paragraph {target: <outline_claims>, language: zh, section_structure: 章-节}
3. *(Python script is written and executed — not a composer call)*
4. **composer:** format-routing {target: draft, format_check: full, language: zh}
5. **composer:** docx-assembly {script_path: <generated_script>, output: <draft_path>}
6. **composer:** citation-anchor-format {target: <draft>, output_dir: <output_dir>}

## Gate

### QC3 Gate Checklist
- [ ] Draft is generated via Python script (not manual prose)
- [ ] Evidence ledger is attached/integrated
- [ ] Every paragraph follows claim-to-paragraph pattern (topic sentence + evidence + bridge); weak-evidence claims removed
- [ ] References are numbered by first-appearance order
- [ ] Only cited references appear in bibliography
- [ ] Citations carry two-layer traceable structure (ref + anchor); top-5 citation alignment audit passed with no DOES NOT SUPPORT verdicts
- [ ] AI use declaration is present
- [ ] Em dash density is within limits (<=1/paragraph, <=15/1.5万字)
- [ ] At least 3-5 charts/figures/tables embedded with numbered captions (图N/表N)
- [ ] Chinese character count reaches 15,000+
- [ ] **正文内容来源于 .md 中间文件** — Python 脚本仅负责排版组装（字体、间距、图表嵌入），禁止将正文硬编码在 Python 列表中。中间文件使内容可独立审阅、可从源头避免引号编码问题。
- [ ] Basic format checks pass (headers, fonts, spacing)
- [ ] **Chinese curly quote direction verified** — all opening quotes are LEFT (“ / U+201C), all closing quotes are RIGHT (“ / U+201D). Use pair-matching algorithm per paragraph: first quote after CJK text → LEFT/opening, next quote → RIGHT/closing, alternating. Run `verify_quotes.py` (see `scripts/verify_quotes.py`) to auto-detect and report direction errors. Right-to-left imbalance > 2 → fix before gate.
- [ ] **Post-generation smoke test passed** — 生成脚本执行后立即自动运行 `python scripts/verify_quotes.py <output.docx>`，引号方向错误应在 C3 阶段拦截，不得留给 C4 或用户发现。

### Gate Failure Route
- Failed QC3 → route back to C3A (outline phase):
  - Identify deficient sections
  - Supplement outline and references for those sections
  - Re-generate via updated Python script
  - Re-evaluate QC3
