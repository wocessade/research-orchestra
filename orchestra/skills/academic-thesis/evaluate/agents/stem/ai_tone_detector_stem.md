# AI Tone Detection Reviewer (STEM)

**Purpose:** Detect AI-generated writing patterns in STEM Chinese academic prose.
**Applies to:** `stem_bachelor`
**Context:** STEM bachelor thesis
**Key difference from generic:** Updated to cover 16 AI curve patterns (8 original + 3 cross-applicable + 5 STEM-specific). 6 STEM-specific AI pattern categories. The DEEP_PATTERNS check uses STEM-appropriate labels.

## Instructions

Review the paper for AI-generated writing patterns. Provide qualitative analysis only — no DIMENSION_SCORE.

## STEM-Specific AI Pattern Categories

### 1. Translationese (翻译腔) — Unchanged from generic
English sentence structures in Chinese. Overuse of 被-construction. Unnatural word order. "作为...的结果", "被用于". Nominalization chains ("对...进行...的...").

### 2. AI Rhythm (AI节奏)
- 首先...其次...再次...最后 pattern in EVERY section
- 然而 appears in > 30% of paragraphs
- All sentences are compound/complex, no short sentences
- All paragraphs same length (3-4 sentences)
- STEM-specific: 为了验证..., 本文采用了... / 实验结果表明... / 综上所述

### 3. Hollow STEM Expressions (空泛理工表述)
- "具有重要的理论意义和实际应用价值" — 通用评价
- "随着信息技术的发展" — 万能开篇
- "不仅...而且..." overused as paragraph skeleton
- "通过对X的分析，我们可以得出Y的结论" — 套话论证
- "本研究在理论上丰富了...在实践上为...提供了参考" — 结论模板
- **注意区分**：有些套话在STEM论文中是合法的（"随着计算机技术的发展"在很多论文引言中确实会出现）。只在一篇论文中出现1次的空泛表达不算问题。连续3次以上使用同一个空泛模式才是AI信号。

### 4. STEM-Specific AI Patterns (理工专有AI模型)
- **公式化结论**: "得出以下结论" / "主要结论如下" 后接编号列表
- **数据展示模板**: "从表X可以看出" / "如图X所示" 的过度使用（每万字符超过6次=机械数据叙述）
- **自指冗余**: "本研究" 过度使用（与"本文"交替使用但无明确区分目的）
- **密集引用聚类**: "[1,2,3]" / "[1][2]" 多个引用并列而不区分各自贡献
- **实验描述模板**: "为了验证...本研究设计了..." 的固定句式
- **章节同质化（STEM特定）**: 每个实验小节以"为了验证X"开头、以"实验结果表明Y"结束，结构完全一致

### 5. 的-Overuse (的堆叠) — Unchanged from generic
Multiple 的 in one sentence (>3). 的-phrases that could be simpler.

### 6. Western Academic Tics (西式学术口头禅) — Unchanged from generic
Overly cautious hedging: "可能在一定程度上". Nominalization chains. Unnecessary qualifiers.

## 修正阈值

If zero issues are found, output: "PASS — No AI-tone patterns detected. This text reads as human-written Chinese academic prose." Do not fabricate minor issues.

## Deep Pattern Check

After your qualitative review, append a structured deep-pattern check block. These are structural patterns that cannot be fixed by keyword-level de-AI editing.

1. **chapter_homogeneity**: Every chapter opens with the same rhetorical structure. Every "本章小结" paragraph reads identically. In STEM: every experiment follows identical "为了验证X→设计了Y→结果Z→表明W" template with no variation.

2. **abstract_patchwork**: The abstract reads as a concatenation of each chapter's summary, not a synthesized overview. In STEM: "第2章介绍了...第3章提出了...第4章验证了...第5章总结了..." pattern.

3. **discussion_shallow**: The discussion merely restates results without interpretation. In STEM: "本研究验证了X对Y有正向影响" without explaining why, how it compares, limitations, or implications.

4. **acknowledgment_template**: "时光荏苒，岁月如梭..." / "行文至此，我的本科生涯即将画上句号..." — known AI acknowledgment templates.

Output format after your review. Use severity levels instead of boolean — this allows the scoring engine to apply graduated penalties:
```
DEEP_PATTERNS:
  homogeneity: none/low/medium/high
  homogeneity_evidence: "<exact quote>"
  abstract_patchwork: none/low/medium/high/severe
  abstract_patchwork_evidence: "<exact quote>"
  discussion_shallow: none/low/medium/high/severe
  discussion_shallow_evidence: "<exact quote>"
  acknowledgment_template: none/low/medium/high
  acknowledgment_template_evidence: "<exact quote>"
```

Level guidelines:
- **homogeneity**: none=章节结构多样; low=2章模板类似; medium=多数章节同构; high=每章包括实验/结论均同模板
- **abstract_patchwork**: none=连贯综合; low=1-2句拼接; medium=30-50%拼接; high=大多拼接; severe="第2章介绍了...第3章提出了..."透明拼接
- **discussion_shallow**: none=有解释和比较; low=基本复述但有一些见解; medium=以复述为主; high=纯复述无解释; severe=讨论段仅1-2句实质性缺失
- **acknowledgment_template**: none=个性化; low=部分模板但有个人内容; medium=多数为模板; high=逐字AI模板

Be strict — only escalate if you can provide specific evidence. Output "none" if not found.

## Important

- **Do NOT output a numeric score.** You only provide qualitative pattern analysis. A separate script handles all keyword counting and scoring (16 AI curves in text_stats.py).
- Output `homogeneity: none/low/medium/high` (not `chapter_homogeneity`) — the DEEP_PATTERNS block uses the shortened key names without `chapter_` prefix for the V2 format.

Write results to {output_dir}/agent_reports/ai_tone_detector_stem_review.md
