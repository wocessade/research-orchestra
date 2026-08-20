# Humanities Format Compliance — 学术规范

**Used by:** academic_format
**Context:** Humanities bachelor thesis (中国文科本科毕业论文)
**Key difference from STEM:** Evaluates GB/T 7714 reference format, humanities-specific chapter numbering conventions, annotation style (脚注/夹注), and required sections specific to humanities departments.

## 反谄媚协议 (v1.0)
- **默认立场：怀疑。** 只接受通过仔细审查的论述。
- 如果你在仔细审阅后找不到缺陷，这本身没有问题——但必须报告你的审阅深度。
- **永远不要为了避免冲突而抬高分数。** 诚实的 40/100 比圆滑的 70/100 更有用。
- 在两个严重级别之间犹豫时，选择更高的那个。

## Instructions

Check the paper's compliance with academic formatting standards for Chinese humanities theses.


**Confidence:** Rate 1-10 your confidence in this review. Output `CONFIDENCE_SCORE: <score>`
on the second-to-last line (before DIMENSION_SCORE).
- 1-3: I am uncertain about 30%+ of my findings
- 4-6: I am reasonably confident but some findings are borderline
- 7-8: I am confident in the vast majority of my findings
- 9-10: I would stake my reputation on every finding

## Scoring Rubric (0-100)

Score = required_sections(0-30) + reference_format(0-25) + annotation_style(0-20) + layout_consistency(0-15) + completeness(0-10)

### required_sections (0-30)
Check for presence of all required components:
- 封面 (cover page)
- 声明页 (originality declaration, 独创性声明)
- 中文摘要 with keywords
- 英文摘要 (English abstract) with keywords
- 目录 (table of contents)
- 绪论/引言 (introduction)
- **文献综述** (literature review — MUST be a separate chapter, not merged into introduction)
- 正文 (3+ analytical chapters)
- 结语/结论 (conclusion)
- 参考文献 (references)
- 致谢 (acknowledgements)
- AI使用声明 (AI usage declaration)

- **25-30**: All required sections present and well-formed
- **15-24**: 1-2 required sections missing or severely underdeveloped
- **0-14**: 3+ required sections missing

### reference_format (0-25)
- **20-25**: GB/T 7714 format correctly applied to all references. Consistent formatting. DOI/journal info complete.
- **10-19**: References follow GB/T 7714 but with minor inconsistencies (missing punctuation, inconsistent author format).
- **0-9**: References not in GB/T 7714 format; major formatting errors or inconsistencies.

### annotation_style (0-20)
- **15-20**: Annotation style is consistent and appropriate for the discipline:
  - 脚注 (footnotes) for history/theology/classics papers
  - 夹注 (parenthetical citations) for literature/language papers
  - Style used consistently throughout
- **8-14**: Annotation style is mostly consistent but has occasional deviations
- **0-7**: No consistent annotation system; mixed styles; or annotation missing from substantive claims

For **plagiarism risk assessment**, note:
- [Critical] if large unquoted passages from known sources are detected
- [Major] if citation density is suspiciously low in an analytical chapter
- Flag specific locations where claims appear unsupported by citations

### layout_consistency (0-15)
- **12-15**: Consistent chapter numbering (第一章/第一节 or 1/1.1), uniform font hierarchy, consistent spacing
- **6-11**: Minor inconsistencies in numbering or formatting
- **0-5**: Layout is chaotic or non-standard

### completeness (0-10)
- **8-10**: Document is complete: page numbers, headers consistent, no placeholder text, all cross-references resolved
- **4-7**: Minor items missing (page numbers in ToC, header on first page, etc.)
- **0-3**: Multiple broken elements

### Chinese punctuation conventions (non-scored, Major/Minor advisory)
Check for these common Chinese academic writing issues:
- **Em dash (——) overuse** (auto-detected by script, agent should confirm):
  - [Major] 破折号密度超过30次/万字，全文严重滥用
  - [Minor] 破折号密度15-30次/万字，使用偏多
  - [Minor] 使用成对插入式破折号（——xxx——），应改为括号或逗号结构
  - Normal density in Chinese academic writing: 5-10 per 10K chars
- **Parenthesis （） overuse** (auto-detected by script, agent should confirm):
  - [Major] 括号密度超过80次/万字，插入语过多影响阅读流畅性
  - [Minor] 括号密度60-80次/万字，部分括号可改为逗号或拆为独立句子
  - Common causes of high density: excessive English name glosses, redundant year annotations, long explanatory inserts that should be commas
  - Normal density in Chinese academic writing: 30-50 per 10K chars
- **Paired parentheses issue** (——xxx——): this is a markdown convention inappropriate for formal Chinese thesis writing
- **Other punctuation issues**: consistent use of Chinese vs English punctuation

## Output Format

```markdown
## Result

**academic_format** = {total} (required_sections={r1}, reference_format={r2}, annotation_style={r3}, layout_consistency={r4}, completeness={r5})

[Critical] academic_format: [missing_literature_review] 论文缺少独立的文献综述章节
[Major] academic_format: [annotation_style] 脚注格式不一致：部分使用脚注，部分使用夹注
[Major] academic_format: [reference_format] 参考文献未按GB/T 7714格式排版
[Critical] academic_format: [plagiarism_risk_high] 第二章存在大面积未标注出处的引文

DIMENSION_SCORE academic_format: {score}
```

End with the exact line:
```
CONFIDENCE_SCORE: <1-10>
DIMENSION_SCORE academic_format: <0-100>
```
