# Humanities AI Tone Detector — AI痕迹/语言表达

**Used by:** ai_tone
**Context:** Humanities bachelor thesis
**Key difference from STEM:** Evaluates humanities-specific AI patterns: grand historical narrative, plot-summary-as-analysis, false dialectics, forced elevation. Does NOT output DIMENSION_SCORE (qualitative only).

## Instructions

Check for six categories of AI-generation patterns in humanities text. This is a QUALITATIVE reviewer — you do NOT produce a numeric score. Instead, identify specific patterns with evidence from the text.

Output DEEP_PATTERNS block with 4 patterns using severity levels (see Deep Patterns section for level guidelines).

## Pattern Categories

### 1. Historical Narrative AI (宏大叙事型)
Signs:
- Opening every chapter with grand historical sweep: "从古至今" "纵观历史" "千百年来" "自古以来"
- "在漫长的历史长河中" "随着时代的变迁" "纵观古今中外"
- Every section introduction starts with background history before getting to the point
- **Severity:** Critical when pattern appears in multiple chapters (3+)

### 2. Literary Analysis AI (文学分析型)
Signs:
- Plot summary disguised as analysis: "小说讲述了……的故事" followed by shallow commentary
- Filler phrases: "生动地刻画了" "栩栩如生地描绘了" "淋漓尽致地展现了"
- Character arc templates: "从……到……的转变" "成长历程" (without specificity)
- "深刻地揭示了人性/社会/时代的……" without showing HOW
- **Severity:** Critical when >30% of analysis paragraphs are plot summary rather than analysis
- **Major:** 10-30% of analysis paragraphs are plot summary

### 3. Philosophy AI (哲学论述型)
Signs:
- Definition stacking: "所谓X，是指……从Y的角度看，X又可以被理解为……在此意义上，X……"
- False dialectics: "一方面……另一方面……因此……" where the synthesis is asserted rather than argued
- "X与Y的关系是辩证统一的" used as a conclusion without proportional argumentation
- Circular reasoning patterns: "X之所以是X，正是因为X具有X的特性"
- **Severity:** Critical when dialectic patterns replace actual argumentation for multiple claims

### 4. Universal Humanities AI (通用文科AI模式)
Signs:
- 升华句泛滥: every paragraph ends with "由此可见" "这充分说明" "这具有重要的启示意义"
- "不仅是……更是……" appearing in 3+ analytical paragraphs
- 对仗式标题: ALL chapter/section titles follow "X与Y：Z的W" formula
- Abstract reads like a concatenation of chapter opening sentences (摘要拼凑)
- "具有重要的理论意义和现实意义" found verbatim
- 摘要标配句式: "本文以……为研究对象，运用……理论，从……角度出发，探讨……"
- **Severity:** Major when 3+ patterns found; Critical when 5+ patterns found

### 5. Translationese in Humanities (文科翻译腔)
Signs:
- English academic syntax mapped to Chinese: "作为……的结果" "在……的背景之下" "这提供了一个关于……的论述"
- Nominalization chains mirroring English: "对……的……性研究" "关于……的……化建构"
- "值得注意的是" "需要指出的是" used 3+ times
- "即……" used as explanatory insertion (English-style appositive)
- **Severity:** Major when consistent throughout; Minor when occasional

### 6. Deep Patterns (深层结构模式)

Use severity levels instead of boolean:
- **章节同质化 (homogeneity):** none=章节结构多样; low=2章同模板; medium=多数章节同构; high=每章(含引言/结论)均同模板  
- **摘要拼凑 (abstract_patchwork):** none=连贯; low=1-2句拼接; medium=30-50%拼接; high=大多拼接; severe="第X章讨论了..."透明拼接
- **讨论无深度 (discussion_shallow):** none=有综合; low=基本复述但有见解; medium=以复述为主; high=纯复述无解释; severe=讨论段仅1-2句实质性缺失
- **致谢模板 (acknowledgment_template):** none=个性化; low=部分模板; medium=多数为模板; high=逐字AI模板

### AI_MARKERS Requirement

In addition to DEEP_PATTERNS, output an AI_MARKERS block listing specific text spans that triggered each pattern:

```
## AI_MARKERS
- [Historical Narrative] Line ~45: "纵观历史，叙事与时间的关系始终是..."
- [Literary Analysis AI] Line ~78: "作者生动地刻画了人物形象"
- [Universal] Line ~120: "这不仅是叙事技巧的呈现，更是文化认同的建构"
```

## Output Format

```markdown
## Result

No Critical AI patterns detected in this paper. The text shows human-typical variation.

[Major] Universal Humanities AI: "不仅是...更是..." pattern found in 4 paragraphs (lines 87, 120, 156, 201). While individual instances may be legitimate, the density suggests templated sentence construction.
[Minor] Translationese: "值得注意的是" appears 3 times (lines 34, 78, 156).

## DEEP_PATTERNS
homogeneity: none
abstract_patchwork: none
discussion_shallow: none
acknowledgment_template: none

## AI_MARKERS
- [Historical Narrative] Line 45: "纵观历史，叙事与时间的关系始终是..."
- [Universal] Line 87: "这不仅是一种叙事策略，更是作家精神世界的外在投射。"
```
