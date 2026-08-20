# Humanities Reference Quality — 参考文献质量 (兼文献综述评估)

**Used by:** literature_review
**Context:** Humanities bachelor thesis
**Key difference from STEM:**
- Primary texts (原著) are ESSENTIAL in humanities references — must include the works being analyzed
- Theory books (专著) matter more than recent journal articles; a 1960s theory text is fine
- Need both Chinese AND foreign language sources
- Currency is less important than authority

## 反谄媚协议 (v1.0)
- **默认立场：怀疑。** 只接受通过仔细审查的论述。
- 如果你在仔细审阅后找不到缺陷，这本身没有问题——但必须报告你的审阅深度。
- **永远不要为了避免冲突而抬高分数。** 诚实的 40/100 比圆滑的 70/100 更有用。
- 在两个严重级别之间犹豫时，选择更高的那个。

## Instructions

Evaluate the reference list quality AND the literature review chapter quality. The reference list reveals whether the student knows the field; the literature review reveals whether the student can position their work within scholarly conversation.


**Confidence:** Rate 1-10 your confidence in this review. Output `CONFIDENCE_SCORE: <score>`
on the second-to-last line (before DIMENSION_SCORE).
- 1-3: I am uncertain about 30%+ of my findings
- 4-6: I am reasonably confident but some findings are borderline
- 7-8: I am confident in the vast majority of my findings
- 9-10: I would stake my reputation on every finding

## Scoring Rubric: literature_review (0-100)

Score = primary_text_coverage(0-25) + theory_coverage(0-25) + field_awareness(0-25) + source_authority(0-15) + language_mix(0-10)

### primary_text_coverage (0-25)
- **20-25**: ALL primary texts (原著) analyzed in the paper are listed in references with complete publication info (edition, publisher, year). For literature: correct edition of the novel/poetry collection. For history: correct archival source or document edition.
- **10-19**: Primary texts are listed but edition information is incomplete or uses a non-standard edition.
- **0-9**: Primary texts are not listed; reader cannot verify which edition the author analyzed.

### theory_coverage (0-25)
- **20-25**: Covers core theoretical works in the field (books AND journal articles). Shows awareness of the intellectual tradition the paper draws on. For a Bakhtinian analysis, this means at minimum the key Bakhtin texts plus major secondary scholarship.
- **10-19**: Includes basic theoretical sources but relies heavily on textbooks, introductions, or secondary summaries rather than primary theory texts.
- **0-9**: Theory references are minimal; paper operates without scholarly grounding.

### field_awareness (0-25)
- **20-25**: The literature review demonstrates command of the research field — knows the major debates, schools of thought, and key turning points. The paper is positioned within a specific scholarly conversation, not just adjacent to it.
- **10-19**: Literature review identifies relevant works but reads as a list ("A said X, B said Y, C said Z") rather than a structured conversation with camps and debates.
- **0-9**: Literature review is absent, copied from another context, or merely lists 2-3 sources without synthesis.

### source_authority (0-15)
- **12-15**: Sources include recognized authorities in the field: known scholars, established publishers (三联/商务/北大/社科文献/等 for Chinese; Routledge/Cambridge/Oxford/etc. for English), peer-reviewed journals. No or minimal web-only sources.
- **6-11**: Mix of authoritative and less authoritative sources.
- **0-5**: Heavy reliance on non-academic sources, web resources, or sources without established scholarly value.

### language_mix (0-10)
- **8-10**: Good mix of Chinese and foreign-language sources appropriate to the discipline. For a Chinese department paper on Chinese literature, some foreign theory sources (in translation or original) would be expected. For comparative literature, substantial foreign-language sources required.
- **4-7**: Primarily one language, with some other-language sources.
- **0-3**: Completely monolingual in a context where multi-language sources are expected.

## Output Format

```markdown
## Result

**literature_review** = {total} (primary_text_coverage={r1}, theory_coverage={r2}, field_awareness={r3}, source_authority={r4}, language_mix={r5})

[Critical] literature_review: [primary_text] 论文详细分析了《北上》的时间意识，但参考文献中未列出任何版本的《北上》，无法判断分析基于何种文本
[Major] literature_review: [theory_coverage] 论文使用了"时间意识"概念但未引用任何关于时间哲学或叙事时间理论的经典著作（如热奈特、利科、巴赫金）
[Major] literature_review: [field_awareness] 文献综述仅列出15篇参考文献，且均为简单罗列，未展示对该小说研究现状的系统梳理
[Minor] literature_review: [language_mix] 所有参考文献均为中文，对于一篇涉及叙事学理论的论文，缺少外文理论文献

DIMENSION_SCORE literature_review: {score}
```

End with the exact line:
```
CONFIDENCE_SCORE: <1-10>
DIMENSION_SCORE literature_review: <0-100>
```
