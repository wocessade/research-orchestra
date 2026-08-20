---
name: T6-check
description: Plagiarism report processing sub-stage — PDF auto-parsing, manual input, or guidance-only mode for 查重报告 integration during T6 revision loop
---

# T6-Check: 查重结果处理

**Trigger:** During T6 (修订与收敛), when the user has a plagiarism check report from CNKI AMLC, 维普, or 万方.

**Goal:** Parse the report, identify high-similarity passages, produce targeted revision guidance, and feed results back into the T6 revision loop.

## Input Mode Detection

Ask the user: "你有查重报告吗? 如果有, 是什么格式?"

| User Has | Mode | Method |
|----------|------|--------|
| PDF 报告文件 | **Mode A: Auto-Parse** | PyMuPDF extraction |
| 网页上的数字+标红段落 | **Mode B: Manual Input** | Structured template |
| 不知道具体数字, 只知道"某章重复率高" | **Mode C: Guidance Only** | Qualitative guidance |

---

## Mode A: PDF Auto-Parse

### A1. Quick Probe (RUN FIRST)

Read the first page of the PDF with PyMuPDF. Determine the red-marking method:

```python
import fitz
doc = fitz.open("查重报告.pdf")
page = doc[0]
blocks = page.get_text("dict")["blocks"]

# Probe 1: Check text span colors
has_red_text = False
for block in blocks:
    for line in block.get("lines", []):
        for span in line["spans"]:
            if span["color"] & 0xFF0000:  # reddish
                has_red_text = True
                break

# Probe 2: Check annotations
has_red_annot = False
for annot in page.annots():
    if annot.colors and annot.colors.get("stroke"):
        r, g, b = annot.colors["stroke"]
        if r > 0.5 and g < 0.3 and b < 0.3:
            has_red_annot = True
```

**Decision:**
- `has_red_text` → use color-span extraction (highest confidence)
- `has_red_annot` but no red text → use annotation extraction
- Neither → warn user: "报告中未检测到标红标记, 可能是背景矩形标注方式. 请确认报告是否有标红段落, 或切换到 Mode B 手动输入."

### A2. Full Extraction

**Extract overall metrics:**
Search for patterns like:
- `总文字复制比[：:]\s*(\d+\.?\d*)%`
- `去除引用文献复制比[：:]\s*(\d+\.?\d*)%`
- `去除本人已发表文献复制比[：:]\s*(\d+\.?\d*)%`

**Extract per-chapter metrics:**
Search for chapter names followed by percentage patterns.

**Extract highlighted passages:**
Collect all text spans where color is red (0xFF0000 or similar). Group by proximity into passages.

### A3. User Confirmation

Before proceeding, present extracted data for confirmation:

```
从查重报告中提取到:
- 总文字复制比: X%
- 去除引用复制比: Y%
- 标红段落: N 段
- 各章复制比:
  绪论: A%  |  文献综述: B%  |  研究方法: C%
  核心章节1: D%  |  核心章节2: E%  |  结论: F%

这些数字是否正确? (如有偏差请纠正)
```

### A4. Handling Edge Cases

| Issue | Action |
|-------|--------|
| Color is dark red (0xCC0000) vs bright red (0xFF0000) | Accept both. Threshold: R component > 0xB0 and G < 0x30 and B < 0x30 |
| Color is orange/warm (0xFF6600) — used by some systems for "partial match" | Flag as "possible partial match", lower priority for revision |
| Red background rect (text color is black, red is underneath) | Hard to detect reliably. Warn user and offer Mode B fallback |
| Page contains scanned image (no text layer) | Cannot parse. Offer Mode B fallback |
| Report is from a system not yet encountered | Try generic extraction. If < 50% of expected data found → Mode B |

---

## Mode B: Manual Structured Input

Present this template:

```
请提供以下信息 (从查重报告中复制):

1. 查重系统: [ ] CNKI AMLC  [ ] 维普  [ ] 万方  [ ] 其他: ___
2. 总文字复制比: ___%
3. 去除引用文献复制比: ___%
4. 去除本人已发表文献复制比: ___% (如不适用留空)
5. 各章节复制比 (如有):
   - 绪论/引言: ___%
   - 文献综述: ___%
   - 研究方法: ___%
   - 核心章节1 (____): ___%
   - 核心章节2 (____): ___%
   - 核心章节3 (____): ___%
   - 结论: ___%
6. 标红最严重的 3-5 段文字 (直接复制粘贴):
   [段落1 - 复制比 ___% - 来源: ______]
   [段落2 - 复制比 ___% - 来源: ______]
   [段落3 - 复制比 ___% - 来源: ______]
```

---

## Mode C: Guidance Only

When the user has no report data but knows problem areas:

Ask: "哪些章节或段落你觉得重复率最高? 大概是什么程度?"

Use qualitative judgment to:
1. Identify likely high-similarity section types (literature review > introduction > methods)
2. Suggest targeted reduction strategies per section type (see §Reduction Strategies)
3. Recommend running a formal check if any core chapter is suspected >20%

---

## Reduction Strategies by Section

| Section | Common Cause | Strategy |
|---------|-------------|----------|
| **文献综述** | 直接引用过多、综述写法接近原文 | 按主题归类改写，用自己的框架重新组织文献；减少连续直接引述；每段综述用"研究发现...然而...因此..."的论证结构替代"某某研究发现..."的列举结构 |
| **研究方法** | 标准方法描述与教科书/已发表论文雷同 | 精简标准方法描述（一句话+引用即可）；详写本研究的特殊调整；详写数据来源的具体细节（这些是独一无二的） |
| **绪论/引言** | 背景描述与多篇论文雷同 | 用自己的研究问题和贡献来组织背景，而非通用的"XX 是一个重要问题"；从 S3 的 claim outline 出发重构引言段落 |
| **核心章节** | 数据分析描述与已有文献雷同 | 这是最危险的——核心章节的雷同意味着原创性不足。检查分析角度是否独特；检查是否可以从不同维度重新分析同一数据 |
| **结论** | 结论表述与已有文献雷同 | 结论必须紧密锚定本研究的独特发现，而非领域通用结论 |

## Priority Sorting

After extracting all highlighted passages, sort by revision priority:

```
Priority = Section Weight × Similarity %

Section Weights:
- 核心章节: 3.0 (most dangerous — signals weak originality)
- 绪论: 2.0
- 结论: 2.0
- 文献综述: 1.5 (commonly has higher similarity, less alarming)
- 研究方法: 1.0 (standard methods expected to match)
```

Output the top 5-10 passages to fix, ordered by priority.

## Integration with T6 Revision Loop

1. Parse report → produce priority-sorted passage list
2. User selects which passages to fix first (or accepts the priority order)
3. For each passage: rewrite using the §Reduction Strategies → mark as [FIXED]
4. After all priority passages fixed: re-check the chapter-level percentages
5. If any chapter still exceeds target → another round of targeted fixes
6. When all chapters within target → return to main T6 flow

**Target thresholds** (thesis-specific):
- 学位论文 (bachelor): <30%
- 学位论文 (master): <25%

## Unsupported Formats

| Format | Why Not Supported | Alternative |
|--------|-------------------|-------------|
| Screenshots/photos of reports | OCR unreliable for color-coded text; color info lost | Use Mode B |
| .dat / .caj proprietary formats | Closed binary, no parser available | Export to PDF from the system, or use Mode B |
| University custom report formats | Too many variants to maintain | Export to PDF or use Mode B |
