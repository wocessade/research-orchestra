# Composer: de-ai-detect

**Purpose:** Detect and fix AI-typical writing patterns in academic prose, for both English and Chinese manuscripts.
**Used by:** academic-journal S7
**Parameters:** `{language}` (en/zh), `{de_ai_depth}` (quick/deep)

## Instructions

### English De-AI Detection

For comprehensive English De-AI rules, load `references/english-de-ai-guide.md` (16 dimensions with field-specific appendices, surface-vs-deep classification, NNES caveats, and composite scoring).

**Quick-reference patterns to detect and fix:**

| AI Pattern | Fix |
|------------|-----|
| "Moreover, furthermore, additionally, it is noteworthy that..." | Reduce to field-baseline discourse marker density. Vary position and type. "Moreover" -> 0 instances. |
| Every paragraph same length and structure | Vary paragraph length. Some 1-sentence, some 5-sentence. Prioritize sentence-level burstiness (D3 in english-de-ai-guide.md). |
| "Delve into", "pivotal", "tapestry", "realm" | Delete or replace with plain alternatives. These are the highest-confidence single-word AI signals. |
| Overly hedged claims (stacked: "may potentially suggest") | Target DIVERSE hedging, not less hedging. One hedge per claim, vary construction. Calibrate to evidence strength. Overclaiming is also an AI trait. |
| Bullet-point-like prose in paragraphs | Read aloud. If it sounds like a list, rewrite for flow. |
| Generic conclusion ("more research is needed") | Say specifically WHAT research is needed and WHY. |
| "Not only...but also..." | Zero tolerance. Split into two sentences or use compound predicate. |
| Missing methodological narrative | Add "why" clauses, rejected alternatives, process details, surprises. |
| Passive voice everywhere | NOT an AI signal per se. GPT-4 uses passive LESS than human writers. The signal is stance monotonicity, not grammatical voice. |

**NNES author threshold adjustment:** Raise thresholds by 30% for D2 (lexical richness) and D5 (syntactic complexity). Deep features (D12 narrative, D13 stance, D15 specificity) are safer diagnostics than surface lexical features for NNES authors.

### Chinese De-AI Detection

Load `references/chinese-de-ai-guide.md` for the full 19-dimension detection rules:

1. **D1** - Connective templates (关联词模板)
2. **D2** - Nominalized verbs (动词名词化)
3. **D3** - Redundant prepositions (冗余介词)
4. **D4** - Hedging calibration (模糊限制语校准)
5. **D5** - Vague pronouns (模糊代词)
6. **D6** - Run-on sentences (流水句)
7. **D7** - Repeated subjects (重复主语)
8. **D8** - Conclusion AI traces (结论部分AI痕迹)
9. **D9** - Over-balanced structures (过度平衡结构)
10. **D10** - Uniform paragraph length (均匀段落长度)
11. **D11** - Absent author stance (缺失作者立场)
12. **D12** - Missing data/details (缺失数据/细节)
13. **D13** - Monotonous syntax (单调句法)
14. **D14** - Section-specific academic patterns (章节特定学术模式)
15. **D15** - Monotonous result-reporting verbs (单调结果报告动词: 提示/表明/说明/可能/可推测/结合)
16. **D16** - Zero-subject/topic-comment flattening (零主语/话题-评论扁平化)
17. **D17** - 的-stacking detection (的字叠用检测)
18. **D18** - 被-overuse detection (被字过度使用检测)
19. **D19** - Composite AI score with section risk weights (复合AI分数与章节风险权重)

Plus: dual abstract compliance check and NNES false-positive caveats. Dual abstract mismatch -> major item at Q7 gate.

### Depth Modes

- **quick**: Run the English quick-reference patterns or Chinese D1-D10 only. Best for routine checks.
- **deep**: Load full `references/english-de-ai-guide.md` (16 dimensions, field-specific appendices, composite scoring) or `references/chinese-de-ai-guide.md` (D1-D19 full). Best for high-stakes submissions.

### Correctness Threshold

If `{de_ai_depth}=quick` and zero patterns are flagged, output confirmation: "No AI rhythm patterns detected." Do NOT iterate the de-ai pass just to meet a pass-count quota — over-polishing degrades prose quality. (See `english-de-ai-quick-ref.md` / `chinese-de-ai-quick-ref.md` core principle sections.)

## Verification
- [ ] All relevant AI patterns checked against the manuscript
- [ ] NNES author: thresholds raised by 30% for D2/D5
- [ ] Chinese: all 19 dimensions checked (deep) or D1-D10 checked (quick)
- [ ] Dual abstract mismatch flagged if present (Chinese)
- [ ] Fixes applied for each detected pattern, not just flagged
- [ ] Over-polishing avoided: zero flags = confirm and proceed

## Common Pitfalls
- **Hunting single words in isolation:** "delve" and "pivotal" are high-confidence signals, but most AI patterns are structural (paragraph uniformity, hedge stacking) — focus on those
- **Flagging passive voice as AI:** Passive voice is NOT an AI signal; GPT-4 uses passive LESS than human writers. The real signal is stance monotonicity.
- **Applying English thresholds to NNES authors:** NNES writers naturally show lower lexical diversity (D2) and simpler syntax (D5) — adjust thresholds +30% to avoid false positives
- **Skipping section-specific checks:** Chinese D14 and D15 are section-dependent — a pattern fine in Methods may be suspicious in Discussion
- **Over-polishing:** if de-ai returns zero flags, do NOT re-run the pass — this degrades natural prose rhythm
## LaTeX manuscripts

IF `writingFormat == latex`, also follow `../academic-latex/references/style-de-ai.md` safety zones:
do not rewrite math, `\cite`/`\label`/`\ref`, siunitx, paths, or verbatim when de-AI polishing.