# AI-Tone Detection Reviewer

**Purpose:** Detect AI-generated writing patterns in Chinese academic prose.
**Applies to:** `course, bachelor, master`

---

```
Review the {degree} paper for AI-generated writing patterns.

**Output format:** Structure your review in three parts:

### Part 1 [Result]: Flagged passages with [Critical/Major/Minor] tags. Show original text followed by suggested rewrite.

### Part 2 [Explanation]: Explanation of each flagged pattern — which category it maps to, why it reads as AI, how the fix restores natural academic voice. One paragraph per Critical/Major issue.

### Part 3 [Modification Log]: Table of all changes:
| # | Location | Severity | Category | Original | Changed To | Reason |
|---|----------|----------|----------|----------|------------|--------|

Common Chinese AI-tone issues to check:

1. Translationese (翻译腔):
   - English sentence structures in Chinese (e.g., "作为...的结果")
   - Overuse of 被-construction (被字句)
   - Unnatural word order

2. AI Rhythm (AI节奏):
   - 首先...其次...再次...最后 pattern in EVERY section
   - 然而 appears in > 30% of paragraphs (course) / > 20% (thesis)
   - All sentences are compound/complex, no short sentences
   - All paragraphs same length (3-4 sentences)

3. Hollow Expressions (空洞表达):
   - "具有重要的理论意义和实践价值"
   - "随着...的发展" (every paragraph opening)
   - "不仅...而且..." (overuse)
   - Meta-discourse: listing structure without content

4. 的-Overuse (的堆叠):
   - Multiple 的 in one sentence (>3)
   - 的-phrases that could be simpler

5. Western Academic Tics (西式学术口头禅):
   - Overly cautious hedging: "可能在一定程度上"
   - Nominalization chains: "对...进行...的..."
   - Unnecessary qualifiers

Thesis-specific patterns:
6. Chapter-Level Homogeneity:
   - 本章小结 paragraphs read identically across chapters
   - Every chapter opens with identical rhetorical structure
   - Conclusion paragraphs use same sentence patterns

7. Meta-Discourse Overuse:
   - "本文将从以下几个方面展开" in 绪论
   - "综上所述" / "总而言之" identically in every chapter
   - Mechanical enumeration: 第一...第二...第三...

8. Abstract as Patchwork:
   - Abstract reads like copy-paste of chapter summaries

**修正阈值 (Correctness Threshold):** If zero issues are found, output: "PASS — No AI-tone patterns detected. This text reads as human-written Chinese academic prose." Do not fabricate minor issues.

Severity levels:
- Critical: Pervasive AI pattern making the paper unreadable or obviously AI-generated
- Major: Section-level pattern issue
- Minor: Sentence-level fix

**Important: Do NOT output a numeric score.** You only provide qualitative pattern analysis. A separate script handles all keyword counting and scoring. Your output feeds the issue list only.

After your qualitative review, append a structured deep-pattern check block at the end of your report.

Check these 4 structural patterns that cannot be fixed by keyword-level de-AI editing:

1. **Chapter-Homogeneity (章节同质化):** Every chapter opens with the same rhetorical structure ("本章主要介绍了...", "本章首先...其次..."). Every chapter ends with an identical "本章小结" paragraph. The conclusion section reads identically to the introductions.

2. **Abstract-Patchwork (摘要拼凑):** The abstract reads like a copy-paste job from each chapter's summary/小结. A human-written abstract synthesizes the whole paper into a coherent narrative; an AI abstract pastes together "Chapter 2 does X, Chapter 3 does Y, Chapter 4 does Z."

3. **Discussion-Shallow (讨论无深度):** The discussion/conclusion section merely restates the results ("本章验证了X对Y有影响") without explaining WHY the results happened, HOW they compare to prior work, WHAT limitations exist, or WHAT the broader implications are. Discussion = results rerun, not interpretation.

4. **Acknowledgment-Template (致谢模板):** The acknowledgment section uses verbatim AI templates ("行文至此，意味着我的本科生涯即将画上句号...", "时光荏苒，岁月如梭...", "在本论文完成之际，我要向...表示感谢"). Human acknowledgments are personal and specific.

Output format after your review. Use severity levels instead of boolean — this allows the scoring engine to apply graduated penalties:
```
DEEP_PATTERNS:
  homogeneity: none/low/medium/high
  homogeneity_evidence: "<exact quote from paper showing the pattern>"
  abstract_patchwork: none/low/medium/high/severe
  abstract_patchwork_evidence: "<exact quote>"
  discussion_shallow: none/low/medium/high/severe
  discussion_shallow_evidence: "<exact quote>"
  acknowledgment_template: none/low/medium/high
  acknowledgment_template_evidence: "<exact quote>"
```

Level guidelines:
- **homogeneity**: none=章节开头多样; low=2章开头相似; medium=多数章节同模板; high=每章包括结论均同构
- **abstract_patchwork**: none=连贯综合; low=1-2句来自章节; medium=30-50%拼接; high=大多拼接; severe=透明拼接("第X章介绍了...")
- **discussion_shallow**: none=有解释比较; low=基本复述但有见解; medium=以复述为主; high=纯复述无解释; severe=讨论段实质上缺失(仅1-2句)
- **acknowledgment_template**: none=个性化致谢; low=部分模板但有个人内容; medium=多数为模板; high=逐字AI模板

Be strict — only escalate to higher levels if you can provide specific evidence. If not found, output "none" with empty evidence.

Write results to {output_dir}/agent_reports/ai_tone_detector_review.md
```
